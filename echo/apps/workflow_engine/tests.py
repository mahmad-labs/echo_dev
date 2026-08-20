from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from echo.apps.authentication.models import Permission, RolePermission, UserRole
from echo.apps.tool_manager.models import Tool

from .executor import WorkflowExecutor
from .models import Checkpoint, Workflow, WorkflowExecution


class WorkflowExecutionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="workflow@example.com",
            password="StrongPassphrase123!",
        )
        permission, _ = Permission.objects.get_or_create(
            codename="tools.execute",
            defaults={"name": "Execute tools"},
        )
        role, _ = UserRole.objects.get_or_create(name="Workflow Operator")
        RolePermission.objects.get_or_create(role=role, permission=permission)
        self.user.roles.add(role)
        self.tool = Tool.objects.create(
            owner=self.user,
            name="calculator",
            title="Calculator",
            status="active",
            configuration={"handler": "math.calculate"},
        )

    def test_dependency_ordered_workflow_completes(self):
        workflow = Workflow.objects.create(
            owner=self.user,
            name="calculation",
            title="Calculation workflow",
            status="active",
            configuration={
                "steps": [
                    {"id": "first", "tool_id": str(self.tool.pk), "input": {"operation": "add", "left": 2, "right": 3}},
                    {"id": "second", "depends_on": ["first"], "tool_id": str(self.tool.pk), "input": {"operation": "multiply", "left": 3, "right": 4}},
                ]
            },
        )
        execution = WorkflowExecutor.execute(workflow, self.user)
        self.assertEqual(execution.status, "completed")
        self.assertEqual(Checkpoint.objects.filter(owner=self.user).count(), 2)

    def test_cycle_is_rejected(self):
        with self.assertRaises(ValidationError):
            WorkflowExecutor._ordered_steps(
                {"steps": [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]}
            )

    def test_failed_workflow_execution_is_persisted(self):
        workflow = Workflow.objects.create(
            owner=self.user,
            name="failure",
            title="Failure workflow",
            status="active",
            configuration={
                "steps": [
                    {
                        "id": "failure",
                        "tool_id": str(self.tool.pk),
                        "input": {"operation": "divide", "left": 1, "right": 0},
                    }
                ]
            },
        )
        with self.assertRaises(Exception):
            WorkflowExecutor.execute(workflow, self.user)
        execution = WorkflowExecution.objects.get(owner=self.user, name="failure")
        self.assertEqual(execution.status, "failed")
        self.assertEqual(execution.configuration["error"], "division by zero")
