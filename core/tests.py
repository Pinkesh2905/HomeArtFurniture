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
