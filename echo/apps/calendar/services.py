from echo.common.services import DomainService

from .models import Calendar, Event, Reminder, AvailabilityRule, EventParticipant

class CalendarService(DomainService):
    model = Calendar

class EventService(DomainService):
    model = Event

class SchedulingService(DomainService):
    model = Event

class ReminderService(DomainService):
    model = Reminder

class AvailabilityService(DomainService):
    model = AvailabilityRule

class InvitationService(DomainService):
    model = EventParticipant

class SyncService(DomainService):
    model = Calendar

class AnalyticsService(DomainService):
    model = Event
