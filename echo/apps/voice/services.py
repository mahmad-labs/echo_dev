from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.module_loading import import_string
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from echo.apps.chat.models import Conversation, Message
from echo.apps.agent_manager.orchestration import AgentManagerOrchestrator
from echo.apps.memory.models import Memory

from .models import (
    AudioAsset,
    SpeechSynthesis,
    SpeechTranscript,
    VoiceEvent,
    VoiceProfile,
    VoiceSession,
    WakeWordConfiguration,
    SpeakerProfile,
    SpeakerEnrollmentSample,
    SpeakerVerificationEvent,
)
from .providers import SynthesisResult, TranscriptionResult, VoiceProviderError, VoiceProviderRegistry


class VoiceSessionError(RuntimeError):
    pass


class VoiceResourceNotFound(VoiceSessionError):
    pass


class VoiceWakeWordRequired(VoiceSessionError):
    """Raised for ordinary speech heard while Echo is intentionally in wake-word mode."""

    def __init__(self, session: VoiceSession):
        super().__init__(f"Say {session.wake_word or 'Echo'} to begin an active voice session.")
        self.session = session


class VoiceWakeActivated(VoiceSessionError):
    """Control-flow signal for a wake-word-only utterance.

    Wake activation is a lifecycle event, not a conversational command. Keeping it
    out of Agent Manager avoids an unnecessary LLM/tool turn for a bare "Echo".
    """

    def __init__(self, session: VoiceSession):
        super().__init__("Active voice session started.")
        self.session = session


class VoiceSpeakerRejected(VoiceSessionError):
    """Raised when probabilistic speaker verification rejects a command."""

    def __init__(self, session: VoiceSession, score: float | None = None):
        super().__init__("I didn't recognize the authorized speaker.")
        self.session = session
        self.score = score


@dataclass(frozen=True)
class VoiceTurnResult:
    session: VoiceSession
    transcript: SpeechTranscript
    response: Message
    content: str
    route: str
    should_speak: bool
    memory_candidate: bool
    command_data: dict[str, Any]


class VoiceProfileService:
    EDITABLE_FIELDS = {
        "language",
        "speech_to_text_provider",
        "text_to_speech_provider",
        "voice_name",
        "speaking_rate",
        "pitch",
        "volume",
        "auto_speak",
        "continuous_listening",
        "barge_in_enabled",
        "save_audio",
        "memory_requires_approval",
        "speaker_identification_enabled",
        "reject_unrecognized_speakers",
        "voice_history_enabled",
        "transcript_retention_days",
        "active_session_minutes",
    }

    @classmethod
    def default_for(cls, user) -> VoiceProfile:
        profile = VoiceProfile.objects.filter(owner=user, is_default=True).first()
        if profile:
            return profile
        try:
            with transaction.atomic():
                return VoiceProfile.objects.create(
                    owner=user,
                    name="Default voice",
                    title="Default voice",
                    status="active",
                    category="default",
                    is_default=True,
                    active_session_minutes=min(60, int(getattr(settings, "VOICE_ACTIVE_SESSION_MINUTES", 60))),
                )
        except IntegrityError:
            # A concurrent request may have created the unique default first.
            return VoiceProfile.objects.get(owner=user, is_default=True)

    @classmethod
    @transaction.atomic
    def update(cls, user, values: dict[str, Any]) -> VoiceProfile:
        profile = cls.default_for(user)
        for field_name in cls.EDITABLE_FIELDS:
            if field_name in values:
                setattr(profile, field_name, values[field_name])
        profile.full_clean()
        profile.save()
        return profile


