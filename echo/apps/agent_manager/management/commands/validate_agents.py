from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from echo.apps.authentication.models import Permission
from echo.apps.agent_manager.models import Agent
from echo.apps.agent_manager.registry import AgentRegistry
from echo.apps.tool_manager.execution import ToolExecutor


class Command(BaseCommand):
    help = "Validate registered Echo agents, dependencies, tool access, permissions and persisted agent records."

    def handle(self, *args, **options):
        report = AgentRegistry.validation_report()
        issues = list(report.get("issues") or [])
        warnings = list(report.get("warnings") or [])
        tools = set(ToolExecutor.available_handlers())
        known_permissions = set(Permission.objects.values_list("codename", flat=True))

        for definition in AgentRegistry.definitions():
            missing_tools = [item for item in definition.required_tools if item not in tools]
            if missing_tools:
                issues.append({"type": "missing_tools", "agent": definition.identifier, "tools": missing_tools})
            missing_permissions = [item for item in definition.required_permissions if item not in known_permissions]
            if missing_permissions:
                issues.append({"type": "unknown_permission", "agent": definition.identifier, "permissions": missing_permissions})
            for tool_name in definition.required_tools:
                if tool_name in tools:
                    tool = ToolExecutor.definition(tool_name)
                    if tool.agent_access and definition.identifier not in tool.agent_access:
                        issues.append({"type": "agent_tool_access_mismatch", "agent": definition.identifier, "tool": tool_name})

        registered = {item.identifier for item in AgentRegistry.definitions()}
        for item in Agent.objects.filter(category="builtin").exclude(identifier__in=registered):
            issues.append({"type": "orphan_agent_record", "agent_id": str(item.pk), "identifier": item.identifier})

        for definition in AgentRegistry.definitions():
            self.stdout.write(f"  - {definition.identifier}: tools={list(definition.required_tools)} permissions={list(definition.required_permissions)}")
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))
        if issues:
            for issue in issues:
                self.stderr.write(f"ERROR: {issue}")
            raise CommandError(f"Echo agent validation failed with {len(issues)} issue(s).")
        self.stdout.write(self.style.SUCCESS(f"Agent registry valid: {len(registered)} agents; {len(warnings)} runtime availability warning(s)."))
