from datetime import timedelta
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import APIToken, EmailVerificationToken, PasswordResetToken


class AuthService:
    @staticmethod
    def authenticate(email, password): return authenticate(email=email, password=password)
class JWTService:
    @staticmethod
    def issue(user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh=RefreshToken.for_user(user); return {'refresh':str(refresh),'access':str(refresh.access_token)}
class OTPService:
    @staticmethod
    def generate():
        import secrets
        return f'{secrets.randbelow(1_000_000):06d}'
class EmailService:
    @staticmethod
    def send(subject, body, recipient):
        from django.core.mail import send_mail
        return send_mail(subject, body, None, [recipient], fail_silently=False)
class TokenService:
    @staticmethod
    def email_verification(user): return EmailVerificationToken.issue(user, timedelta(hours=24))
    @staticmethod
    def password_reset(user): return PasswordResetToken.issue(user, timedelta(hours=1))
