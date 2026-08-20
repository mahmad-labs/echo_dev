from django.urls import path

from .views import (
    AudioTranscriptionView,
    BrowserTranscriptView,
    VoiceCapabilitiesView,
    VoiceRuntimeView,
    VoiceMemoryDecisionView,
    VoiceProfileView,
    VoiceSessionDetailView,
    VoiceSessionEndView,
    VoiceSessionGreetingView,
    VoiceSessionDisableView,
    VoiceSessionShutdownView,
    VoiceSessionListCreateView,
    VoiceSessionStateView,
    VoiceSynthesisView,
    VoiceSessionActivateView,
    VoiceSpeechCompleteView,
    SpeakerProfileView,
    SpeakerEnrollmentView,
    VoicePrivacyView,
)

app_name = "voice"

urlpatterns = [
    path("capabilities/", VoiceCapabilitiesView.as_view(), name="capabilities"),
    path("runtime/", VoiceRuntimeView.as_view(), name="runtime"),
    path("profile/", VoiceProfileView.as_view(), name="profile"),
    path("sessions/", VoiceSessionListCreateView.as_view(), name="session-list-create"),
    path("sessions/<uuid:session_id>/", VoiceSessionDetailView.as_view(), name="session-detail"),
    path("sessions/<uuid:session_id>/state/", VoiceSessionStateView.as_view(), name="session-state"),
    path("sessions/<uuid:session_id>/activate/", VoiceSessionActivateView.as_view(), name="session-activate"),
    path("sessions/<uuid:session_id>/greeted/", VoiceSessionGreetingView.as_view(), name="session-greeted"),
    path("sessions/<uuid:session_id>/speech-complete/", VoiceSpeechCompleteView.as_view(), name="speech-complete"),
    path("sessions/<uuid:session_id>/disable/", VoiceSessionDisableView.as_view(), name="session-disable"),
    path("sessions/<uuid:session_id>/shutdown/", VoiceSessionShutdownView.as_view(), name="session-shutdown"),
    path("sessions/<uuid:session_id>/end/", VoiceSessionEndView.as_view(), name="session-end"),
    path("transcripts/browser/", BrowserTranscriptView.as_view(), name="browser-transcript"),
    path("transcripts/audio/", AudioTranscriptionView.as_view(), name="audio-transcription"),
    path("synthesize/", VoiceSynthesisView.as_view(), name="synthesize"),
    path("transcripts/<uuid:transcript_id>/memory/", VoiceMemoryDecisionView.as_view(), name="memory-decision"),
    path("speaker/", SpeakerProfileView.as_view(), name="speaker-profile"),
    path("speaker/enroll/", SpeakerEnrollmentView.as_view(), name="speaker-enroll"),
    path("privacy/", VoicePrivacyView.as_view(), name="privacy"),
]

