from __future__ import annotations

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "display_name",
        "is_verified",
        "is_staff",
        "is_active",
        "last_login",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "is_verified", "is_deleted")
    search_fields = ("email", "username", "display_name", "first_name", "last_name")
    readonly_fields = ("created_at", "updated_at", "last_login", "date_joined")
    filter_horizontal = ("groups", "user_permissions", "roles")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "display_name",
                    "first_name",
                    "last_name",
                    "phone",
                    "country",
                    "timezone",
                    "language",
                    "profile_picture",
                    "bio",
                    "date_of_birth",
                    "gender",
                )
            },
        ),
        (
            "Access",
            {
                "fields": (
                    "is_active",
                    "is_verified",
                    "is_deleted",
                    "is_staff",
                    "is_superuser",
                    "roles",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


for model in apps.get_app_config("authentication").get_models():
    if model is User:
        continue
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
