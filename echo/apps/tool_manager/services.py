from echo.common.services import DomainService

from .models import Tool, ToolExecution, ToolPermission, ToolSecretReference, ToolHealth

class ToolService(DomainService):
    model = Tool

class ExecutionService(DomainService):
    model = ToolExecution

class RegistryService(DomainService):
    model = Tool

class PermissionService(DomainService):
    model = ToolPermission

class SecretService(DomainService):
    model = ToolSecretReference

class MonitoringService(DomainService):
    model = ToolHealth

class AnalyticsService(DomainService):
    model = ToolExecution

class HealthService(DomainService):
    model = ToolHealth
