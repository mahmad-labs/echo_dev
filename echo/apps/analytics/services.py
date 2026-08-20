from echo.common.services import DomainService

from .models import AnalyticsEvent, MetricDefinition, UsageAggregate, Report, DashboardSnapshot

class EventService(DomainService):
    model = AnalyticsEvent

class MetricService(DomainService):
    model = MetricDefinition

class AggregationService(DomainService):
    model = UsageAggregate

class ReportingService(DomainService):
    model = Report

class RetentionService(DomainService):
    model = DashboardSnapshot
