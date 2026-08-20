from echo.common.services import DomainService

from .models import Workflow, WorkflowExecution, StepDependency, WorkflowStep, Checkpoint, ExecutionEvent

class WorkflowService(DomainService):
    model = Workflow

class ExecutionService(DomainService):
    model = WorkflowExecution

class DependencyService(DomainService):
    model = StepDependency

class QueueService(DomainService):
    model = WorkflowExecution

class SchedulingService(DomainService):
    model = WorkflowStep

class RecoveryService(DomainService):
    model = Checkpoint

class MonitoringService(DomainService):
    model = ExecutionEvent

class AnalyticsService(DomainService):
    model = WorkflowExecution
