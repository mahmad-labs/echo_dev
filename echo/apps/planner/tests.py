from django.apps import apps
from django.test import TestCase


class PlannerModelTests(TestCase):
    def test_models_are_registered(self):
        self.assertGreaterEqual(len(list(apps.get_app_config('planner').get_models())), 6)
