from __future__ import annotations

from rest_framework import serializers

from .models import VoiceSession


class VoiceSessionStartSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    client_session_id = serializers.CharField(required=False, allow_blank=True, max_length=120)
    language = serializers.CharField(required=False, allow_blank=True, max_length=32)
    input_mode = serializers.ChoiceField(required=False, choices=("voice", "text", "mixed"), default="voice")


class VoiceStateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=VoiceSession.State.choices)
    detail = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    error_code = serializers.CharField(required=False, allow_blank=True, max_length=80)
    permission = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        choices=("", "unknown", "prompt", "granted", "denied", "unavailable"),
    )
    browser_capabilities = serializers.DictField(required=False)


class BrowserTranscriptSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    text = serializers.CharField(max_length=20_000, trim_whitespace=True)
    provider = serializers.ChoiceField(required=False, default="browser", choices=("browser", "typed"))
    confidence = serializers.FloatField(required=False, default=0, min_value=0, max_value=1)
    language = serializers.CharField(required=False, allow_blank=True, max_length=32)
    is_final = serializers.BooleanField(required=False, default=True)
    speaker_embedding = serializers.ListField(child=serializers.FloatField(), required=False, allow_empty=True, min_length=8, max_length=256)


class AudioTranscriptionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    audio = serializers.FileField()
    speaker_embedding = serializers.JSONField(required=False)


class SynthesisRequestSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    text = serializers.CharField(max_length=20_000, trim_whitespace=True)
    message_id = serializers.UUIDField(required=False, allow_null=True)
    format = serializers.ChoiceField(required=False, choices=("mp3", "wav", "ogg"), default="mp3")


class MemoryDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()


class VoiceProfileSerializer(serializers.Serializer):
    language = serializers.CharField(required=False, max_length=32)
    speech_to_text_provider = serializers.CharField(required=False, max_length=64)
    text_to_speech_provider = serializers.CharField(required=False, max_length=64)
    voice_name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    speaking_rate = serializers.DecimalField(required=False, max_digits=4, decimal_places=2, min_value=0.5, max_value=2)
    pitch = serializers.DecimalField(required=False, max_digits=4, decimal_places=2, min_value=0, max_value=2)
    volume = serializers.DecimalField(required=False, max_digits=4, decimal_places=2, min_value=0, max_value=1)
    auto_speak = serializers.BooleanField(required=False)
    continuous_listening = serializers.BooleanField(required=False)
    barge_in_enabled = serializers.BooleanField(required=False)
    save_audio = serializers.BooleanField(required=False)
    memory_requires_approval = serializers.BooleanField(required=False)
    speaker_identification_enabled = serializers.BooleanField(required=False)
    reject_unrecognized_speakers = serializers.BooleanField(required=False)
    voice_history_enabled = serializers.BooleanField(required=False)
    transcript_retention_days = serializers.IntegerField(required=False, min_value=0, max_value=365)
    active_session_minutes = serializers.IntegerField(required=False, min_value=1, max_value=60)

    def validate_speech_to_text_provider(self, value):
        if value not in {"browser", "configured_http", "custom"}:
            raise serializers.ValidationError("Unknown speech-to-text provider.")
        return value

    def validate_text_to_speech_provider(self, value):
        if value not in {"browser", "configured_http", "custom"}:
            raise serializers.ValidationError("Unknown text-to-speech provider.")
        return value


class DynamicModelSerializer(serializers.ModelSerializer):
    """Retained for compatibility with the application's dynamic API router."""

    class Meta:
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "owner")


class VoiceActivateSerializer(serializers.Serializer):
    speaker_embedding = serializers.ListField(child=serializers.FloatField(), required=False, allow_empty=True, min_length=8, max_length=256)


class SpeakerEnrollmentSerializer(serializers.Serializer):
    embedding = serializers.ListField(child=serializers.FloatField(), min_length=8, max_length=256)
    quality = serializers.FloatField(required=False, default=1.0, min_value=0, max_value=1)
    duration_ms = serializers.IntegerField(required=False, default=0, min_value=0, max_value=30000)


class VoicePrivacySerializer(serializers.Serializer):
    clear_voice_data = serializers.BooleanField(required=False, default=False)
    clear_speaker_enrollment = serializers.BooleanField(required=False, default=False)
