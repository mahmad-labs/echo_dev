from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class SearchProvider(DomainModel):
    provider_type = models.CharField(max_length=255, blank=True, db_index=False)
    api_endpoint = models.URLField(max_length=2048, blank=True)
    api_key_reference = models.UUIDField(null=True, blank=True, db_index=True)
    priority = models.BigIntegerField(default=0)
    enabled = models.BooleanField(default=False)
    rate_limit = models.BigIntegerField(default=0)
    timeout = models.BigIntegerField(default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'Search Provider'
        verbose_name_plural = 'Search Provider records'


class SearchQuery(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='internet_search_query_user')
    query = models.TextField(blank=True)
    search_type = models.CharField(max_length=255, blank=True, db_index=False)
    provider = models.CharField(max_length=255, blank=True, db_index=False)
    language = models.CharField(max_length=255, blank=True, db_index=False)
    region = models.CharField(max_length=255, blank=True, db_index=False)
    safe_search = models.CharField(max_length=255, blank=True, db_index=False)
    requested_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Search Query'
        verbose_name_plural = 'Search Query records'


class SearchResult(DomainModel):
    query = models.TextField(blank=True)
    url = models.URLField(max_length=2048, blank=True)
    snippet = models.TextField(blank=True)
    domain = models.CharField(max_length=255, blank=True, db_index=False)
    rank = models.BigIntegerField(default=0)
    relevance_score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    retrieved_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Search Result'
        verbose_name_plural = 'Search Result records'


class WebPage(DomainModel):
    url = models.URLField(max_length=2048, blank=True)
    status_code = models.TextField(blank=True)
    content_type = models.TextField(blank=True)
    language = models.CharField(max_length=255, blank=True, db_index=False)
    metadata = models.JSONField(default=dict, blank=True)
    content_hash = models.TextField(blank=True)
    last_fetched = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Web Page'
        verbose_name_plural = 'Web Page records'


class RSSFeed(DomainModel):
    url = models.URLField(max_length=2048, blank=True)
    category = models.CharField(max_length=255, blank=True, db_index=True)
    enabled = models.BooleanField(default=False)
    last_checked = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'R S S Feed'
        verbose_name_plural = 'R S S Feed records'


class WebsiteMonitor(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='internet_website_monitor_user')
    url = models.URLField(max_length=2048, blank=True)
    check_interval = models.CharField(max_length=255, blank=True, db_index=False)
    last_changed = models.DateTimeField(null=True, blank=True, db_index=True)
    notification_enabled = models.BooleanField(default=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Website Monitor'
        verbose_name_plural = 'Website Monitor records'


class DomainReputation(DomainModel):
    domain = models.CharField(max_length=255, blank=True, db_index=False)
    trust_score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    category = models.CharField(max_length=255, blank=True, db_index=True)
    blacklisted = models.BooleanField(default=False)
    last_updated = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Domain Reputation'
        verbose_name_plural = 'Domain Reputation records'


class Website(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Website'
        verbose_name_plural = 'Website records'


class CrawledPage(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Crawled Page'
        verbose_name_plural = 'Crawled Page records'


class ApiConnection(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Api Connection'
        verbose_name_plural = 'Api Connection records'


class Download(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Download'
        verbose_name_plural = 'Download records'


class DomainPolicy(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Domain Policy'
        verbose_name_plural = 'Domain Policy records'



class BrowserSession(DomainModel):
    """Durable owner-scoped state for a controlled browser instance."""

    engine = models.CharField(max_length=32, default="chrome", db_index=True)
    headless = models.BooleanField(default=False)
    current_url = models.URLField(max_length=4096, blank=True)
    current_title = models.CharField(max_length=512, blank=True)
    active_tab_handle = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_activity_at = models.DateTimeField(null=True, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Browser Session"
        verbose_name_plural = "Browser Sessions"
        indexes = [models.Index(fields=("owner", "status", "-last_activity_at"), name="browser_session_owner_state")]


class BrowserObservation(DomainModel):
    """Structured snapshot used by the computer-use observe/verify loop."""

    session = models.ForeignKey(BrowserSession, on_delete=models.CASCADE, related_name="observations")
    sequence = models.PositiveIntegerField(default=0)
    url = models.URLField(max_length=4096, blank=True)
    page_title = models.CharField(max_length=512, blank=True)
    visible_text = models.TextField(blank=True)
    dom = models.JSONField(default=dict, blank=True)
    accessibility_tree = models.JSONField(default=dict, blank=True)
    viewport = models.JSONField(default=dict, blank=True)
    media = models.JSONField(default=list, blank=True)
    screenshot = models.FileField(upload_to="browser/observations/%Y/%m/%d/", blank=True)
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    observed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Browser Observation"
        verbose_name_plural = "Browser Observations"
        indexes = [models.Index(fields=("session", "-sequence"), name="browser_observation_seq")]


class BrowserAction(DomainModel):
    """One tool action with pre/post observations and verification evidence."""

    session = models.ForeignKey(BrowserSession, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=80, db_index=True)
    target = models.TextField(blank=True)
    arguments = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    pre_observation = models.ForeignKey(BrowserObservation, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions_before")
    post_observation = models.ForeignKey(BrowserObservation, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions_after")
    verified = models.BooleanField(default=False, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    error_message = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Browser Action"
        verbose_name_plural = "Browser Actions"
        indexes = [models.Index(fields=("session", "-created_at"), name="browser_action_recent")]


class ComputerUseOperation(DomainModel):
    """Cancellable multi-step computer-use job with safe execution status."""

    session = models.ForeignKey(BrowserSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="operations")
    conversation = models.ForeignKey("chat.Conversation", on_delete=models.SET_NULL, null=True, blank=True, related_name="computer_use_operations")
    request_text = models.TextField()
    plan = models.JSONField(default=list, blank=True)
    result = models.JSONField(default=dict, blank=True)
    current_step = models.PositiveIntegerField(default=0)
    progress = models.PositiveSmallIntegerField(default=0)
    current_operation = models.CharField(max_length=255, blank=True)
    current_tool = models.CharField(max_length=120, blank=True)
    cancellable = models.BooleanField(default=True)
    cancel_requested = models.BooleanField(default=False, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    error_message = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Computer Use Operation"
        verbose_name_plural = "Computer Use Operations"
        indexes = [models.Index(fields=("owner", "status", "-updated_at"), name="computer_use_owner_state")]


class MediaUnderstanding(DomainModel):
    """Evidence-backed temporary understanding of media in a browser session."""

    session = models.ForeignKey(BrowserSession, on_delete=models.CASCADE, related_name="media_understandings")
    operation = models.ForeignKey(ComputerUseOperation, on_delete=models.SET_NULL, null=True, blank=True, related_name="media_understandings")
    source_url = models.URLField(max_length=4096, blank=True)
    media_metadata = models.JSONField(default=dict, blank=True)
    transcript = models.TextField(blank=True)
    visual_notes = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    evidence = models.JSONField(default=list, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Media Understanding"
        verbose_name_plural = "Media Understandings"
        indexes = [models.Index(fields=("owner", "-processed_at"), name="media_understanding_recent")]


class ComputerSession(DomainModel):
    """Durable session for an authorized local/remote desktop environment."""

    environment = models.CharField(max_length=96, default="desktop.local", db_index=True)
    display_name = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_activity_at = models.DateTimeField(null=True, blank=True, db_index=True)
    active_window = models.JSONField(default=dict, blank=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Computer Session"
        verbose_name_plural = "Computer Sessions"
        indexes = [models.Index(fields=("owner", "status", "-last_activity_at"), name="computer_session_owner_idx")]


class ComputerObservation(DomainModel):
    """Screen/UI observation shared with Browser and Computer agents."""

    session = models.ForeignKey(ComputerSession, on_delete=models.CASCADE, related_name="observations")
    sequence = models.PositiveIntegerField(default=0)
    screenshot = models.FileField(upload_to="computer/observations/%Y/%m/%d/", blank=True)
    ocr_text = models.TextField(blank=True)
    vision = models.JSONField(default=dict, blank=True)
    ui_tree = models.JSONField(default=dict, blank=True)
    window_info = models.JSONField(default=dict, blank=True)
    cursor = models.JSONField(default=dict, blank=True)
    viewport = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    observed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Computer Observation"
        verbose_name_plural = "Computer Observations"
        indexes = [models.Index(fields=("session", "-sequence"), name="computer_observation_seq_idx")]


class ComputerAction(DomainModel):
    """Desktop input action with before/after evidence and verification result."""

    session = models.ForeignKey(ComputerSession, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=80, db_index=True)
    target = models.JSONField(default=dict, blank=True)
    arguments = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    pre_observation = models.ForeignKey(ComputerObservation, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions_before")
    post_observation = models.ForeignKey(ComputerObservation, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions_after")
    verified = models.BooleanField(default=False, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    error_message = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Computer Action"
        verbose_name_plural = "Computer Actions"
        indexes = [models.Index(fields=("session", "-created_at"), name="computer_action_recent_idx")]
