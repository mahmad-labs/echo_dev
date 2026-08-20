from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from echo.apps.knowledge.services import KnowledgeAgentService
from echo.apps.internet.models import BrowserSession, ComputerSession
from echo.apps.memory.models import Memory
from echo.apps.projects.models import Project
from echo.apps.tool_manager.execution import ToolExecutor

from .intent_router import UniversalIntentRouter
from .models import AgentCommunication, AgentTask
from .orchestration import AgentManagerOrchestrator
from .registry import AgentRegistry


@override_settings(AI_PROVIDER_BASE_URL="", AI_PROVIDER_API_KEY="", AI_PROVIDER_MODEL="")
class AgentManagerIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(email="agents@example.com", password="EchoAgents!2026")
        cls.other = get_user_model().objects.create_user(email="other-agents@example.com", password="EchoAgents!2026")

    def test_registry_materializes_specialists_with_declared_capabilities(self):
        identifiers = {item.identifier for item in AgentRegistry.materialize_all(self.user)}
        self.assertTrue({"memory", "knowledge", "planner", "browser", "computer", "documents", "projects", "tasks", "workflow", "chat"}.issubset(identifiers))
        browser = AgentRegistry.get("browser")
        self.assertIn("browser.verify", browser.capabilities)
        self.assertIn("tools.execute", browser.required_permissions)

    def test_text_memory_routes_through_manager_and_persists_structured_task_graph(self):
        result = AgentManagerOrchestrator(self.user, source="text", section="home").execute(
            "Remember that Echo is my main AI project"
        )
        self.assertEqual(result.route, "memory.store")
        self.assertTrue(Memory.objects.filter(owner=self.user, content__icontains="main AI project").exists())
        root = AgentTask.objects.get(pk=result.data["parent_agent_task_id"], owner=self.user)
        child = root.child_tasks.select_related("agent").get(pk=result.data["child_agent_task_id"])
        self.assertEqual(child.agent.identifier, "memory")
        self.assertEqual(root.status, "completed")
        self.assertTrue(child.communications.filter(message_type="assignment").exists())
        self.assertTrue(child.communications.filter(message_type="result").exists())

    def test_knowledge_agent_uses_central_knowledge_service_and_owner_scope(self):
        KnowledgeAgentService.ingest(self.user, title="Django authentication", content="Django authentication supports sessions and pluggable backends.", source_type="test", source_id="django-auth")
        KnowledgeAgentService.ingest(self.other, title="Private other knowledge", content="authentication secret other owner", source_type="test", source_id="other")
        result = AgentManagerOrchestrator(self.user).execute("Search my knowledge for Django authentication")
        self.assertEqual(result.route, "knowledge.search")
        sources = result.data.get("sources", [])
        self.assertTrue(any("Django authentication" in item.get("title", "") for item in sources))
        self.assertFalse(any("Private other knowledge" in item.get("title", "") for item in sources))

    def test_continue_project_coordinates_planner_memory_knowledge_and_project_agent(self):
        project = Project.objects.create(owner=self.user, name="Echo", title="Echo", description="Main AI operating environment", status="active", category="ai", configuration={})
        KnowledgeAgentService.ingest(self.user, title="Echo architecture", content="Echo uses a central Agent Manager.", source_type="project", source_id=str(project.pk))
        AgentManagerOrchestrator(self.user).execute("Remember that Echo uses owner scoped context")
        result = AgentManagerOrchestrator(self.user).execute("Continue my Echo project")
        root = AgentTask.objects.get(pk=result.data["parent_agent_task_id"])
        children = list(root.child_tasks.select_related("agent").order_by("created_at"))
        self.assertGreaterEqual(len(children), 2)
        self.assertEqual(children[0].agent.identifier, "planner")
        self.assertEqual(children[-1].agent.identifier, "projects")
        planner_assignment = children[0].communications.filter(message_type="assignment").first()
        self.assertEqual((planner_assignment.payload.get("context") or {}).get("project_id"), str(project.pk))
        self.assertEqual(((planner_assignment.payload.get("context") or {}).get("project_context") or {}).get("title"), "Echo")
        self.assertEqual(root.project_id, project.pk)
        self.assertEqual(result.conversation.data.get("current_project_id"), str(project.pk))
        context_messages = AgentCommunication.objects.filter(task__in=children, message_type__in=("context_request", "context_result"))
        participants = set(context_messages.values_list("sender_agent__identifier", flat=True)) | set(context_messages.values_list("recipient_agent__identifier", flat=True))
        self.assertIn("memory", participants)
        self.assertIn("knowledge", participants)

    def test_workflow_tool_can_delegate_back_to_shared_agent_manager(self):
        self.assertIn("agent.execute", ToolExecutor.available_handlers())
        execution = ToolExecutor.execute_named("agent.execute", self.user, {"prompt": "Show my active tasks", "source": "workflow"})
        self.assertEqual(execution.status, "completed")
        self.assertIn(execution.output["route"], {"tasks.list", "agent.tasks"})
        self.assertTrue(execution.output.get("agent_task_id"))

    def test_cancel_latest_cancels_root_and_nonterminal_children(self):
        root = AgentTask.objects.create(owner=self.user, name="root", title="root", status="running", category="orchestration_root", request_text="long task")
        child = AgentTask.objects.create(owner=self.user, parent_task=root, agent=AgentRegistry.ensure_record(self.user, "chat"), name="child", title="child", status="waiting", request_text="long task")
        cancelled = AgentManagerOrchestrator.cancel_latest(self.user)
        self.assertEqual(cancelled.pk, root.pk)
        root.refresh_from_db(); child.refresh_from_db()
        self.assertTrue(root.cancel_requested)
        self.assertTrue(child.cancel_requested)
        self.assertEqual(child.status, "cancelled")

    def test_bare_voice_stop_cancels_active_work_before_disabling_listening(self):
        root = AgentTask.objects.create(owner=self.user, name="voice-root", title="voice-root", status="running", category="orchestration_root", request_text="browser task")
        result = AgentManagerOrchestrator(self.user, source="voice", section="voice").execute("Stop")
        root.refresh_from_db()
        self.assertEqual(result.route, "agent.cancel")
        self.assertTrue(root.cancel_requested)


class UniversalIntentRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(email="routing@example.com", password="EchoRouting!2026")

    def setUp(self):
        self.manager = AgentManagerOrchestrator(self.user)

    def test_local_applications_route_to_computer_before_browser(self):
        for command in ("Open Firefox", "Open Chrome", "Open VS Code", "Open Terminal"):
            decision = self.manager.decide(command)
            self.assertEqual(decision.agent, "computer", command)
            self.assertEqual(decision.intent, "local_application", command)

    @patch("echo.apps.agent_manager.intent_router.ApplicationDiscoveryService.recognizes_application_name", return_value=True)
    def test_exact_website_alias_wins_over_fuzzy_application_match(self, _recognizes):
        decision = UniversalIntentRouter.classify("Open Google", user=self.user)
        self.assertEqual(decision.agent, "browser")
        self.assertEqual(decision.intent, "website_action")
        self.assertEqual(decision.url, "https://www.google.com/")

    @patch("echo.apps.agent_manager.intent_router.ApplicationDiscoveryService.recognizes_application_name", return_value=True)
    def test_explicit_computer_environment_preserves_compound_firefox_search_task(self, _recognizes):
        decision = UniversalIntentRouter.classify(
            "Open Firefox on my computer and search Django 5.2 documentation",
            user=self.user,
        )
        self.assertEqual(decision.agent, "computer")
        self.assertEqual(decision.intent, "computer_task")
        self.assertEqual(decision.metadata["environment"], "local_computer")
        self.assertEqual(decision.metadata["application"], "Firefox")
        self.assertEqual(decision.query, "Django 5.2 documentation")
        self.assertEqual(
            [item["type"] for item in decision.metadata["actions"]],
            ["open_application", "browser_search_in_application"],
        )

    @patch("echo.apps.agent_manager.intent_router.ApplicationDiscoveryService.recognizes_application_name", return_value=True)
    def test_compound_local_application_search_is_not_generic_web_search(self, _recognizes):
        decision = self.manager.decide("Open Firefox and search Django 5.2 documentation")
        self.assertEqual(decision.agent, "computer")
        self.assertEqual(decision.intent, "computer_task")
        self.assertFalse(decision.clarification)
        self.assertEqual(decision.query, "Django 5.2 documentation")

    @patch("echo.apps.agent_manager.intent_router.ApplicationDiscoveryService.recognizes_application_name", return_value=True)
    def test_explicit_using_application_environment_beats_search_verb(self, _recognizes):
        decision = UniversalIntentRouter.classify("Search Django 5.2 documentation using Firefox", user=self.user)
        self.assertEqual(decision.agent, "computer")
        self.assertEqual(decision.intent, "computer_task")
        self.assertEqual(decision.metadata["application"], "Firefox")
        self.assertEqual(decision.query, "Django 5.2 documentation")

    def test_system_locations_route_to_computer_not_web_search(self):
        for command in ("Open Trash Bin", "Open Downloads", "Open Downloads folder", "Open Documents", "Open File Manager", "Show my project directory"):
            decision = self.manager.decide(command)
            self.assertEqual(decision.agent, "computer", command)
            self.assertEqual(decision.intent, "local_system_location", command)

    def test_websites_and_explicit_search_remain_browser_intents(self):
        expected = {
            "Open YouTube": "website_action",
            "Open Google": "website_action",
            "Go to github.com": "website_action",
            "Search Google for Django": "web_search",
        }
        for command, intent in expected.items():
            decision = self.manager.decide(command)
            self.assertEqual(decision.agent, "browser", command)
            self.assertEqual(decision.intent, intent, command)

    def test_ambiguous_open_does_not_become_google_search(self):
        decision = self.manager.decide("Open Python")
        self.assertEqual(decision.agent, "chat")
        self.assertEqual(decision.intent, "ambiguous_open")
        self.assertTrue(decision.clarification)

    def test_contextual_open_uses_recent_browser_instead_of_ambiguous_search(self):
        BrowserSession.objects.create(owner=self.user, name="browser", title="Browser", status="active", current_url="https://www.youtube.com/", last_activity_at=timezone.now())
        decision = self.manager.decide("Open that video")
        self.assertEqual(decision.agent, "browser")
        self.assertEqual(decision.intent, "contextual_interaction")

    def test_contextual_scroll_prefers_recent_desktop_when_desktop_is_active(self):
        ComputerSession.objects.create(owner=self.user, name="desktop", title="Desktop", status="active", last_activity_at=timezone.now())
        decision = self.manager.decide("Scroll down")
        self.assertEqual(decision.agent, "computer")
        self.assertEqual(decision.intent, "contextual_interaction")
