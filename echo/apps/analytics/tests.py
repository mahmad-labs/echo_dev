from django.apps import apps
from django.test import TestCase


class AnalyticsModelTests(TestCase):
    def test_models_are_registered(self):
        self.assertGreaterEqual(len(list(apps.get_app_config('analytics').get_models())), 6)
