# Computer Control

Echo Computer Control is a general environment-control layer shared by the Browser and Computer agents. It is not website-specific and contains no YouTube-specific execution API.

## Evidence hierarchy

Environment understanding uses the strongest available evidence first:

1. browser DOM and accessibility structure for controlled browser sessions;
2. operating-system UI/accessibility tree for configured desktop providers;
3. structured browser/window state and visible text;
4. a real screenshot;
5. OCR/vision interpretation of that screenshot when configured.

Targets are resolved dynamically from current evidence. Pixel coordinates are not hard-coded for named controls. Explicit user-supplied coordinates are treated as explicit coordinates; named targets are resolved through UI structure first and screenshot vision only as a fallback.

## Browser environment

The Selenium-backed browser environment supports generic navigation, back/forward/refresh, tabs, click/double-click/right-click, type, keyboard input, scroll/scroll-until, find, select, hover, drag, focus, waits, DOM inspection, accessibility inspection, screenshots, page answering, and permitted media analysis. Each significant action captures pre- and post-action observations and verifies the result before success is reported.

`ComputerUseOperation` is the durable asynchronous task identity for multi-step browser work. It stores plan steps, progress, current tool/operation, result, error, cancellation state, approval state, and completion timestamps. Independent requests remain responsive while browser work executes in Celery or the configured local background executor.

## Desktop environment

`LocalDesktopBackend` provides authorized mouse/keyboard/screenshot/window operations through standard Python libraries. `ComputerObservationService` persists screenshots, current window data, cursor/viewport state, configured UI-tree evidence, OCR/vision evidence, and a content hash. `ComputerActionService` performs one authorized action and records a post-action observation used for verification.

The OS UI-tree adapter is replaceable through `ECHO_COMPUTER_UI_TREE_PROVIDER_CLASS`. Screenshot OCR/vision uses the configured vision-capable AI provider. This lets platform-specific accessibility adapters evolve independently from Agent Manager and Tool Manager.

## Local applications, system locations, and windows

Local computer commands are resolved before browser/search intent. `ApplicationDiscoveryService` discovers applications from operating-system metadata (`.desktop` entries on Linux, application bundles on macOS, Start Menu metadata on Windows) with PATH lookup as a direct-query fallback. `ApplicationLauncherService` launches only a resolved local application and reports success only when process or matching window evidence verifies the launch. Commands such as “Open Firefox” therefore use `computer.launch_application`; they are never converted into web searches.

`SystemLocationResolver` maps owner-safe natural locations such as Trash, Downloads, Documents, Desktop, Home, Pictures, Videos, Music, File System, and the Echo project to native OS file-manager actions. Arbitrary paths are limited to the user's home and Echo installation roots unless a stronger file-system permission layer is added. `DesktopWindowService` lists and identifies the active window, focuses existing windows, and supports verified minimize/maximize/restore plus confirmation-gated close.

The central Tool Registry exposes `computer.list_applications`, `computer.launch_application`, `computer.application_status`, `computer.open_path`, `computer.list_windows`, `computer.get_active_window`, `computer.focus_window`, and `computer.capture_screen` alongside the existing mouse/keyboard tools. Agent Manager receives runtime tool availability from that same registry; unavailable local desktop capabilities are not advertised as executable.

## Observe-act-observe-verify

Browser and desktop execution follow the same contract:

`observe → plan → act → observe result → verify → continue/replan`

Echo never reports a click, navigation, scroll, or media-processing action as successful solely because an input event was sent. Unverified actions are persisted as unverified/failed evidence and surfaced truthfully.

## Human intervention and approvals

CAPTCHA, MFA, login/security verification, and permission blockers pause automation and identify required human intervention. They are never bypassed. Sensitive/external/destructive actions use the approval boundary registered by Tool Manager. Browser operation resume grants approval only to the current waiting step; it does not create a blanket future approval.

## Browser/Computer sharing

Agent Context can contain both the latest browser and desktop observations when an agent declares observation access. This allows Browser and Computer agents to share structured state through Agent Manager without importing each other's private services or duplicating tools.

## Media intelligence

Media processing uses only permitted accessible evidence such as captions/text tracks, accessible live text, permitted rendered-audio capture, and bounded visual frames. DRM and access controls are not bypassed. `MediaUnderstanding` records evidence and confidence; follow-up answers are limited to content Echo actually processed.
