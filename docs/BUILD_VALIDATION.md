# Build Validation Record

This release modifies the current Echo project in place. It preserves the authoritative Tool Registry repair and completes the next integration layer: a server-authoritative Voice lifecycle with wake/active/disable/shutdown behavior and playback-completion synchronization, deterministic local-computer versus website/search intent routing, compound local-computer task decomposition, OS application discovery, verified application/system-location opening, and active-window context for follow-up computer commands. See `SYSTEM_AUDIT.md`.

## Completed release validation

The packaged source passed `scripts/static_validate.py` and companion dependency-free checks, including:

- 24 Echo application packages.
- 189 final migration model states aligned with source declarations.
- Strict source/migration field parity for Voice, Agent Manager orchestration records, browser computer-use records, and desktop Computer Control records.
- 238 unique specification-compatible method/path entries.
- Central Agent Registry definitions for Memory, Knowledge, Planner, Browser, Computer, Documents, Projects, Tasks, Workflow, and Chat.
- One explicit Tool Registry bootstrap for core, browser, desktop, agent, Memory, and Knowledge tool families.
- Registry-backed browser/desktop APIs and the Tool Manager `agent.execute` workflow bridge.
- Structured unknown-handler errors, schema validation, runtime availability, and non-weakenable registry permissions.
- General browser and desktop tool contracts, including DOM/accessibility/screenshot observation and desktop screen/input control.
- No website-specific YouTube automation API.
- Wake-word, active-session, speaker-awareness, and Agent Manager voice contracts.
- Python syntax validation across the complete source tree.
- JavaScript syntax validation for the Echo browser runtime.
- Django template control-block balance checks.
- SVG parsing and validation of referenced icon identifiers.
- CSS block-balance validation.
- Shell syntax checks for deployment scripts.
- Checks for unfinished implementation markers in executable source/templates.
- Confirmation that no Docker, Compose, Kubernetes, or container configuration is present.

The final release archive is extracted into a clean directory and independently verified against `MANIFEST.sha256` before delivery.

## Django runtime validation boundary

The packaging environment does not contain Django, Django REST Framework, Selenium, Celery, Redis, or the remaining runtime dependencies. A clean `pip install -r requirements.txt` was attempted during this release, but the configured package mirror returned no Django distributions. Therefore Django system checks, migration execution, live Selenium/desktop tests, and the Django test runner cannot truthfully be reported as executed here.

After installing dependencies in a normal Python environment, run:

```bash
python scripts/static_validate.py
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py validate_echo
python manage.py validate_tools
python manage.py validate_agents
python manage.py echo_health
python manage.py cleanup_voice_audio
python manage.py test
```

## Included integration coverage

Automated tests in the source cover:

- Agent Registry materialization and declared capabilities.
- Text → Agent Manager → Memory persistence with structured task/communication records.
- Owner-scoped Knowledge Agent retrieval.
- Project continuation through Planner + Memory/Knowledge context + Project Agent.
- Workflow → Tool Manager `agent.execute` → Agent Manager delegation.
- Root/child cancellation behavior.
- General browser planning, screen evidence, safety approvals, operation cancellation/resume, and anti-bypass behavior.
- General desktop tool registration, installed-application discovery/launch verification, system-location resolution, active-window controls, and structured UI-tree target matching.
- Voice wake-word gating, one-time startup greeting, server-authoritative Activate/Disable/Shutdown transitions, one-hour inactivity expiry back to wake-word mode, typed continuity, TTS playback-completion synchronization/stale-callback protection, self-trigger protection, and continuous capture recovery.
- Compound local-computer routing for application launch plus follow-up browser work without generic web-search fallback.
- Speaker enrollment/verification and configured server-side speaker embedding normalization.
- Voice → Agent Manager → Tasks/Memory/Chat persistence.
- Document extraction, durable failure states, and Knowledge indexing.

Real browser, microphone, speaker-verification-provider, desktop input, and external AI/STT/TTS smoke tests require those devices/providers to be available on the machine running Echo.
