from django.apps import apps
from django.test import TestCase


class KnowledgeModelTests(TestCase):
    def test_models_are_registered(self):
        self.assertGreaterEqual(len(list(apps.get_app_config('knowledge').get_models())), 10)
