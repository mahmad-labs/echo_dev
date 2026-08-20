from echo.common.services import DomainService

from .models import Task, TaskDependency, Reminder, RecurrenceRule, TimeEntry, TaskActivity

class TaskService(DomainService):
    model = Task

class SchedulingService(DomainService):
    model = Task

class DependencyService(DomainService):
    model = TaskDependency

class ReminderService(DomainService):
    model = Reminder

class RecurrenceService(DomainService):
    model = RecurrenceRule

class AutomationService(DomainService):
    model = Task

class TrackingService(DomainService):
    model = TimeEntry

class AnalyticsService(DomainService):
    model = TaskActivity
