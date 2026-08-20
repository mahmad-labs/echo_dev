# Echo Voice

Echo Voice is a first-class conversation channel built on the existing Chat, Command, Tasks, Planner, Workflows, Knowledge, Documents, and Memory systems. Voice sessions do not create a separate silo: every accepted utterance becomes a normal owner-scoped conversation message and remains available in conversation history.

## Runtime modes

### Browser speech

The default profile uses browser speech recognition and browser speech synthesis when the browser exposes those APIs. Echo detects support at runtime and never reports that it is listening until `getUserMedia` succeeds and the recognition or recording path is active.

Microphone access requires HTTPS in production. Browsers permit it on `http://127.0.0.1` and `http://localhost` for local development. Permission may be `unknown`, `prompt`, `granted`, `denied`, or `unavailable`; the UI displays the real state.

When native browser recognition is unavailable, Echo records audio with `MediaRecorder` and submits it to the configured server speech-to-text provider. If neither capability is available, the user can continue the same session by typing.

### Server speech provider

Echo includes a provider-agnostic HTTP adapter. Configure:

```env
VOICE_PROVIDER_BASE_URL=https://speech.example.com
VOICE_PROVIDER_API_KEY=secret
VOICE_PROVIDER_TIMEOUT=60
VOICE_MAX_AUDIO_BYTES=26214400
VOICE_MAX_SYNTHESIS_BYTES=26214400
```

The adapter calls:

```text
POST {VOICE_PROVIDER_BASE_URL}/transcribe
POST {VOICE_PROVIDER_BASE_URL}/synthesize
```

`/transcribe` receives multipart fields `audio` and `language`, and returns JSON containing `text` plus optional `confidence`, `language`, and `duration_ms`.

`/synthesize` receives JSON containing `text`, `voice`, `language`, `format`, `speaking_rate`, `pitch`, and `volume`. It may return raw `audio/*` bytes or JSON containing `audio_base64`, `mime_type`, `format`, and optional `duration_ms`.

Custom providers can implement `SpeechToTextProvider` or `TextToSpeechProvider` and be selected with:

```env
VOICE_STT_PROVIDER_CLASS=my_package.voice.CustomSTT
VOICE_TTS_PROVIDER_CLASS=my_package.voice.CustomTTS
```

## State machine

`VoiceSession.state` is the authoritative lifecycle. The supported states are:

- `starting`
- `greeting`
- `disabled`
- `wake_word_listening`
- `active_session`
- `processing`
- `speaking`
- `sleeping`
- `shutdown`
- `error`

The browser owns only ephemeral microphone/recognition/playback resources. It reports permission/capability changes to the backend, but it does not maintain an independent authoritative listening state. Every server transition creates a `VoiceEvent` with user-safe execution metadata.

On workspace startup Echo creates or resumes one non-shutdown runtime. A new runtime enters `greeting`, the greeting marker is persisted before speech begins, and then Echo enters `wake_word_listening`. If microphone permission was already granted, wake capture can resume without prompting again. Browsers still require a user gesture before a new permission grant.

The Voice workspace exposes three lifecycle controls: **Activate Voice**, **Disable Voice**, and **Shutdown Voice**. Activate enters `active_session` immediately. Disable stops command processing and returns to `wake_word_listening`; it does not terminate the subsystem. Shutdown stops recognition/TTS, releases microphone resources, marks the runtime `shutdown`, and prevents automatic restart. That shutdown preference persists across page reloads, so Echo does not silently reopen the microphone or create a new listening runtime. Activating after shutdown explicitly creates a fresh runtime.

## Wake-word and active-session lifecycle

Wake-word mode accepts only a validated leading “Echo”/“Hey Echo” acoustic activation. Ordinary nearby speech is ignored before Agent Manager. Wake detections use a configurable confidence threshold and short duplicate-detection cooldown. After activation, commands do not require the wake word. Valid user activity resets the inactivity deadline, capped by the profile at 60 minutes. One hour without accepted activity returns the runtime to `wake_word_listening` rather than shutting it down.

