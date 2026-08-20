from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

import requests
from django.conf import settings


class VoiceProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderCapabilities:
    identifier: str
    display_name: str
    server_side: bool
    speech_to_text: bool = False
    text_to_speech: bool = False
    streaming: bool = False
    requires_configuration: bool = False
    configured: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    confidence: float = 0
    language: str = ""
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SynthesisResult:
    audio: bytes
    mime_type: str
    format_name: str
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class SpeechToTextProvider(ABC):
    identifier = "base"

    @abstractmethod
    def transcribe(self, audio: bytes, *, mime_type: str, language: str) -> TranscriptionResult:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def capabilities(cls) -> ProviderCapabilities:
        raise NotImplementedError


class TextToSpeechProvider(ABC):
    identifier = "base"

    @abstractmethod
    def synthesize(
        self,
        text: str,
        *,
        voice: str,
        language: str,
        format_name: str,
        speaking_rate: float,
        pitch: float,
        volume: float,
    ) -> SynthesisResult:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def capabilities(cls) -> ProviderCapabilities:
        raise NotImplementedError


class BrowserSpeechProvider:
    """Capability descriptor for browser Web Speech APIs.

    Recognition and synthesis happen in the user's browser. Echo never claims this
    provider is available until the client reports its runtime capabilities and the
    browser grants microphone permission.
    """

    identifier = "browser"

    @classmethod
    def capabilities(cls) -> ProviderCapabilities:
        return ProviderCapabilities(
            identifier=cls.identifier,
            display_name="Browser speech services",
            server_side=False,
            speech_to_text=True,
            text_to_speech=True,
            streaming=True,
            metadata={"runtime_detection_required": True},
        )


