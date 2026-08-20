from echo.common.services import DomainService

from .models import UserSetting, IntegrationSetting, SecretReference, ConfigurationAudit

class SettingsService(DomainService):
    model = UserSetting

class IntegrationSettingsService(DomainService):
    model = IntegrationSetting

class SecretReferenceService(DomainService):
    model = SecretReference

class ConfigurationAuditService(DomainService):
    model = ConfigurationAudit
