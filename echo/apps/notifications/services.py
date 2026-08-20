from echo.common.services import DomainService

from .models import Notification, NotificationChannel, DeliveryLog, NotificationPreference, NotificationTemplate, NotificationDigest

class NotificationService(DomainService):
    model = Notification

class RoutingService(DomainService):
    model = NotificationChannel

class DeliveryService(DomainService):
    model = DeliveryLog

class PreferenceService(DomainService):
    model = NotificationPreference

class TemplateService(DomainService):
    model = NotificationTemplate

class RetryService(DomainService):
    model = DeliveryLog

class DigestService(DomainService):
    model = NotificationDigest

class AnalyticsService(DomainService):
    model = DeliveryLog
