from __future__ import annotations

from rest_framework.permissions import BasePermission

from echo.common.permissions import IsAdministrator, IsOwnerOrAdministrator


class HasPlatformPermission(BasePermission):
    """Resolve a permission codename through Echo roles, Django permissions, or staff status."""

    required_permission: str | None = None

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True

        codename = getattr(view, "required_permission", None) or self.required_permission
        if not codename:
            return True
        if user.has_perm(codename):
            return True
        return user.roles.filter(permission_links__permission__codename=codename).exists()


__all__ = ("HasPlatformPermission", "IsAdministrator", "IsOwnerOrAdministrator")
