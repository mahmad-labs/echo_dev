from echo.common.services import DomainService

from .models import DashboardLayout, DashboardWidget, RecentActivity, FavoriteItem

class DashboardService(DomainService):
    model = DashboardLayout

class WidgetService(DomainService):
    model = DashboardWidget

class AnalyticsService(DomainService):
    model = RecentActivity

class SearchService(DomainService):
    model = FavoriteItem

class LayoutService(DomainService):
    model = DashboardLayout
