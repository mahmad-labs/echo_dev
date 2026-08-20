from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .computer_use import (
    BrowserActionService,
    BrowserObservationService,
    BrowserSafetyPolicy,
    BrowserSessionService,
    ComputerEnvironmentRegistry,
    ComputerUseOperationService,
    ComputerUsePlanner,
    HumanInterventionRequired,
    normalize_url,
)
from echo.apps.tool_manager.execution import ToolExecutor
from .models import BrowserSession, ComputerUseOperation
from .desktop_control import ComputerControlCommandRouter, ComputerTargetResolver, ComputerTaskPlanner
from .safe_fetch import UnsafeURL, validate_public_url


class SafeFetchTests(SimpleTestCase):
    def test_private_network_targets_are_rejected(self):
        with self.assertRaises(UnsafeURL):
            validate_public_url("http://127.0.0.1/private")


class ComputerUsePlanningTests(SimpleTestCase):
    def test_general_compound_request_builds_observe_act_capabilities(self):
        plan = ComputerUsePlanner.deterministic(
            "Open YouTube, search for Python Django tutorials, open the first video, watch and listen to this video"
        )
        tools = [step["tool"] for step in plan]
        self.assertEqual(tools[0], "browser.open_url")
        self.assertIn("browser.search", tools)
        self.assertIn("browser.click", tools)
        self.assertIn("media.analyze", tools)
        self.assertNotIn("youtube.open", tools)

    def test_scroll_until_uses_generic_browser_tool(self):
        plan = ComputerUsePlanner.deterministic("Scroll down until you find the Python tutorial")
        self.assertEqual(plan[0]["tool"], "browser.scroll_until")
        self.assertEqual(plan[0]["input"]["query"], "the Python tutorial")

    def test_site_aliases_are_only_navigation_convenience(self):
        self.assertEqual(normalize_url("YouTube"), "https://www.youtube.com/")
        self.assertEqual(normalize_url("example.org/docs"), "https://example.org/docs")

    def test_unknown_navigation_target_does_not_silently_become_google_search(self):
        with self.assertRaises(ValidationError):
            normalize_url("some ambiguous desktop thing")

    def test_site_scoped_search_opens_site_then_uses_its_search_surface(self):
        plan = ComputerUsePlanner.deterministic("Search YouTube for Django tutorials")
        self.assertEqual(plan[0]["tool"], "browser.open_url")
        self.assertEqual(plan[0]["input"]["url"], "https://www.youtube.com/")
        self.assertEqual(plan[1]["tool"], "browser.search")
        self.assertEqual(plan[1]["input"]["query"], "Django tutorials")
        self.assertEqual(plan[1]["input"]["fallback"], "error")


    def test_environment_registry_exposes_real_registered_environment_only(self):
        names = {item["name"] for item in ComputerEnvironmentRegistry.capabilities()}
        self.assertIn("browser.selenium", names)
        self.assertNotIn("desktop.fake", names)

    def test_relevant_ordinal_media_request_remains_generic(self):
        plan = ComputerUsePlanner.deterministic("Open the first relevant video")
        self.assertEqual(plan[0]["tool"], "browser.click")
        self.assertEqual(plan[0]["input"]["target"]["kind"], "media_link")
        self.assertEqual(plan[0]["input"]["target"]["index"], 0)

    def test_referential_video_uses_current_evidence_instead_of_fixed_coordinates(self):
        plan = ComputerUsePlanner.deterministic("Open that video")
        self.assertEqual(plan[0]["tool"], "browser.click")
        self.assertEqual(plan[0]["input"]["target"].casefold(), "open that video")

    def test_generic_icon_click_uses_dom_or_visual_target_resolution(self):
        plan = ComputerUsePlanner.deterministic("Click the settings icon")
        self.assertEqual(plan[0]["tool"], "browser.click")
        self.assertEqual(plan[0]["input"]["target"].casefold(), "settings icon")

    def test_visual_relationship_is_preserved_for_screen_resolution(self):
        plan = ComputerUsePlanner.deterministic("Click the video thumbnail on the right")
        self.assertEqual(plan[0]["tool"], "browser.click")
        self.assertIsInstance(plan[0]["input"]["target"], str)
        self.assertIn("right", plan[0]["input"]["target"].lower())

    def test_current_page_questions_and_find_use_generic_tools(self):
        self.assertEqual(ComputerUsePlanner.deterministic("What is this?")[0]["tool"], "browser.answer_page")
        self.assertEqual(ComputerUsePlanner.deterministic("Find the login button")[0]["tool"], "browser.find")


