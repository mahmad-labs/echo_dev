from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from echo.apps.agent_manager.registry import AgentRegistry
from echo.apps.tool_manager.execution import ToolExecutor
from echo.apps.vector_database.embedding import feature_hash_embedding


class Command(BaseCommand):
    help = "Run meaningful health checks for Echo's major integrated subsystems."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")

    def _result(self, status: str, detail: str, **metadata: Any) -> dict[str, Any]:
        return {"status": status, "detail": detail, **metadata}

    def handle(self, *args, **options):
        checks: dict[str, dict[str, Any]] = {}
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                checks["database"] = self._result("healthy", f"Database responded with {cursor.fetchone()[0]}.")
        except Exception as exc:
            checks["database"] = self._result("failed", str(exc))

        tool_report = ToolExecutor.validation_report()
        checks["tools"] = self._result("healthy" if tool_report["ok"] else "failed", f"{tool_report['count']} tools discovered.", issues=tool_report["issues"])
        agent_report = AgentRegistry.validation_report()
        agent_status = "failed" if not agent_report["ok"] else "degraded" if agent_report.get("warnings") else "healthy"
        checks["agents"] = self._result(agent_status, f"{agent_report['count']} agents discovered.", issues=agent_report["issues"], warnings=agent_report.get("warnings") or [])

        for name, dotted in {
            "memory": "echo.apps.memory.models.Memory",
            "knowledge": "echo.apps.knowledge.models.KnowledgeDocument",
            "planner": "echo.apps.planner.models.Goal",
            "workflow": "echo.apps.workflow_engine.models.Workflow",
            "tasks": "echo.apps.tasks.models.Task",
            "notifications": "echo.apps.notifications.models.Notification",
            "voice": "echo.apps.voice.models.VoiceSession",
        }.items():
            try:
                module_name, class_name = dotted.rsplit(".", 1)
                model = getattr(__import__(module_name, fromlist=[class_name]), class_name)
                list(model.objects.all().values_list("pk", flat=True)[:1])
                checks[name] = self._result("healthy", "Database model query succeeded.")
            except Exception as exc:
                checks[name] = self._result("failed", str(exc))

        try:
            vector = feature_hash_embedding("echo health probe", dimensions=32)
            norm = sum(float(x) * float(x) for x in vector) ** 0.5
            checks["vector_database"] = self._result("healthy" if len(vector) == 32 and norm > 0 else "failed", f"Deterministic embedding probe dimension={len(vector)} norm={norm:.4f}.")
        except Exception as exc:
            checks["vector_database"] = self._result("failed", str(exc))

        try:
            cache.set("echo-health-probe", "ok", 5)
            checks["cache"] = self._result("healthy" if cache.get("echo-health-probe") == "ok" else "failed", "Cache round-trip completed.")
        except Exception as exc:
            checks["cache"] = self._result("degraded", str(exc))

        try:
            from types import SimpleNamespace
            from echo.apps.internet.computer_use import SeleniumBrowserBackend
            dependency = SeleniumBrowserBackend.capabilities()
            if not dependency.get("available"):
                checks["browser"] = self._result("unavailable", str(dependency.get("reason") or "Selenium browser runtime is unavailable."), environment=dependency)
            else:
                probe_session = SimpleNamespace(owner_id="health", pk="health", engine=getattr(settings, "ECHO_BROWSER_ENGINE", "chrome"), headless=True)
                backend = SeleniumBrowserBackend(probe_session)
                try:
                    driver = backend.start()
                    current_url = str(driver.current_url or "")
                    checks["browser"] = self._result("healthy", "A controlled headless browser session started successfully.", engine=dependency.get("engine"), current_url=current_url)
                finally:
                    backend.close()
        except Exception as exc:
            checks["browser"] = self._result("unavailable", f"Controlled browser probe failed: {exc}")

        try:
            from echo.apps.internet.local_system import ApplicationDiscoveryService, DesktopWindowService, SystemLocationResolver
            applications = ApplicationDiscoveryService.list_public(limit=20)
            home_location = SystemLocationResolver.resolve("home")
            window_capabilities = DesktopWindowService.capabilities()
            checks["local_system"] = self._result(
                "healthy" if home_location.target else "failed",
                f"Local application/system resolver initialized; discovered {len(applications)} application records in the health sample.",
                application_sample_count=len(applications),
                home_target=home_location.target,
                active_window=window_capabilities.get("active_window"),
                window_count=window_capabilities.get("window_count", 0),
            )
        except Exception as exc:
            checks["local_system"] = self._result("failed", f"Local application/system resolver probe failed: {exc}")

        try:
            from echo.apps.voice.models import VoiceSession
            required_states = {
                "starting", "greeting", "disabled", "wake_word_listening", "active_session",
                "processing", "speaking", "sleeping", "shutdown", "error",
            }
            actual_states = {value for value, _label in VoiceSession.State.choices}
            default_state = VoiceSession._meta.get_field("state").get_default()
            voice_ok = required_states.issubset(actual_states) and default_state == VoiceSession.State.STARTING
            checks["voice_lifecycle"] = self._result(
                "healthy" if voice_ok else "failed",
                "Authoritative voice state machine and startup default are consistent." if voice_ok else "Voice lifecycle state definitions are inconsistent.",
                default_state=default_state,
                inactivity_minutes=min(60, max(1, int(getattr(settings, "VOICE_ACTIVE_SESSION_MINUTES", 60)))),
                wake_word_confidence=float(getattr(settings, "VOICE_WAKE_WORD_MIN_CONFIDENCE", 0.45)),
                wake_word_cooldown_seconds=float(getattr(settings, "VOICE_WAKE_WORD_COOLDOWN_SECONDS", 2.0)),
            )
        except Exception as exc:
            checks["voice_lifecycle"] = self._result("failed", f"Voice lifecycle probe failed: {exc}")

        try:
            from echo.apps.internet.desktop_control import LocalDesktopBackend
            desktop_capabilities = LocalDesktopBackend.capabilities()
            if not desktop_capabilities.get("available"):
                checks["computer_control"] = self._result("unavailable", str(desktop_capabilities.get("reason") or "Desktop screen/input backend is unavailable."), capabilities=desktop_capabilities)
            else:
                screenshot = LocalDesktopBackend.screenshot_png()
                checks["computer_control"] = self._result(
                    "healthy" if screenshot else "failed",
                    "Desktop input backend initialized and screen capture succeeded." if screenshot else "Desktop screen capture returned no data.",
                    capabilities=desktop_capabilities, screenshot_bytes=len(screenshot),
                )
        except Exception as exc:
            checks["computer_control"] = self._result("unavailable", f"Desktop screen/input probe failed: {exc}")

        ai_configured = bool(getattr(settings, "AI_PROVIDER_BASE_URL", "") and getattr(settings, "AI_PROVIDER_API_KEY", ""))
        checks["ai"] = self._result("healthy" if ai_configured else "degraded", "AI provider configured." if ai_configured else "AI provider credentials are not configured; deterministic/local paths remain available.")
        voice_base = str(getattr(settings, "VOICE_PROVIDER_BASE_URL", "") or "").strip()
        voice_key = str(getattr(settings, "VOICE_PROVIDER_API_KEY", "") or "").strip()
        custom_stt = str(getattr(settings, "VOICE_STT_PROVIDER_CLASS", "") or "").strip()
        custom_tts = str(getattr(settings, "VOICE_TTS_PROVIDER_CLASS", "") or "").strip()
        stt_server = bool((voice_base and voice_key) or custom_stt)
        tts_server = bool((voice_base and voice_key) or custom_tts)
        checks["stt"] = self._result("healthy" if stt_server else "degraded", "Server STT provider configured." if stt_server else "Server STT is not configured; browser SpeechRecognition can be used when supported.")
        checks["tts"] = self._result("healthy" if tts_server else "degraded", "Server TTS provider configured." if tts_server else "Server TTS is not configured; browser speechSynthesis can be used when supported.")

        failed = [name for name, row in checks.items() if row["status"] == "failed"]
        overall = "failed" if failed else "degraded" if any(row["status"] in {"degraded", "unavailable"} for row in checks.values()) else "healthy"
        payload = {"status": overall, "checks": checks}
        if options["as_json"]:
            self.stdout.write(json.dumps(payload, indent=2, default=str))
        else:
            self.stdout.write(f"Echo health: {overall.upper()}")
            for name, row in checks.items():
                self.stdout.write(f"  {name:18} {row['status']:11} {row['detail']}")
        if failed:
            self.stderr.write(f"Failed subsystems: {', '.join(failed)}")
            raise CommandError(f"Echo health failed for: {', '.join(failed)}")
