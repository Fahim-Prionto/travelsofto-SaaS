"""
apps/tenants/tests.py

Comprehensive Unit & Integration Test Suite for ViserTrip Multi-Tenant SaaS Platform.
Tests:
  1. Custom User Model & Role Permissions
  2. SaaS Subscription Package Seeding
  3. Tenant Creation & Database Router Logic
  4. Super Admin Views
  5. Agency Admin CRUD Views
  6. Customer Portal Views
  7. REST API Endpoints
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings

from apps.tenants.models import Tenant, TenantDomain, GlobalSetting
from apps.subscriptions.models import SubscriptionPackage, Subscription
from apps.travel_packages.models import TravelPackage
from apps.visa.models import VisaService, VisaApplication
from apps.bookings.models import Booking

User = get_user_model()


class MultiTenantSaaSTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Create Super Admin User
        self.superadmin = User.objects.create_superuser(
            email='superadmin@visertrip.com',
            password='Password123!',
            first_name='Super',
            last_name='Admin'
        )

        # Create Subscription Package
        self.package = SubscriptionPackage.objects.create(
            name='Starter Plan',
            package_type='starter',
            monthly_price=Decimal('49.00'),
            yearly_price=Decimal('470.00'),
            trial_days=14
        )

        # Create Test Agency Tenant
        self.tenant = Tenant.objects.create(
            agency_name='Horizon Travels',
            owner_name='John Owner',
            email='owner@horizontravels.com',
            status=Tenant.Status.ACTIVE
        )

        # Create Tenant Admin User
        self.tenant_admin = User.objects.create_user(
            email='admin@horizontravels.com',
            password='Password123!',
            first_name='John',
            last_name='Owner',
            role=User.Role.TENANT_ADMIN,
            tenant_id=self.tenant.slug
        )
        self.tenant.admin_user = self.tenant_admin
        self.tenant.save()

        # Create Subdomain
        TenantDomain.objects.create(
            tenant=self.tenant,
            domain=f'{self.tenant.slug}.localhost',
            domain_type='subdomain',
            status='active'
        )

        # Create Customer User
        self.customer = User.objects.create_user(
            email='customer@gmail.com',
            password='Password123!',
            first_name='Jane',
            last_name='Doe',
            role=User.Role.CUSTOMER,
            tenant_id=self.tenant.slug
        )

    def test_user_roles(self):
        """Test User model role properties."""
        self.assertTrue(self.superadmin.is_super_admin)
        self.assertFalse(self.superadmin.is_customer)
        self.assertTrue(self.tenant_admin.is_tenant_admin)
        self.assertTrue(self.customer.is_customer)

    def test_tenant_creation_and_urls(self):
        """Test Tenant slug auto-generation and domain URLs."""
        self.assertEqual(self.tenant.slug, 'horizon-travels')
        self.assertTrue('horizon-travels' in self.tenant.subdomain_url)

    def test_superadmin_dashboard_access(self):
        """Test Super Admin dashboard authentication enforcement."""
        # Unauthenticated redirect
        response = self.client.get(reverse('superadmin:dashboard'))
        self.assertEqual(response.status_code, 302)

        # Logged in as Super Admin
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse('superadmin:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_agency_admin_panel_access(self):
        """Test Agency Admin panel dashboard access."""
        self.client.force_login(self.tenant_admin)
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_customer_portal_access(self):
        """Test Customer Portal dashboard access."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('public:customer_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_travel_package_api_list(self):
        """Test Travel Package REST API endpoint."""
        response = self.client.get(reverse('travel_packages_api:api_package_list'))
        self.assertEqual(response.status_code, 200)

    def test_visa_service_api_list(self):
        """Test Visa Service REST API endpoint."""
        response = self.client.get(reverse('visa_api:api_visa_services'))
        self.assertEqual(response.status_code, 200)
