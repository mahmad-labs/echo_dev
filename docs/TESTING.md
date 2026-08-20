# Testing strategy

The repository uses Django's test framework and DRF's API client. Every app includes at least a model-registration test. Focused tests cover authentication and API-token use, user ownership isolation, route-catalog completeness, deterministic vector math, private-network URL rejection, calendar conflicts, safe tool execution, workflow dependency ordering and cycle rejection, and project export/restore, voice session ownership and state transitions, voice-to-task and voice-to-memory integration, document extraction and knowledge indexing, and the adaptive homepage.

## Local quality gate

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py validate_echo
python manage.py validate_tools
python manage.py validate_agents
python manage.py echo_health
python manage.py test
```

Install `requirements-dev.txt` for static analysis and coverage:

```bash
ruff check .
ruff format --check .
mypy echo config
coverage run manage.py test
coverage report --fail-under=80
```

## Test design

- Unit tests isolate deterministic algorithms and validators.
- Service tests verify transactions, state transitions, ownership, and persistence.
- API tests verify authentication, permissions, validation, serialization, and status codes.
- Adapter tests mock provider boundaries and verify timeout/error contracts without external calls.
- Migration tests verify clean database creation and upgrade plans.
- Deployment smoke tests exercise health, readiness, login, one authenticated API request, static assets, and background task execution.

Security changes must include denial cases. Data-portability changes must include malformed input and cross-owner attempts. Workflow and task changes must include retries, partial failure, cycles, and idempotency behavior.

## Computer-use and media test coverage

Focused tests cover deterministic local-vs-web intent routing, installed-application discovery, verified application launch, system-location resolution, active-window controls, contextual commands such as “scroll down” and “open that video”, website-neutral browser planning, generic scroll-until behavior, environment registry integrity, private-network URL rejection, owner-scoped operation APIs, durable cancellation/resume state, sensitive-action approval policy, navigation/scroll verification, continuous Voice state transitions, and Voice integration with normal Echo conversations. Provider/browser adapter tests are designed to mock external WebDriver and model boundaries; production smoke tests should additionally exercise an approved real browser against a controlled test site.

Recommended browser smoke cases are: open a public test page; observe DOM/accessibility/screenshot evidence; scroll; select/click a stable control; verify the post-action observation; cancel a long wait; pause on a simulated human-verification page; resume after the blocker is removed; and process an organization-owned test media page with captions and, when configured, permitted audio/vision sampling.


## Voice lifecycle acceptance coverage

The Voice test suite verifies the one-time greeting, wake-word filtering, explicit Activate → Active transition, Disable → wake-word transition, explicit Shutdown, restart after shutdown, inactivity renewal and expiry, low-confidence wake-word rejection, speaker filtering, ignored-turn recovery from PROCESSING, typed/voice continuity, and microphone/TTS state coordination at the browser-controller boundary. Device-level microphone and browser speech-engine smoke tests still require a real secure browser context.
