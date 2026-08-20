from django.apps import apps
from django.test import TestCase


class NotificationsModelTests(TestCase):
    def test_models_are_registered(self):
        self.assertGreaterEqual(len(list(apps.get_app_config('notifications').get_models())), 6)
