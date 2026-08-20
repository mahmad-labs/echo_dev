from __future__ import annotations

import hashlib
import secrets
import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from echo.common.models import UUIDModel


class UserManager(BaseUserManager):
    use_in_migrations = True
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email address is required.')
        email = self.normalize_email(email).strip().lower()
        username = extra_fields.pop('username', email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.full_clean(exclude=['password'])
        user.save(using=self._db)
        return user
    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False); extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True); extra_fields.setdefault('is_superuser', True); extra_fields.setdefault('is_verified', True)
        if extra_fields.get('is_staff') is not True or extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser requires is_staff=True and is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=2, blank=True)
    timezone = models.CharField(max_length=64, default='UTC')
    language = models.CharField(max_length=12, default='en')
    profile_picture = models.ImageField(upload_to='profiles/%Y/%m/', blank=True)
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=32, blank=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    roles = models.ManyToManyField('UserRole', related_name='users', blank=True)
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    def __str__(self): return self.display_name or self.get_full_name() or self.email


class UserProfile(UUIDModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    theme = models.CharField(max_length=20, default='system')
    accent_color = models.CharField(max_length=20, default='indigo')
    font_size = models.CharField(max_length=20, default='medium')
    dashboard_layout = models.JSONField(default=dict, blank=True)
    preferred_language = models.CharField(max_length=12, default='en')
    preferred_ai_model = models.CharField(max_length=255, blank=True)
    notification_preferences = models.JSONField(default=dict, blank=True)
    timezone = models.CharField(max_length=64, default='UTC')


class UserRole(UUIDModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    def __str__(self): return self.name


class Permission(UUIDModel):
    name = models.CharField(max_length=150)
    codename = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    def __str__(self): return self.codename


class RolePermission(UUIDModel):
    role = models.ForeignKey(UserRole, on_delete=models.CASCADE, related_name='permission_links')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_links')
    class Meta(UUIDModel.Meta):
        constraints = [models.UniqueConstraint(fields=['role', 'permission'], name='unique_role_permission')]


class UserDevice(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='devices')
    device_name = models.CharField(max_length=255, blank=True)
    browser = models.CharField(max_length=255, blank=True)
    operating_system = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    trusted = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta(UUIDModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=['user', 'device_name'], name='unique_user_device_name')
        ]


class LoginHistory(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    browser = models.CharField(max_length=255, blank=True)
    device = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=32, default='success')
    login_time = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(null=True, blank=True)


class ExpiringToken(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    used = models.BooleanField(default=False)
    class Meta: abstract = True
    @classmethod
    def issue(cls, user, lifetime):
        raw = secrets.token_urlsafe(32)
        cls.objects.create(user=user, token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=timezone.now()+lifetime)
        return raw
    def matches(self, raw): return secrets.compare_digest(self.token_hash, hashlib.sha256(raw.encode()).hexdigest())
    @property
    def is_valid(self): return not self.used and self.expires_at > timezone.now()


class EmailVerificationToken(ExpiringToken):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_verification_tokens')
class PasswordResetToken(ExpiringToken):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_reset_tokens')


class APIToken(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_tokens')
    token_prefix = models.CharField(max_length=12, db_index=True)
    token_hash = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)
    @classmethod
    def issue(cls, user, name, expires_at=None):
        raw = secrets.token_urlsafe(40)
        obj = cls.objects.create(user=user, name=name, token_prefix=raw[:12], token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=expires_at)
        return obj, raw


class UserSession(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='session_records')
    session_key = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    browser = models.CharField(max_length=255, blank=True)
    device = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    active = models.BooleanField(default=True)
