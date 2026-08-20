from django.urls import path

from echo.common.router import build_app_router
from .views import AgentRegistryView, AgentTaskListView, AgentTaskDetailView, AgentTaskCancelView, AgentTaskApproveView

router = build_app_router('agent_manager')

urlpatterns = [
    path('orchestration/registry/', AgentRegistryView.as_view(), name='agent-registry'),
    path('orchestration/tasks/', AgentTaskListView.as_view(), name='agent-tasks'),
    path('orchestration/tasks/<uuid:pk>/', AgentTaskDetailView.as_view(), name='agent-task-detail'),
    path('orchestration/tasks/<uuid:pk>/cancel/', AgentTaskCancelView.as_view(), name='agent-task-cancel'),
    path('orchestration/tasks/<uuid:pk>/approve/', AgentTaskApproveView.as_view(), name='agent-task-approve'),
] + router.urls
