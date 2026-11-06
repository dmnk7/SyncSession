from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kalender.models import Session
from lerngruppen.models import LearningGroup, Membership


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "anna",
            password="Raumplan-48",
            first_name="Anna",
            last_name="Adler",
        )
        self.other = User.objects.create_user(
            "ben",
            password="Tafelbild-48",
            first_name="Ben",
            last_name="Berger",
        )
        self.own_group = LearningGroup.objects.create(name="Eigene Gruppe", created_by=self.user)
        Membership.objects.create(group=self.own_group, user=self.user)
        self.other_group = LearningGroup.objects.create(name="Fremde Gruppe", created_by=self.other)
        Membership.objects.create(group=self.other_group, user=self.other)
        Membership.objects.create(group=self.other_group, user=self.user)
        start = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        self.own_session = Session.objects.create(
            group=self.other_group,
            title="Eigener Termin",
            start=start,
            end=start + timedelta(hours=1),
            created_by=self.user,
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_name_link_points_to_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("profile"))
        self.assertContains(response, "Anna Adler")

    def test_update_name(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile"),
            {"first_name": "Anja", "last_name": "Albers"},
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Anja")
        self.assertEqual(self.user.last_name, "Albers")
        self.assertEqual(self.user.username, "anna")

    def test_name_is_required(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile"),
            {"first_name": "", "last_name": "Adler"},
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Anna")

    def test_wrong_password_keeps_account(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("delete_account"),
            {"password": "falsch"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Das Passwort ist nicht korrekt.")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_account_with_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("delete_account"),
            {"password": "Raumplan-48"},
        )
        self.assertRedirects(response, reverse("landing"))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(LearningGroup.objects.filter(pk=self.own_group.pk).exists())
        self.assertTrue(LearningGroup.objects.filter(pk=self.other_group.pk).exists())
        self.assertFalse(Membership.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Session.objects.filter(pk=self.own_session.pk).exists())
        follow = self.client.get(reverse("home"))
        self.assertEqual(follow.status_code, 302)
