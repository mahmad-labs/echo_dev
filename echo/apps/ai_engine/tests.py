from django.apps import apps
from django.test import TestCase


class AiEngineModelTests(TestCase):
    def test_models_are_registered(self):
        self.assertGreaterEqual(len(list(apps.get_app_config('ai_engine').get_models())), 7)
