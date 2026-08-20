from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ExecutionPlan, Goal, PlanStep, RiskAssessment


class PlanningEngine:
    """Create an executable plan from explicit outcomes, milestones, and constraints."""

    @classmethod
    @transaction.atomic
    def build(cls, goal: Goal, user) -> ExecutionPlan:
        configuration = goal.configuration or {}
        outcome = str(configuration.get("outcome") or goal.description or goal.title).strip()
        if not outcome:
            raise ValidationError({"outcome": "The goal must define an outcome."})
        milestones = configuration.get("milestones") or [
            "Confirm requirements and acceptance criteria",
            "Prepare dependencies and implementation inputs",
            "Execute the work and capture evidence",
            "Validate the result against acceptance criteria",
        ]
        if not isinstance(milestones, list) or not all(str(item).strip() for item in milestones):
            raise ValidationError({"milestones": "Milestones must be a non-empty list of text values."})

        plan = ExecutionPlan.objects.create(
            owner=user,
            name=goal.name,
            title=f"Plan: {goal.title or goal.name}",
            description=outcome,
            status="ready",
            category=goal.category,
            configuration={
                "goal_id": str(goal.pk),
                "constraints": configuration.get("constraints", []),
                "success_criteria": configuration.get("success_criteria", []),
                "step_count": len(milestones),
            },
        )
        for position, milestone in enumerate(milestones, start=1):
            PlanStep.objects.create(
                owner=user,
                name=f"step-{position}",
                title=str(milestone).strip(),
                status="pending",
                category="plan.step",
                configuration={
                    "plan_id": str(plan.pk),
                    "position": position,
                    "depends_on": [] if position == 1 else [f"step-{position - 1}"],
                },
            )

        risks = configuration.get("risks", [])
        for risk in risks if isinstance(risks, list) else []:
            risk_data: dict[str, Any] = risk if isinstance(risk, dict) else {"description": str(risk)}
            RiskAssessment.objects.create(
                owner=user,
                name=risk_data.get("name", "risk"),
                title=risk_data.get("title", risk_data.get("description", "Risk")),
                description=risk_data.get("description", ""),
                status="open",
                category="plan.risk",
                configuration={"plan_id": str(plan.pk), **risk_data},
            )
        return plan
