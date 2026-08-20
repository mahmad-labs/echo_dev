from echo.common.services import DomainService

from .models import ExecutionPlan, Goal, StepDependency, PlanStep, RiskAssessment

class PlannerService(DomainService):
    model = ExecutionPlan

class GoalService(DomainService):
    model = Goal

class DependencyService(DomainService):
    model = StepDependency

class OptimizationService(DomainService):
    model = ExecutionPlan

class SchedulingService(DomainService):
    model = PlanStep

class ProgressService(DomainService):
    model = PlanStep

class EstimationService(DomainService):
    model = RiskAssessment