class DesktopComputerControlArchitectureTests(SimpleTestCase):
    def test_structured_ui_tree_target_matching_is_generic(self):
        elements = [
            {"label": "Save document", "role": "button", "bbox": {"x": 20, "y": 40, "width": 100, "height": 30}},
            {"label": "Open settings", "role": "button", "bbox": {"x": 150, "y": 40, "width": 120, "height": 30}},
        ]
        match = ComputerTargetResolver._match(elements, "open settings")
        self.assertEqual(match["label"], "Open settings")

    def test_shared_tool_registry_exposes_general_browser_and_computer_tools(self):
        tools = set(ToolExecutor.available_handlers())
        self.assertTrue({"browser.open_url", "browser.click", "browser.scroll", "computer.observe", "computer.click", "computer.scroll"}.issubset(tools))
        self.assertFalse(any(name.startswith("youtube.") for name in tools))


class BrowserSafetyPolicyTests(SimpleTestCase):
    def observation(self, elements):
        return SimpleNamespace(dom={"elements": elements})

    def test_reversible_navigation_does_not_require_confirmation(self):
        observation = self.observation([{"echo_id": "echo-1", "tag": "a", "text": "Documentation", "href": "https://docs.example.com"}])
        self.assertIsNone(BrowserSafetyPolicy.require_confirmation(observation, "click", {"target": {"echo_id": "echo-1"}}))

    def test_external_or_financial_action_requires_confirmation(self):
        observation = self.observation([{"echo_id": "echo-2", "tag": "button", "text": "Place order", "role": "button"}])
        message = BrowserSafetyPolicy.require_confirmation(observation, "click", {"target": {"echo_id": "echo-2"}})
        self.assertIn("requires your confirmation", message)
        self.assertIsNone(BrowserSafetyPolicy.require_confirmation(observation, "click", {"target": {"echo_id": "echo-2"}, "confirmed": True}))

    def test_sensitive_input_requires_confirmation(self):
        observation = self.observation([{"echo_id": "echo-3", "tag": "input", "type": "password", "name": "password"}])
        message = BrowserSafetyPolicy.require_confirmation(observation, "type", {"target": {"echo_id": "echo-3"}, "text": "secret"})
        self.assertIn("sensitive credentials", message)


class BrowserVerificationTests(SimpleTestCase):
    def observation(self, *, url="https://example.com/", content_hash="a", scroll_y=0):
        return SimpleNamespace(url=url, content_hash=content_hash, visible_text="", viewport={"scroll_y": scroll_y, "document_height": 2000, "height": 800})

    def test_navigation_verification_uses_actual_destination(self):
        pre = self.observation(url="about:blank")
        post = self.observation(url="https://www.example.com/docs", content_hash="b")
        self.assertTrue(BrowserActionService.verify("open_url", {"url": "https://example.com/"}, {"url": post.url}, pre, post))
        wrong = self.observation(url="https://other.example.net/", content_hash="c")
        self.assertFalse(BrowserActionService.verify("open_url", {"url": "https://example.com/"}, {"url": wrong.url}, pre, wrong))

    def test_scroll_requires_observed_scroll_change(self):
        pre = self.observation(scroll_y=0)
        post = self.observation(scroll_y=700, content_hash="b")
        self.assertTrue(BrowserActionService.verify("scroll", {"direction": "down"}, {"scroll_y": 700}, pre, post))


