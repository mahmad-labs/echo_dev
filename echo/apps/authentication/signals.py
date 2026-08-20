from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import LoginHistory, User, UserDevice, UserProfile, UserSession


def _client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')) or None


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                'timezone': instance.timezone,
                'preferred_language': instance.language,
            },
        )
        from .models import UserRole

        default_role = UserRole.objects.filter(
            name='Administrator' if instance.is_staff else 'Standard User'
        ).first()
        if default_role:
            instance.roles.add(default_role)


@receiver(user_logged_in)
def record_browser_login(sender, request, user, **kwargs):
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
    ip_address = _client_ip(request)
    LoginHistory.objects.create(
        user=user,
        ip_address=ip_address,
        browser=user_agent,
        device=user_agent,
        status='success',
    )
    UserDevice.objects.update_or_create(
        user=user,
        device_name=user_agent or 'Browser',
        defaults={
            'browser': user_agent,
            'ip_address': ip_address,
            'last_login': timezone.now(),
        },
    )
    if request.session.session_key:
        UserSession.objects.update_or_create(
            session_key=request.session.session_key,
            defaults={
                'user': user,
                'ip_address': ip_address,
                'browser': user_agent,
                'device': user_agent,
                'expires_at': request.session.get_expiry_date(),
                'active': True,
            },
        )


@receiver(user_logged_out)
def record_browser_logout(sender, request, user, **kwargs):
    if request and request.session.session_key:
        UserSession.objects.filter(session_key=request.session.session_key).update(active=False)
    if user:
        latest_login = (
            LoginHistory.objects.filter(user=user, logout_time__isnull=True)
            .order_by('-login_time')
            .first()
        )
        if latest_login:
            latest_login.logout_time = timezone.now()
            latest_login.save(update_fields=['logout_time', 'updated_at'])
