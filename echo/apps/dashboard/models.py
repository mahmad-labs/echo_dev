from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class DashboardLayout(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_dashboard_layout_user')
    is_default = models.BooleanField(default=False)
    columns = models.BigIntegerField(default=0)
    theme = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Dashboard Layout'
        verbose_name_plural = 'Dashboard Layout records'


class DashboardWidget(DomainModel):
    layout = models.CharField(max_length=255, blank=True, db_index=False)
    widget_type = models.CharField(max_length=255, blank=True, db_index=False)
    position_x = models.BigIntegerField(default=0)
    position_y = models.BigIntegerField(default=0)
    width = models.BigIntegerField(default=0)
    height = models.BigIntegerField(default=0)
    collapsed = models.CharField(max_length=255, blank=True, db_index=False)
    visible = models.CharField(max_length=255, blank=True, db_index=False)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Dashboard Widget'
        verbose_name_plural = 'Dashboard Widget records'


class QuickAction(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_quick_action_user')
    icon = models.CharField(max_length=255, blank=True, db_index=False)
    action = models.CharField(max_length=255, blank=True, db_index=False)
    url = models.URLField(max_length=2048, blank=True)
    order = models.BigIntegerField(default=0)
    enabled = models.BooleanField(default=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Quick Action'
        verbose_name_plural = 'Quick Action records'


class FavoriteItem(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_favorite_item_user')
    item_type = models.CharField(max_length=255, blank=True, db_index=False)
    item_id = models.UUIDField(null=True, blank=True, db_index=True)
    icon = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Favorite Item'
        verbose_name_plural = 'Favorite Item records'


class RecentActivity(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_recent_activity_user')
    activity_type = models.CharField(max_length=255, blank=True, db_index=False)
    module = models.CharField(max_length=255, blank=True, db_index=False)
    reference_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Recent Activity'
        verbose_name_plural = 'Recent Activity records'


class DashboardNotification(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_dashboard_notification_user')
    message = models.TextField(blank=True)
    priority = models.BigIntegerField(default=0)
    is_read = models.BooleanField(default=False)
    action_url = models.URLField(max_length=2048, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Dashboard Notification'
        verbose_name_plural = 'Dashboard Notification records'


class WidgetPreference(DomainModel):
    widget = models.CharField(max_length=255, blank=True, db_index=False)
    key = models.CharField(max_length=255, blank=True, db_index=True)
    value = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Widget Preference'
        verbose_name_plural = 'Widget Preference records'

