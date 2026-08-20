from echo.common.services import DomainService

from .models import AIRequest, PromptTemplate, AIModel, ContextSnapshot, AIResponse, AIProvider

class AIService(DomainService):
    model = AIRequest

class PromptService(DomainService):
    model = PromptTemplate

class ModelService(DomainService):
    model = AIModel

class ContextService(DomainService):
    model = ContextSnapshot

class TokenService(DomainService):
    model = AIRequest

class StreamingService(DomainService):
    model = AIResponse

class TelemetryService(DomainService):
    model = AIRequest

class ProviderService(DomainService):
    model = AIProvider

class RoutingService(DomainService):
    model = AIProvider

class ResponseService(DomainService):
    model = AIResponse

class AnalyticsService(DomainService):
    model = AIRequest
