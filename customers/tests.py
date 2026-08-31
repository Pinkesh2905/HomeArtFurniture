from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from measurements.models import FurnitureDimension
from .models import Customer


class CustomerViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(full_name='Rajesh Kumar', phone='+91 98765 43210', city='Jaipur')
        FurnitureDimension.objects.create(customer=self.customer, furniture_type='sofa', values={'Width': '40'})

    def test_phone_lookup_normalizes_phone_and_returns_measurements(self):
        response = self.client.get(reverse('api_get_customer_by_phone', args=['+91-98765-43210']))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['customer']['phone'], '+919876543210')
        self.assertEqual(data['measurements']['sofa']['values']['Width'], '40')

    def test_unauthenticated_customer_views_redirect_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('customer_list'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('customer_list')}")

        response_detail = self.client.get(reverse('customer_detail', args=[self.customer.id]))
        self.assertRedirects(response_detail, f"{reverse('login')}?next={reverse('customer_detail', args=[self.customer.id])}")

    def test_customer_detail_shows_final_amount_and_in_progress_status(self):
        from decimal import Decimal
        from orders.models import Order
        Order.objects.create(
            order_number='HAF-CUST-ORD-01',
            customer=self.customer,
            date='2026-06-01',
            final_amount=Decimal('8500.00'),
            advance_paid=Decimal('3500.00'),
            grand_total=Decimal('5000.00'),
            status='in_progress',
        )
        response = self.client.get(reverse('customer_detail', args=[self.customer.id]))
        self.assertEqual(response.status_code, 200)
        # Total column must display final_amount (8500.00), NOT grand_total (5000.00)
        self.assertContains(response, '₹8500.00')
        self.assertNotContains(response, '₹5000.00')
        # in_progress status must render with blue badge class
        self.assertContains(response, 'In Progress')
        self.assertContains(response, 'bg-blue-500/20')

    def test_customer_create_same_phone_and_name_redirects_to_existing(self):
        response = self.client.post(reverse('customer_create'), {
            'full_name': 'Rajesh Kumar',
            'phone': '9876543210',
            'country_code': '+91',
            'city': 'Jaipur',
        })
        self.assertRedirects(response, reverse('customer_detail', args=[self.customer.id]))

    def test_customer_create_same_phone_different_name_shows_confirmation(self):
        response = self.client.post(reverse('customer_create'), {
            'full_name': 'Rohan Kumar',
            'phone': '9876543210',
            'country_code': '+91',
            'city': 'Jaipur',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['confirm_prompt'])
        self.assertEqual(response.context['existing_customer'], self.customer)
        self.assertContains(response, 'A customer with this phone number already exists: Rajesh Kumar')
        self.assertContains(response, 'Create Separate Customer')

    def test_customer_create_same_phone_different_name_with_confirmation_succeeds(self):
        response = self.client.post(reverse('customer_create'), {
            'full_name': 'Rohan Kumar',
            'phone': '9876543210',
            'country_code': '+91',
            'city': 'Jaipur',
            'confirm_create': 'true',
        })
        new_customer = Customer.objects.get(full_name='Rohan Kumar')
        self.assertEqual(new_customer.phone, self.customer.phone)
        self.assertRedirects(response, reverse('customer_detail', args=[new_customer.id]))
        # Confirm two distinct customers now share the same phone
        matching_customers = Customer.objects.filter(phone=self.customer.phone)
        self.assertEqual(matching_customers.count(), 2)

    def test_customer_city_normalization_on_save(self):
        c1 = Customer.objects.create(full_name='City User 1', phone='+91 91111 22222', city='  jaipur  ')
        self.assertEqual(c1.city, 'Jaipur')

        c2 = Customer.objects.create(full_name='City User 2', phone='+91 93333 44444', city='NEW DELHI')
        self.assertEqual(c2.city, 'New Delhi')

    def test_phone_validation_model_rejects_too_long(self):
        from django.core.exceptions import ValidationError
        # 11 digits after +91
        with self.assertRaises(ValidationError):
            Customer.objects.create(full_name='Too Long', phone='+9112345678909')
        # 12 digits local
        with self.assertRaises(ValidationError):
            Customer.objects.create(full_name='Too Long Local', phone='123456789012')

    def test_phone_validation_model_rejects_too_short(self):
        from django.core.exceptions import ValidationError
        # 5 digits local
        with self.assertRaises(ValidationError):
            Customer.objects.create(full_name='Too Short', phone='12345')
        # 5 digits after +91
        with self.assertRaises(ValidationError):
            Customer.objects.create(full_name='Too Short With CC', phone='+9112345')

    def test_customer_create_view_rejects_invalid_phone(self):
        # Too long phone
        response = self.client.post(reverse('customer_create'), {
            'full_name': 'Invalid Phone User',
            'phone': '12345678909',  # 11 digits
            'country_code': '+91',
            'city': 'Surat',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Phone number must be exactly 10 digits')

        # Too short phone
        response_short = self.client.post(reverse('customer_create'), {
            'full_name': 'Invalid Short Phone',
            'phone': '98765',  # 5 digits
            'country_code': '+91',
            'city': 'Surat',
        })
        self.assertEqual(response_short.status_code, 200)
        self.assertContains(response_short, 'Phone number must be exactly 10 digits')

    def test_customer_edit_view_updates_details_and_redirects(self):
        response = self.client.post(reverse('customer_edit', args=[self.customer.id]), {
            'full_name': 'Rajesh Sharma',
            'country_code': '+91',
            'phone': '9123456780',
            'city': 'Udaipur',
        })
        self.assertRedirects(response, reverse('customer_detail', args=[self.customer.id]))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, 'Rajesh Sharma')
        self.assertEqual(self.customer.phone, '+919123456780')
        self.assertEqual(self.customer.city, 'Udaipur')

    def test_customer_edit_view_ajax_updates_and_returns_json(self):
        response = self.client.post(
            reverse('customer_edit', args=[self.customer.id]),
            {
                'full_name': 'Rajesh Varma',
                'country_code': '+91',
                'phone': '9811122233',
                'city': 'Mumbai',
                'is_ajax': 'true',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['customer']['full_name'], 'Rajesh Varma')
        self.assertEqual(data['customer']['phone'], '+919811122233')
        self.assertEqual(data['customer']['city'], 'Mumbai')

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, 'Rajesh Varma')

    def test_customer_edit_view_rejects_invalid_phone(self):
        response = self.client.post(
            reverse('customer_edit', args=[self.customer.id]),
            {
                'full_name': 'Rajesh Varma',
                'country_code': '+91',
                'phone': '12345',  # too short
                'city': 'Mumbai',
                'is_ajax': 'true',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('10 digits', data['message'])

    def test_customer_edit_view_rejects_duplicate_phone(self):
        other = Customer.objects.create(full_name='Other Customer', phone='+91 91111 22222')
        response = self.client.post(
            reverse('customer_edit', args=[self.customer.id]),
            {
                'full_name': 'Rajesh Duplicate',
                'country_code': '+91',
                'phone': '9111122222',
                'city': 'Mumbai',
                'is_ajax': 'true',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('already has the phone number', data['message'])

    def test_delete_zero_order_customer_removes_record(self):
        zero_cust = Customer.objects.create(full_name='Zero Order User', phone='+91 95555 66666', city='Jaipur')
        cust_id = zero_cust.id
        self.assertEqual(zero_cust.orders.count(), 0)

        response = self.client.post(reverse('customer_delete', args=[cust_id]))
        self.assertRedirects(response, reverse('customer_list'))
        self.assertFalse(Customer.objects.filter(id=cust_id).exists())

    def test_attempt_delete_customer_with_orders_blocked_and_archived_instead(self):
        from orders.models import Order
        order = Order.objects.create(
            order_number='HAF-DEL-TEST-01',
            customer=self.customer,
            date='2026-06-01',
            final_amount=5000,
            grand_total=5000,
            status='pending',
        )
        self.assertEqual(self.customer.orders.count(), 1)

        response = self.client.post(reverse('customer_delete', args=[self.customer.id]))
        # Must redirect to customer detail with warning message, NOT delete
        self.assertRedirects(response, reverse('customer_detail', args=[self.customer.id]))
        
        # Verify customer still exists and was archived instead
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_archived)
        # Verify order and financial records are intact
        self.assertTrue(Order.objects.filter(id=order.id).exists())
        self.assertEqual(order.customer.id, self.customer.id)

    def test_archiving_hides_customer_from_default_search_but_preserves_orders(self):
        from orders.models import Order
        order = Order.objects.create(
            order_number='HAF-ARCH-01',
            customer=self.customer,
            date='2026-06-01',
            final_amount=3000,
            grand_total=3000,
            status='pending',
        )

        # Archive customer
        response = self.client.post(reverse('customer_archive', args=[self.customer.id]))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_archived)

        # 1. Default directory list hides archived customer from context
        list_response = self.client.get(reverse('customer_list'))
        customers_in_context = list_response.context['customers'].object_list
        self.assertNotIn(self.customer, customers_in_context)

        # 2. Directory search for archived customer on active directory returns empty (flash message consumed)
        search_response = self.client.get(reverse('customer_list'), {'q': 'Rajesh'})
        self.assertNotIn(self.customer, search_response.context['customers'].object_list)
        self.assertNotContains(search_response, 'Rajesh Kumar')

        # 3. Filtered archived view shows archived customer
        archived_response = self.client.get(reverse('customer_list'), {'archived': 'true'})
        self.assertContains(archived_response, 'Rajesh Kumar')
        self.assertContains(archived_response, 'ARCHIVED')

        # 4. API search for new order creation hides archived customer
        api_search = self.client.get(reverse('api_search_customers'), {'q': 'Rajesh'})
        data = api_search.json()
        self.assertEqual(len(data['results']), 0)

        # 5. Order detail still displays customer name and details properly
        order_response = self.client.get(reverse('order_detail', args=[order.id]))
        self.assertEqual(order_response.status_code, 200)
        self.assertContains(order_response, 'Rajesh Kumar')

    def test_unarchive_restores_customer_to_active_directory(self):
        self.customer.is_archived = True
        self.customer.save()

        # Unarchive
        response = self.client.post(reverse('customer_unarchive', args=[self.customer.id]))
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_archived)

        # Restored to default directory
        list_response = self.client.get(reverse('customer_list'))
        self.assertContains(list_response, 'Rajesh Kumar')




