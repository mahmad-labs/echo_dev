from django.contrib.auth import get_user_model
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from echo.apps.chat.models import Conversation, Message
from echo.apps.memory.models import Memory
from echo.apps.tasks.models import Task

from .models import SpeechSynthesis, SpeechTranscript, VoiceEvent, VoiceProfile, VoiceSession
from .services import SpeakerAwarenessService, VoiceSessionService


class DummySpeakerProvider:
    def embedding(self, audio, *, mime_type=""):
        return [3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


@override_settings(AI_PROVIDER_BASE_URL="", AI_PROVIDER_API_KEY="", AI_PROVIDER_MODEL="")
class VoiceAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="voice@example.com",
            password="VoicePassword!2026",
        )
        cls.other = get_user_model().objects.create_user(
            email="other-voice@example.com",
            password="VoicePassword!2026",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def start_session(self):
        response = self.client.post(
            reverse("voice:session-list-create"),
            {"input_mode": "mixed", "language": "en-US"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data["session"]

    def test_capabilities_and_profile_are_real_and_owner_scoped(self):
        response = self.client.get(reverse("voice:capabilities"))
        self.assertEqual(response.status_code, 200)
        identifiers = {item["identifier"] for item in response.data["providers"]}
        self.assertIn("browser", identifiers)
        profile = VoiceProfile.objects.get(owner=self.user, is_default=True)
        self.assertEqual(response.data["profile"]["id"], str(profile.pk))

    def test_starting_voice_creates_a_normal_chat_conversation(self):
        session_payload = self.start_session()
        session = VoiceSession.objects.get(pk=session_payload["id"])
        self.assertEqual(session.owner, self.user)
        self.assertEqual(session.input_mode, "mixed")
        self.assertIsNotNone(session.conversation)
        self.assertEqual(session.conversation.conversation_type, "voice")
        self.assertTrue(VoiceEvent.objects.filter(session=session, event_type="session_started").exists())

    def test_typed_voice_turn_creates_task_transcript_messages_and_synthesis(self):
        session = self.start_session()
        response = self.client.post(
            reverse("voice:browser-transcript"),
            {
                "session_id": session["id"],
                "text": "Create a task to review the Echo voice integration tomorrow",
                "provider": "typed",
                "confidence": 1,
                "language": "en-US",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["response"]["route"], "tasks.create")
        self.assertTrue(Task.objects.filter(owner=self.user, title__icontains="review the Echo voice integration").exists())
        transcript = SpeechTranscript.objects.get(pk=response.data["transcript"]["id"])
        self.assertEqual(transcript.conversation_id, VoiceSession.objects.get(pk=session["id"]).conversation_id)
        self.assertEqual(transcript.command_route, "tasks.create")
        self.assertTrue(Message.objects.filter(owner=self.user, conversation=transcript.conversation, role="user").exists())
        self.assertTrue(Message.objects.filter(owner=self.user, conversation=transcript.conversation, role="assistant").exists())
        self.assertTrue(SpeechSynthesis.objects.filter(session_id=session["id"], provider="browser", status="ready").exists())

    def test_voice_memory_requires_explicit_approval_by_default(self):
        session = self.start_session()
        response = self.client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Echo, remember that Echo uses owner-scoped context", "provider": "browser"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        transcript = SpeechTranscript.objects.get(pk=response.data["transcript"]["id"])
        self.assertEqual(transcript.memory_status, SpeechTranscript.MemoryStatus.PENDING)
        self.assertFalse(Memory.objects.filter(owner=self.user, source_type="voice_transcript").exists())

        approval = self.client.post(
            reverse("voice:memory-decision", kwargs={"transcript_id": transcript.pk}),
            {"approve": True},
            format="json",
        )
        self.assertEqual(approval.status_code, 200)
        transcript.refresh_from_db()
        self.assertEqual(transcript.memory_status, SpeechTranscript.MemoryStatus.APPROVED)
        self.assertTrue(Memory.objects.filter(pk=approval.data["memory_id"], owner=self.user).exists())

    def test_session_and_transcript_endpoints_reject_other_owners(self):
        session = self.start_session()
        other_client = APIClient()
        other_client.force_authenticate(self.other)
        detail = other_client.get(reverse("voice:session-detail", kwargs={"session_id": session["id"]}))
        self.assertEqual(detail.status_code, 404)
        transcript = other_client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Show my active tasks", "provider": "browser"},
            format="json",
        )
        self.assertEqual(transcript.status_code, 404)
        self.assertFalse(Conversation.objects.filter(owner=self.other, title__icontains="Voice conversation").exists())

    def test_runtime_greets_once_then_enters_wake_word_mode(self):
        first = self.client.get(reverse("voice:runtime"))
        self.assertEqual(first.status_code, 200)
        session = first.data["session"]
        self.assertEqual(session["state"], VoiceSession.State.GREETING)
        self.assertTrue(session["greeting_pending"])
        marked = self.client.post(reverse("voice:session-greeted", kwargs={"session_id": session["id"]}), {}, format="json")
        self.assertEqual(marked.status_code, 200)
        self.assertEqual(marked.data["session"]["state"], VoiceSession.State.WAKE_WORD_LISTENING)
        second = self.client.get(reverse("voice:runtime"))
        self.assertFalse(second.data["session"]["greeting_pending"])
        self.assertEqual(second.data["session"]["id"], session["id"])

    def test_activate_disable_shutdown_and_restart_are_authoritative_transitions(self):
        runtime = self.client.get(reverse("voice:runtime")).data["session"]
        self.client.post(reverse("voice:session-greeted", kwargs={"session_id": runtime["id"]}), {}, format="json")
        activated = self.client.post(reverse("voice:session-activate", kwargs={"session_id": runtime["id"]}), {}, format="json")
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.data["session"]["state"], VoiceSession.State.ACTIVE_SESSION)
        self.assertGreater(activated.data["session"]["remaining_seconds"], 0)
        disabled = self.client.post(reverse("voice:session-disable", kwargs={"session_id": runtime["id"]}), {}, format="json")
        self.assertEqual(disabled.data["session"]["state"], VoiceSession.State.WAKE_WORD_LISTENING)
        shutdown = self.client.post(reverse("voice:session-shutdown", kwargs={"session_id": runtime["id"]}), {}, format="json")
        self.assertEqual(shutdown.data["session"]["state"], VoiceSession.State.SHUTDOWN)
        self.assertFalse(shutdown.data["session"]["microphone_enabled"])
        persisted = self.client.get(reverse("voice:runtime")).data["session"]
        self.assertEqual(persisted["id"], runtime["id"])
        self.assertEqual(persisted["state"], VoiceSession.State.SHUTDOWN)
        restarted = self.start_session()
        self.assertNotEqual(restarted["id"], runtime["id"])
        self.assertEqual(restarted["state"], VoiceSession.State.STARTING)
        activated_again = self.client.post(reverse("voice:session-activate", kwargs={"session_id": restarted["id"]}), {}, format="json")
        self.assertEqual(activated_again.data["session"]["state"], VoiceSession.State.ACTIVE_SESSION)

    def test_legacy_browser_state_reports_map_into_authoritative_state_machine(self):
        session_payload = self.start_session()
        session_id = session_payload["id"]
        VoiceSessionService.activate(self.user, session_id)
        for state, expected in (("listening", VoiceSession.State.ACTIVE_SESSION), ("processing", VoiceSession.State.PROCESSING), ("thinking", VoiceSession.State.PROCESSING), ("executing", VoiceSession.State.PROCESSING), ("speaking", VoiceSession.State.SPEAKING), ("waiting", VoiceSession.State.ACTIVE_SESSION)):
            response = self.client.post(reverse("voice:session-state", kwargs={"session_id": session_id}), {"state": state, "permission": "granted"}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["session"]["state"], expected)

    def test_session_end_is_backward_compatible_shutdown(self):
        session = self.start_session()
        ended = self.client.post(reverse("voice:session-end", kwargs={"session_id": session["id"]}), {}, format="json")
        self.assertEqual(ended.status_code, 200)
        self.assertEqual(ended.data["session"]["state"], VoiceSession.State.SHUTDOWN)
        self.assertEqual(VoiceSession.objects.get(pk=session["id"]).status, "completed")

    def test_generic_voice_crud_route_is_not_exposed(self):
        response = self.client.get("/api/v1/voice/voiceevent/")
        self.assertEqual(response.status_code, 404)

    def test_wake_word_mode_ignores_ordinary_acoustic_conversation(self):
        session = self.start_session()
        response = self.client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Open Google", "provider": "browser"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ignored"])
        self.assertEqual(response.data["reason"], "wake_word_required")
        self.assertEqual(response.data["session"]["state"], VoiceSession.State.WAKE_WORD_LISTENING)
        self.assertFalse(SpeechTranscript.objects.filter(session_id=session["id"]).exists())
        stored = VoiceSession.objects.get(pk=session["id"])
        self.assertEqual(stored.mode, VoiceSession.Mode.WAKE_WORD)
        self.assertEqual(stored.state, VoiceSession.State.WAKE_WORD_LISTENING)

    def test_echo_wake_word_starts_bounded_active_session(self):
        session = self.start_session()
        response = self.client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Echo", "provider": "browser"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        active = VoiceSession.objects.get(pk=session["id"])
        self.assertEqual(active.mode, VoiceSession.Mode.ACTIVE)
        self.assertEqual(response.data["reason"], "wake_activated")
        self.assertIsNotNone(active.active_expires_at)
        self.assertLessEqual((active.active_expires_at - active.active_started_at).total_seconds(), 3600)
        self.assertFalse(SpeechTranscript.objects.filter(session_id=session["id"]).exists())

    def test_expired_active_session_returns_to_wake_mode_and_does_not_execute_plain_speech(self):
        session = self.start_session()
        record = VoiceSession.objects.get(pk=session["id"])
        record.mode = VoiceSession.Mode.ACTIVE
        record.state = VoiceSession.State.ACTIVE_SESSION
        record.active_started_at = timezone.now() - timedelta(minutes=61)
        record.active_expires_at = timezone.now() - timedelta(seconds=1)
        record.save()
        before = Task.objects.filter(owner=self.user).count()
        response = self.client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Create a task to ignore this", "provider": "browser"},
            format="json",
        )
        self.assertTrue(response.data["ignored"])
        self.assertEqual(response.data["reason"], "wake_word_required")
        self.assertEqual(Task.objects.filter(owner=self.user).count(), before)
        record.refresh_from_db()
        self.assertEqual(record.mode, VoiceSession.Mode.WAKE_WORD)

    def test_valid_activity_resets_one_hour_inactivity_deadline(self):
        session = self.start_session()
        record = VoiceSessionService.activate(self.user, session["id"])
        old_expiry = record.active_expires_at
        record.last_activity_at = timezone.now() - timedelta(minutes=20)
        record.active_expires_at = timezone.now() + timedelta(minutes=1)
        record.save(update_fields=["last_activity_at", "active_expires_at", "updated_at"])
        touched = VoiceSessionService.touch_activity(record)
        self.assertGreater(touched.active_expires_at, old_expiry - timedelta(seconds=5))
        self.assertLessEqual((touched.active_expires_at - touched.last_activity_at).total_seconds(), 3600)

    @override_settings(VOICE_WAKE_WORD_MIN_CONFIDENCE=0.75)
    def test_low_confidence_wake_word_does_not_activate(self):
        session = self.start_session()
        response = self.client.post(reverse("voice:browser-transcript"), {"session_id": session["id"], "text": "Echo", "provider": "browser", "confidence": 0.3}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ignored"])
        self.assertEqual(response.data["reason"], "wake_word_required")
        record = VoiceSession.objects.get(pk=session["id"])
        self.assertEqual(record.mode, VoiceSession.Mode.WAKE_WORD)

    @override_settings(VOICE_WAKE_WORD_COOLDOWN_SECONDS=30)
    def test_recent_wake_activation_marker_rejects_duplicate_wake_detection(self):
        session = self.start_session()
        record = VoiceSession.objects.get(pk=session["id"])
        record.configuration = {**(record.configuration or {}), "last_wake_activation_at": timezone.now().isoformat()}
        record.save(update_fields=["configuration", "updated_at"])
        response = self.client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Echo", "provider": "browser", "confidence": 0.95},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ignored"])
        self.assertEqual(response.data["reason"], "wake_word_required")
        record.refresh_from_db()
        self.assertEqual(record.state, VoiceSession.State.WAKE_WORD_LISTENING)


    def test_probabilistic_speaker_enrollment_filters_unrecognized_acoustic_commands(self):
        vector = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        for _ in range(3):
            SpeakerAwarenessService.enroll(self.user, vector, quality=1.0, duration_ms=1200)
        profile = VoiceProfile.objects.get(owner=self.user, is_default=True)
        profile.speaker_identification_enabled = True
        profile.reject_unrecognized_speakers = True
        profile.save(update_fields=["speaker_identification_enabled", "reject_unrecognized_speakers", "updated_at"])
        session = self.start_session()
        wake = self.client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Echo", "provider": "browser", "speaker_embedding": vector},
            format="json",
        )
        self.assertFalse(wake.data.get("ignored", False))
        active = VoiceSession.objects.get(pk=session["id"])
        self.assertEqual(active.mode, VoiceSession.Mode.ACTIVE)
        other_speaker = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        response = self.client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Show my active tasks", "provider": "browser", "speaker_embedding": other_speaker},
            format="json",
        )
        self.assertTrue(response.data["ignored"])
        self.assertEqual(response.data["reason"], "speaker_unrecognized")
        self.assertEqual(response.data["session"]["state"], VoiceSession.State.ACTIVE_SESSION)
        active.refresh_from_db()
        self.assertEqual(active.state, VoiceSession.State.ACTIVE_SESSION)

    def test_browser_tts_completion_returns_server_to_active_session(self):
        session = self.start_session()
        VoiceSessionService.activate(self.user, session["id"])
        speaking = self.client.post(
            reverse("voice:session-state", kwargs={"session_id": session["id"]}),
            {"state": "speaking", "permission": "granted"},
            format="json",
        )
        self.assertEqual(speaking.data["session"]["state"], VoiceSession.State.SPEAKING)
        completed = self.client.post(
            reverse("voice:speech-complete", kwargs={"session_id": session["id"]}),
            {"outcome": "completed"},
            format="json",
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["session"]["state"], VoiceSession.State.ACTIVE_SESSION)

    def test_stale_tts_completion_cannot_release_a_newer_speaking_state(self):
        session = self.start_session()
        record = VoiceSessionService.activate(self.user, session["id"])
        record = VoiceSessionService.transition(self.user, record.pk, VoiceSession.State.SPEAKING, force=True)
        old = SpeechSynthesis.objects.create(owner=self.user, session=record, name="old", title="Old", status="ready", text="old", provider="browser")
        newer = SpeechSynthesis.objects.create(owner=self.user, session=record, name="new", title="New", status="ready", text="new", provider="browser")
        record.configuration = {**(record.configuration or {}), "active_synthesis_id": str(newer.pk)}
        record.save(update_fields=["configuration", "updated_at"])
        completed = self.client.post(
            reverse("voice:speech-complete", kwargs={"session_id": session["id"]}),
            {"synthesis_id": str(old.pk), "outcome": "completed"},
            format="json",
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["session"]["state"], VoiceSession.State.SPEAKING)
        record.refresh_from_db()
        self.assertEqual(record.configuration.get("active_synthesis_id"), str(newer.pk))

    def test_browser_tts_completion_returns_server_to_wake_word_mode(self):
        session = self.start_session()
        record = VoiceSession.objects.get(pk=session["id"])
        record.mode = VoiceSession.Mode.WAKE_WORD
        record.state = VoiceSession.State.SPEAKING
        record.save(update_fields=["mode", "state", "updated_at"])
        completed = self.client.post(
            reverse("voice:speech-complete", kwargs={"session_id": session["id"]}),
            {"outcome": "completed"},
            format="json",
        )
        self.assertEqual(completed.data["session"]["state"], VoiceSession.State.WAKE_WORD_LISTENING)

    def test_speaker_status_does_not_claim_enrollment_before_minimum_samples(self):
        self.start_session()
        profile = VoiceProfile.objects.get(owner=self.user, is_default=True)
        profile.speaker_identification_enabled = True
        profile.save(update_fields=["speaker_identification_enabled", "updated_at"])
        response = self.client.get(reverse("voice:speaker-profile"))
        self.assertEqual(response.status_code, 200)
        speaker = response.data["speaker"]
        self.assertFalse(speaker["enrolled"])
        self.assertGreaterEqual(speaker["minimum_samples"], 1)
        self.assertIn(speaker["status"], {"NOT_ENROLLED", "ENROLLING", "NOT_CONFIGURED"})

    def test_typed_input_remains_available_in_wake_word_mode(self):
        session = self.start_session()
        response = self.client.post(
            reverse("voice:browser-transcript"),
            {"session_id": session["id"], "text": "Show my active tasks", "provider": "typed"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data.get("ignored", False))
        self.assertEqual(response.data["response"]["route"], "tasks.list")


    @override_settings(VOICE_SPEAKER_PROVIDER_CLASS="echo.apps.voice.tests.DummySpeakerProvider")
    def test_configured_server_speaker_provider_returns_normalized_derived_embedding(self):
        vector = SpeakerAwarenessService.embedding_from_audio(b"temporary-audio-bytes", mime_type="audio/webm")
        self.assertEqual(len(vector), 8)
        self.assertAlmostEqual(vector[0], 0.6, places=4)
        self.assertAlmostEqual(vector[1], 0.8, places=4)

