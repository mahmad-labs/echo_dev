from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from echo.apps.authentication.views import (
    APITokenDeleteView, APITokenListCreateView, ChangePasswordView, CurrentUserView,
    DeviceDeleteView, DeviceListView, ForgotPasswordView, LoginView, LogoutView as APILogoutView,
    RegistrationView, ResetPasswordView, SessionDeleteView, SessionListView,
    login_page, register_page,
)
from rest_framework_simplejwt.views import TokenRefreshView
from echo.apps.dashboard.pages import ai_command, dashboard, upload_document, workspace, workspace_action, workspace_record_update, workspace_search
from echo.apps.api.spec_views import EndpointCatalogView, SpecEndpointView
from echo.common.health import health, metrics, readiness

urlpatterns = [
    path('admin/', admin.site.urls), path('', dashboard, name='dashboard'),
    path('workspace/<slug:section>/', workspace, name='workspace'),
    path('workspace/action/create/', workspace_action, name='workspace-action'),
    path('workspace/action/update/', workspace_record_update, name='workspace-record-update'),
    path('workspace/command/', ai_command, name='ai-command'),
    path('workspace/search/', workspace_search, name='workspace-search'),
    path('workspace/documents/upload/', upload_document, name='workspace-upload'),
    path('login/', login_page, name='login'), path('register/', register_page, name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('health/', health, name='health'), path('ready/', readiness, name='readiness'), path('metrics/', metrics, name='metrics'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/v1/auth/', include('echo.apps.authentication.urls')),
    path('api/auth/register/', RegistrationView.as_view()),
    path('api/auth/login/', LoginView.as_view()),
    path('api/auth/logout/', APILogoutView.as_view()),
    path('api/auth/refresh/', TokenRefreshView.as_view()),
    path('api/auth/change-password/', ChangePasswordView.as_view()),
    path('api/auth/forgot-password/', ForgotPasswordView.as_view()),
    path('api/auth/reset-password/', ResetPasswordView.as_view()),
    path('api/user/', CurrentUserView.as_view()),
    path('api/sessions/', SessionListView.as_view()),
    path('api/sessions/<uuid:pk>/', SessionDeleteView.as_view()),
    path('api/devices/', DeviceListView.as_view()),
    path('api/devices/<uuid:pk>/', DeviceDeleteView.as_view()),
    path('api/tokens/', APITokenListCreateView.as_view()),
    path('api/tokens/<uuid:pk>/', APITokenDeleteView.as_view()),
    path('api/v1/core/', include('echo.apps.core.urls')),
    path('api/v1/dashboard/', include('echo.apps.dashboard.urls')),
    path('api/v1/chat/', include('echo.apps.chat.urls')),
    path('api/v1/ai-engine/', include('echo.apps.ai_engine.urls')),
    path('api/v1/memory/', include('echo.apps.memory.urls')),
    path('api/v1/vector-database/', include('echo.apps.vector_database.urls')),
    path('api/v1/knowledge/', include('echo.apps.knowledge.urls')),
    path('api/v1/documents/', include('echo.apps.documents.urls')),
    path('api/v1/internet/', include('echo.apps.internet.urls')),
    path('api/v1/code-assistant/', include('echo.apps.code_assistant.urls')),
    path('api/v1/planner/', include('echo.apps.planner.urls')),
    path('api/v1/agent-manager/', include('echo.apps.agent_manager.urls')),
    path('api/v1/workflow-engine/', include('echo.apps.workflow_engine.urls')),
    path('api/v1/tool-manager/', include('echo.apps.tool_manager.urls')),
    path('api/v1/tasks/', include('echo.apps.tasks.urls')),
    path('api/v1/calendar/', include('echo.apps.calendar.urls')),
    path('api/v1/email/', include('echo.apps.email.urls')),
    path('api/v1/notifications/', include('echo.apps.notifications.urls')),
    path('api/v1/api/', include('echo.apps.api.urls')),
    path('api/v1/analytics/', include('echo.apps.analytics.urls')),
    path('api/v1/settings/', include('echo.apps.settings.urls')),
    path('api/v1/voice/', include('echo.apps.voice.urls')),
    path('api/v1/projects/', include('echo.apps.projects.urls')),

    path('api/v1/endpoint-catalog/', EndpointCatalogView.as_view(), name='endpoint-catalog'),
    re_path(r'^api/(?P<resource_path>.+)/$', SpecEndpointView.as_view(), name='spec-endpoint-fallback'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
