from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    APITokenDeleteView,
    APITokenListCreateView,
    ChangePasswordView,
    CurrentUserView,
    DeviceDeleteView,
    DeviceListView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    RegistrationView,
    ResetPasswordView,
    SessionDeleteView,
    SessionListView,
)

urlpatterns = [
    path('register/', RegistrationView.as_view(), name='api-register'),
    path('login/', LoginView.as_view(), name='api-login'),
    path('logout/', LogoutView.as_view(), name='api-logout'),
    path('refresh/', TokenRefreshView.as_view(), name='api-refresh'),
    path('change-password/', ChangePasswordView.as_view(), name='api-change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='api-forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='api-reset-password'),
    path('user/', CurrentUserView.as_view(), name='api-user'),
    path('sessions/', SessionListView.as_view(), name='api-sessions'),
    path('sessions/<uuid:pk>/', SessionDeleteView.as_view(), name='api-session-detail'),
    path('devices/', DeviceListView.as_view(), name='api-devices'),
    path('devices/<uuid:pk>/', DeviceDeleteView.as_view(), name='api-device-detail'),
    path('tokens/', APITokenListCreateView.as_view(), name='api-tokens'),
    path('tokens/<uuid:pk>/', APITokenDeleteView.as_view(), name='api-token-detail'),
]
