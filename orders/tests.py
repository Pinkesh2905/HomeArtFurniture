from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from measurements.models import FurnitureDimension
from .models import Order, OrderItem
from .services import create_order_from_post


class OrderServiceTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name='Rajesh Kumar', phone='+91 98765 43210')
        FurnitureDimension.objects.create(
            customer=self.customer,
            furniture_type='sofa',
            values={'Length': '40', 'Width': '38'},
        )

    def test_order_item_uses_decimal_total(self):
        order = Order.objects.create(
            order_number='TMP-test',
            customer=self.customer,
            date='2026-05-03',
        )
        item = OrderItem.objects.create(
            order=order,
            furniture_type='sofa',
            description='sofa',
            quantity=2,
            rate=Decimal('499.50'),
            total_amount=Decimal('0.00'),
        )
        self.assertEqual(item.total_amount, Decimal('999.00'))

    def test_server_recomputes_totals_and_ignores_hidden_values(self):
        from django.http import QueryDict

        query = QueryDict('', mutable=True)
        query.setlist('item_furniture_type[]', ['sofa'])
        query.setlist('item_description[]', ['sofa'])
        query.setlist('item_qty[]', ['2'])
        query.setlist('item_rate[]', ['500.00'])
        query['subtotal'] = '1.00'
        query['final_amount'] = '1.00'
        query['grand_total'] = '1.00'
        query['discount'] = '100.00'
        query['advance_paid'] = '200.00'
        query['notes'] = 'Urgent'
        order = create_order_from_post(query, self.customer)

        self.assertEqual(order.subtotal, Decimal('1000.00'))
        self.assertEqual(order.discount_amount, Decimal('100.00'))
        self.assertEqual(order.final_amount, Decimal('900.00'))
        self.assertEqual(order.advance_paid, Decimal('200.00'))
        self.assertEqual(order.grand_total, Decimal('700.00'))
        self.assertRegex(order.order_number, r'^HAF-\d{8}-\d{3}$')

    def test_discount_and_advance_cannot_exceed_order_value(self):
        from django.core.exceptions import ValidationError
        from django.http import QueryDict

        query = QueryDict('', mutable=True)
        query.setlist('item_furniture_type[]', ['sofa'])
        query.setlist('item_description[]', ['sofa'])
        query.setlist('item_qty[]', ['1'])
        query.setlist('item_rate[]', ['100.00'])
        query['discount'] = '101.00'

        with self.assertRaises(ValidationError):
            create_order_from_post(query, self.customer)


class OrderViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')
        self.customer = Customer.objects.create(full_name='Amit Shah', phone='9999999999')

    def test_order_post_creates_items_and_redirects_to_print(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('order_create'), {
            'customer_id': self.customer.id,
            'item_furniture_type[]': ['dining_table'],
            'item_description[]': ['dining_table'],
            'item_qty[]': ['1'],
            'item_rate[]': ['800.00'],
            'discount': '50.00',
            'advance_paid': '100.00',
        })
        order = Order.objects.get()
        self.assertRedirects(response, reverse('order_print', args=[order.id]))
        self.assertEqual(order.final_amount, Decimal('750.00'))
        self.assertEqual(order.balance_due, Decimal('650.00'))
        self.assertEqual(order.items.count(), 1)



    def test_order_detail_rejects_payment_above_balance(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            order_number='HAF-20260503-001',
            customer=self.customer,
            date='2026-05-03',
            final_amount=Decimal('500.00'),
            advance_paid=Decimal('100.00'),
            grand_total=Decimal('400.00'),
        )
        self.client.post(reverse('order_detail', args=[order.id]), {'additional_payment': '500.00'})
        order.refresh_from_db()
        self.assertEqual(order.advance_paid, Decimal('100.00'))
        self.assertEqual(order.grand_total, Decimal('400.00'))

    def test_order_list_filters_by_exact_date(self):
        self.client.force_login(self.user)
        matching = Order.objects.create(
            order_number='HAF-20260503-001',
            customer=self.customer,
            date='2026-05-10',
        )
        Order.objects.create(
            order_number='HAF-20260503-002',
            customer=self.customer,
            date='2026-05-11',
        )

        response = self.client.get(reverse('order_list'), {
            'date': '2026-05-10',
        })

        self.assertContains(response, matching.order_number)
        self.assertNotContains(response, 'HAF-20260503-002')

    def test_order_list_print_uses_same_filters(self):
        self.client.force_login(self.user)
        matching = Order.objects.create(
            order_number='HAF-20260503-003',
            customer=self.customer,
            date='2026-05-10',
            grand_total=Decimal('1200.00'),
        )
        Order.objects.create(
            order_number='HAF-20260503-004',
            customer=self.customer,
            date='2026-05-11',
            grand_total=Decimal('900.00'),
        )

        response = self.client.get(reverse('order_list_print'), {'date': '2026-05-10'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Filtered Orders & Bills List')
        self.assertContains(response, matching.order_number)
        self.assertContains(response, 'Rs 1200.00')
        self.assertNotContains(response, 'HAF-20260503-004')

    def test_api_update_order_shortcut_status_success(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            order_number='HAF-20260503-100',
            customer=self.customer,
            date='2026-05-03',
            status='pending',
        )
        response = self.client.post(reverse('api_update_order_shortcut', args=[order.id]), {
            'status': 'in_progress'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'in_progress')
        order.refresh_from_db()
        self.assertEqual(order.status, 'in_progress')

    def test_api_update_order_shortcut_payment_success(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            order_number='HAF-20260503-101',
            customer=self.customer,
            date='2026-05-03',
            final_amount=Decimal('1000.00'),
            advance_paid=Decimal('200.00'),
            grand_total=Decimal('800.00'),
        )
        response = self.client.post(reverse('api_update_order_shortcut', args=[order.id]), {
            'payment_amount': '300.00',
            'payment_method': 'upi'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['grand_total'], '500.00')
        order.refresh_from_db()
        self.assertEqual(order.advance_paid, Decimal('500.00'))
        self.assertEqual(order.grand_total, Decimal('500.00'))
        self.assertEqual(order.payment_method, 'upi')

    def test_api_update_order_shortcut_validation_error(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            order_number='HAF-20260503-102',
            customer=self.customer,
            date='2026-05-03',
            final_amount=Decimal('1000.00'),
            advance_paid=Decimal('200.00'),
            grand_total=Decimal('800.00'),
        )
        # Payment above balance due
        response = self.client.post(reverse('api_update_order_shortcut', args=[order.id]), {
            'payment_amount': '900.00',
            'payment_method': 'upi'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('errors', data)

    def test_order_creation_with_duplicate_categories_and_different_FurnitureDimensions(self):
        self.client.force_login(self.user)
        
        # Create 2 distinct FurnitureDimensions for self.customer for furniture_type = 'sofa'
        m1 = FurnitureDimension.objects.create(
            customer=self.customer,
            furniture_type='sofa',
            values={'Length': '40', 'Width': '38'},
            notes='sofa 1'
        )
        m2 = FurnitureDimension.objects.create(
            customer=self.customer,
            furniture_type='sofa',
            values={'Length': '42', 'Width': '40'},
            notes='sofa 2'
        )
        
        # Post to order_create, passing item_FurnitureDimension_id[] explicitly
        response = self.client.post(reverse('order_create'), {
            'customer_id': self.customer.id,
            'item_furniture_type[]': ['sofa', 'sofa'],
            'item_FurnitureDimension_id[]': [str(m1.id), str(m2.id)],
            'item_description[]': ['sofa style A', 'sofa style B'],
            'item_qty[]': ['1', '1'],
            'item_rate[]': ['800.00', '900.00'],
            'discount': '0.00',
            'advance_paid': '100.00',
        })
        
        # Assert order was created and redirected
        order = Order.objects.get(customer=self.customer)
        self.assertRedirects(response, reverse('order_print', args=[order.id]))
        self.assertEqual(order.items.count(), 2)
        
        # Verify items point to distinct FurnitureDimension records
        items = list(order.items.order_by('id'))
        self.assertEqual(items[0].dimension.id, m1.id)
        self.assertEqual(items[0].dimension.notes, 'sofa 1')
        self.assertEqual(items[1].dimension.id, m2.id)
        self.assertEqual(items[1].dimension.notes, 'sofa 2')

    def test_order_creation_fallback_clones_shared_FurnitureDimensions(self):
        self.client.force_login(self.user)
        
        # Only 1 sofa FurnitureDimension exists
        m = FurnitureDimension.objects.create(
            customer=self.customer,
            furniture_type='sofa',
            values={'Length': '40', 'Width': '38'},
            notes='Original sofa'
        )
        
        # Post 2 sofa items, both without explicit FurnitureDimension IDs
        response = self.client.post(reverse('order_create'), {
            'customer_id': self.customer.id,
            'item_furniture_type[]': ['sofa', 'sofa'],
            'item_FurnitureDimension_id[]': ['', ''],
            'item_description[]': ['sofa A', 'sofa B'],
            'item_qty[]': ['1', '1'],
            'item_rate[]': ['800.00', '900.00'],
            'discount': '0.00',
            'advance_paid': '100.00',
        })
        
        order = Order.objects.get(customer=self.customer)
        items = list(order.items.order_by('id'))
        self.assertEqual(len(items), 2)
        
        # First item should use the original FurnitureDimension
        self.assertEqual(items[0].dimension.id, m.id)
        # Second item should use a cloned, separate FurnitureDimension
        self.assertNotEqual(items[1].dimension.id, m.id)
        self.assertEqual(items[1].dimension.furniture_type, 'sofa')
        self.assertEqual(items[1].dimension.values, m.values)

    def test_order_item_edit_clones_shared_FurnitureDimension(self):
        self.client.force_login(self.user)
        
        # Create a single shared FurnitureDimension
        m = FurnitureDimension.objects.create(
            customer=self.customer,
            furniture_type='sofa',
            values={'Length': '40', 'Width': '38'},
            notes='Shared sofa'
        )
        
        order = Order.objects.create(
            order_number='HAF-test-edit',
            customer=self.customer,
            date='2026-05-03',
        )
        
        # 2 OrderItems share the same FurnitureDimension ID
        item1 = OrderItem.objects.create(
            order=order,
            furniture_type='sofa',
            dimension=m,
            description='sofa 1',
            quantity=1,
            rate=Decimal('500.00'),
            total_amount=Decimal('500.00')
        )
        item2 = OrderItem.objects.create(
            order=order,
            furniture_type='sofa',
            dimension=m,
            description='sofa 2',
            quantity=1,
            rate=Decimal('500.00'),
            total_amount=Decimal('500.00')
        )
        
        # Post edit to item2 only, changing Length from 40 to 42
        response = self.client.post(reverse('order_item_edit', args=[order.id, item2.id]), {
            'description': 'sofa 2 Updated',
            'quantity': '1',
            'rate': '500.00',
            'is_standard_catalog': 'off',
            'measure_Length': '42',
            'measure_Width': '38',
            'FurnitureDimension_notes': 'Only item 2 updated'
        })
        
        # Verify item2's FurnitureDimension is cloned and updated, while item1 is unchanged
        item1.refresh_from_db()
        item2.refresh_from_db()
        
        self.assertNotEqual(item1.dimension.id, item2.dimension.id)
        
        # Item 1 FurnitureDimension remains 40
        self.assertEqual(item1.dimension.values.get('Length'), '40')
        self.assertEqual(item1.dimension.notes, 'Shared sofa')
        
        # Item 2 FurnitureDimension is now 42
        self.assertEqual(item2.dimension.values.get('Length'), '42')
        self.assertEqual(item2.dimension.notes, 'Only item 2 updated')

    def test_payment_report_view_filters_and_totals(self):
        self.client.force_login(self.user)
        # Cash order
        Order.objects.create(
            order_number='HAF-CASH-1',
            customer=self.customer,
            date='2026-06-01',
            payment_method='cash',
            advance_paid=Decimal('200.00'),
            grand_total=Decimal('300.00'),
        )
        # UPI order
        Order.objects.create(
            order_number='HAF-UPI-1',
            customer=self.customer,
            date='2026-06-02',
            payment_method='upi',
            advance_paid=Decimal('400.00'),
            grand_total=Decimal('100.00'),
        )
        
        response = self.client.get(reverse('payment_report'), {
            'start_date': '2026-06-01',
            'end_date': '2026-06-03'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HAF-CASH-1')
        self.assertContains(response, 'HAF-UPI-1')
        self.assertContains(response, '600.00')

    def test_unauthenticated_order_views_redirect_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('order_list'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('order_list')}")

        response_create = self.client.get(reverse('order_create'))
        self.assertRedirects(response_create, f"{reverse('login')}?next={reverse('order_create')}")

    def test_public_order_invoice_accessible_without_login(self):
        order = Order.objects.create(
            order_number='HAF-PUBLIC-01',
            customer=self.customer,
            date='2026-06-01',
            final_amount=Decimal('1500.00'),
            advance_paid=Decimal('500.00'),
            grand_total=Decimal('1000.00'),
        )
        self.client.logout()
        response = self.client.get(reverse('public_invoice', args=[order.access_token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HAF-PUBLIC-01')
        self.assertContains(response, self.customer.full_name)


