# Authentication and authorization

## Identity

Echo uses a custom UUID-based user model with email as the login identifier. Passwords are validated by Django's similarity, length, common-password, and numeric-password checks and are hashed with Argon2 by default. User creation normalizes email addresses and creates a one-to-one profile.

## Browser sessions

The browser interface uses Django sessions, CSRF protection, HTTP-only cookies, SameSite restrictions, and secure cookies outside debug mode. Login and logout events create device, session, and login-history records.

## JWT

`POST /api/v1/auth/login/` returns access and refresh tokens. Access tokens are short-lived. Refresh tokens rotate and the previous token is blacklisted. `POST /api/v1/auth/logout/` blacklists the supplied refresh token. Clients must transmit access tokens as `Authorization: Bearer <token>`.

## API tokens

Authenticated users can create named API tokens. Echo returns the raw token once, stores only a SHA-256 hash and short lookup prefix, supports expiration and revocation, and records last use. Clients transmit the token with `Authorization: Token <raw-token>` or `X-API-Key`.

## Roles and permissions

Migration bootstrap creates Administrator, Developer, and Standard User roles plus platform permission codenames. Users can hold multiple roles. Staff and superusers bypass custom role checks. The `HasPlatformPermission` permission class resolves Django permissions and Echo role permissions.

## Object ownership

Domain records normally carry an `owner`. Non-staff querysets are filtered to the authenticated owner at both generated viewset and service layers. Ownership fields are read-only in generated serializers and cannot be reassigned during updates. Staff can inspect all records through administration and APIs. Models without an owner, user, or actor relation are not exposed to normal users by the generated API.

## Password reset

The reset endpoint issues a cryptographically random token, stores only its hash, expires it after one hour, and always returns a neutral response to prevent account enumeration. Reset tokens are single-use and password validation runs before the password changes.
