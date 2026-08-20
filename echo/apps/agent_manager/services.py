from echo.common.services import DomainService

from .models import Agent, AgentCapability, AgentTask, AgentCommunication, AgentPerformance
from .orchestration import AgentContextBuilder, AgentManagerOrchestrator, AgentMessageBus
from .registry import AgentRegistry


class AgentService(DomainService):
    model = Agent


class RegistryService(DomainService):
    model = Agent

    @staticmethod
    def definitions():
        return [item.public() for item in AgentRegistry.definitions()]

    @staticmethod
    def materialize(user):
        return AgentRegistry.materialize_all(user)


class CapabilityService(DomainService):
    model = AgentCapability


class AssignmentService(DomainService):
    model = AgentTask


class CommunicationService(DomainService):
    model = AgentCommunication


class LifecycleService(DomainService):
    model = Agent


class MonitoringService(DomainService):
    model = AgentPerformance


class AnalyticsService(DomainService):
    model = AgentPerformance
