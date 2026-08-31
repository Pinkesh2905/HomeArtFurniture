from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from .models import Material, Supplier, StockTransaction, MaterialCategory, UnitOfMeasure, TransactionType
from .services import (
    record_stock_in, record_stock_out, record_adjustment, record_damage,
    create_material_from_post, update_material_from_post
)


class InventoryModelTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="Test Wood Co", phone="1234567890")
        self.material = Material.objects.create(
            name="Teak Wood",
            category=MaterialCategory.WOOD,
            unit=UnitOfMeasure.SQ_FT,
            min_stock=100.0,
            cost_per_unit=150.0,
            supplier=self.supplier
        )
        self.material.assign_sku()

    def test_material_creation(self):
        self.assertTrue(self.material.sku.startswith("HAF-WD-"))
        self.assertEqual(self.material.current_stock, Decimal('0'))
        self.assertTrue(self.material.is_low_stock)
        self.assertTrue(self.material.is_out_of_stock)
        self.assertEqual(self.material.stock_value, Decimal('0'))

    def test_stock_in_updates_current_stock(self):
        record_stock_in(self.material, Decimal('50.0'), Decimal('160.0'))
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, Decimal('50.0'))
        self.assertEqual(self.material.cost_per_unit, Decimal('160.0'))
        self.assertEqual(self.material.stock_value, Decimal('8000.0'))
        
        # Verify transaction
        txn = self.material.transactions.first()
        self.assertEqual(txn.transaction_type, TransactionType.STOCK_IN)
        self.assertEqual(txn.quantity, Decimal('50.0'))
        self.assertEqual(txn.total_cost, Decimal('8000.0'))

    def test_stock_out_updates_current_stock(self):
        record_stock_in(self.material, Decimal('100.0'))
        record_stock_out(self.material, Decimal('30.0'))
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, Decimal('70.0'))

    def test_stock_out_insufficient_raises(self):
        record_stock_in(self.material, Decimal('20.0'))
        with self.assertRaises(ValidationError):
            record_stock_out(self.material, Decimal('30.0'))

    def test_adjustment_sets_absolute_stock(self):
        record_stock_in(self.material, Decimal('50.0'))
        record_adjustment(self.material, Decimal('75.0'))
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, Decimal('75.0'))
        
        # Verify delta transaction
        txn = self.material.transactions.order_by('-id').first()
        self.assertEqual(txn.transaction_type, TransactionType.ADJUSTMENT)
        self.assertEqual(txn.quantity, Decimal('25.0'))

    def test_damage_reduces_stock(self):
        record_stock_in(self.material, Decimal('50.0'))
        record_damage(self.material, Decimal('5.0'))
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, Decimal('45.0'))

    def test_low_stock_property(self):
        # min_stock is 100
        record_stock_in(self.material, Decimal('90.0'))
        self.assertTrue(self.material.is_low_stock)
        self.assertFalse(self.material.is_out_of_stock)

        record_stock_in(self.material, Decimal('20.0')) # total 110
        self.assertFalse(self.material.is_low_stock)


from django.contrib.auth.models import User

class InventoryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')
        self.client.force_login(self.user)
        self.material = Material.objects.create(name="Glue", min_stock=10, cost_per_unit=50)
        self.material.assign_sku()
        self.supplier = Supplier.objects.create(name="Adhesives Ltd", phone="9998887776")

    def test_unauthenticated_inventory_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('material_list'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('material_list')}")

    def test_material_list_view_200(self):
        response = self.client.get(reverse('material_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Glue")

    def test_material_detail_view_200(self):
        response = self.client.get(reverse('material_detail', args=[self.material.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Glue")

    def test_material_create_post(self):
        data = {
            'name': 'Fabric Rolls',
            'category': 'fabric',
            'unit': 'm',
            'min_stock': '50',
            'cost_per_unit': '250',
            'supplier': self.supplier.pk
        }
        response = self.client.post(reverse('material_create'), data)
        self.assertEqual(response.status_code, 302) # redirect
        self.assertTrue(Material.objects.filter(name='Fabric Rolls').exists())

    def test_stock_transaction_view_post(self):
        data = {
            'transaction_type': 'in',
            'quantity': '100',
            'unit_cost': '45',
            'date': timezone.localdate().isoformat()
        }
        response = self.client.post(reverse('stock_transaction', args=[self.material.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.material.refresh_from_db()
        self.assertEqual(self.material.current_stock, Decimal('100'))
        self.assertEqual(self.material.cost_per_unit, Decimal('45'))

    def test_inventory_print_view_200(self):
        response = self.client.get(reverse('inventory_print'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory Report")
        self.assertContains(response, "Glue")

    def test_material_list_stock_filtering_and_db_metrics(self):
        # self.material has min_stock=10, current_stock=0 (out of stock)
        # Create adequate stock material
        mat_ok = Material.objects.create(
            name="Steel Screws",
            sku="TEST-SCR-01",
            category=MaterialCategory.HARDWARE,
            unit=UnitOfMeasure.PIECES,
            min_stock=50,
            current_stock=100,
            cost_per_unit=5,
        )
        # Create low stock material (current_stock <= min_stock and > 0)
        mat_low = Material.objects.create(
            name="Varnish Can",
            sku="TEST-VAR-01",
            category=MaterialCategory.PAINT,
            unit=UnitOfMeasure.LITERS,
            min_stock=20,
            current_stock=10,
            cost_per_unit=200,
        )

        # Test low stock filter
        response_low = self.client.get(reverse('material_list'), {'stock': 'low'})
        self.assertEqual(response_low.status_code, 200)
        low_names = [m.name for m in response_low.context['materials']]
        self.assertIn("Varnish Can", low_names)
        self.assertNotIn("Steel Screws", low_names)
        self.assertNotIn("Glue", low_names)

        # Test out of stock filter
        response_out = self.client.get(reverse('material_list'), {'stock': 'out'})
        self.assertEqual(response_out.status_code, 200)
        out_names = [m.name for m in response_out.context['materials']]
        self.assertIn("Glue", out_names)
        self.assertNotIn("Steel Screws", out_names)
        self.assertNotIn("Varnish Can", out_names)

        # Test metrics calculated at DB level
        self.assertEqual(response_low.context['total_count'], 3)
        self.assertEqual(response_low.context['low_stock_count'], 1)
        self.assertEqual(response_low.context['out_of_stock_count'], 1)
        # total_value = (100 * 5) + (10 * 200) + (0 * 50) = 500 + 2000 = 2500
        self.assertEqual(response_low.context['total_value'], Decimal('2500.00'))
