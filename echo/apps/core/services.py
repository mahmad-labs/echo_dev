from echo.common.services import DomainService

from .models import SystemConfiguration, UploadedFile, SystemLog, ApplicationRegistry, AuditLog

class ConfigService(DomainService):
    model = SystemConfiguration

class CacheService(DomainService):
    model = SystemConfiguration

class StorageService(DomainService):
    model = UploadedFile

class LoggingService(DomainService):
    model = SystemLog

class MetricsService(DomainService):
    model = SystemLog

class HealthService(DomainService):
    model = ApplicationRegistry

class EventService(DomainService):
    model = AuditLog

class RegistryService(DomainService):
    model = ApplicationRegistry
