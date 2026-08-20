from echo.common.services import DomainService

from .models import EmailAccount, EmailMessage, EmailDraft, EmailRule

class AccountService(DomainService):
    model = EmailAccount

class MessageService(DomainService):
    model = EmailMessage

class SyncService(DomainService):
    model = EmailAccount

class DraftService(DomainService):
    model = EmailDraft

class AutomationService(DomainService):
    model = EmailRule

class SearchService(DomainService):
    model = EmailMessage

class ProviderService(DomainService):
    model = EmailAccount

class AnalyticsService(DomainService):
    model = EmailMessage
