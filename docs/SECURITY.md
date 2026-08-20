# Security

Echo applies defense in depth at the framework, domain, integration, and deployment layers.

## Application controls

- Argon2 password hashing and Django password validation
- rotating JWT refresh tokens with blacklist support
- hashed, expiring, revocable API tokens
- authenticated-by-default REST policy and route-specific public exceptions
- owner-scoped querysets and immutable ownership fields
- staff-only administrative access
- request throttling, CSRF protection, secure cookie defaults, HSTS support, frame denial, MIME sniffing protection, and restricted referrers
- correlation IDs and persisted request audit events
- structured exception responses that avoid stack-trace disclosure
- upload size limits and explicit document-type extraction

## External integrations

HTTP adapters define timeouts and surface provider failures. Web fetching accepts only HTTP/HTTPS, resolves host addresses before access, blocks private, loopback, link-local, reserved, and multicast destinations, disables redirects, limits response bytes, and uses a distinct user agent. The tool executor exposes only explicitly registered in-process handlers and provides no shell or arbitrary import execution.

Secrets are loaded from environment variables. API-token and password-reset raw values are not stored. IMAP configuration names an environment variable rather than persisting the password.

## Production requirements

Run behind HTTPS, set explicit hosts/origins, disable debug mode, use PostgreSQL, protect environment files, isolate the operating-system account, restrict database and Redis network access, patch dependencies, centralize logs, encrypt backups, and control administrative access with organizational identity and network policy.

## Security review checklist

Review authorization changes with negative tests. Threat-model new provider adapters. Validate file types by content when higher assurance is needed. Add malware scanning for untrusted uploads. Review data retention, privacy, and regulatory requirements for the deployment. Rotate credentials immediately after suspected exposure and invalidate active tokens where applicable.


## Voice security

Echo never silently grants itself microphone permission. On startup it may resume wake-word capture only when the browser reports that permission was already granted; a new permission grant still requires the browser/user interaction required by the platform. Browser permission state is reported truthfully and microphone capture requires a secure context outside localhost. Voice endpoints enforce authentication and ownership, audio size limits, supported media types, provider timeouts, bounded synthesis responses, and configurable retention. Permanent memory requires explicit approval by default. Server speech credentials remain in environment variables and are never sent to the browser.

## Computer-use security

Computer-use is owner-scoped and requires the `tools.execute` capability for execution-producing API paths. Standard Echo users receive that capability through the bootstrapped Standard User role; administrators remain separately privileged. Browser actions are selected from an explicit registry and do not expose arbitrary Python or shell execution. Local application launch is limited to discovered operating-system application metadata/default-browser integration, and local path opening is restricted to recognized system locations or owner-safe paths; Echo never turns arbitrary model text into a shell command.

Navigation rejects credential-bearing URLs and private/loopback/link-local/reserved destinations by default. `ECHO_BROWSER_ALLOW_LOCALHOST` and `ECHO_BROWSER_ALLOW_PRIVATE_NETWORKS` are explicit deployment opt-ins. Post-navigation observations re-check the resulting location. CAPTCHA, login/password, MFA, and human-verification states are not overridable by tool/model input; Echo pauses until the user resolves the page state.

Consequential or externally visible actions such as publishing, sending, purchasing, transferring, account deletion, or credential/financial input require an explicit operation approval. Planner-generated payloads cannot self-approve: approval flags are stripped and may only be added by the durable operation resume path for the exact interrupted step. Downloads require explicit permission and completion verification.

Media intelligence never bypasses DRM or authentication. Encrypted media is rejected for direct rendered-audio capture. Echo uses accessible captions/text, legitimate rendered audio exposed by the browser, and rendered visual frames only; stored answers are evidence-bound and report insufficiency instead of inventing coverage.
