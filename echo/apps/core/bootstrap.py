from __future__ import annotations

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction


@transaction.atomic
def bootstrap_platform() -> dict[str, int]:
    """Create the idempotent baseline required by a newly migrated Echo database."""
    from echo.apps.authentication.models import Permission, RolePermission, UserRole
    from echo.apps.core.models import ApplicationRegistry, FeatureFlag, SystemConfiguration

    permission_codes = [
        "platform.view",
        "platform.manage",
        "users.manage",
        "agents.execute",
        "workflows.execute",
        "tools.execute",
        "memory.read",
        "memory.write",
        "knowledge.read",
        "knowledge.write",
        "projects.manage",
    ]
    permission_objects = {
        code: Permission.objects.get_or_create(
            codename=code,
            defaults={"name": code.replace(".", " ").title()},
        )[0]
        for code in permission_codes
    }
    role_definitions = {
        "Administrator": permission_codes,
        "Developer": [
            "platform.view",
            "agents.execute",
            "workflows.execute",
            "tools.execute",
            "memory.read",
            "memory.write",
            "knowledge.read",
            "knowledge.write",
        ],
        "Standard User": ["platform.view", "agents.execute", "workflows.execute", "tools.execute", "memory.read", "memory.write", "knowledge.read", "knowledge.write"],
    }
    roles = {}
    for role_name, codes in role_definitions.items():
        role, _ = UserRole.objects.get_or_create(
            name=role_name,
            defaults={"is_system": True},
        )
        roles[role_name] = role
        for code in codes:
            RolePermission.objects.get_or_create(
                role=role,
                permission=permission_objects[code],
            )

    for user in get_user_model().objects.all():
        user.roles.add(roles["Administrator"] if user.is_staff else roles["Standard User"])

    SystemConfiguration.objects.get_or_create(
        key="platform.name",
        defaults={
            "name": "platform.name",
            "title": "Platform name",
            "status": "active",
            "value": {"value": "Echo"},
            "value_type": "string",
            "category": "platform",
            "editable": False,
        },
    )
    FeatureFlag.objects.get_or_create(
        name="enterprise_api",
        defaults={
            "title": "Enterprise API",
            "status": "active",
            "enabled": True,
            "rollout_percentage": 100,
            "environment": "all",
        },
    )
    for app_config in apps.get_app_configs():
        if app_config.name.startswith("echo.apps."):
            ApplicationRegistry.objects.get_or_create(
                name=app_config.label,
                defaults={
                    "title": app_config.verbose_name,
                    "status": "active",
                    "version": 1,
                    "enabled": True,
                },
            )
    return {
        "permissions": len(permission_objects),
        "roles": len(roles),
        "applications": ApplicationRegistry.objects.count(),
    }
