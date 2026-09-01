from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class CoreViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')
        self.client.force_login(self.user)

    def test_dashboard_loads(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_dashboard_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_unauthenticated_search_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('global_search'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('global_search')}")

    def test_dashboard_inventory_alerts_database_level(self):
        from decimal import Decimal
        from inventory.models import Material, MaterialCategory, UnitOfMeasure
        Material.objects.create(
            name="Sofa Springs",
            sku="CORE-SPR-01",
            category=MaterialCategory.HARDWARE,
            unit=UnitOfMeasure.PIECES,
            min_stock=50,
            current_stock=20,  # low stock
            cost_per_unit=15,
        )
        Material.objects.create(
            name="Empty Wood Polish",
            sku="CORE-POL-01",
            category=MaterialCategory.PAINT,
            unit=UnitOfMeasure.LITERS,
            min_stock=10,
            current_stock=0,  # out of stock
            cost_per_unit=100,
        )
        Material.objects.create(
            name="Ample Cotton Fabric",
            sku="CORE-FAB-01",
            category=MaterialCategory.FABRIC,
            unit=UnitOfMeasure.METERS,
            min_stock=10,
            current_stock=200,  # adequate
            cost_per_unit=50,
        )

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['low_stock_count'], 2)  # 1 low + 1 out
        # total_stock_value = (20 * 15) + (0 * 100) + (200 * 50) = 300 + 10000 = 10300
        self.assertEqual(response.context['total_stock_value'], Decimal('10300.00'))
        low_names = [m.name for m in response.context['low_stock_materials']]
        self.assertIn("Sofa Springs", low_names)
        out_names = [m.name for m in response.context['out_of_stock_materials']]
        self.assertIn("Empty Wood Polish", out_names)

    def test_custom_404_template_rendered(self):
        from django.test import override_settings
        with override_settings(DEBUG=False):
            response = self.client.get('/this-path-definitely-does-not-exist-12345/')
            self.assertEqual(response.status_code, 404)
            self.assertTemplateUsed(response, '404.html')
            self.assertContains(response, 'Page Not Found', status_code=404)

    def test_custom_500_template_rendered(self):
        from django.views.defaults import server_error
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Internal Server Error', response.content)

    def test_favicon_static_file_exists(self):
        from django.contrib.staticfiles import finders
        result = finders.find('core/img/favicon.svg')
        self.assertIsNotNone(result)
        with open(result, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('<svg viewBox="0 0 64 64"', content)
        self.assertIn('#3B2820', content)
        self.assertIn('#A0845E', content)

    def test_favicon_link_in_templates(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'rel="icon" type="image/svg+xml"')
        self.assertContains(response, 'favicon.svg')

        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'rel="icon" type="image/svg+xml"')
        self.assertContains(response, 'favicon.svg')

    def test_login_page_split_layout_content(self):
        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'walnut-brand-panel')
        self.assertContains(response, 'Home ')
        self.assertContains(response, 'FURNITURE')
        self.assertContains(response, 'Store Management &amp; Atelier')
        self.assertContains(response, 'Staff Sign In')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'Sign In')

    def test_sidebar_logout(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log out')
        self.assertContains(response, reverse('logout'))

        # Test POST logout functionality
        logout_response = self.client.post(reverse('logout'))
        self.assertEqual(logout_response.status_code, 302)
        self.assertRedirects(logout_response, reverse('login'))

    def test_authenticated_response_has_no_cache_headers(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Cache-Control', response.headers)
        self.assertEqual(response.headers['Cache-Control'], 'no-store, no-cache, must-revalidate')
        self.assertEqual(response.headers.get('Pragma'), 'no-cache')
        self.assertEqual(response.headers.get('Expires'), '0')

    def test_unauthenticated_response_not_modified_by_no_cache_middleware(self):
        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        # Our middleware sets exactly 'no-store, no-cache, must-revalidate' and Expires: '0'
        self.assertNotEqual(response.headers.get('Cache-Control'), 'no-store, no-cache, must-revalidate')
        self.assertNotEqual(response.headers.get('Expires'), '0')

    def test_public_invoice_unauthenticated_not_affected_by_no_cache(self):
        from customers.models import Customer
        from orders.models import Order
        import uuid
        self.client.logout()
        customer = Customer.objects.create(full_name='Test Public Client', phone='9876543210')
        order = Order.objects.create(
            order_number='HAF-TEST-PUB-01',
            customer=customer,
            access_token=uuid.uuid4(),
            grand_total=1000,
        )
        response = self.client.get(reverse('public_invoice', kwargs={'token': order.access_token}))
        self.assertEqual(response.status_code, 200)
        cache_control = response.headers.get('Cache-Control', '')
        self.assertNotIn('no-store', cache_control)
        self.assertNotEqual(response.headers.get('Pragma'), 'no-cache')
        self.assertNotEqual(response.headers.get('Expires'), '0')

    def test_healthz_and_ping_endpoints(self):
        self.client.logout()
        r1 = self.client.get(reverse('healthz'))
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.content, b"OK")
        self.assertEqual(r1.headers.get('Content-Type'), 'text/plain')

        r2 = self.client.get(reverse('ping'))
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.content, b"OK")