After a normal spoken response, STT resumes automatically. Silence, `no-speech`, recoverable recognition endings, and temporary recognition interruptions restart capture without creating commands. During TTS Echo suspends recognition and releases/gates the microphone so its own output is not treated as user speech; capture resumes after output completes. Intentional wake-word or speaker rejections are explicitly restored to the correct wake/active capture state so they cannot leave the runtime stuck in `processing`. Long computer-use operations remain independent, allowing Voice to resume while the operation continues.

Speaker identification is optional and disabled by default. Enrollment stores normalized derived speaker vectors rather than raw enrollment audio. When enabled, an enrolled speaker representation is probabilistically verified for wake and acoustic command turns. Unrecognized speech can be ignored according to profile policy, but speaker matching is not treated as strong authentication and never bypasses approval requirements. Deployments can configure `VOICE_SPEAKER_PROVIDER_CLASS` for a server-side speaker embedding implementation; browser spectral fingerprints remain a lower-assurance fallback.

The browser uses speech-recognition events or VAD depending on the STT path, requests echo cancellation/noise suppression where available, and keeps one singleton client runtime per page. Raw microphone audio is retained only when the user explicitly enables audio saving. Voice-history and transcript-retention controls are exposed in the Voice workspace, and speaker enrollment can be cleared independently.

## Conversation and command integration

A voice turn is processed by `AgentManagerOrchestrator`, the same orchestration entry point used by the homepage text composer and workflow agent bridge. High-confidence commands use deterministic services for tasks, daily plans, projects, workflows, research, document analysis, agents, navigation, and knowledge retrieval. Ambiguous conversational requests use the configured OpenAI-compatible provider. If a provider is missing, the request and conversation are still saved and the UI shows the required configuration instead of inventing a response.

## Memory policy

Voice transcripts are searchable conversation context. Permanent memory is opt-in by default. Commands such as “remember that…” create a pending memory candidate. Approval creates an owner-scoped `Memory` record linked to the transcript. Rejection leaves the source transcript intact but prevents permanent memory creation.

The profile option `memory_requires_approval` can be disabled by the user. Echo never changes that setting implicitly.

## Audio retention

Audio is not retained by default. When `save_audio` is disabled, server-generated speech assets expire automatically. Run scheduled cleanup through Celery beat or manually:

```bash
python manage.py cleanup_voice
```

The command removes expired audio and returns expired active sessions to wake-word mode; explicit shutdown remains user-controlled. Treat retained audio as sensitive user content and apply deployment-specific privacy and retention policies.

## API

- `GET /api/v1/voice/capabilities/`
- `GET /api/v1/voice/runtime/`
- `GET|PATCH /api/v1/voice/profile/`
- `GET|POST /api/v1/voice/sessions/`
- `GET /api/v1/voice/sessions/<uuid>/`
- `POST /api/v1/voice/sessions/<uuid>/state/`
- `POST /api/v1/voice/sessions/<uuid>/greeted/`
- `POST /api/v1/voice/sessions/<uuid>/activate/`
- `POST /api/v1/voice/sessions/<uuid>/disable/`
- `POST /api/v1/voice/sessions/<uuid>/shutdown/`
- `POST /api/v1/voice/sessions/<uuid>/end/` (backward-compatible explicit shutdown)
- `POST /api/v1/voice/transcripts/browser/`
- `POST /api/v1/voice/transcripts/audio/`
- `POST /api/v1/voice/synthesize/`
- `POST /api/v1/voice/transcripts/<uuid>/memory/`

The Voice API intentionally does not expose unrestricted generic CRUD endpoints for sessions, events, transcripts, or audio. State transitions, ownership, provider selection, retention, and memory approval must pass through the domain services.

## Browser support and accessibility

The interface is keyboard accessible, announces live state through ARIA live regions, traps focus inside the voice dialog, restores focus when closed, supports interruption, and respects reduced-motion preferences. Speech recognition availability varies by browser. Typed continuation remains available in every supported browser.
