# API Guide

## Base URLs

Generated resource APIs are rooted at `/api/v1/`. The specification-compatible interface is rooted at `/api/`. Interactive documentation is available at `/api/docs/`, ReDoc at `/api/redoc/`, and the machine-readable schema at `/api/schema/`.

## Authentication

JWT clients authenticate with:

```http
Authorization: Bearer <access-token>
```

Service clients authenticate with either:

```http
Authorization: Token <raw-api-token>
```

or:

```http
X-API-Key: <raw-api-token>
```

API tokens are returned only at creation. Store them in a secrets manager. Browser requests may use Django sessions and CSRF protection.

## Authentication routes

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `POST /api/auth/logout/`
- `POST /api/auth/change-password/`
- `POST /api/auth/forgot-password/`
- `POST /api/auth/reset-password/`
- `GET|PUT|DELETE /api/user/`
- `GET /api/sessions/`
- `DELETE /api/sessions/<uuid>/`
- `GET /api/devices/`
- `DELETE /api/devices/<uuid>/`
- `GET|POST /api/tokens/`
- `DELETE /api/tokens/<uuid>/`


## Voice API

Echo Voice uses protected domain endpoints rather than unrestricted generic CRUD. The complete contract, provider adapter, state machine, memory approval flow, and browser requirements are documented in `docs/VOICE.md`.

- `GET /api/v1/voice/capabilities/`
- `GET /api/v1/voice/runtime/`
- `GET|PATCH /api/v1/voice/profile/`
- `GET|POST /api/v1/voice/sessions/`
- `GET /api/v1/voice/sessions/<uuid>/`
- `POST /api/v1/voice/sessions/<uuid>/state/`
- `POST /api/v1/voice/sessions/<uuid>/greeted/`
- `POST /api/v1/voice/sessions/<uuid>/speech-complete/` — acknowledges real client/server playback completion and restores the authoritative listening state.
- `POST /api/v1/voice/sessions/<uuid>/activate/`
- `POST /api/v1/voice/sessions/<uuid>/disable/`
- `POST /api/v1/voice/sessions/<uuid>/shutdown/`
- `POST /api/v1/voice/sessions/<uuid>/end/` (compatibility shutdown)
- `POST /api/v1/voice/transcripts/browser/`
- `POST /api/v1/voice/transcripts/audio/`
- `POST /api/v1/voice/synthesize/`
- `POST /api/v1/voice/transcripts/<uuid>/memory/`

## Computer-use API

Echo's general-purpose browser computer-use interface is owner-scoped and permission-aware. Mutating or long-running requests execute through the existing Tool Manager and durable `ComputerUseOperation` records rather than a parallel automation stack. `POST /computer/media/analyze/` returns `202 Accepted` with an operation identifier.

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

Computer-use execution requires `tools.execute`; reads remain owner-scoped. CAPTCHA, login/MFA, security verification, network-boundary violations, and other protected states are never bypassed. Consequential actions pause for explicit user approval through the operation resume path. See `docs/COMPUTER_USE.md` for the observe/act/verify contract, media evidence rules, and runtime configuration.

## Generated resources

Every domain app exposes DRF resource routes under `/api/v1/<domain>/`. List endpoints are paginated. Collection creation sets the owner or user field to the authenticated principal when the model supports it. Detail routes use UUID primary keys.

Common query parameters:

- `page`: page number.
- `page_size`: requested page size up to the configured maximum.
- `search`: text search across declared searchable fields.
- `ordering`: comma-separated ordering fields, with `-` for descending order.
- Filter parameters defined by a model viewset.

A paginated response has this shape:

```json
{
  "count": 42,
  "next": "https://example.test/api/v1/tasks/tasks/?page=2",
  "previous": null,
  "results": []
}
```

## Compatibility routes

The compatibility controller implements all 238 documented method/path pairs in `docs/API_ENDPOINT_CATALOG.md`. Action routes dispatch to concrete application services. Resource routes use domain-aware model resolution and the same ownership policy as the generated API.

The authenticated endpoint catalog is available at:

```http
GET /api/v1/endpoint-catalog/
```

## Status codes

- `200 OK`: successful read, update, or action.
- `201 Created`: resource or operation created.
- `202 Accepted`: a recorded operation has been accepted for later execution.
- `204 No Content`: deletion completed.
- `400 Bad Request`: validation failed.
- `401 Unauthorized`: credentials are absent or invalid.
- `403 Forbidden`: credentials are valid but permission is insufficient.
- `404 Not Found`: the resource is absent or outside the caller's ownership scope.
- `409 Conflict`: a state or scheduling conflict prevents the operation.
- `429 Too Many Requests`: request throttling was triggered.
- `500 Internal Server Error`: an unexpected failure occurred and was assigned a correlation ID.
- `503 Service Unavailable`: readiness checks indicate a required dependency is unavailable.

## Error format

The global exception handler returns a stable envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request could not be processed.",
    "details": {},
    "correlation_id": "b88dc3e2-5af0-4f70-92c5-83eaf559d31f"
  }
}
```

Validation details retain field-level messages. Logs include the same correlation ID sent in the `X-Correlation-ID` response header.

## Idempotency and retries

GET, PUT, and DELETE operations should be treated according to standard HTTP idempotency. Provider-backed actions may create durable request records before contacting an external service. Clients should use their own stable operation reference in resource metadata when automatic retries could otherwise duplicate work.

## Uploads and downloads

The configured upload limit defaults to 25 MiB. Validate MIME type and extension at the client and server. Uploaded content is stored through Django's storage abstraction. In production, serve media through a controlled storage service or authenticated proxy rather than the Django development server.

## Versioning

The generated resource interface is explicitly versioned as `/api/v1/`. Compatibility routes remain at `/api/` because their paths are part of the supplied specification. Introduce breaking changes under a new version and keep migrations or adapters for existing clients.
