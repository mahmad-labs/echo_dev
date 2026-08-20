from django.apps import apps
from django.test import TestCase


class SettingsModelTests(TestCase):
    def test_models_are_registered(self):
        self.assertGreaterEqual(len(list(apps.get_app_config('settings').get_models())), 6)
