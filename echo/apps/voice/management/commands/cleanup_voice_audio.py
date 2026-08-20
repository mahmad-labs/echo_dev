from echo.apps.voice.management.commands.cleanup_voice import Command as CleanupVoiceCommand


class Command(CleanupVoiceCommand):
    help = "Delete expired temporary voice audio and enforce the active-session inactivity policy."
