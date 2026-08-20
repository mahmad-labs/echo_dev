from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from echo.common.models import DomainModel


class VoiceProfile(DomainModel):
    """Per-user speech preferences and provider selection.

    Provider values are identifiers, not implementation details. The provider registry
    resolves them at runtime so Echo can add or replace speech services without
    changing the persistence model or the client contract.
    """

    category = models.CharField(max_length=100, blank=True, default="default", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    language = models.CharField(max_length=32, default="en-US")
    speech_to_text_provider = models.CharField(max_length=64, default="browser")
    text_to_speech_provider = models.CharField(max_length=64, default="browser")
    voice_name = models.CharField(max_length=160, blank=True)
    speaking_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0.5), MaxValueValidator(2)],
    )
    pitch = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(2)],
    )
    volume = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    auto_speak = models.BooleanField(default=True)
    continuous_listening = models.BooleanField(default=True)
    barge_in_enabled = models.BooleanField(default=True)
    save_audio = models.BooleanField(default=False)
    memory_requires_approval = models.BooleanField(default=True)
    speaker_identification_enabled = models.BooleanField(default=False)
    reject_unrecognized_speakers = models.BooleanField(default=True)
    voice_history_enabled = models.BooleanField(default=True)
    transcript_retention_days = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(0), MaxValueValidator(365)])
    active_session_minutes = models.PositiveSmallIntegerField(default=60, validators=[MinValueValidator(1), MaxValueValidator(60)])
    is_default = models.BooleanField(default=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Voice Profile"
        verbose_name_plural = "Voice Profiles"
        constraints = [
            models.UniqueConstraint(
                fields=("owner",),
                condition=models.Q(is_default=True),
                name="voice_one_default_profile_per_owner",
            )
        ]


class VoiceSession(DomainModel):
    class State(models.TextChoices):
        STARTING = "starting", "Starting"
        GREETING = "greeting", "Greeting"
        DISABLED = "disabled", "Disabled"
        WAKE_WORD_LISTENING = "wake_word_listening", "Wake-word listening"
        ACTIVE_SESSION = "active_session", "Active session"
        PROCESSING = "processing", "Processing"
        SPEAKING = "speaking", "Speaking"
        SLEEPING = "sleeping", "Sleeping"
        SHUTDOWN = "shutdown", "Shutdown"
        ERROR = "error", "Error"

    category = models.CharField(max_length=100, blank=True, default="conversation", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    conversation = models.ForeignKey(
        "chat.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voice_sessions",
    )
    profile = models.ForeignKey(
        VoiceProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    class Mode(models.TextChoices):
        WAKE_WORD = "wake_word", "Wake-word mode"
        ACTIVE = "active", "Active voice session"

    state = models.CharField(max_length=32, choices=State.choices, default=State.STARTING, db_index=True)
    mode = models.CharField(max_length=24, choices=Mode.choices, default=Mode.WAKE_WORD, db_index=True)
    active_started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    active_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    wake_word = models.CharField(max_length=80, default="Echo")
    speaker_state = models.CharField(max_length=32, default="not_enrolled", db_index=True)
    client_session_id = models.CharField(max_length=120, blank=True, db_index=True)
    input_mode = models.CharField(max_length=32, default="voice")
    language = models.CharField(max_length=32, default="en-US")
    stt_provider = models.CharField(max_length=64, default="browser")
    tts_provider = models.CharField(max_length=64, default="browser")
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_activity_at = models.DateTimeField(null=True, blank=True, db_index=True)
    greeted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    shutdown_at = models.DateTimeField(null=True, blank=True, db_index=True)
    turn_count = models.PositiveIntegerField(default=0)
    last_error_code = models.CharField(max_length=80, blank=True)
    last_error_message = models.TextField(blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Voice Session"
        verbose_name_plural = "Voice Sessions"
        indexes = [
            models.Index(fields=("owner", "state", "-last_activity_at"), name="voice_session_owner_state"),
        ]


class AudioAsset(DomainModel):
    class Direction(models.TextChoices):
        INPUT = "input", "Input"
        OUTPUT = "output", "Output"

    category = models.CharField(max_length=100, blank=True, default="speech", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    session = models.ForeignKey(
        VoiceSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audio_assets",
    )
    file = models.FileField(upload_to="voice/%Y/%m/%d/", blank=True)
    direction = models.CharField(max_length=16, choices=Direction.choices, default=Direction.INPUT)
    provider = models.CharField(max_length=64, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    format_name = models.CharField(max_length=24, blank=True)
    byte_size = models.PositiveBigIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Audio Asset"
        verbose_name_plural = "Audio Assets"


class SpeechTranscript(DomainModel):
    class MemoryStatus(models.TextChoices):
        NOT_CANDIDATE = "not_candidate", "Not a candidate"
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    category = models.CharField(max_length=100, blank=True, default="utterance", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    session = models.ForeignKey(
        VoiceSession,
        on_delete=models.CASCADE,
        related_name="transcripts",
        null=True,
        blank=True,
    )
    conversation = models.ForeignKey(
        "chat.Conversation",
        on_delete=models.SET_NULL,
        related_name="voice_transcripts",
        null=True,
        blank=True,
    )
    message = models.ForeignKey(
        "chat.Message",
        on_delete=models.SET_NULL,
        related_name="voice_transcripts",
        null=True,
        blank=True,
    )
    audio_asset = models.ForeignKey(
        AudioAsset,
        on_delete=models.SET_NULL,
        related_name="transcripts",
        null=True,
        blank=True,
    )
    sequence = models.PositiveIntegerField(default=0)
    text = models.TextField()
    language = models.CharField(max_length=32, default="en-US")
    provider = models.CharField(max_length=64, default="browser")
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    is_final = models.BooleanField(default=True)
    intent = models.CharField(max_length=80, blank=True, db_index=True)
    command_route = models.CharField(max_length=80, blank=True, db_index=True)
    command_result = models.JSONField(default=dict, blank=True)
    memory_status = models.CharField(
        max_length=24,
        choices=MemoryStatus.choices,
        default=MemoryStatus.NOT_CANDIDATE,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Speech Transcript"
        verbose_name_plural = "Speech Transcripts"
        indexes = [models.Index(fields=("owner", "-created_at"), name="voice_transcript_owner_time")]


class SpeechSynthesis(DomainModel):
    category = models.CharField(max_length=100, blank=True, default="response", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    session = models.ForeignKey(
        VoiceSession,
        on_delete=models.CASCADE,
        related_name="syntheses",
        null=True,
        blank=True,
    )
    message = models.ForeignKey(
        "chat.Message",
        on_delete=models.SET_NULL,
        related_name="voice_syntheses",
        null=True,
        blank=True,
    )
    audio_asset = models.ForeignKey(
        AudioAsset,
        on_delete=models.SET_NULL,
        related_name="syntheses",
        null=True,
        blank=True,
    )
    text = models.TextField()
    provider = models.CharField(max_length=64, default="browser")
    voice_name = models.CharField(max_length=160, blank=True)
    language = models.CharField(max_length=32, default="en-US")
    format_name = models.CharField(max_length=24, default="mp3")
    duration_ms = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Speech Synthesis"
        verbose_name_plural = "Speech Syntheses"


class WakeWordConfiguration(DomainModel):
    category = models.CharField(max_length=100, blank=True, default="wake_word", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    phrase = models.CharField(max_length=80, default="Echo")
    enabled = models.BooleanField(default=True)
    sensitivity = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0.7,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    require_foreground = models.BooleanField(default=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Wake Word Configuration"
        verbose_name_plural = "Wake Word Configurations"


class VoiceEvent(DomainModel):
    """Immutable, user-visible state history for observability and troubleshooting."""

    session = models.ForeignKey(VoiceSession, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=64, db_index=True)
    from_state = models.CharField(max_length=32, blank=True)
    to_state = models.CharField(max_length=32, blank=True)
    detail = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Voice Event"
        verbose_name_plural = "Voice Events"
        indexes = [models.Index(fields=("session", "created_at"), name="voice_event_session_time")]


class SpeakerProfile(DomainModel):
    """Probabilistic speaker representation for the authenticated Echo user.

    The profile stores only a derived feature centroid by default. It is an
    additional command-filtering signal and never replaces approval/authentication
    for sensitive operations.
    """

    category = models.CharField(max_length=100, blank=True, default="speaker", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True, db_index=True)
    enrolled = models.BooleanField(default=False, db_index=True)
    embedding = models.JSONField(default=list, blank=True)
    sample_count = models.PositiveSmallIntegerField(default=0)
    threshold = models.DecimalField(max_digits=4, decimal_places=3, default=0.820, validators=[MinValueValidator(0), MaxValueValidator(1)])
    enrolled_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Speaker Profile"
        verbose_name_plural = "Speaker Profiles"
        constraints = [models.UniqueConstraint(fields=("owner",), name="voice_one_speaker_profile_per_owner")]


class SpeakerEnrollmentSample(DomainModel):
    category = models.CharField(max_length=100, blank=True, default="speaker_sample", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    profile = models.ForeignKey(SpeakerProfile, on_delete=models.CASCADE, related_name="samples")
    embedding = models.JSONField(default=list, blank=True)
    quality_score = models.DecimalField(max_digits=5, decimal_places=4, default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta(DomainModel.Meta):
        verbose_name = "Speaker Enrollment Sample"
        verbose_name_plural = "Speaker Enrollment Samples"


class SpeakerVerificationEvent(DomainModel):
    category = models.CharField(max_length=100, blank=True, default="speaker_verification", db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    profile = models.ForeignKey(SpeakerProfile, on_delete=models.CASCADE, related_name="verification_events")
    session = models.ForeignKey(VoiceSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="speaker_events")
    transcript = models.ForeignKey(SpeechTranscript, on_delete=models.SET_NULL, null=True, blank=True, related_name="speaker_events")
    decision = models.CharField(max_length=24, default="unknown", db_index=True)
    score = models.DecimalField(max_digits=5, decimal_places=4, default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    threshold = models.DecimalField(max_digits=5, decimal_places=4, default=0.82, validators=[MinValueValidator(0), MaxValueValidator(1)])

    class Meta(DomainModel.Meta):
        verbose_name = "Speaker Verification Event"
        verbose_name_plural = "Speaker Verification Events"
        indexes = [models.Index(fields=("owner", "-created_at"), name="voice_speaker_verify_time")]
