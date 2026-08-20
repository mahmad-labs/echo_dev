from __future__ import annotations

import ast
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from echo.apps.agent_manager.registry import AgentRegistry
from echo.apps.authentication.models import Permission
from echo.apps.tool_manager.execution import ToolExecutor
from echo.apps.tool_manager.models import Tool


class Command(BaseCommand):
    help = "Validate Echo's authoritative Tool Registry against handlers, agents, planners and persisted tools."

    def handle(self, *args, **options):
        report = ToolExecutor.validation_report()
        available = set(report["registered_tools"])
        issues = list(report["issues"])

        root = Path(settings.BASE_DIR)
        referenced: set[str] = set()
        for path in (root / "echo").rglob("*.py"):
            if any(part in {"migrations", "__pycache__"} for part in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                # Deterministic/planner plan dictionaries: {"tool": "browser.open_url"}
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if isinstance(key, ast.Constant) and key.value == "tool" and isinstance(value, ast.Constant) and isinstance(value.value, str):
                            if "." in value.value:
                                referenced.add(value.value.lower())
                # ToolExecutor.execute_named("...") calls.
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "execute_named" and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        referenced.add(first.value.lower())
                # AgentDefinition(required_tools=(...))
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "AgentDefinition":
                    for keyword in node.keywords:
                        if keyword.arg == "required_tools" and isinstance(keyword.value, (ast.Tuple, ast.List)):
                            for item in keyword.value.elts:
                                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                                    referenced.add(item.value.lower())

        for name in sorted(referenced - available):
            issues.append({"type": "unregistered_reference", "tool": name})

        for tool in Tool.objects.exclude(configuration__handler=""):
            handler = str((tool.configuration or {}).get("handler") or tool.name).strip().lower()
            if handler and handler not in available:
                issues.append({"type": "orphan_persisted_tool", "tool_id": str(tool.pk), "handler": handler})

        agent_report = AgentRegistry.validation_report()
        issues.extend({"type": "agent_registry", **item} for item in agent_report.get("issues", []))
        known_agents = set(agent_report.get("registered_agents") or []) | {"workflow", "voice"}
        known_permissions = set(Permission.objects.values_list("codename", flat=True))
        for name in sorted(available):
            definition = ToolExecutor.definition(name)
            for permission in definition.permissions:
                if permission not in known_permissions:
                    issues.append({"type": "unknown_tool_permission", "tool": name, "permission": permission})
            for agent in definition.agent_access:
                if agent not in known_agents:
                    issues.append({"type": "unknown_agent_access", "tool": name, "agent": agent})

        self.stdout.write(f"Registered tools ({len(available)}):")
        for name in sorted(available):
            definition = ToolExecutor.definition(name)
            self.stdout.write(f"  - {name} [{definition.category}] availability={'available' if definition.is_available() else 'unavailable'} mode={definition.execution_mode} risk={definition.risk_level}")
        if issues:
            for issue in issues:
                self.stderr.write(f"ERROR: {issue}")
            raise CommandError(f"Echo tool validation failed with {len(issues)} issue(s).")
        self.stdout.write(self.style.SUCCESS(f"Tool registry valid: {len(available)} tools; {len(referenced)} static references resolved."))
