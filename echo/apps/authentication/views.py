from __future__ import annotations

import hashlib
import logging

from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import redirect, render
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import APIToken, LoginHistory, PasswordResetToken, UserDevice, UserSession
from .serializers import (
    APITokenCreateSerializer,
    APITokenSerializer,
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    RegistrationSerializer,
    UserDeviceSerializer,
    UserSerializer,
    UserSessionSerializer,
)

logger = logging.getLogger(__name__)


def _client_ip(request) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')) or None


class RegistrationView(generics.CreateAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegistrationSerializer


class LoginView(TokenObtainPairView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = EmailTokenObtainPairSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            user = get_user_model().objects.filter(email__iexact=request.data.get('email', '')).first()
            if user:
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
                    device_name=user_agent or 'API client',
                    defaults={'browser': user_agent, 'ip_address': ip_address, 'last_login': user.last_login},
                )
        return response


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get('refresh')
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except Exception as exc:
                logger.info('Refresh token could not be blacklisted: %s', exc.__class__.__name__)
                return Response({'detail': 'Refresh token is invalid.'}, status=status.HTTP_400_BAD_REQUEST)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ForgotPasswordView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'login'

    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        user = get_user_model().objects.filter(email=email, is_active=True).first()
        if user:
            from .services import EmailService, TokenService

            token = TokenService.password_reset(user)
            try:
                EmailService.send(
                    'Echo password reset',
                    f'Use this password reset token: {token}',
                    user.email,
                )
            except Exception:
                logger.exception('Password reset email delivery failed.')
        return Response(
            {'detail': 'If the account exists, reset instructions have been sent.'},
            status=status.HTTP_202_ACCEPTED,
        )


class ResetPasswordView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'login'

    def post(self, request):
        raw_token = str(request.data.get('token', ''))
        new_password = str(request.data.get('new_password', ''))
        try:
            validate_password(new_password)
        except DjangoValidationError as exc:
            return Response({'new_password': list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token = (
            PasswordResetToken.objects.select_related('user')
            .filter(token_hash=token_hash, used=False)
            .first()
        )
        if not token or not token.is_valid:
            return Response(
                {'detail': 'The reset token is invalid or expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token.user.set_password(new_password)
        token.user.save(update_fields=['password'])
        token.used = True
        token.save(update_fields=['used', 'updated_at'])
        return Response({'detail': 'Password reset completed.'})


class CurrentUserView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_deleted = True
        instance.save(update_fields=['is_active', 'is_deleted', 'updated_at'])


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        update_session_auth_hash(request, user)
        return Response({'detail': 'Password changed.'})


class APITokenListCreateView(generics.ListCreateAPIView):
    def get_queryset(self):
        return APIToken.objects.filter(user=self.request.user, revoked=False)

    def get_serializer_class(self):
        return APITokenCreateSerializer if self.request.method == 'POST' else APITokenSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token, raw_token = APIToken.issue(
            request.user,
            serializer.validated_data['name'],
            serializer.validated_data.get('expires_at'),
        )
        return Response(
            {**APITokenSerializer(token).data, 'token': raw_token},
            status=status.HTTP_201_CREATED,
        )


class APITokenDeleteView(generics.DestroyAPIView):
    serializer_class = APITokenSerializer

    def get_queryset(self):
        return APIToken.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        instance.revoked = True
        instance.save(update_fields=['revoked', 'updated_at'])


class SessionListView(generics.ListAPIView):
    serializer_class = UserSessionSerializer

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user, active=True)


class SessionDeleteView(generics.DestroyAPIView):
    serializer_class = UserSessionSerializer

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        instance.active = False
        instance.save(update_fields=['active'])


class DeviceListView(generics.ListAPIView):
    serializer_class = UserDeviceSerializer

    def get_queryset(self):
        return UserDevice.objects.filter(user=self.request.user)


class DeviceDeleteView(generics.DestroyAPIView):
    serializer_class = UserDeviceSerializer

    def get_queryset(self):
        return UserDevice.objects.filter(user=self.request.user)


def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        from django.contrib.auth import authenticate

        user = authenticate(
            request,
            email=request.POST.get('email', ''),
            password=request.POST.get('password', ''),
        )
        if user:
            login(request, user)
            return redirect(request.GET.get('next') or 'dashboard')
        return render(
            request,
            'authentication/login.html',
            {'error': 'Invalid email or password.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return render(request, 'authentication/login.html')


def register_page(request):
    if request.method == 'POST':
        serializer = RegistrationSerializer(data=request.POST)
        if serializer.is_valid():
            user = serializer.save()
            login(request, user)
            return redirect('dashboard')
        return render(
            request,
            'authentication/register.html',
            {'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return render(request, 'authentication/register.html')
