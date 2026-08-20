from django.core.management.base import BaseCommand

from echo.apps.voice.tasks import cleanup_expired_audio_assets, enforce_voice_inactivity


class Command(BaseCommand):
    help = "Delete expired temporary voice audio and return inactive active sessions to wake-word mode."

    def handle(self, *args, **options):
        audio = cleanup_expired_audio_assets()
        sessions = enforce_voice_inactivity()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {audio['deleted']} expired audio assets; "
                f"returned {sessions['returned_to_wake_word']} inactive sessions to wake-word mode."
            )
        )
