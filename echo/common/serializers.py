from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers


class DynamicModelSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def _validate_related_owner(self, field_name, value, user):
        if value is None:
            return
        values = list(value) if isinstance(value, (list, tuple, set)) else [value]
        user_model = get_user_model()
        for related in values:
            if isinstance(related, user_model):
                if related.pk != user.pk:
                    raise serializers.ValidationError(
                        {field_name: "The related user is outside your access scope."}
                    )
                continue
            field_names = {field.name for field in related._meta.fields}
            scope_field = next(
                (name for name in ("owner", "user", "actor") if name in field_names),
                None,
            )
            if scope_field and getattr(related, f"{scope_field}_id", None) != user.pk:
                raise serializers.ValidationError(
                    {field_name: "The related resource is outside your access scope."}
                )

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not user.is_staff:
            model = self.Meta.model
            relation_fields = {
                field.name: field
                for field in model._meta.get_fields()
                if field.is_relation and not field.auto_created
            }
            for field_name, value in attrs.items():
                if field_name in relation_fields:
                    self._validate_related_owner(field_name, value, user)
        return super().validate(attrs)

    def create(self, validated_data):
        request = self.context.get("request")
        model = self.Meta.model
        field_names = {field.name for field in model._meta.fields}
        if request and request.user.is_authenticated:
            if "owner" in field_names and not validated_data.get("owner"):
                validated_data["owner"] = request.user
            elif "user" in field_names and not validated_data.get("user"):
                validated_data["user"] = request.user
            elif "actor" in field_names and not validated_data.get("actor"):
                validated_data["actor"] = request.user
        return super().create(validated_data)
