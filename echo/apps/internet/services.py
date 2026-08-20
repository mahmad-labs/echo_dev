from echo.common.services import DomainService

from .models import SearchQuery, WebPage, DomainReputation, WebsiteMonitor, CrawledPage, ApiConnection, DomainPolicy

class SearchService(DomainService):
    model = SearchQuery

class FetchService(DomainService):
    model = WebPage

class ExtractionService(DomainService):
    model = WebPage

class ValidationService(DomainService):
    model = DomainReputation

class CacheService(DomainService):
    model = WebPage

class MonitoringService(DomainService):
    model = WebsiteMonitor

class AnalyticsService(DomainService):
    model = SearchQuery

class CrawlerService(DomainService):
    model = CrawledPage

class ApiService(DomainService):
    model = ApiConnection

class SecurityService(DomainService):
    model = DomainPolicy
