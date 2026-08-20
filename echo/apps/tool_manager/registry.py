from __future__ import annotations

import importlib
import threading
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RegistryProvider:
    name: str
    module: str
    function: str


class ToolRegistry:
    """The one bootstrap path for every executable Echo tool family."""

    _providers: tuple[RegistryProvider, ...] = (
        RegistryProvider("core_tools", "echo.apps.tool_manager.execution", "register_core_tools"),
        RegistryProvider("computer_use", "echo.apps.internet.computer_use", "register_computer_use_tools"),
        RegistryProvider("desktop_control", "echo.apps.internet.desktop_control", "register_desktop_control_tools"),
        RegistryProvider("agent_manager", "echo.apps.agent_manager.tooling", "register_agent_tools"),
        RegistryProvider("domain_services", "echo.apps.tool_manager.domain_tools", "register_domain_tools"),
    )
    _bootstrapped = False
    _bootstrapping = False
    _lock = threading.RLock()
    _errors: dict[str, str] = {}

    @classmethod
    def providers(cls) -> tuple[RegistryProvider, ...]:
        return cls._providers

    @classmethod
    def bootstrap(cls, *, force: bool = False) -> dict[str, str]:
        with cls._lock:
            if cls._bootstrapped and not force:
                return dict(cls._errors)
            if cls._bootstrapping:
                return dict(cls._errors)
            cls._bootstrapping = True
            cls._errors = {}
            try:
                for provider in cls._providers:
                    try:
                        module = importlib.import_module(provider.module)
                        registrar: Callable = getattr(module, provider.function)
                        registrar()
                    except Exception as exc:
                        cls._errors[provider.name] = f"{exc.__class__.__name__}: {exc}"
                # A partial registry is never treated as a completed bootstrap.
                # Successful providers are idempotent, so a later discovery call can
                # retry transient provider/import failures without duplicating tools.
                cls._bootstrapped = not cls._errors
            finally:
                cls._bootstrapping = False
            return dict(cls._errors)

    @classmethod
    def errors(cls) -> dict[str, str]:
        return dict(cls._errors)
