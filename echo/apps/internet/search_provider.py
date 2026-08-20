from __future__ import annotations

from typing import Any

import requests
from django.conf import settings


class SearchProviderError(RuntimeError):
    pass


class ConfiguredSearchProvider:
    """Adapter for a JSON search endpoint configured by environment variables."""

    def search(self, query: str, *, search_type: str = "web", limit: int = 10) -> list[dict[str, Any]]:
        endpoint = getattr(settings, "INTERNET_SEARCH_ENDPOINT", "")
        if not endpoint:
            raise SearchProviderError("INTERNET_SEARCH_ENDPOINT is not configured.")
        headers = {"Accept": "application/json"}
        api_key = getattr(settings, "INTERNET_SEARCH_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = requests.get(
            endpoint,
            params={"q": query, "type": search_type, "limit": max(1, min(limit, 50))},
            headers=headers,
            timeout=20,
        )
        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SearchProviderError(f"Search provider request failed: {exc}") from exc
        records = payload.get("results", payload) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise SearchProviderError("Search provider response must contain a result list.")
        return [record for record in records if isinstance(record, dict)][:limit]
