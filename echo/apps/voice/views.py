from __future__ import annotations

from django.urls import reverse
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SpeechTranscript, VoiceSession
from .providers import VoiceProviderRegistry
from .serializers import (
    AudioTranscriptionSerializer,
    BrowserTranscriptSerializer,
    MemoryDecisionSerializer,
    SynthesisRequestSerializer,
    VoiceProfileSerializer,
    VoiceSessionStartSerializer,
    VoiceStateSerializer,
    VoiceActivateSerializer,
    SpeakerEnrollmentSerializer,
    VoicePrivacySerializer,
)
from .services import (
    SynthesisService,
    TranscriptService,
    VoiceProfileService,
    VoiceResourceNotFound,
    VoiceSessionError,
    VoiceSessionService,
    VoiceWakeWordRequired,
    VoiceWakeActivated,
    VoiceSpeakerRejected,
    SpeakerAwarenessService,
    VoicePrivacyService,
)


def _profile_payload(profile):
    return {
        "id": str(profile.pk),
        "language": profile.language,
        "speech_to_text_provider": profile.speech_to_text_provider,
        "text_to_speech_provider": profile.text_to_speech_provider,
        "voice_name": profile.voice_name,
        "speaking_rate": float(profile.speaking_rate),
        "pitch": float(profile.pitch),
        "volume": float(profile.volume),
        "auto_speak": profile.auto_speak,
        "continuous_listening": profile.continuous_listening,
        "barge_in_enabled": profile.barge_in_enabled,
        "save_audio": profile.save_audio,
        "memory_requires_approval": profile.memory_requires_approval,
        "speaker_identification_enabled": profile.speaker_identification_enabled,
        "reject_unrecognized_speakers": profile.reject_unrecognized_speakers,
        "voice_history_enabled": profile.voice_history_enabled,
        "transcript_retention_days": profile.transcript_retention_days,
        "active_session_minutes": profile.active_session_minutes,
    }


def _error(exc, code="voice_error", http_status=status.HTTP_400_BAD_REQUEST):
    if isinstance(exc, VoiceResourceNotFound):
        http_status = status.HTTP_404_NOT_FOUND
    return Response({"ok": False, "code": code, "detail": str(exc)}, status=http_status)


class VoiceCapabilitiesView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        profile = VoiceProfileService.default_for(request.user)
        return Response(
            {
                "ok": True,
                "providers": VoiceProviderRegistry.capabilities(),
                "profile": _profile_payload(profile),
                "browser_runtime_required": True,
                "microphone_permission_managed_by_browser": True,
                "settings_url": reverse("workspace", kwargs={"section": "settings"}),
            }
        )