class ConfiguredHTTPVoiceProvider(SpeechToTextProvider, TextToSpeechProvider):
    """Provider-agnostic HTTP adapter.

    Expected endpoints:
      POST {base_url}/transcribe (multipart audio, language)
      POST {base_url}/synthesize (JSON text/voice/language/format/rate/pitch/volume)

    The synthesis endpoint may return raw audio or JSON with ``audio_base64``.
    """

    identifier = "configured_http"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int | None = None):
        self.base_url = (base_url or getattr(settings, "VOICE_PROVIDER_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or getattr(settings, "VOICE_PROVIDER_API_KEY", "")
        self.timeout = timeout or int(getattr(settings, "VOICE_PROVIDER_TIMEOUT", 45))
        if not self.base_url:
            raise VoiceProviderError("VOICE_PROVIDER_BASE_URL is not configured.")

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json, audio/*"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @classmethod
    def capabilities(cls) -> ProviderCapabilities:
        configured = bool(getattr(settings, "VOICE_PROVIDER_BASE_URL", ""))
        return ProviderCapabilities(
            identifier=cls.identifier,
            display_name="Configured speech provider",
            server_side=True,
            speech_to_text=True,
            text_to_speech=True,
            streaming=False,
            requires_configuration=True,
            configured=configured,
        )

    def transcribe(self, audio: bytes, *, mime_type: str = "audio/webm", language: str = "en-US") -> TranscriptionResult:
        if not audio:
            raise ValueError("Audio is required.")
        max_bytes = int(getattr(settings, "VOICE_MAX_AUDIO_BYTES", 25 * 1024 * 1024))
        if len(audio) > max_bytes:
            raise ValueError("Audio exceeds the configured size limit.")
        try:
            response = requests.post(
                f"{self.base_url}/transcribe",
                headers=self.headers,
                files={"audio": ("speech", audio, mime_type)},
                data={"language": language},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise VoiceProviderError(f"Speech recognition failed: {exc}") from exc
        text = str(data.get("text", "")).strip()
        if not text:
            raise VoiceProviderError("Speech recognition returned no transcript.")
        return TranscriptionResult(
            text=text,
            confidence=float(data.get("confidence", 0) or 0),
            language=str(data.get("language", language) or language),
            duration_ms=int(data.get("duration_ms", 0) or 0),
            metadata={key: value for key, value in data.items() if key not in {"text", "confidence", "language", "duration_ms"}},
        )

    def synthesize(
        self,
        text: str,
        *,
        voice: str = "default",
        language: str = "en-US",
        format_name: str = "mp3",
        speaking_rate: float = 1,
        pitch: float = 1,
        volume: float = 1,
    ) -> SynthesisResult:
        text = str(text or "").strip()
        if not text:
            raise ValueError("Text is required.")
        try:
            response = requests.post(
                f"{self.base_url}/synthesize",
                headers={**self.headers, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "voice": voice,
                    "language": language,
                    "format": format_name,
                    "speaking_rate": speaking_rate,
                    "pitch": pitch,
                    "volume": volume,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise VoiceProviderError(f"Speech synthesis failed: {exc}") from exc
        content_type = response.headers.get("Content-Type", "audio/mpeg").split(";", 1)[0].strip()
        metadata: dict[str, Any] = {}
        duration_ms = 0
        if "application/json" in content_type:
            try:
                payload = response.json()
                audio = base64.b64decode(payload["audio_base64"], validate=True)
                content_type = str(payload.get("mime_type", "audio/mpeg"))
                format_name = str(payload.get("format", format_name))
                duration_ms = int(payload.get("duration_ms", 0) or 0)
                metadata = {key: value for key, value in payload.items() if key != "audio_base64"}
            except (KeyError, ValueError, TypeError) as exc:
                raise VoiceProviderError("Provider returned invalid encoded audio.") from exc
        else:
            audio = response.content
        if not audio:
            raise VoiceProviderError("Provider returned empty audio.")
        max_bytes = int(getattr(settings, "VOICE_MAX_SYNTHESIS_BYTES", 25 * 1024 * 1024))
        if len(audio) > max_bytes:
            raise VoiceProviderError("Provider audio exceeds the configured response limit.")
        if not str(content_type).startswith("audio/"):
            raise VoiceProviderError("Provider returned an unsupported synthesis content type.")
        return SynthesisResult(audio=audio, mime_type=content_type, format_name=format_name, duration_ms=duration_ms, metadata=metadata)


class VoiceProviderRegistry:
    STT_PROVIDERS = {
        "configured_http": ConfiguredHTTPVoiceProvider,
    }
    TTS_PROVIDERS = {
        "configured_http": ConfiguredHTTPVoiceProvider,
    }

    @staticmethod
    def _load_class(path: str):
        module_name, class_name = path.rsplit(".", 1)
        return getattr(import_module(module_name), class_name)

    @classmethod
    def stt(cls, identifier: str) -> SpeechToTextProvider:
        identifier = identifier or "configured_http"
        if identifier == "browser":
            raise VoiceProviderError("Browser recognition transcripts must be submitted through the transcript endpoint.")
        provider_class = cls.STT_PROVIDERS.get(identifier)
        if not provider_class:
            custom_path = getattr(settings, "VOICE_STT_PROVIDER_CLASS", "")
            if custom_path and identifier == "custom":
                provider_class = cls._load_class(custom_path)
        if not provider_class:
            raise VoiceProviderError(f"Unknown speech-to-text provider: {identifier}")
        return provider_class()

    @classmethod
    def tts(cls, identifier: str) -> TextToSpeechProvider:
        identifier = identifier or "configured_http"
        if identifier == "browser":
            raise VoiceProviderError("Browser synthesis is executed by the client.")
        provider_class = cls.TTS_PROVIDERS.get(identifier)
        if not provider_class:
            custom_path = getattr(settings, "VOICE_TTS_PROVIDER_CLASS", "")
            if custom_path and identifier == "custom":
                provider_class = cls._load_class(custom_path)
        if not provider_class:
            raise VoiceProviderError(f"Unknown text-to-speech provider: {identifier}")
        return provider_class()

    @classmethod
    def capabilities(cls) -> list[dict[str, Any]]:
        capabilities = [BrowserSpeechProvider.capabilities(), ConfiguredHTTPVoiceProvider.capabilities()]
        for identifier, path, kind in (
            ("custom", getattr(settings, "VOICE_STT_PROVIDER_CLASS", ""), "stt"),
            ("custom", getattr(settings, "VOICE_TTS_PROVIDER_CLASS", ""), "tts"),
        ):
            if not path:
                continue
            try:
                provider_class = cls._load_class(path)
                item = provider_class.capabilities()
                capabilities.append(
                    ProviderCapabilities(
                        identifier="custom",
                        display_name=item.display_name,
                        server_side=True,
                        speech_to_text=kind == "stt",
                        text_to_speech=kind == "tts",
                        streaming=item.streaming,
                        requires_configuration=item.requires_configuration,
                        configured=item.configured,
                        metadata={**item.metadata, "provider_identifier": item.identifier},
                    )
                )
            except Exception:
                capabilities.append(
                    ProviderCapabilities(
                        identifier=f"{identifier}_{kind}",
                        display_name=f"Custom {kind.upper()} provider",
                        server_side=True,
                        speech_to_text=kind == "stt",
                        text_to_speech=kind == "tts",
                        requires_configuration=True,
                        configured=False,
                        metadata={"configuration_error": True},
                    )
                )
        unique = {}
        for item in capabilities:
            payload = {
                "identifier": item.identifier,
                "display_name": item.display_name,
                "server_side": item.server_side,
                "speech_to_text": item.speech_to_text,
                "text_to_speech": item.text_to_speech,
                "streaming": item.streaming,
                "requires_configuration": item.requires_configuration,
                "configured": item.configured,
                "metadata": item.metadata,
            }
            unique[(item.identifier, item.speech_to_text, item.text_to_speech)] = payload
        return list(unique.values())