@override_settings(AI_PROVIDER_BASE_URL="", AI_PROVIDER_API_KEY="", AI_PROVIDER_MODEL="")
class ComputerUseAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(email="computer@example.com", password="EchoPassword!2026")
        cls.other = get_user_model().objects.create_user(email="other-computer@example.com", password="EchoPassword!2026")
        cls.session = BrowserSession.objects.create(
            owner=cls.user, name="browser", title="Browser", status="active", engine="chrome", configuration={"environment": "browser.selenium"}
        )
        cls.operation = ComputerUseOperation.objects.create(
            owner=cls.user, session=cls.session, name="Scroll", title="Scroll", status="running",
            request_text="Scroll down", plan=[{"tool": "browser.scroll", "input": {"direction": "down"}}],
            current_operation="Scroll down", progress=10,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_operation_api_is_owner_scoped(self):
        response = self.client.get("/api/v1/internet/computer/operations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["operations"]], [str(self.operation.pk)])
        other = APIClient(); other.force_authenticate(self.other)
        self.assertEqual(other.get(f"/api/v1/internet/computer/operations/{self.operation.pk}/").status_code, 404)

    def test_operation_cancel_is_durable(self):
        response = self.client.post(f"/api/v1/internet/computer/operations/{self.operation.pk}/cancel/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.operation.refresh_from_db()
        self.assertTrue(self.operation.cancel_requested)
        self.assertEqual(self.operation.status, "cancelling")

    def test_execution_api_requires_tools_execute_permission(self):
        self.user.roles.clear()
        response = self.client.post("/api/v1/internet/computer/operations/", {"request": "Scroll down"}, format="json")
        self.assertEqual(response.status_code, 403)

    @patch.object(ComputerUseOperationService, "dispatch", return_value="media-queue")
    def test_media_analysis_api_is_durable_and_fixed_to_media_tool(self, dispatch):
        response = self.client.post("/api/v1/internet/computer/media/analyze/", {"session_id": str(self.session.pk)}, format="json")
        self.assertEqual(response.status_code, 202)
        operation = ComputerUseOperation.objects.get(pk=response.data["operation"]["id"])
        self.assertEqual(operation.plan, [{"tool": "media.analyze", "input": {}, "description": "Process accessible media evidence"}])
        dispatch.assert_called_once()

    @patch.object(ToolExecutor, "execute_named")
    def test_planner_cannot_self_approve_operation_step(self, execute_named):
        execute_named.return_value = SimpleNamespace(execution_id="tool-test", output={"ok": True})
        operation = ComputerUseOperation.objects.create(
            owner=self.user, session=self.session, name="approval", title="approval", status="queued",
            request_text="Click submit", plan=[{"tool": "browser.click", "input": {"target": "submit", "confirmed": True}}],
        )
        ComputerUseOperationService.run(str(operation.pk))
        payload = execute_named.call_args.args[2]
        self.assertNotIn("confirmed", payload)

    @patch.object(BrowserObservationService, "blocker", return_value={"type": "captcha", "detail": "Human verification required."})
    @patch.object(BrowserObservationService, "observe", return_value=SimpleNamespace(dom={"elements": []}))
    @patch.object(BrowserSessionService, "backend")
    def test_blocker_cannot_be_overridden_by_action_input(self, backend, observe, blocker):
        with self.assertRaises(HumanInterventionRequired):
            BrowserActionService.execute(self.user, self.session, "click", {"target": "Continue", "allow_on_blocked_page": True})
        backend.return_value.perform.assert_not_called()

    @patch.object(ComputerUseOperationService, "dispatch", return_value="test-queue")
    def test_resume_after_approval_marks_only_current_step_confirmed(self, dispatch):
        self.operation.status = "waiting_user"
        self.operation.current_step = 0
        self.operation.configuration = {"attention": {"type": "approval", "detail": "Confirm external action"}}
        self.operation.save()
        response = self.client.post(f"/api/v1/internet/computer/operations/{self.operation.pk}/resume/", {}, format="json")
        self.assertEqual(response.status_code, 202)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.configuration.get("approval_granted_for_step"), 0)
        dispatch.assert_called_once()

from echo.apps.internet.local_system import (
    ApplicationDescriptor,
    ApplicationDiscoveryService,
    ApplicationLauncherService,
    DesktopWindowService,
    SystemLocationResolver,
)


class CompoundComputerTaskPlanningTests(SimpleTestCase):
    @patch("echo.apps.internet.desktop_control.ApplicationDiscoveryService.recognizes_application_name", return_value=True)
    def test_explicit_local_firefox_search_builds_single_computer_task(self, _recognizes):
        plan = ComputerTaskPlanner.from_request(
            "Open Firefox on my computer and search Django 5.2 documentation"
        )
        self.assertEqual(plan["environment"], "local_computer")
        self.assertEqual(plan["application"], "Firefox")
        self.assertEqual(
            [item["type"] for item in plan["actions"]],
            ["open_application", "browser_search_in_application"],
        )
        self.assertEqual(plan["actions"][1]["query"], "Django 5.2 documentation")

    @patch.object(ToolExecutor, "execute_named")
    def test_compound_command_delegates_to_authoritative_computer_task_tool(self, execute_named):
        execute_named.return_value = SimpleNamespace(
            execution_id="compound-task",
            output={"ok": True, "verified": True, "application": {"name": "Firefox"}, "steps": []},
        )
        metadata = {
            "environment": "local_computer",
            "application": "Firefox",
            "actions": [
                {"type": "open_application", "application": "Firefox"},
                {"type": "browser_search_in_application", "query": "Django 5.2 documentation"},
            ],
            "task_text": "search Django 5.2 documentation",
        }
        result = ComputerControlCommandRouter.handle(
            SimpleNamespace(is_staff=False),
            "Open Firefox on my computer and search Django 5.2 documentation",
            route_metadata=metadata,
        )
        self.assertEqual(result["route"], "computer.execute_task")
        self.assertEqual(execute_named.call_args.args[0], "computer.execute_task")
        self.assertNotEqual(execute_named.call_args.args[0], "text.search")


class LocalComputerUseRoutingTests(SimpleTestCase):
    def test_common_application_names_are_local_capability_candidates(self):
        self.assertTrue(ApplicationDiscoveryService.recognizes_application_name("Firefox"))
        self.assertTrue(ApplicationDiscoveryService.recognizes_application_name("Chrome"))
        self.assertTrue(ApplicationDiscoveryService.recognizes_application_name("VS Code"))
        self.assertTrue(ApplicationDiscoveryService.recognizes_application_name("Terminal"))

    def test_system_locations_resolve_without_web_search(self):
        self.assertTrue(SystemLocationResolver.recognizes("Trash Bin"))
        self.assertTrue(SystemLocationResolver.recognizes("Downloads"))
        self.assertTrue(SystemLocationResolver.recognizes("Downloads folder"))
        self.assertTrue(SystemLocationResolver.recognizes("Documents"))
        self.assertTrue(SystemLocationResolver.recognizes("Project directory"))
        self.assertTrue(SystemLocationResolver.recognizes("File Manager"))

    @patch.object(DesktopWindowService, "active_window", side_effect=[{"available": True, "title": "Desktop"}, {"available": True, "title": "Firefox"}])
    @patch("echo.apps.internet.local_system.ProcessInspector.executable_running", return_value=True)
    @patch("echo.apps.internet.local_system.subprocess.Popen")
    @patch.object(ApplicationDiscoveryService, "find")
    def test_application_launcher_reports_success_only_after_verification(self, find, popen, running, active_window):
        find.return_value = ApplicationDescriptor("firefox", "Firefox", "/usr/bin/firefox", (), "test")
        process = SimpleNamespace(pid=1234, poll=lambda: None)
        popen.return_value = process
        result = ApplicationLauncherService.launch("Firefox")
        self.assertTrue(result["verified"])
        self.assertEqual(result["application"]["name"], "Firefox")
        self.assertEqual(result["pid"], 1234)

    @patch.object(DesktopWindowService, "active_window", return_value={"available": False})
    @patch("echo.apps.internet.local_system.ProcessInspector.executable_running", return_value=False)
    @patch("echo.apps.internet.local_system.subprocess.Popen")
    @patch.object(ApplicationDiscoveryService, "find")
    def test_application_launcher_does_not_fabricate_success(self, find, popen, running, active_window):
        find.return_value = ApplicationDescriptor("firefox", "Firefox", "/usr/bin/firefox", (), "test")
        popen.return_value = SimpleNamespace(pid=1234, poll=lambda: 1)
        result = ApplicationLauncherService.launch("Firefox")
        self.assertFalse(result["verified"])
        self.assertEqual(result["verification"], "launch_sent_but_not_verified")

    @patch.object(ToolExecutor, "execute_named")
    def test_open_firefox_executes_local_application_tool_not_browser(self, execute_named):
        execute_named.return_value = SimpleNamespace(
            execution_id="launch-firefox",
            output={"verified": True, "application": {"name": "Firefox"}, "pid": 321},
        )
        result = ComputerControlCommandRouter.handle(SimpleNamespace(is_staff=False), "Open Firefox")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["route"], "computer.launch_application")
        self.assertEqual(execute_named.call_args.args[0], "computer.launch_application")
        self.assertNotIn("browser", execute_named.call_args.args[0])

    @patch.object(ToolExecutor, "execute_named")
    def test_open_trash_executes_system_location_tool_not_web_search(self, execute_named):
        execute_named.return_value = SimpleNamespace(
            execution_id="open-trash",
            output={"verified": True, "location": {"name": "Trash"}},
        )
        result = ComputerControlCommandRouter.handle(SimpleNamespace(is_staff=False), "Open Trash Bin")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["route"], "computer.open_path")
        self.assertEqual(execute_named.call_args.args[0], "computer.open_path")