class VoiceRuntimeView(APIView):
    """Return the single authoritative voice runtime for the authenticated user."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        try:
            session = VoiceSessionService.current_or_start(
                request.user,
                client_session_id=str(request.query_params.get("client_session_id") or "")[:120],
                input_mode="mixed",
            )
        except VoiceSessionError as exc:
            return _error(exc, "runtime_unavailable")
        return Response({"ok": True, "session": VoiceSessionService.serialize(session, include_turns=False)})


class VoiceProfileView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def get(self, request):
        return Response({"ok": True, "profile": _profile_payload(VoiceProfileService.default_for(request.user))})

    def patch(self, request):
        serializer = VoiceProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            profile = VoiceProfileService.update(request.user, serializer.validated_data)
        except Exception as exc:
            return _error(exc, "invalid_voice_profile")
        return Response({"ok": True, "profile": _profile_payload(profile)})

    put = patch


class VoiceSessionListCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def get(self, request):
        sessions = VoiceSessionService.owned(request.user).select_related("conversation", "profile").order_by("-last_activity_at", "-created_at")[:30]
        return Response({"ok": True, "sessions": [VoiceSessionService.serialize(item) for item in sessions]})

    def post(self, request):
        serializer = VoiceSessionStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            session = VoiceSessionService.start(
                request.user,
                conversation_id=str(values.get("conversation_id") or "") or None,
                client_session_id=values.get("client_session_id", ""),
                language=values.get("language", ""),
                input_mode=values.get("input_mode", "voice"),
            )
        except VoiceSessionError as exc:
            return _error(exc, "session_start_failed")
        return Response({"ok": True, "session": VoiceSessionService.serialize(session, include_turns=True)}, status=status.HTTP_201_CREATED)


class VoiceSessionDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, session_id):
        try:
            session = VoiceSessionService.get_owned(request.user, session_id)
        except VoiceSessionError as exc:
            return _error(exc, "session_not_found", status.HTTP_404_NOT_FOUND)
        session = VoiceSessionService.enforce_active_window(session)
        return Response({"ok": True, "session": VoiceSessionService.serialize(session, include_turns=True)})


class VoiceSessionStateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def post(self, request, session_id):
        serializer = VoiceStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            session = VoiceSessionService.transition(
                request.user,
                session_id,
                values["state"],
                detail=values.get("detail", ""),
                error_code=values.get("error_code", ""),
                browser_capabilities=values.get("browser_capabilities"),
                permission=values.get("permission", ""),
            )
        except VoiceSessionError as exc:
            return _error(exc, "invalid_state_transition")
        return Response({"ok": True, "session": VoiceSessionService.serialize(session)})


class VoiceSessionGreetingView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, session_id):
        try:
            session = VoiceSessionService.mark_greeted(request.user, session_id)
        except VoiceSessionError as exc:
            return _error(exc, "greeting_failed")
        return Response({"ok": True, "session": VoiceSessionService.serialize(session)})


class VoiceSessionDisableView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, session_id):
        try:
            session = VoiceSessionService.disable(request.user, session_id)
        except VoiceSessionError as exc:
            return _error(exc, "disable_failed")
        return Response({"ok": True, "session": VoiceSessionService.serialize(session)})


class VoiceSessionShutdownView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, session_id):
        try:
            session = VoiceSessionService.shutdown(request.user, session_id)
        except VoiceSessionError as exc:
            return _error(exc, "shutdown_failed")
        profile = session.profile or VoiceProfileService.default_for(request.user)
        if not profile.voice_history_enabled:
            session.transcripts.filter(data__retention="session_only").delete()
        return Response({"ok": True, "session": VoiceSessionService.serialize(session)})


class VoiceSessionEndView(VoiceSessionShutdownView):
    """Backward-compatible endpoint; ending voice now means explicit shutdown."""



class BrowserTranscriptView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def post(self, request):
        serializer = BrowserTranscriptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            turn = TranscriptService.ingest(request.user, **serializer.validated_data)
        except VoiceWakeActivated as exc:
            return Response({"ok": True, "ignored": True, "reason": "wake_activated", "detail": str(exc), "session": VoiceSessionService.serialize(exc.session)})
        except VoiceWakeWordRequired as exc:
            recovered = VoiceSessionService.recover_after_rejected_input(request.user, exc.session.pk, detail="Wake-word input was ignored safely.")
            return Response({"ok": True, "ignored": True, "reason": "wake_word_required", "detail": str(exc), "session": VoiceSessionService.serialize(recovered)})
        except VoiceSpeakerRejected as exc:
            recovered = VoiceSessionService.recover_after_rejected_input(request.user, exc.session.pk, detail="Unrecognized-speaker input was ignored safely.")
            return Response({"ok": True, "ignored": True, "reason": "speaker_unrecognized", "detail": str(exc), "session": VoiceSessionService.serialize(recovered)})
        except Exception as exc:
            return _error(exc, "voice_command_failed", status.HTTP_502_BAD_GATEWAY if not isinstance(exc, VoiceSessionError) else status.HTTP_400_BAD_REQUEST)
        synthesis = None
        synthesis_error = ""
        if turn.should_speak:
            try:
                synthesis = SynthesisService.synthesize(
                    request.user,
                    turn.session.pk,
                    text=turn.content,
                    message_id=str(turn.response.pk),
                )
            except VoiceSessionError as exc:
                synthesis_error = str(exc)
        return Response(
            {
                "ok": True,
                "session": VoiceSessionService.serialize(VoiceSessionService.get_owned(request.user, turn.session.pk)),
                "transcript": TranscriptService.serialize(turn.transcript),
                "response": {
                    "message_id": str(turn.response.pk),
                    "content": turn.content,
                    "route": turn.route,
                    "command": turn.command_data,
                },
                "synthesis": SynthesisService.serialize(synthesis) if synthesis else None,
                "synthesis_error": synthesis_error or None,
                "should_speak": bool(turn.should_speak and not synthesis_error),
                "memory_candidate": turn.memory_candidate,
            }
        )


class AudioTranscriptionView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = AudioTranscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            turn = TranscriptService.transcribe_upload(
                request.user,
                serializer.validated_data["session_id"],
                serializer.validated_data["audio"],
                speaker_embedding=serializer.validated_data.get("speaker_embedding"),
            )
        except VoiceWakeActivated as exc:
            return Response({"ok": True, "ignored": True, "reason": "wake_activated", "detail": str(exc), "session": VoiceSessionService.serialize(exc.session)})
        except VoiceWakeWordRequired as exc:
            recovered = VoiceSessionService.recover_after_rejected_input(request.user, exc.session.pk, detail="Wake-word input was ignored safely.")
            return Response({"ok": True, "ignored": True, "reason": "wake_word_required", "detail": str(exc), "session": VoiceSessionService.serialize(recovered)})
        except VoiceSpeakerRejected as exc:
            recovered = VoiceSessionService.recover_after_rejected_input(request.user, exc.session.pk, detail="Unrecognized-speaker input was ignored safely.")
            return Response({"ok": True, "ignored": True, "reason": "speaker_unrecognized", "detail": str(exc), "session": VoiceSessionService.serialize(recovered)})
        except Exception as exc:
            return _error(
                exc,
                "transcription_failed",
                status.HTTP_400_BAD_REQUEST if isinstance(exc, VoiceSessionError) else status.HTTP_502_BAD_GATEWAY,
            )
        synthesis = None
        synthesis_error = ""
        if turn.should_speak:
            try:
                synthesis = SynthesisService.synthesize(
                    request.user,
                    turn.session.pk,
                    text=turn.content,
                    message_id=str(turn.response.pk),
                )
            except VoiceSessionError as exc:
                synthesis_error = str(exc)
        return Response(
            {
                "ok": True,
                "session": VoiceSessionService.serialize(VoiceSessionService.get_owned(request.user, turn.session.pk)),
                "transcript": TranscriptService.serialize(turn.transcript),
                "response": {"message_id": str(turn.response.pk), "content": turn.content, "route": turn.route, "command": turn.command_data},
                "synthesis": SynthesisService.serialize(synthesis) if synthesis else None,
                "synthesis_error": synthesis_error or None,
                "should_speak": bool(turn.should_speak and not synthesis_error),
                "memory_candidate": turn.memory_candidate,
            }
        )


class VoiceSynthesisView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def post(self, request):
        serializer = SynthesisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            synthesis = SynthesisService.synthesize(
                request.user,
                values["session_id"],
                text=values["text"],
                message_id=str(values.get("message_id") or "") or None,
                format_name=values.get("format", "mp3"),
            )
        except VoiceSessionError as exc:
            return _error(exc, "synthesis_failed", status.HTTP_502_BAD_GATEWAY)
        return Response({"ok": True, "synthesis": SynthesisService.serialize(synthesis)})


class VoiceSpeechCompleteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def post(self, request, session_id):
        try:
            session = SynthesisService.complete_playback(
                request.user, session_id,
                synthesis_id=str(request.data.get("synthesis_id") or ""),
                outcome=str(request.data.get("outcome") or "completed"),
            )
        except VoiceSessionError as exc:
            return _error(exc, "speech_completion_failed")
        return Response({"ok": True, "session": VoiceSessionService.serialize(session)})


class VoiceMemoryDecisionView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def post(self, request, transcript_id):
        serializer = MemoryDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = TranscriptService.memory_decision(request.user, transcript_id, approve=serializer.validated_data["approve"])
        except VoiceSessionError as exc:
            return _error(exc, "memory_decision_failed")
        return Response({"ok": True, **result})


class VoiceSessionActivateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def post(self, request, session_id):
        serializer = VoiceActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = VoiceSessionService.activate(request.user, session_id, speaker_embedding=serializer.validated_data.get("speaker_embedding"))
        except VoiceSpeakerRejected as exc:
            return Response({"ok": False, "code": "speaker_unrecognized", "detail": str(exc), "session": VoiceSessionService.serialize(exc.session)}, status=status.HTTP_403_FORBIDDEN)
        except VoiceSessionError as exc:
            return _error(exc, "activation_failed")
        return Response({"ok": True, "session": VoiceSessionService.serialize(session)})


class SpeakerProfileView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        profile = SpeakerAwarenessService.profile(request.user)
        return Response({"ok": True, "speaker": SpeakerAwarenessService.serialize(profile)})

    def delete(self, request):
        return Response({"ok": True, "speaker": SpeakerAwarenessService.clear(request.user)})


class SpeakerEnrollmentView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def post(self, request):
        serializer = SpeakerEnrollmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = SpeakerAwarenessService.enroll(request.user, serializer.validated_data["embedding"], quality=serializer.validated_data.get("quality", 1), duration_ms=serializer.validated_data.get("duration_ms", 0))
        except VoiceSessionError as exc:
            return _error(exc, "speaker_enrollment_failed")
        return Response({"ok": True, "speaker": payload}, status=status.HTTP_201_CREATED)


class VoicePrivacyView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (JSONParser, FormParser)

    def post(self, request):
        serializer = VoicePrivacySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = {}
        if serializer.validated_data.get("clear_speaker_enrollment"):
            result["speaker"] = SpeakerAwarenessService.clear(request.user)
        if serializer.validated_data.get("clear_voice_data"):
            result["voice_data"] = VoicePrivacyService.clear_voice_data(request.user)
        if not result:
            result["retention_deleted"] = VoicePrivacyService.enforce_retention(request.user)
        return Response({"ok": True, **result})
