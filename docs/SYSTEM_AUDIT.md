# Echo System Audit and Integration Repair

This release audits and repairs the existing Echo project in place. The objective is one execution architecture: authenticated user input enters the Agent Manager, agents discover capabilities from one Tool Registry, every executable tool crosses one Tool Executor boundary, and structured results return to agents, Voice, and the workspace.

## Root cause repaired

The reported `Unknown handler 'browser.open_url'` failure was caused by inconsistent registration lifecycle. Browser handlers existed in source, but their registration depended on incidental imports while other tool families were registered differently. Planner and agent code could therefore reference a valid implementation before the Tool Manager knew it existed.

Echo now uses `echo.apps.tool_manager.registry.ToolRegistry` as the single explicit bootstrap path. Core, browser, desktop, agent, memory, and knowledge tool families register through that provider list. Registration is idempotent, duplicate conflicts are rejected, provider failures remain visible, and discovery lazily retries incomplete bootstrap attempts.

## Authoritative tool contract

`ToolDefinition` is the authoritative executable contract. Every registered tool defines its name, description, category, input/output schemas, handler, permissions, runtime availability, execution mode, timeout, risk, confirmation policy, cancellation support, allowed agents, and source module.

All execution paths use `ToolExecutor`: agents, workflows, Browser Agent, Computer Agent, direct browser/desktop APIs, domain tools, and the generic tool API. Persisted `Tool` rows can add restrictions but cannot weaken registry permissions. Per-tool execution grants can satisfy only the generic `tools.execute` gate and cannot bypass domain permissions such as `memory.write` or `knowledge.read`.

Unknown tools return a structured `unknown_handler` error with the currently registered handlers. Runtime discovery separately exposes only handlers whose availability probes pass, so AI/browser planning is not given unavailable capabilities.

## Browser and computer control

Browser and desktop control remain separate environments with a shared execution contract.

Browser tools use DOM/accessibility evidence before visual fallback, then perform observe → act → observe → verify. Navigation is URL validated and subject to existing SSRF/network policy. CAPTCHA, login, MFA, permission, and consequential-action boundaries pause rather than being bypassed.

Desktop tools use screen capture, active-window information, UI-tree providers where configured, and screenshot vision/OCR fallback. Mouse and keyboard actions resolve current targets before input and preserve confirmation requirements for consequential input.

`browser.execute_allowed_action` no longer maintains a duplicate hard-coded browser action list. It resolves the requested browser capability from the authoritative registry and delegates through the same Tool Executor.

## Agent integration

The Agent Registry remains the authoritative agent catalog. Agent definitions expose capabilities, required tools, permissions, scoped context, schemas, handler availability, and runtime tool availability. Memory and Knowledge agents explicitly declare their read permissions while their write operations continue to enforce stronger write permissions at tool execution time.

Voice and text enter `AgentManagerOrchestrator`. Browser, Computer, Memory, Knowledge, Planner, Project, Task, Document, Workflow, and Chat work is recorded through the existing parent/child `AgentTask` graph and structured `AgentCommunication` records. Workflow delegation uses the registry-backed `agent.execute` bridge.

## Memory and knowledge

Memory and Knowledge continue to use their existing owner-scoped services and database models. Registry-backed `memory.*` and `knowledge.*` tools are adapters over those central services rather than duplicate subsystems. Context assembly may perform scoped read-only retrieval directly, while executable agent actions cross the Tool Manager boundary.

## Validation commands

The project includes three deployment diagnostics:

```bash
python manage.py validate_tools
python manage.py validate_agents
python manage.py echo_health
```

`validate_tools` checks registration/provider failures, duplicate definitions, schemas, persisted orphan handlers, static planner/agent references, permissions, and agent access declarations. It displays runtime availability for every tool.

`validate_agents` checks registered agents, required tools, permissions, agent/tool access consistency, persisted built-in records, and runtime availability warnings.

`echo_health` performs actual database/cache probes plus registry, agent, vector, browser startup, desktop capture, memory, knowledge, planner, workflow, task, notification, Voice, AI, STT, and TTS configuration checks. Optional device/provider unavailability is reported as degraded rather than fabricated as healthy.

