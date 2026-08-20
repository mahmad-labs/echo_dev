from rest_framework import permissions, viewsets

from .permissions import IsOwnerOrAdministrator


class SecuredModelViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrAdministrator)
    ordering_fields = '__all__'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return queryset
        names = {field.name for field in queryset.model._meta.fields}
        if 'owner' in names:
            return queryset.filter(owner=user)
        if 'user' in names:
            return queryset.filter(user=user)
        if 'actor' in names:
            return queryset.filter(actor=user)
        return queryset.none()

    def perform_create(self, serializer):
        names = {field.name for field in serializer.Meta.model._meta.fields}
        if 'owner' in names:
            serializer.save(owner=self.request.user)
        elif 'user' in names:
            serializer.save(user=self.request.user)
        elif 'actor' in names:
            serializer.save(actor=self.request.user)
        else:
            serializer.save()
