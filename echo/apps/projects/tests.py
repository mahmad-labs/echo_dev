from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Project
from .portability import ProjectPortabilityService


class ProjectPortabilityTests(TestCase):
    def test_export_and_restore_are_owner_scoped(self):
        user = get_user_model().objects.create_user(
            email="projects@example.com",
            password="StrongPassphrase123!",
        )
        Project.objects.create(owner=user, name="alpha", title="Alpha", status="active")
        package = ProjectPortabilityService.export(user)
        self.assertEqual(package["counts"]["project"], 1)
        restored = ProjectPortabilityService.restore(user, package["records"])
        self.assertEqual(restored["project"], 1)
        self.assertEqual(Project.objects.filter(owner=user).count(), 2)
