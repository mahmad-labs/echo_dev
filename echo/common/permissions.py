from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrAdministrator(BasePermission):
    message = 'You do not have access to this resource.'

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        for attr in ('owner_id', 'user_id', 'actor_id'):
            if hasattr(obj, attr):
                value = getattr(obj, attr)
                return value == request.user.pk
        return request.method in SAFE_METHODS


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)
