from echo.common.services import DomainService

from .models import APIClient, APIKey, WebhookEndpoint, IdempotencyRecord, APIRequestLog

class APIClientService(DomainService):
    model = APIClient

class KeyService(DomainService):
    model = APIKey

class WebhookService(DomainService):
    model = WebhookEndpoint

class IdempotencyService(DomainService):
    model = IdempotencyRecord

class RequestLogService(DomainService):
    model = APIRequestLog
