from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from .models import AudioAsset, VoiceSession


@shared_task
def cleanup_expired_audio_assets() -> dict[str, int]:
    deleted = 0
    queryset = AudioAsset.objects.filter(expires_at__isnull=False, expires_at__lte=timezone.now())
    for asset in queryset.iterator(chunk_size=100):
        if asset.file:
            asset.file.delete(save=False)
        asset.delete()
        deleted += 1
    return {"deleted": deleted}


@shared_task
def enforce_voice_inactivity() -> dict[str, int]:
    """Return expired active sessions to wake-word mode; never auto-shutdown Voice."""
    now = timezone.now()
    queryset = VoiceSession.objects.filter(
        state=VoiceSession.State.ACTIVE_SESSION,
        active_expires_at__isnull=False,
        active_expires_at__lte=now,
    )
    updated = queryset.update(
        state=VoiceSession.State.WAKE_WORD_LISTENING,
        mode=VoiceSession.Mode.WAKE_WORD,
        active_started_at=None,
        active_expires_at=None,
    )
    return {"returned_to_wake_word": updated}


@shared_task
def close_abandoned_voice_sessions(max_idle_minutes: int = 120) -> dict[str, int]:
    """Compatibility task: old deployments called this periodically.

    Voice shutdown is now an explicit user action, so unattended sessions are never
    silently terminated. The task simply enforces the active-session inactivity limit.
    """
    return enforce_voice_inactivity.run()
