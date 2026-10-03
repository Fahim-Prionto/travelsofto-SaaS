"""
apps/accounts/models.py

Custom User model for ViserTrip.
This single model serves all roles:
  - Super Admin
  - Tenant Admin / Staff
  - Customer

Role-based access is controlled via the 'role' field and the Tenant FK.
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom manager for the User model (email-based auth)."""

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email address is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.SUPER_ADMIN)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Central User model for ViserTrip.
    All roles share this model; the 'role' field differentiates them.
    For customers and tenant staff, 'tenant_id' identifies which agency they belong to.
    """

    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', _('Super Admin')
        SUPPORT_MEMBER = 'support_member', _('Support Member')
        TENANT_ADMIN = 'tenant_admin', _('Tenant Admin')
        TENANT_STAFF = 'tenant_staff', _('Tenant Staff')
        AMBASSADOR = 'ambassador', _('Ambassador')
        CUSTOMER = 'customer', _('Customer')

    # ── Identifiers ────────────────────────────────────────────────────────────
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # ── Personal Info ──────────────────────────────────────────────────────────
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    mobile = models.CharField(_('mobile number'), max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # ── Role & Tenant ──────────────────────────────────────────────────────────
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
    )
    # tenant_id is stored here for quick lookup without joining the tenant table.
    # NULL for super admin users; set for all tenant-level users.
    tenant_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text='Slug of the tenant this user belongs to.',
    )

    # ── Account Status ─────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)

    # ── Verification ───────────────────────────────────────────────────────────
    email_verified = models.BooleanField(default=False)
    mobile_verified = models.BooleanField(default=False)
    kyc_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)

    # ── Balance (for customers) ────────────────────────────────────────────────
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email

    @property
    def is_super_admin(self):
        return self.role in (self.Role.SUPER_ADMIN, self.Role.SUPPORT_MEMBER) or self.is_superuser

    @property
    def is_support_member(self):
        return self.role == self.Role.SUPPORT_MEMBER

    @property
    def is_tenant_admin(self):
        return self.role == self.Role.TENANT_ADMIN

    @property
    def is_tenant_staff(self):
        return self.role == self.Role.TENANT_STAFF

    @property
    def is_ambassador(self):
        return self.role == self.Role.AMBASSADOR

    @property
    def tenant(self):
        if not self.tenant_id:
            return None
        from apps.tenants.models import Tenant
        return Tenant.objects.filter(slug=self.tenant_id).first()

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER


class UserProfile(models.Model):
    """Extended profile for customers."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # ── Address ────────────────────────────────────────────────────────────────
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # ── Identity ───────────────────────────────────────────────────────────────
    date_of_birth = models.DateField(blank=True, null=True)
    passport_number = models.CharField(max_length=50, blank=True)
    national_id = models.CharField(max_length=50, blank=True)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Profile of {self.user.email}'


class LoginHistory(models.Model):
    """Records login history for users."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=10,
        choices=[('success', 'Success'), ('failed', 'Failed')],
        default='success',
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']
        verbose_name_plural = 'login histories'

    def __str__(self):
        return f'{self.user.email} – {self.logged_at}'


class PasswordResetToken(models.Model):
    """Secure password reset tokens."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()

    def __str__(self):
        return f'Reset token for {self.user.email}'
