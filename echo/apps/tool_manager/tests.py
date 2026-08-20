from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.exceptions import PermissionDenied

from echo.apps.authentication.models import Permission, RolePermission, UserRole

from .execution import ToolExecutionError, ToolExecutor
from .models import Tool, ToolExecution, ToolPermission


class ToolExecutionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="tool@example.com",
            password="StrongPassphrase123!",
        )
        permission, _ = Permission.objects.get_or_create(
            codename="tools.execute",
            defaults={"name": "Execute tools"},
        )
        role, _ = UserRole.objects.get_or_create(name="Tool Operator")
        RolePermission.objects.get_or_create(role=role, permission=permission)
        self.user.roles.add(role)

    def test_registered_tool_executes_and_persists_result(self):
        tool = Tool.objects.create(
            owner=self.user,
            name="calculator",
            title="Calculator",
            status="active",
            configuration={"handler": "math.calculate"},
        )
        result = ToolExecutor.execute(
            tool,
            self.user,
            {"operation": "multiply", "left": "6", "right": "7"},
        )
        self.assertEqual(result.output, {"result": "42"})
        self.assertTrue(ToolExecution.objects.filter(pk=result.execution_id, status="completed").exists())


    def test_persisted_tool_cannot_weaken_registry_permissions(self):
        weak = get_user_model().objects.create_user(
            email="weak-tool@example.com",
            password="StrongPassphrase123!",
        )
        weak.roles.clear()
        permission, _ = Permission.objects.get_or_create(
            codename="platform.view",
            defaults={"name": "View platform"},
        )
        role, _ = UserRole.objects.get_or_create(name="Weak Tool Role")
        RolePermission.objects.get_or_create(role=role, permission=permission)
        weak.roles.add(role)
        tool = Tool.objects.create(
            owner=weak,
            name="weakened-calculator",
            title="Weakened calculator",
            status="active",
            configuration={"handler": "math.calculate", "required_permissions": ["platform.view"]},
        )
        with self.assertRaises(PermissionDenied):
            ToolExecutor.execute(tool, weak, {"operation": "add", "left": 1, "right": 2})

    def test_tool_specific_execute_grant_cannot_bypass_domain_permission(self):
        weak = get_user_model().objects.create_user(
            email="tool-grant@example.com",
            password="StrongPassphrase123!",
        )
        weak.roles.clear()
        tool = ToolExecutor.ensure_owned_tool("memory.search", weak)
        ToolPermission.objects.create(
            owner=weak,
            name="Memory search execute grant",
            status="active",
            permission_levels="execute",
            data={"tool_id": str(tool.pk)},
        )
        with self.assertRaises(PermissionDenied):
            ToolExecutor.execute(tool, weak, {"query": "Echo"}, agent="memory")

    def test_failed_tool_execution_is_persisted(self):
        tool = Tool.objects.create(
            owner=self.user,
            name="calculator-failure",
            title="Calculator failure",
            status="active",
            configuration={"handler": "math.calculate"},
        )
        with self.assertRaises(ToolExecutionError):
            ToolExecutor.execute(
                tool,
                self.user,
                {"operation": "divide", "left": 1, "right": 0},
            )
        execution = ToolExecution.objects.get(owner=self.user, name="math.calculate")
        self.assertEqual(execution.status, "failed")
        self.assertEqual(execution.configuration["error"], "division by zero")

class ToolRegistryContractTests(TestCase):
    def test_authoritative_registry_bootstraps_browser_computer_agent_and_domain_tools(self):
        handlers = set(ToolExecutor.available_handlers())
        expected = {
            "agent.execute", "browser.open_url", "browser.navigate", "browser.click", "browser.scroll",
            "computer.observe", "computer.click", "computer.scroll", "computer.launch_application",
            "computer.list_applications", "computer.open_path", "computer.focus_window", "computer.execute_task",
            "computer.get_active_window", "computer.capture_screen", "memory.search", "memory.store",
            "knowledge.search", "knowledge.ingest",
        }
        self.assertTrue(expected.issubset(handlers), expected - handlers)


    def test_local_computer_tool_definitions_are_real_registry_contracts(self):
        for name in ("computer.launch_application", "computer.list_applications", "computer.open_path", "computer.focus_window", "computer.get_active_window", "computer.capture_screen", "computer.execute_task"):
            definition = ToolExecutor.definition(name)
            self.assertTrue(callable(definition.handler), name)
            self.assertEqual(definition.category, "computer", name)
            self.assertIn("computer", definition.agent_access, name)

    def test_browser_open_url_definition_is_executable_contract(self):
        definition = ToolExecutor.definition("browser.open_url")
        self.assertTrue(callable(definition.handler))
        self.assertEqual(definition.category, "browser")
        self.assertIn("url", definition.input_schema.get("required", []))
        self.assertIn("browser", definition.agent_access)

    def test_unknown_handler_returns_structured_validation_error(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as caught:
            ToolExecutor.definition("browser.definitely_missing")
        payload = caught.exception.message_dict
        self.assertIn("error_type", payload)
        self.assertIn("available_handlers", payload)
        self.assertIn("browser.open_url", payload["available_handlers"])


    def test_execute_safe_preserves_unknown_handler_error_type(self):
        payload = ToolExecutor.execute_safe("browser.definitely_missing", self.user, {})
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error_type"], "unknown_handler")
        details = payload.get("details") or {}
        available = details.get("available_handlers") or []
        self.assertIn("browser.open_url", available)

    def test_registry_validation_has_no_provider_or_duplicate_errors(self):
        report = ToolExecutor.validation_report()
        self.assertTrue(report["ok"], report["issues"])
