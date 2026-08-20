from django.apps import apps
from django.test import TestCase


class CodeAssistantModelTests(TestCase):
    def test_models_are_registered(self):
        self.assertGreaterEqual(len(list(apps.get_app_config('code_assistant').get_models())), 7)