class VoiceSessionService:
    """Authoritative server-side lifecycle for Echo Voice.

    ``VoiceSession.state`` is the single source of truth. The legacy ``mode`` column is
    retained only as a compatibility mirror for older clients/data and is always
    derived from lifecycle transitions here.
    """

    GREETING_TEXT = "Hello. I'm Echo. I'm ready when you are."
    LEGACY_STATE_ALIASES = {
        "idle": VoiceSession.State.WAKE_WORD_LISTENING,
        "listening": VoiceSession.State.ACTIVE_SESSION,
        "waiting": VoiceSession.State.ACTIVE_SESSION,
        "thinking": VoiceSession.State.PROCESSING,
        "executing": VoiceSession.State.PROCESSING,
        "paused": VoiceSession.State.SLEEPING,
        "stopped": VoiceSession.State.WAKE_WORD_LISTENING,
        "ended": VoiceSession.State.SHUTDOWN,
    }
    ALLOWED_TRANSITIONS = {
        VoiceSession.State.STARTING: {VoiceSession.State.GREETING, VoiceSession.State.WAKE_WORD_LISTENING, VoiceSession.State.ACTIVE_SESSION, VoiceSession.State.ERROR, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.GREETING: {VoiceSession.State.WAKE_WORD_LISTENING, VoiceSession.State.ACTIVE_SESSION, VoiceSession.State.SPEAKING, VoiceSession.State.ERROR, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.DISABLED: {VoiceSession.State.WAKE_WORD_LISTENING, VoiceSession.State.ACTIVE_SESSION, VoiceSession.State.ERROR, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.WAKE_WORD_LISTENING: {VoiceSession.State.ACTIVE_SESSION, VoiceSession.State.PROCESSING, VoiceSession.State.SPEAKING, VoiceSession.State.SLEEPING, VoiceSession.State.ERROR, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.ACTIVE_SESSION: {VoiceSession.State.PROCESSING, VoiceSession.State.SPEAKING, VoiceSession.State.WAKE_WORD_LISTENING, VoiceSession.State.SLEEPING, VoiceSession.State.ERROR, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.PROCESSING: {VoiceSession.State.ACTIVE_SESSION, VoiceSession.State.WAKE_WORD_LISTENING, VoiceSession.State.SPEAKING, VoiceSession.State.ERROR, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.SPEAKING: {VoiceSession.State.ACTIVE_SESSION, VoiceSession.State.WAKE_WORD_LISTENING, VoiceSession.State.SLEEPING, VoiceSession.State.ERROR, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.SLEEPING: {VoiceSession.State.WAKE_WORD_LISTENING, VoiceSession.State.ACTIVE_SESSION, VoiceSession.State.ERROR, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.ERROR: {VoiceSession.State.WAKE_WORD_LISTENING, VoiceSession.State.ACTIVE_SESSION, VoiceSession.State.SHUTDOWN},
        VoiceSession.State.SHUTDOWN: set(),
    }

    @staticmethod
    def owned(user):
        queryset = VoiceSession.objects.all()
        return queryset if user.is_staff else queryset.filter(owner=user)

    @classmethod
    def get_owned(cls, user, session_id) -> VoiceSession:
        try:
            session = cls.owned(user).select_related("conversation", "profile").get(pk=session_id)
        except (VoiceSession.DoesNotExist, ValueError, TypeError) as exc:
            raise VoiceResourceNotFound("Voice session was not found.") from exc
        return session

    @classmethod
    def _event(cls, session: VoiceSession, event_type: str, *, from_state: str = "", to_state: str = "", detail: str = "", payload: dict[str, Any] | None = None) -> VoiceEvent:
        return VoiceEvent.objects.create(
            owner=session.owner, session=session, name=event_type, title=event_type.replace("_", " ").title(),
            description=detail, status="completed", event_type=event_type, from_state=from_state,
            to_state=to_state, detail=detail, payload=payload or {},
        )

    @classmethod
    def _active_timeout(cls, session: VoiceSession) -> timedelta:
        profile = session.profile or VoiceProfileService.default_for(session.owner)
        minutes = min(60, max(1, int(profile.active_session_minutes or getattr(settings, "VOICE_ACTIVE_SESSION_MINUTES", 60))))
        return timedelta(minutes=minutes)

    @staticmethod
    def _persist_shutdown_preference(profile: VoiceProfile, shutdown: bool) -> None:
        configuration = dict(profile.configuration or {})
        if shutdown:
            configuration["voice_shutdown"] = True
        else:
            configuration.pop("voice_shutdown", None)
        if configuration != (profile.configuration or {}):
            profile.configuration = configuration
            profile.save(update_fields=["configuration", "updated_at"])

    @classmethod
    @transaction.atomic
    def start(cls, user, *, conversation_id: str | None = None, client_session_id: str = "", language: str = "", input_mode: str = "voice") -> VoiceSession:
        profile = VoiceProfileService.default_for(user)
        # Creating a new session is an explicit restart (UI Activate or API start), so
        # it is the only operation that clears a previously persisted Shutdown choice.
        cls._persist_shutdown_preference(profile, False)
        conversation = None
        if conversation_id:
            conversation_query = Conversation.objects.filter(pk=conversation_id)
            if not user.is_staff:
                conversation_query = conversation_query.filter(owner=user)
            conversation = conversation_query.first()
            if not conversation:
                raise VoiceSessionError("Conversation was not found.")
        if not conversation:
            now_local = timezone.localtime()
            conversation = Conversation.objects.create(
                owner=user, user=user, name=f"Voice conversation {now_local:%Y-%m-%d %H:%M}",
                title=f"Voice conversation · {now_local:%b %d, %H:%M}", description="A conversation started through Echo Voice.",
                status="active", conversation_type="voice", last_message_at=timezone.now(), data={"origin": "voice"},
            )
        now = timezone.now()
        session = VoiceSession.objects.create(
            owner=user, name=f"Voice session {now.isoformat()}", title=conversation.title or "Voice conversation",
            description="Live Echo voice session.", status="active", category="conversation", conversation=conversation,
            profile=profile, state=VoiceSession.State.STARTING, mode=VoiceSession.Mode.WAKE_WORD, wake_word="Echo",
            speaker_state="disabled" if not profile.speaker_identification_enabled else "not_enrolled",
            client_session_id=str(client_session_id or "")[:120], input_mode=input_mode if input_mode in {"voice", "text", "mixed"} else "voice",
            language=(language or profile.language)[:32], stt_provider=profile.speech_to_text_provider, tts_provider=profile.text_to_speech_provider,
            started_at=now, last_activity_at=now, configuration={"browser_capabilities": {}, "permission": "unknown", "microphone_enabled": False},
        )
        WakeWordConfiguration.objects.update_or_create(
            owner=user, name="default", defaults={"title": "Echo wake word", "status": "active", "category": "wake_word", "phrase": "Echo", "enabled": True},
        )
        cls._event(session, "session_started", to_state=session.state, detail="Voice subsystem is starting.")
        return session

    @classmethod
    @transaction.atomic
    def current_or_start(cls, user, *, client_session_id: str = "", input_mode: str = "mixed") -> VoiceSession:
        profile = VoiceProfileService.default_for(user)
        if bool((profile.configuration or {}).get("voice_shutdown")):
            shutdown_session = cls.owned(user).filter(state=VoiceSession.State.SHUTDOWN).order_by("-shutdown_at", "-updated_at").first()
            if shutdown_session:
                return shutdown_session
        session = cls.owned(user).exclude(state=VoiceSession.State.SHUTDOWN).exclude(status="completed").order_by("-updated_at").first()
        if not session:
            session = cls.start(user, client_session_id=client_session_id, input_mode=input_mode)
        session = cls.enforce_active_window(session)
        if session.state == VoiceSession.State.STARTING:
            previous = session.state
            session.state = VoiceSession.State.GREETING
            session.mode = VoiceSession.Mode.WAKE_WORD
            session.save(update_fields=["state", "mode", "updated_at"])
            cls._event(session, "greeting_ready", from_state=previous, to_state=session.state, detail=cls.GREETING_TEXT)
        return session

    @classmethod
    @transaction.atomic
    def mark_greeted(cls, user, session_id) -> VoiceSession:
        session = cls.get_owned(user, session_id)
        if session.state == VoiceSession.State.SHUTDOWN:
            raise VoiceSessionError("Voice is shut down.")
        previous = session.state
        session.greeted_at = session.greeted_at or timezone.now()
        if session.state in {VoiceSession.State.STARTING, VoiceSession.State.GREETING}:
            session.state = VoiceSession.State.WAKE_WORD_LISTENING
            session.mode = VoiceSession.Mode.WAKE_WORD
        session.save(update_fields=["greeted_at", "state", "mode", "updated_at"])
        cls._event(session, "greeting_completed", from_state=previous, to_state=session.state, detail="Startup greeting completed.")
        return session

    @classmethod
    @transaction.atomic
    def transition(cls, user, session_id, state: str, *, detail: str = "", error_code: str = "", browser_capabilities: dict[str, Any] | None = None, permission: str = "", force: bool = False) -> VoiceSession:
        session = cls.get_owned(user, session_id)
        raw = str(state or "").strip().casefold()
        if raw in cls.LEGACY_STATE_ALIASES:
            target = cls.LEGACY_STATE_ALIASES[raw]
            if raw in {"listening", "waiting"} and session.mode != VoiceSession.Mode.ACTIVE:
                target = VoiceSession.State.WAKE_WORD_LISTENING
        else:
            try:
                target = VoiceSession.State(raw)
            except ValueError as exc:
                raise VoiceSessionError("Unknown voice state.") from exc
        current = session.state
        if target != current and not force and target not in cls.ALLOWED_TRANSITIONS.get(current, set()):
            raise VoiceSessionError(f"Voice state cannot move from {current} to {target}.")
        configuration = dict(session.configuration or {})
        if browser_capabilities is not None:
            configuration["browser_capabilities"] = browser_capabilities
        if permission:
            if permission not in {"unknown", "prompt", "granted", "denied", "unavailable"}:
                raise VoiceSessionError("Unknown microphone permission state.")
            configuration["permission"] = permission
            configuration["microphone_enabled"] = permission == "granted" and target != VoiceSession.State.SHUTDOWN
        session.state = target
        session.configuration = configuration
        if target == VoiceSession.State.ACTIVE_SESSION:
            session.mode = VoiceSession.Mode.ACTIVE
            if not session.active_expires_at:
                session.active_started_at = session.active_started_at or timezone.now()
                session.active_expires_at = timezone.now() + cls._active_timeout(session)
        elif target == VoiceSession.State.WAKE_WORD_LISTENING:
            session.mode = VoiceSession.Mode.WAKE_WORD
            session.active_started_at = None
            session.active_expires_at = None
        if target == VoiceSession.State.ERROR:
            session.last_error_code = str(error_code or "voice_error")[:80]
            session.last_error_message = detail[:4000]
        elif target != VoiceSession.State.SHUTDOWN:
            session.last_error_code = ""
            session.last_error_message = ""
        if target == VoiceSession.State.SHUTDOWN:
            now = timezone.now()
            session.mode = VoiceSession.Mode.WAKE_WORD
            session.active_started_at = None
            session.active_expires_at = None
            session.shutdown_at = now
            session.ended_at = now
            session.status = "completed"
            configuration["microphone_enabled"] = False
            session.configuration = configuration
        session.save()
        if target != current or detail or permission:
            cls._event(session, "state_changed", from_state=current, to_state=target, detail=detail, payload={"permission": permission} if permission else {})
        return session

    @classmethod
    @transaction.atomic
    def touch_activity(cls, session: VoiceSession, *, detail: str = "User interaction") -> VoiceSession:
        now = timezone.now()
        session.last_activity_at = now
        if session.mode == VoiceSession.Mode.ACTIVE and session.state != VoiceSession.State.SHUTDOWN:
            session.active_expires_at = now + cls._active_timeout(session)
        session.save(update_fields=["last_activity_at", "active_expires_at", "updated_at"])
        cls._event(session, "user_activity", to_state=session.state, detail=detail)
        return session

    @classmethod
    def recover_after_rejected_input(cls, user, session_id, *, detail: str = "Voice input was ignored safely.") -> VoiceSession:
        """Return a rejected acoustic turn to the capture state implied by session mode."""
        session = cls.get_owned(user, session_id)
        if session.state == VoiceSession.State.SHUTDOWN:
            return session
        target = VoiceSession.State.ACTIVE_SESSION if session.mode == VoiceSession.Mode.ACTIVE else VoiceSession.State.WAKE_WORD_LISTENING
        return cls.transition(user, session.pk, target, detail=detail, force=True)

    @classmethod
    @transaction.atomic
    def enforce_active_window(cls, session: VoiceSession) -> VoiceSession:
        if session.mode == VoiceSession.Mode.ACTIVE and session.active_expires_at and timezone.now() >= session.active_expires_at:
            previous = session.state
            session.mode = VoiceSession.Mode.WAKE_WORD
            session.active_started_at = None
            session.active_expires_at = None
            session.state = VoiceSession.State.WAKE_WORD_LISTENING
            session.save(update_fields=["mode", "active_started_at", "active_expires_at", "state", "updated_at"])
            cls._event(session, "active_session_inactivity_timeout", from_state=previous, to_state=session.state, detail=f"Active voice session timed out after inactivity. Say {session.wake_word or 'Echo'} to reactivate.")
        return session

    @classmethod
    @transaction.atomic
    def activate(cls, user, session_id, *, speaker_embedding=None, require_speaker: bool = False) -> VoiceSession:
        session = cls.get_owned(user, session_id)
        if session.state == VoiceSession.State.SHUTDOWN:
            raise VoiceSessionError("Voice is shut down. Start a new voice runtime first.")
        profile = session.profile or VoiceProfileService.default_for(user)
        verification = SpeakerAwarenessService.verify(user, speaker_embedding, session=session, purpose="wake_word") if (speaker_embedding or require_speaker) else {"decision": session.speaker_state if session.speaker_state not in {"unrecognized", "unknown"} else "not_checked", "score": None}
        if require_speaker and profile.speaker_identification_enabled and profile.reject_unrecognized_speakers and verification["decision"] != "recognized":
            session.speaker_state = "unrecognized"
            session.save(update_fields=["speaker_state", "updated_at"])
            raise VoiceSpeakerRejected(session, verification.get("score"))
        now = timezone.now()
        previous = session.state
        session.mode = VoiceSession.Mode.ACTIVE
        session.active_started_at = now
        session.active_expires_at = now + cls._active_timeout(session)
        session.state = VoiceSession.State.ACTIVE_SESSION
        if verification.get("decision"):
            session.speaker_state = str(verification["decision"])
        session.last_activity_at = now
        if not session.greeted_at:
            session.greeted_at = now
        session.status = "active"
        session.ended_at = None
        session.shutdown_at = None
        session.save(update_fields=["mode", "active_started_at", "active_expires_at", "state", "speaker_state", "last_activity_at", "greeted_at", "status", "ended_at", "shutdown_at", "updated_at"])
        cls._event(session, "active_session_started", from_state=previous, to_state=session.state, detail="Active voice session started. Inactivity resets the one-hour timer.", payload={"speaker_state": session.speaker_state})
        return session

    @classmethod
    @transaction.atomic
    def disable(cls, user, session_id, *, detail: str = "Voice disabled; wake-word listening remains available.") -> VoiceSession:
        session = cls.get_owned(user, session_id)
        if session.state == VoiceSession.State.SHUTDOWN:
            return session
        previous = session.state
        session.mode = VoiceSession.Mode.WAKE_WORD
        session.active_started_at = None
        session.active_expires_at = None
        session.state = VoiceSession.State.WAKE_WORD_LISTENING
        session.save(update_fields=["mode", "active_started_at", "active_expires_at", "state", "updated_at"])
        cls._event(session, "voice_disabled_to_wake_word", from_state=previous, to_state=session.state, detail=detail)
        return session

    @classmethod
    def return_to_wake_mode(cls, user, session_id, *, detail="Active session ended.") -> VoiceSession:
        return cls.disable(user, session_id, detail=detail)

    @classmethod
    @transaction.atomic
    def shutdown(cls, user, session_id, *, detail: str = "Voice subsystem shut down by the user.") -> VoiceSession:
        session = cls.get_owned(user, session_id)
        profile = session.profile or VoiceProfileService.default_for(user)
        cls._persist_shutdown_preference(profile, True)
        if session.state == VoiceSession.State.SHUTDOWN:
            return session
        return cls.transition(user, session.pk, VoiceSession.State.SHUTDOWN, detail=detail, force=True)

    @classmethod
    def serialize(cls, session: VoiceSession, *, include_turns: bool = False) -> dict[str, Any]:
        session = cls.enforce_active_window(session)
        profile = session.profile or VoiceProfileService.default_for(session.owner)
        config = session.configuration or {}
        remaining = max(0, int((session.active_expires_at - timezone.now()).total_seconds())) if session.mode == VoiceSession.Mode.ACTIVE and session.active_expires_at else 0
        payload = {
            "id": str(session.pk), "conversation_id": str(session.conversation_id) if session.conversation_id else None,
            "title": session.title, "state": session.state, "mode": "active" if session.mode == VoiceSession.Mode.ACTIVE else "wake_word",
            "wake_word": session.wake_word or "Echo", "wake_word_enabled": session.state != VoiceSession.State.SHUTDOWN,
            "voice_enabled": session.state != VoiceSession.State.SHUTDOWN, "microphone_enabled": bool(config.get("microphone_enabled", False)),
            "speaker_state": session.speaker_state, "active_started_at": session.active_started_at.isoformat() if session.active_started_at else None,
            "active_expires_at": session.active_expires_at.isoformat() if session.active_expires_at else None,
            "active_remaining_seconds": remaining, "remaining_seconds": remaining, "status": session.status,
            "language": session.language, "input_mode": session.input_mode, "stt_provider": session.stt_provider, "tts_provider": session.tts_provider,
            "turn_count": session.turn_count, "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None, "shutdown_at": session.shutdown_at.isoformat() if session.shutdown_at else None,
            "greeted_at": session.greeted_at.isoformat() if session.greeted_at else None,
            "greeting_pending": session.state == VoiceSession.State.GREETING and not session.greeted_at,
            "greeting": cls.GREETING_TEXT if session.state == VoiceSession.State.GREETING and not session.greeted_at else "",
            "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
            "permission": config.get("permission", "unknown"), "browser_capabilities": config.get("browser_capabilities", {}),
            "last_error": {"code": session.last_error_code, "message": session.last_error_message} if session.last_error_message else None,
            "profile": {
                "language": profile.language, "voice_name": profile.voice_name, "speaking_rate": float(profile.speaking_rate), "pitch": float(profile.pitch), "volume": float(profile.volume),
                "auto_speak": profile.auto_speak, "continuous_listening": profile.continuous_listening, "barge_in_enabled": profile.barge_in_enabled,
                "save_audio": profile.save_audio, "memory_requires_approval": profile.memory_requires_approval,
                "speaker_identification_enabled": profile.speaker_identification_enabled, "reject_unrecognized_speakers": profile.reject_unrecognized_speakers,
                "voice_history_enabled": profile.voice_history_enabled, "transcript_retention_days": profile.transcript_retention_days,
                "active_session_minutes": profile.active_session_minutes,
            },
        }
        if include_turns:
            transcripts = session.transcripts.select_related("message").order_by("sequence", "created_at")[:100]
            syntheses = session.syntheses.select_related("message").order_by("created_at")[:100]
            payload["transcripts"] = [TranscriptService.serialize(item) for item in transcripts]
            payload["syntheses"] = [SynthesisService.serialize(item) for item in syntheses]
        return payload


class SpeakerAwarenessService:
    """Probabilistic speaker enrollment/verification using privacy-preserving derived vectors.

    Browser clients may supply a short-lived derived spectral representation. Deployments
    that need stronger speaker verification can configure VOICE_SPEAKER_PROVIDER_CLASS;
    that provider receives the in-memory utterance bytes and must return an embedding.
    Echo persists only the normalized derived vector unless audio retention is explicitly
    enabled in the user's voice profile.
    """

    @classmethod
    def embedding_from_audio(cls, audio: bytes, *, mime_type: str) -> list[float]:
        dotted = str(getattr(settings, "VOICE_SPEAKER_PROVIDER_CLASS", "") or "").strip()
        if not dotted:
            return []
        provider_factory = import_string(dotted)
        provider = provider_factory() if isinstance(provider_factory, type) else provider_factory
        method = getattr(provider, "embedding", None) or getattr(provider, "embed", None)
        if not callable(method):
            raise VoiceSessionError("Configured speaker provider must expose embedding(audio, mime_type=...).")
        try:
            value = method(audio, mime_type=mime_type)
        except TypeError:
            value = method(audio)
        return cls._normalize_embedding(value)

    @staticmethod
    def _normalize_embedding(value) -> list[float]:
        if value in (None, "", []):
            return []
        if not isinstance(value, (list, tuple)) or not 8 <= len(value) <= 256:
            raise VoiceSessionError("Speaker representation must contain 8 to 256 numeric features.")
        output = []
        for item in value:
            try:
                number = float(item)
            except (TypeError, ValueError) as exc:
                raise VoiceSessionError("Speaker representation contains a non-numeric feature.") from exc
            if not math.isfinite(number) or abs(number) > 1000:
                raise VoiceSessionError("Speaker representation contains an invalid feature.")
            output.append(number)
        magnitude = math.sqrt(sum(item * item for item in output))
        if magnitude <= 1e-9:
            raise VoiceSessionError("Speaker representation contains no usable signal.")
        return [item / magnitude for item in output]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))

    @classmethod
    def profile(cls, user) -> SpeakerProfile:
        profile, _ = SpeakerProfile.objects.get_or_create(
            owner=user,
            defaults={
                "name": "authorized-speaker", "title": "Authorized speaker", "description": "Derived speaker representation for this Echo account.",
                "status": "active", "threshold": float(getattr(settings, "VOICE_SPEAKER_THRESHOLD", 0.82)),
            },
        )
        return profile

    @classmethod
    @transaction.atomic
    def enroll(cls, user, embedding, *, quality: float = 1.0, duration_ms: int = 0) -> dict[str, Any]:
        vector = cls._normalize_embedding(embedding)
        profile = cls.profile(user)
        quality = max(0.0, min(float(quality or 0), 1.0))
        if quality < float(getattr(settings, "VOICE_SPEAKER_MIN_QUALITY", 0.35)):
            raise VoiceSessionError("The voice sample was too noisy for reliable enrollment.")
        SpeakerEnrollmentSample.objects.create(
            owner=user, profile=profile, name=f"sample-{profile.sample_count + 1}", title="Speaker enrollment sample",
            status="completed", embedding=vector, quality_score=quality, duration_ms=max(0, int(duration_ms or 0)),
        )
        samples = list(profile.samples.order_by("created_at").values_list("embedding", flat=True))
        length = len(vector)
        usable = [list(map(float, row)) for row in samples if isinstance(row, list) and len(row) == length]
        centroid = [sum(row[i] for row in usable) / len(usable) for i in range(length)]
        magnitude = math.sqrt(sum(item * item for item in centroid)) or 1.0
        centroid = [item / magnitude for item in centroid]
        minimum = max(2, int(getattr(settings, "VOICE_SPEAKER_MIN_SAMPLES", 3)))
        profile.embedding = centroid
        profile.sample_count = len(usable)
        profile.enrolled = len(usable) >= minimum
        profile.enrolled_at = timezone.now() if profile.enrolled else None
        profile.save(update_fields=["embedding", "sample_count", "enrolled", "enrolled_at", "updated_at"])
        return cls.serialize(profile)

    @classmethod
    def verify(cls, user, embedding, *, session: VoiceSession | None = None, transcript: SpeechTranscript | None = None, purpose: str = "command") -> dict[str, Any]:
        voice_profile = VoiceProfileService.default_for(user)
        profile = cls.profile(user)
        if not voice_profile.speaker_identification_enabled:
            return {"decision": "disabled", "score": None, "enrolled": profile.enrolled}
        if not profile.enrolled or not profile.embedding:
            return {"decision": "not_enrolled", "score": None, "enrolled": False}
        try:
            vector = cls._normalize_embedding(embedding)
        except VoiceSessionError:
            vector = []
        score = max(0.0, cls._cosine(list(map(float, profile.embedding)), vector)) if vector else 0.0
        threshold = float(profile.threshold)
        decision = "recognized" if score >= threshold else "unrecognized"
        SpeakerVerificationEvent.objects.create(
            owner=user, profile=profile, session=session, transcript=transcript, name=purpose, title=f"Speaker {decision}",
            status="completed", decision=decision, score=score, threshold=threshold,
            configuration={"purpose": purpose, "probabilistic": True},
        )
        if decision == "recognized":
            profile.last_verified_at = timezone.now()
            profile.save(update_fields=["last_verified_at", "updated_at"])
        return {"decision": decision, "score": round(score, 4), "threshold": threshold, "enrolled": True}

    @classmethod
    @transaction.atomic
    def clear(cls, user) -> dict[str, Any]:
        profile = cls.profile(user)
        profile.samples.all().delete()
        profile.embedding = []
        profile.sample_count = 0
        profile.enrolled = False
        profile.enrolled_at = None
        profile.last_verified_at = None
        profile.save(update_fields=["embedding", "sample_count", "enrolled", "enrolled_at", "last_verified_at", "updated_at"])
        return cls.serialize(profile)

    @classmethod
    def serialize(cls, profile: SpeakerProfile) -> dict[str, Any]:
        voice_profile = VoiceProfileService.default_for(profile.owner)
        provider_class = str(getattr(settings, "VOICE_SPEAKER_PROVIDER_CLASS", "") or "").strip()
        if not voice_profile.speaker_identification_enabled:
            status = "DISABLED"
        elif profile.enrolled and profile.embedding:
            status = "ENROLLED"
        elif profile.sample_count:
            status = "ENROLLING"
        else:
            status = "NOT_ENROLLED"
        return {
            "id": str(profile.pk), "enabled": bool(voice_profile.speaker_identification_enabled), "enrolled": profile.enrolled, "sample_count": profile.sample_count,
            "minimum_samples": max(2, int(getattr(settings, "VOICE_SPEAKER_MIN_SAMPLES", 3))),
            "threshold": float(profile.threshold), "enrolled_at": profile.enrolled_at.isoformat() if profile.enrolled_at else None,
            "last_verified_at": profile.last_verified_at.isoformat() if profile.last_verified_at else None,
            "probabilistic": True, "stores_raw_audio": False, "status": status,
            "provider": provider_class or "browser_derived", "server_provider_configured": bool(provider_class),
        }


class VoicePrivacyService:
    @classmethod
    @transaction.atomic
    def clear_voice_data(cls, user, *, include_conversations: bool = False) -> dict[str, int]:
        sessions = VoiceSession.objects.filter(owner=user)
        transcript_count = SpeechTranscript.objects.filter(owner=user).count()
        synthesis_count = SpeechSynthesis.objects.filter(owner=user).count()
        audio_count = AudioAsset.objects.filter(owner=user).count()
        SpeechTranscript.objects.filter(owner=user).delete()
        SpeechSynthesis.objects.filter(owner=user).delete()
        AudioAsset.objects.filter(owner=user).delete()
        VoiceEvent.objects.filter(owner=user).delete()
        session_count = sessions.count()
        sessions.delete()
        # Conversation deletion is intentionally opt-in because typed turns can share it.
        return {"sessions": session_count, "transcripts": transcript_count, "syntheses": synthesis_count, "audio_assets": audio_count}

    @classmethod
    def enforce_retention(cls, user) -> int:
        profile = VoiceProfileService.default_for(user)
        days = int(profile.transcript_retention_days or 0)
        if days <= 0:
            query = SpeechTranscript.objects.filter(owner=user)
        else:
            query = SpeechTranscript.objects.filter(owner=user, created_at__lt=timezone.now() - timedelta(days=days))
        count = query.count()
        query.delete()
        return count


class AudioValidationService:
    ALLOWED_PREFIXES = ("audio/", "video/webm", "application/octet-stream")

    @classmethod
    def validate(cls, upload) -> tuple[bytes, str]:
        if upload is None:
            raise VoiceSessionError("Audio is required.")
        max_size = int(getattr(settings, "VOICE_MAX_AUDIO_BYTES", 25 * 1024 * 1024))
        if upload.size > max_size:
            raise VoiceSessionError("Audio exceeds the configured size limit.")
        mime_type = str(getattr(upload, "content_type", "") or "application/octet-stream").lower()
        if not any(mime_type.startswith(prefix) for prefix in cls.ALLOWED_PREFIXES):
            raise VoiceSessionError("Unsupported audio type.")
        audio = upload.read()
        if not audio:
            raise VoiceSessionError("The audio recording is empty.")
        return audio, mime_type

    @classmethod
    def persist(
        cls,
        session: VoiceSession,
        audio: bytes,
        *,
        mime_type: str,
        direction: str,
        provider: str,
        format_name: str = "",
        duration_ms: int = 0,
        temporary: bool = False,
    ) -> AudioAsset:
        digest = hashlib.sha256(audio).hexdigest()
        extension = format_name or ({"audio/webm": "webm", "audio/wav": "wav", "audio/mpeg": "mp3", "audio/ogg": "ogg"}.get(mime_type, "bin"))
        asset = AudioAsset(
            owner=session.owner,
            session=session,
            name=f"{direction}-{uuid.uuid4().hex[:10]}.{extension}",
            title=f"Voice {direction} audio",
            status="active",
            direction=direction,
            provider=provider,
            mime_type=mime_type,
            format_name=extension,
            byte_size=len(audio),
            duration_ms=max(0, int(duration_ms or 0)),
            checksum=digest,
            expires_at=timezone.now() + timedelta(hours=1) if temporary else None,
            data={"temporary": temporary},
        )
        asset.file.save(asset.name, ContentFile(audio), save=False)
        asset.save()
        return asset


class TranscriptService:
    @staticmethod
    def serialize(transcript: SpeechTranscript) -> dict[str, Any]:
        return {
            "id": str(transcript.pk),
            "session_id": str(transcript.session_id) if transcript.session_id else None,
            "conversation_id": str(transcript.conversation_id) if transcript.conversation_id else None,
            "message_id": str(transcript.message_id) if transcript.message_id else None,
            "sequence": transcript.sequence,
            "text": transcript.text,
            "language": transcript.language,
            "provider": transcript.provider,
            "confidence": float(transcript.confidence),
            "is_final": transcript.is_final,
            "intent": transcript.intent,
            "command_route": transcript.command_route,
            "command_result": transcript.command_result,
            "response": {
                "content": str((transcript.command_result or {}).get("content", "")),
                "route": str((transcript.command_result or {}).get("route", transcript.command_route or "")),
                "message_id": str((transcript.command_result or {}).get("message_id", "")),
                "data": (transcript.command_result or {}).get("data", {}),
            },
            "memory_status": transcript.memory_status,
            "created_at": transcript.created_at.isoformat(),
        }

    @classmethod
    def _memory_status(cls, candidate: str) -> str:
        return SpeechTranscript.MemoryStatus.PENDING if candidate else SpeechTranscript.MemoryStatus.NOT_CANDIDATE

    @classmethod
    def _create_memory(cls, user, transcript: SpeechTranscript, content: str) -> Memory:
        from echo.apps.memory.services import MemoryAgentService
        memory, _created = MemoryAgentService.remember(
            user, content, summary=content[:255], category="conversation", memory_type="voice_approved",
            source_type="voice_transcript", source_id=str(transcript.pk), importance=0.5,
            confidence=max(float(transcript.confidence), 0.75),
            metadata={"conversation_id": str(transcript.conversation_id) if transcript.conversation_id else None, "approved": True},
        )
        return memory

    @classmethod
    def ingest(
        cls,
        user,
        session_id,
        *,
        text: str,
        provider: str = "browser",
        confidence: float = 0,
        language: str = "",
        is_final: bool = True,
        audio_asset: AudioAsset | None = None,
        speaker_embedding=None,
    ) -> VoiceTurnResult:
        session = VoiceSessionService.enforce_active_window(VoiceSessionService.get_owned(user, session_id))
        text = str(text or "").strip()
        if not text:
            raise VoiceSessionError("No speech was detected.")
        if len(text) > 20_000:
            raise VoiceSessionError("Transcript is too long.")
        if session.state == VoiceSession.State.SHUTDOWN:
            raise VoiceSessionError("Voice is shut down. Activate voice to start a new runtime.")
        profile = session.profile or VoiceProfileService.default_for(user)
        wake_pattern = re.compile(rf"^\s*(?:hey\s+)?{re.escape(session.wake_word or 'Echo')}\b[\s,.:;!?-]*", re.IGNORECASE)
        # Typed turns remain available as an authenticated UI channel even while the
        # microphone is in wake-word mode. Wake-word and speaker checks apply only to
        # acoustic input; voice is an interface to the shared Agent Manager, not a
        # separate authorization system.
        acoustic_input = provider != "typed"
        if acoustic_input and session.mode == VoiceSession.Mode.WAKE_WORD:
            match = wake_pattern.match(text)
            minimum_wake_confidence = float(getattr(settings, "VOICE_WAKE_WORD_MIN_CONFIDENCE", 0.45))
            # Some browser recognizers report 0 when confidence is unavailable. Treat
            # that as unknown rather than a negative signal; when confidence is
            # provided, reject low-confidence wake activations before Agent Manager.
            reported_confidence = max(0.0, min(float(confidence or 0), 1.0))
            if not match or (reported_confidence > 0 and reported_confidence < minimum_wake_confidence):
                raise VoiceWakeWordRequired(session)
            # Wake detections can be duplicated by browser recognition engines when a
            # result is finalized more than once. Keep a short server-authoritative
            # cooldown so one acoustic wake event cannot create multiple activations.
            # This does not apply to the explicit Activate Voice UI action.
            wake_cooldown = float(getattr(settings, "VOICE_WAKE_WORD_COOLDOWN_SECONDS", 2.0))
            last_wake_raw = str((session.configuration or {}).get("last_wake_activation_at") or "")
            last_wake_at = parse_datetime(last_wake_raw) if last_wake_raw else None
            if last_wake_at and timezone.is_naive(last_wake_at):
                last_wake_at = timezone.make_aware(last_wake_at, timezone.get_current_timezone())
            if last_wake_at and wake_cooldown > 0 and timezone.now() < last_wake_at + timedelta(seconds=wake_cooldown):
                raise VoiceWakeWordRequired(session)
            session = VoiceSessionService.activate(
                user, session.pk, speaker_embedding=speaker_embedding, require_speaker=True
            )
            configuration = dict(session.configuration or {})
            configuration["last_wake_activation_at"] = timezone.now().isoformat()
            session.configuration = configuration
            session.save(update_fields=["configuration", "updated_at"])
            text = text[match.end():].strip()
            if not text:
                raise VoiceWakeActivated(session)
        elif acoustic_input:
            verification = SpeakerAwarenessService.verify(user, speaker_embedding, session=session, purpose="command")
            session.speaker_state = verification["decision"]
            session.save(update_fields=["speaker_state", "updated_at"])
            if profile.speaker_identification_enabled and profile.reject_unrecognized_speakers and verification["decision"] != "recognized":
                raise VoiceSpeakerRejected(session, verification.get("score"))
            # The wake word is optional while already active. Strip it when present so
            # the shared intent router sees the actual request ("Echo, open Firefox"
            # becomes "open Firefox") without teaching every agent about wake words.
            match = wake_pattern.match(text)
            if match and text[match.end():].strip():
                text = text[match.end():].strip()
        session = VoiceSessionService.touch_activity(session, detail="Voice input received.")
        VoiceSessionService.transition(user, session.pk, VoiceSession.State.PROCESSING, detail="Speech captured and ready for interpretation.", force=True)
        sequence = (session.transcripts.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        transcript = SpeechTranscript.objects.create(
            owner=user,
            session=session,
            conversation=session.conversation,
            audio_asset=audio_asset,
            name=f"utterance-{sequence}",
            title=text[:80],
            description="Voice transcript",
            status="processing",
            sequence=sequence,
            text=text,
            language=(language or session.language)[:32],
            provider=provider[:64],
            confidence=max(0, min(float(confidence or 0), 1)),
            is_final=bool(is_final),
            started_at=timezone.now(),
            data={"speaker_state": session.speaker_state, "retention": "history" if profile.voice_history_enabled else "session_only"},
        )
        action_hint = bool(re.search(r"\b(open|launch|go to|navigate|click|scroll|play|pause|resume|search|create|mark|run|start|execute|remember|analyze|watch|cancel)\b", text, re.IGNORECASE))
        VoiceSessionService._event(
            VoiceSessionService.get_owned(user, session.pk),
            "command_routing",
            to_state=VoiceSession.State.PROCESSING,
            detail="Echo is routing the request through Agent Manager." + (" An executable capability may be required." if action_hint else ""),
            payload={"action_hint": action_hint},
        )
        try:
            result = AgentManagerOrchestrator(user, source="voice", section="voice", voice_session_id=str(session.pk)).execute(
                text,
                conversation_id=str(session.conversation_id) if session.conversation_id else None,
            )
        except Exception as exc:
            transcript.status = "failed"
            transcript.completed_at = timezone.now()
            transcript.data = {"error": str(exc)}
            transcript.save(update_fields=["status", "completed_at", "data", "updated_at"])
            VoiceSessionService.transition(user, session.pk, VoiceSession.State.ERROR, detail=str(exc), error_code="command_failed", force=True)
            raise
        user_message_id = result.data.get("user_message_id")
        if user_message_id:
            transcript.message = Message.objects.filter(pk=user_message_id, owner=user).first()
        transcript.conversation = result.conversation
        transcript.status = "completed" if result.status == "completed" else result.status
        transcript.intent = result.route.split(".", 1)[0][:80]
        transcript.command_route = result.route[:80]
        transcript.command_result = result.as_dict()
        transcript.memory_status = cls._memory_status(result.memory_candidate)
        transcript.completed_at = timezone.now()
        transcript.data = {**(transcript.data or {}), **({"memory_candidate": result.memory_candidate} if result.memory_candidate else {})}
        transcript.save()
        profile = session.profile or VoiceProfileService.default_for(user)
        if result.memory_candidate and not profile.memory_requires_approval:
            memory = cls._create_memory(user, transcript, result.memory_candidate)
            command_result = dict(transcript.command_result or {})
            command_result["memory_id"] = str(memory.pk)
            transcript.command_result = command_result
            transcript.memory_status = SpeechTranscript.MemoryStatus.APPROVED
            transcript.save(update_fields=["command_result", "memory_status", "updated_at"])
        session = VoiceSessionService.get_owned(user, session.pk)
        session.conversation = result.conversation
        session.turn_count = session.turn_count + 1
        session.save(update_fields=["conversation", "turn_count", "updated_at"])
        session = VoiceSessionService.touch_activity(session, detail="Voice command processed.")

        voice_action = str((result.data or {}).get("voice_action") or "").strip().casefold()
        if voice_action == "shutdown":
            session = VoiceSessionService.shutdown(user, session.pk, detail="Voice shutdown requested by the user.")
        elif voice_action == "disable":
            session = VoiceSessionService.disable(user, session.pk)
        elif voice_action == "activate":
            session = VoiceSessionService.activate(user, session.pk)
        else:
            target = VoiceSession.State.ACTIVE_SESSION if session.mode == VoiceSession.Mode.ACTIVE else VoiceSession.State.WAKE_WORD_LISTENING
            session = VoiceSessionService.transition(
                user, session.pk, target, detail="Echo response is ready.", force=True
            )

        VoiceSessionService._event(
            session,
            "response_ready",
            from_state=VoiceSession.State.PROCESSING,
            to_state=session.state,
            detail="Echo response is ready for text display or speech playback.",
            payload={
                "route": result.route,
                "voice_action": voice_action or None,
                "message_id": str(result.message.pk) if result.message else None,
            },
        )
        profile = session.profile or VoiceProfileService.default_for(user)
        return VoiceTurnResult(
            session=session,
            transcript=transcript,
            response=result.message,
            content=result.content,
            route=result.route,
            should_speak=bool(profile.auto_speak and result.content and voice_action != "shutdown"),
            memory_candidate=bool(result.memory_candidate),
            command_data=result.as_dict(),
        )

    @classmethod
    def transcribe_upload(cls, user, session_id, upload, *, speaker_embedding=None) -> VoiceTurnResult:
        session = VoiceSessionService.get_owned(user, session_id)
        profile = session.profile or VoiceProfileService.default_for(user)
        audio, mime_type = AudioValidationService.validate(upload)
        provider_name = session.stt_provider or profile.speech_to_text_provider
        audio_asset = None
        if profile.save_audio:
            audio_asset = AudioValidationService.persist(
                session,
                audio,
                mime_type=mime_type,
                direction=AudioAsset.Direction.INPUT,
                provider=provider_name,
            )
        VoiceSessionService.transition(user, session.pk, VoiceSession.State.PROCESSING, detail="Audio is being transcribed.", force=True)
        try:
            # Prefer a configured server-side speaker model over browser-derived
            # spectral features. The raw utterance stays in memory for this call and
            # is not persisted unless the user's explicit save_audio setting is on.
            provider_embedding = SpeakerAwarenessService.embedding_from_audio(audio, mime_type=mime_type)
            if provider_embedding:
                speaker_embedding = provider_embedding
            result: TranscriptionResult = VoiceProviderRegistry.stt(provider_name).transcribe(
                audio,
                mime_type=mime_type,
                language=session.language,
            )
        except Exception as exc:
            VoiceSessionService.transition(user, session.pk, VoiceSession.State.ERROR, detail=str(exc), error_code="transcription_failed", force=True)
            raise VoiceSessionError(str(exc)) from exc
        return cls.ingest(
            user,
            session.pk,
            text=result.text,
            provider=provider_name,
            confidence=result.confidence,
            language=result.language or session.language,
            is_final=True,
            audio_asset=audio_asset,
            speaker_embedding=speaker_embedding,
        )

    @classmethod
    @transaction.atomic
    def memory_decision(cls, user, transcript_id, *, approve: bool) -> dict[str, Any]:
        queryset = SpeechTranscript.objects.select_for_update().select_related("conversation")
        if not user.is_staff:
            queryset = queryset.filter(owner=user)
        try:
            transcript = queryset.get(pk=transcript_id)
        except (SpeechTranscript.DoesNotExist, ValueError, TypeError) as exc:
            raise VoiceResourceNotFound("Transcript was not found.") from exc
        if transcript.memory_status == SpeechTranscript.MemoryStatus.APPROVED:
            if not approve:
                raise VoiceSessionError("An approved memory must be removed from the Memory workspace, not discarded from its source transcript.")
            existing_id = (transcript.command_result or {}).get("memory_id")
            existing = Memory.objects.filter(pk=existing_id, owner=user).first() if existing_id else None
            if existing:
                return {"approved": True, "memory_id": str(existing.pk), "transcript_id": str(transcript.pk)}
        elif transcript.memory_status != SpeechTranscript.MemoryStatus.PENDING:
            raise VoiceSessionError("This transcript is not awaiting a memory decision.")
        if not approve:
            transcript.memory_status = SpeechTranscript.MemoryStatus.REJECTED
            transcript.save(update_fields=["memory_status", "updated_at"])
            return {"approved": False, "transcript_id": str(transcript.pk)}
        content = str((transcript.data or {}).get("memory_candidate") or transcript.text).strip()
        memory = cls._create_memory(user, transcript, content)
        result = dict(transcript.command_result or {})
        result["memory_id"] = str(memory.pk)
        transcript.command_result = result
        transcript.memory_status = SpeechTranscript.MemoryStatus.APPROVED
        transcript.save(update_fields=["command_result", "memory_status", "updated_at"])
        return {"approved": True, "memory_id": str(memory.pk), "transcript_id": str(transcript.pk)}


class SynthesisService:
    @staticmethod
    def serialize(item: SpeechSynthesis) -> dict[str, Any]:
        return {
            "id": str(item.pk),
            "session_id": str(item.session_id) if item.session_id else None,
            "message_id": str(item.message_id) if item.message_id else None,
            "text": item.text,
            "provider": item.provider,
            "voice_name": item.voice_name,
            "language": item.language,
            "format": item.format_name,
            "duration_ms": item.duration_ms,
            "status": item.status,
            "audio_url": item.audio_asset.file.url if item.audio_asset_id and item.audio_asset.file else None,
            "error": item.error_message or None,
            "created_at": item.created_at.isoformat(),
        }

    @classmethod
    def prepare_browser(cls, user, session_id, *, text: str, message_id: str | None = None) -> SpeechSynthesis:
        session = VoiceSessionService.get_owned(user, session_id)
        if session.state == VoiceSession.State.SHUTDOWN:
            raise VoiceSessionError("Voice is shut down.")
        session = VoiceSessionService.transition(
            user, session.pk, VoiceSession.State.SPEAKING, detail="Echo is speaking.", force=True
        )
        profile = session.profile or VoiceProfileService.default_for(user)
        message = Message.objects.filter(pk=message_id, owner=user).first() if message_id else None
        record = SpeechSynthesis.objects.create(
            owner=user,
            session=session,
            message=message,
            name="browser_synthesis",
            title="Browser speech response",
            status="ready",
            text=text,
            provider="browser",
            voice_name=profile.voice_name,
            language=profile.language,
            format_name="browser",
            completed_at=timezone.now(),
            data={"rate": float(profile.speaking_rate), "pitch": float(profile.pitch), "volume": float(profile.volume)},
        )
        configuration = dict(session.configuration or {})
        configuration["active_synthesis_id"] = str(record.pk)
        session.configuration = configuration
        session.save(update_fields=["configuration", "updated_at"])
        return record

    @classmethod
    @transaction.atomic
    def complete_playback(cls, user, session_id, *, synthesis_id: str = "", outcome: str = "completed") -> VoiceSession:
        """Acknowledge that client/server audio playback actually ended.

        Browser speech synthesis is asynchronous, so creating a synthesis record cannot
        itself prove that audio finished.  This callback is the authoritative bridge
        from playback completion back into the Voice state machine.
        """
        session = VoiceSessionService.get_owned(user, session_id)
        active_synthesis_id = str((session.configuration or {}).get("active_synthesis_id") or "")
        record = None
        if synthesis_id:
            record = SpeechSynthesis.objects.filter(pk=synthesis_id, owner=user, session=session).first()
            if record:
                data = dict(record.data or {})
                data["playback_completed_at"] = timezone.now().isoformat()
                data["playback_outcome"] = str(outcome or "completed")[:40]
                record.data = data
                if outcome == "completed" and record.status == "ready":
                    record.status = "completed"
                record.save(update_fields=["data", "status", "updated_at"])
        # A cancelled/replaced utterance may report completion after a newer synthesis
        # has started. That stale callback must never release the authoritative state
        # from SPEAKING while newer audio is still active.
        if synthesis_id and active_synthesis_id and str(synthesis_id) != active_synthesis_id:
            return session
        if session.state == VoiceSession.State.SHUTDOWN:
            return session
        configuration = dict(session.configuration or {})
        configuration.pop("active_synthesis_id", None)
        session.configuration = configuration
        session.save(update_fields=["configuration", "updated_at"])
        if session.state != VoiceSession.State.SPEAKING:
            return session
        target = VoiceSession.State.ACTIVE_SESSION if session.mode == VoiceSession.Mode.ACTIVE else VoiceSession.State.WAKE_WORD_LISTENING
        return VoiceSessionService.transition(
            user, session.pk, target,
            detail="Speech playback completed; microphone capture may resume." if outcome == "completed" else "Speech playback ended; microphone capture may resume.",
            force=True,
        )

    @classmethod
    def synthesize(cls, user, session_id, *, text: str, message_id: str | None = None, format_name: str = "mp3") -> SpeechSynthesis:
        session = VoiceSessionService.get_owned(user, session_id)
        if session.state == VoiceSession.State.SHUTDOWN:
            raise VoiceSessionError("Voice is shut down.")
        profile = session.profile or VoiceProfileService.default_for(user)
        provider_name = session.tts_provider or profile.text_to_speech_provider
        if provider_name == "browser":
            return cls.prepare_browser(user, session_id, text=text, message_id=message_id)
        session = VoiceSessionService.transition(
            user, session.pk, VoiceSession.State.SPEAKING, detail="Echo is preparing speech output.", force=True
        )
        message = Message.objects.filter(pk=message_id, owner=user).first() if message_id else None
        record = SpeechSynthesis.objects.create(
            owner=user,
            session=session,
            message=message,
            name="speech_synthesis",
            title="Echo voice response",
            status="processing",
            text=text,
            provider=provider_name,
            voice_name=profile.voice_name,
            language=profile.language,
            format_name=format_name,
            started_at=timezone.now(),
        )
        configuration = dict(session.configuration or {})
        configuration["active_synthesis_id"] = str(record.pk)
        session.configuration = configuration
        session.save(update_fields=["configuration", "updated_at"])
        try:
            result: SynthesisResult = VoiceProviderRegistry.tts(provider_name).synthesize(
                text,
                voice=profile.voice_name or "default",
                language=profile.language,
                format_name=format_name,
                speaking_rate=float(profile.speaking_rate),
                pitch=float(profile.pitch),
                volume=float(profile.volume),
            )
            asset = AudioValidationService.persist(
                session,
                result.audio,
                mime_type=result.mime_type,
                direction=AudioAsset.Direction.OUTPUT,
                provider=provider_name,
                format_name=result.format_name,
                duration_ms=result.duration_ms,
                temporary=not profile.save_audio,
            )
            record.audio_asset = asset
            record.duration_ms = result.duration_ms
            record.status = "ready"
            record.completed_at = timezone.now()
            record.data = result.metadata
            record.save()
            return record
        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)
            record.completed_at = timezone.now()
            record.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
            fresh = VoiceSessionService.get_owned(user, session.pk)
            configuration = dict(fresh.configuration or {})
            configuration.pop("active_synthesis_id", None)
            fresh.configuration = configuration
            fresh.save(update_fields=["configuration", "updated_at"])
            resume_state = VoiceSession.State.ACTIVE_SESSION if fresh.mode == VoiceSession.Mode.ACTIVE else VoiceSession.State.WAKE_WORD_LISTENING
            VoiceSessionService.transition(
                user, fresh.pk, resume_state, detail="Speech output failed; voice input remains available.", force=True
            )
            raise VoiceSessionError(str(exc)) from exc
