from __future__ import annotations

import hashlib
import secrets

from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import APIToken


class APITokenAuthentication(authentication.BaseAuthentication):
    """Authenticate long-lived service credentials without storing raw secrets."""

    keyword = "Token"

    def authenticate(self, request):
        raw_token = request.headers.get("X-API-Key", "").strip()
        if not raw_token:
            authorization = authentication.get_authorization_header(request).split()
            if not authorization:
                return None
            if authorization[0].decode("utf-8", errors="ignore").lower() != self.keyword.lower():
                return None
            if len(authorization) != 2:
                raise exceptions.AuthenticationFailed("Invalid API token header.")
            raw_token = authorization[1].decode("utf-8", errors="ignore")

        if len(raw_token) < 24:
            raise exceptions.AuthenticationFailed("Invalid API token.")

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        candidates = APIToken.objects.select_related("user").filter(
            token_prefix=raw_token[:12],
            revoked=False,
        )
        token = next(
            (
                candidate
                for candidate in candidates
                if secrets.compare_digest(candidate.token_hash, token_hash)
            ),
            None,
        )
        if token is None:
            raise exceptions.AuthenticationFailed("Invalid API token.")
        if token.expires_at and token.expires_at <= timezone.now():
            raise exceptions.AuthenticationFailed("API token has expired.")
        if not token.user.is_active or token.user.is_deleted:
            raise exceptions.AuthenticationFailed("User account is inactive.")

        token.last_used = timezone.now()
        token.save(update_fields=["last_used", "updated_at"])
        return token.user, token

    def authenticate_header(self, request):
        return self.keyword
