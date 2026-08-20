# Echo Computer Use

Echo's computer-use subsystem is a website-neutral observe → act → observe → verify runtime. It extends the existing Tool Manager, Command Service, Chat, Voice, Notifications, AI provider, and Celery infrastructure rather than introducing a second command system.

## Runtime contract

Text and voice requests enter `EchoCommandService`. Browser-capable requests are converted into an evidence-driven plan by `ComputerUsePlanner`, then executed through named Tool Manager tools. Every mutating browser action captures a pre-action observation and a post-action observation. Echo only reports success when `BrowserActionService.verify()` can support it from the action result and observed state.

Long operations are represented by `ComputerUseOperation` records with a durable ID, status, current step, current tool, progress, result, attention requirement, error, and cancellation flag. With Redis/Celery configured they run in Celery. Without Redis, Echo uses a bounded local thread executor so a browser workflow does not hold the initiating Django request open.

## Browser environment

The built-in environment is `browser.selenium`, registered through `ComputerEnvironmentRegistry`. The registry is the extension boundary for future explicitly authorized desktop, file, or terminal environments; Echo does not advertise or simulate environments that have not been registered.

Install a current Chrome/Chromium, Edge, or Firefox browser on the machine that runs the browser environment. Selenium Manager resolves a compatible driver when possible. A remote Selenium endpoint can be used with `ECHO_BROWSER_REMOTE_URL` when the browser is intentionally hosted elsewhere.

The controlled browser supports generic tools including navigation, tabs, click/double-click/context click, text entry, key presses, scrolling, find, select, hover, drag, focus, structured page inspection, accessibility inspection, screenshot capture, guarded downloads, generic HTML media controls, page questions, search, and scroll-until-find.

There is no YouTube-specific automation service. Website names such as YouTube or GitHub are only destination aliases for natural-language navigation.

## Observation hierarchy

Echo prefers evidence in this order:

1. visible DOM and accessibility metadata;
2. structured browser state, page text, element metadata, viewport and media state;
3. current viewport screenshot;
4. configured vision-model interpretation when structure alone is ambiguous.

Visible interactive elements receive ephemeral `data-echo-node` identifiers in the current observation. Vision can select only one of those observed IDs; it cannot invent a pixel coordinate. Screenshots are stored as owner-scoped `BrowserObservation` evidence and are secondary to structured data.

## Security and human intervention

Browser navigation validates public HTTP/HTTPS destinations by default. Embedded credentials, loopback, private, link-local, multicast, reserved and unspecified destinations are rejected unless a deployment explicitly opts in. Echo also validates the observed destination after navigation and stops continued execution if a redirected page crosses the configured network boundary.

CAPTCHA, human-verification pages, credential forms, MFA/security-code challenges, and unsupported security boundaries pause an operation with `waiting_user`. Echo never attempts to bypass them. Consequential controls such as purchasing, sending/publishing, transferring, deleting accounts, or other externally visible actions require an explicit resume/approval before the current step can execute. The approval applies to that step only.

Downloads are limited to the browser session's controlled download directory and require a page-exposed download plus confirmation when appropriate. Echo does not bypass DRM, access controls, rate limits, authentication, or platform restrictions.

## Screen and page understanding

`browser.get_page`, `browser.get_dom`, `browser.get_accessibility_tree`, `browser.get_screenshot`, `browser.find`, and `browser.answer_page` expose current evidence to the orchestrator. Requests such as “What is this?”, “What does this page say?”, “Find the login button”, and “What is the error?” are answered from live page evidence. If the evidence or configured AI capability is insufficient, Echo says so instead of fabricating an answer.

## Media intelligence

`media.analyze` processes only content Echo can legitimately access in the controlled browser. It prefers active text-track cues and accessible caption/live text. If captions are insufficient and a server-side speech-to-text provider is configured, Echo can use the browser's standard `HTMLMediaElement.captureStream()` + `MediaRecorder` capability to capture short rendered-audio samples from accessible, non-encrypted media and transcribe those samples. Encrypted-media elements and pages that do not expose capture capability are left untouched. When a vision-capable AI provider is configured, Echo may also sample a bounded number of rendered frames across an accessible HTML media timeline and describe only visible content. It never claims that audio was processed unless an actual `audio_transcription` evidence record exists.

`MediaUnderstanding` persists the source URL, accessible transcript, visual notes, summary, evidence list, confidence, and coverage metadata. Follow-up questions are answered only from that stored evidence. If Echo did not obtain enough content, it returns an insufficient-evidence response.

## Continuous voice integration

Voice and text share `EchoCommandService` and therefore the same Tool Manager and computer-use operations. A voice request may start a long computer-use operation, receive a short acknowledgement, resume microphone listening, and later receive the durable completion or attention result. Browser recognition and TTS are gated so Echo does not feed its own speech back as a user command.

Voice states include `idle`, `listening`, `processing`, `thinking`, `executing`, `speaking`, `waiting`, `paused`, `error`, `stopped`, and `ended`. Normal continuous operation returns to listening after the spoken response. Recoverable recognition endings and silence restart the recognition cycle; explicit stop commands and the Stop Voice control do not.

## API

- `GET|POST /api/v1/internet/computer/sessions/`
- `POST /api/v1/internet/computer/sessions/<uuid>/end/`
- `POST /api/v1/internet/computer/observe/`
- `POST /api/v1/internet/computer/action/`
- `GET|POST /api/v1/internet/computer/operations/`
- `GET /api/v1/internet/computer/operations/<uuid>/`
- `POST /api/v1/internet/computer/operations/<uuid>/cancel/`
- `POST /api/v1/internet/computer/operations/<uuid>/resume/`
- `POST /api/v1/internet/computer/media/analyze/`
- `POST /api/v1/internet/computer/media/question/`

The Browser workspace renders real session, observation, operation, action and media records and polls only the operation endpoint while that workspace is present. Operations sharing one mutable browser session are serialized; unrelated Echo work remains concurrent. The media-analyze endpoint also returns a durable operation (`202 Accepted`) rather than blocking for transcription/vision/model work.
