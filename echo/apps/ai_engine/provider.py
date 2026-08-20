from __future__ import annotations

import json
from collections.abc import Iterable

import requests
from django.conf import settings


class AIProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def _configuration(self):
        if not settings.AI_PROVIDER_BASE_URL or not settings.AI_PROVIDER_API_KEY:
            raise AIProviderError("AI provider configuration is not available.")
        return (
            settings.AI_PROVIDER_BASE_URL.rstrip("/") + "/chat/completions",
            {
                "Authorization": f"Bearer {settings.AI_PROVIDER_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    def complete(self, messages, *, model=None, temperature=0.2, timeout=60):
        endpoint, headers = self._configuration()
        response = requests.post(
            endpoint,
            headers=headers,
            json={
                "model": model or settings.AI_PROVIDER_MODEL,
                "messages": messages,
                "temperature": temperature,
            },
            timeout=timeout,
        )
        try:
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"AI provider request failed: {exc}") from exc
        return content, payload

    def stream(self, messages, *, model=None, temperature=0.2, timeout=120) -> Iterable[str]:
        endpoint, headers = self._configuration()
        try:
            with requests.post(
                endpoint,
                headers={**headers, "Accept": "text/event-stream"},
                json={
                    "model": model or settings.AI_PROVIDER_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True,
                },
                timeout=timeout,
                stream=True,
            ) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines(decode_unicode=True):
                    line = (raw_line or "").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                        content = payload["choices"][0].get("delta", {}).get("content")
                    except (ValueError, KeyError, IndexError, TypeError):
                        continue
                    if content:
                        yield str(content)
        except requests.RequestException as exc:
            raise AIProviderError(f"AI provider stream failed: {exc}") from exc
