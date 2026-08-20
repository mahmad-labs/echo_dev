from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .scheduling import SchedulingService


class SchedulingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="calendar@example.com",
            password="StrongPassphrase123!",
        )

    def test_conflicting_event_is_rejected(self):
        SchedulingService.create_event(
            self.user,
            {"title": "First", "start": "2026-08-10T10:00:00+00:00", "end": "2026-08-10T11:00:00+00:00"},
        )
        with self.assertRaises(ValidationError):
            SchedulingService.create_event(
                self.user,
                {"title": "Second", "start": "2026-08-10T10:30:00+00:00", "end": "2026-08-10T11:30:00+00:00"},
            )