## Release invariants

The dependency-free release validator checks 24 applications, 189 migration model states, 238 compatibility endpoints, source/migration parity, registry references, templates, SVG assets, CSS/JavaScript syntax contracts, and forbidden unfinished-production markers. `validate_echo` has also been corrected to expect the current 189-model project rather than the obsolete 178-model invariant.

The intended installed-environment release sequence is:

```bash
python scripts/static_validate.py
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py validate_echo
python manage.py validate_tools
python manage.py validate_agents
python manage.py echo_health
python manage.py test
```

## Universal local-vs-web intent routing

The Agent Manager now runs a deterministic universal-intent classifier before general model interpretation. Explicit local applications and system locations route to the Computer Agent; exact website aliases and URLs route to Browser; explicit search language routes to web/site search; contextual commands use the most recently verified browser or desktop environment. An unknown `Open X` request is not silently converted into Google search. Ambiguous targets such as `Open Python` produce a clarification request.

Application discovery is operating-system aware: Linux desktop entries and PATH executables, Windows Start Menu metadata, and macOS application bundles are normalized behind one `ApplicationDiscoveryService`. `ApplicationLauncherService` and `SystemLocationResolver` execute without shell interpolation and return verified structured outcomes. Successful local launches update Echo's desktop-session context so follow-up commands such as `scroll down`, `click that`, or `type ...` remain in the environment the user actually opened.

## Authoritative continuous Voice lifecycle

Voice now uses one persisted state machine: `STARTING`, `GREETING`, `DISABLED`, `WAKE_WORD_LISTENING`, `ACTIVE_SESSION`, `PROCESSING`, `SPEAKING`, `SLEEPING`, `SHUTDOWN`, and `ERROR`. The browser client reflects these states instead of inventing a second lifecycle. Startup greeting is marked durable before audio playback to prevent duplicate greetings after reload. Activate starts an active command session; Disable returns to wake-word listening; Shutdown releases voice resources and does not auto-restart; the shutdown preference persists across page reloads until an explicit new session/Activate action clears it.

Active voice uses an inactivity deadline capped at 60 minutes and renews the deadline on valid user activity. Expiry transitions back to wake-word listening rather than terminating Voice. Bare wake-word input activates Voice without creating a conversational transcript or agent task. Low-confidence/cooldown checks reduce false activation, rejected acoustic input recovers to the correct wake/active state, and TTS suspends microphone capture before resuming the authoritative post-speech state so Echo's own output is not interpreted as a user command.

The workspace exposes real Activate Voice, Disable Voice, Shutdown Voice, and Stop Task controls. Current state, remaining session time, microphone/speaker state, active agent/task/tool, and operation metadata are derived from the same backend records used for execution.

## Compound local-computer task routing

This release also closes the combined-command routing gap. The environment is resolved before secondary verbs are interpreted, so a request such as `Open Firefox on my computer and search Django 5.2 documentation` is one `computer_task` with `environment=local_computer`, `application=Firefox`, an application-launch step, and a browser-search-in-application step. The later word `search` cannot reclassify the objective as generic web search.

`ComputerTaskPlanner` and the registry-backed `computer.execute_task` tool preserve that plan through Agent Manager → Computer Agent → Tool Manager. Application launch and focus are verified first. Browser address/search interaction then uses the controlled desktop input tools and captures a final screen observation; completion is reported only when the requested application remains active and a post-action screen change is observed. Explicit `Search the web for ...` remains a Browser/web-search intent.

## Browser speech completion synchronization

Browser and provider TTS now acknowledge actual playback completion through the Voice `speech-complete` endpoint. The server records the active synthesis identifier and ignores stale completion events from cancelled/replaced utterances. Only the currently active playback can release `SPEAKING` back to `ACTIVE_SESSION` or `WAKE_WORD_LISTENING`, preventing frontend/backend state drift and duplicate microphone loops.

Temporary Voice audio cleanup is available through both the existing cleanup task and the explicit diagnostic command:

```bash
python manage.py cleanup_voice_audio
```
