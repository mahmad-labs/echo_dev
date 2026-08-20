from django.urls import path

from echo.common.router import build_app_router
from .computer_views import (
    BrowserActionView,
    BrowserObserveView,
    BrowserSessionEndView,
    BrowserSessionListCreateView,
    ComputerUseOperationCancelView,
    ComputerUseOperationDetailView,
    ComputerUseOperationListCreateView,
    ComputerUseOperationResumeView,
    MediaAnalyzeView,
    MediaQuestionView,
    DesktopSessionListCreateView, DesktopSessionEndView, DesktopObserveView, DesktopActionView,
)

router = build_app_router('internet')

urlpatterns = [
    path('computer/sessions/', BrowserSessionListCreateView.as_view(), name='computer-browser-sessions'),
    path('computer/sessions/<uuid:pk>/end/', BrowserSessionEndView.as_view(), name='computer-browser-session-end'),
    path('computer/observe/', BrowserObserveView.as_view(), name='computer-browser-observe'),
    path('computer/action/', BrowserActionView.as_view(), name='computer-browser-action'),
    path('computer/operations/', ComputerUseOperationListCreateView.as_view(), name='computer-operations'),
    path('computer/operations/<uuid:pk>/', ComputerUseOperationDetailView.as_view(), name='computer-operation-detail'),
    path('computer/operations/<uuid:pk>/cancel/', ComputerUseOperationCancelView.as_view(), name='computer-operation-cancel'),
    path('computer/operations/<uuid:pk>/resume/', ComputerUseOperationResumeView.as_view(), name='computer-operation-resume'),
    path('computer/media/analyze/', MediaAnalyzeView.as_view(), name='computer-media-analyze'),
    path('computer/media/question/', MediaQuestionView.as_view(), name='computer-media-question'),
    path('desktop/sessions/', DesktopSessionListCreateView.as_view(), name='computer-desktop-sessions'),
    path('desktop/sessions/<uuid:pk>/end/', DesktopSessionEndView.as_view(), name='computer-desktop-session-end'),
    path('desktop/observe/', DesktopObserveView.as_view(), name='computer-desktop-observe'),
    path('desktop/action/', DesktopActionView.as_view(), name='computer-desktop-action'),
] + router.urls
