from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kalender.models import Attendance, Session
from lerngruppen.models import LearningGroup, Membership


class AuthEntryTests(TestCase):
    def test_root_sends_anonymous_users_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, reverse("login"))

    def test_root_sends_logged_in_users_home(self):
        user = User.objects.create_user("anna", password="Raumplan-48")
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("home"))

    def test_signup_stays_available(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Konto erstellen")
        self.assertContains(response, reverse("login"))

    def test_login_page_links_to_signup(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Einloggen")
        self.assertContains(response, reverse("landing"))


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
        self.assertRedirects(response, reverse("login"))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(LearningGroup.objects.filter(pk=self.own_group.pk).exists())
        self.assertTrue(LearningGroup.objects.filter(pk=self.other_group.pk).exists())
        self.assertFalse(Membership.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Session.objects.filter(pk=self.own_session.pk).exists())
        follow = self.client.get(reverse("home"))
        self.assertEqual(follow.status_code, 302)


class HomeUpcomingTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user(
            "anna",
            password="Raumplan-48",
            first_name="Anna",
            last_name="Adler",
        )
        self.ben = User.objects.create_user(
            "ben",
            password="Tafelbild-48",
            first_name="Ben",
            last_name="Berger",
        )
        self.clara = User.objects.create_user(
            "clara",
            password="Skriptseite-48",
            first_name="Clara",
            last_name="Conrad",
        )
        self.math = LearningGroup.objects.create(
            name="Angewandte Mathematik",
            created_by=self.anna,
        )
        self.web = LearningGroup.objects.create(
            name="Agile Webentwicklung",
            created_by=self.ben,
        )
        for group in (self.math, self.web):
            for user in (self.anna, self.ben, self.clara):
                Membership.objects.create(group=group, user=user)
        self.now = timezone.now().replace(second=0, microsecond=0)
        self.client.force_login(self.anna)

    def session(self, group, created_by, title, start, location="", **overrides):
        return Session.objects.create(
            group=group,
            title=title,
            location=location,
            start=start,
            end=overrides.get("end", start + timedelta(hours=2)),
            kind=overrides.get("kind", Session.KIND_VORSCHLAG),
            created_by=created_by,
            display_override=overrides.get("display_override", ""),
        )

    def accept(self, session, user, start=None, end=None):
        Attendance.objects.create(
            session=session,
            user=user,
            status="zugesagt",
            start=start or session.start,
            end=end or session.end,
        )

    def decline(self, session, user):
        Attendance.objects.create(session=session, user=user, status="abgesagt")

    def test_empty_state_without_accepted_sessions(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Nächste Termine")
        self.assertContains(response, "Es stehen keine angenommenen Termine an.")

    def test_lists_the_next_accepted_sessions_from_every_group(self):
        later = self.now + timedelta(days=2)
        first = self.session(
            self.web,
            self.ben,
            "Django Views",
            self.now + timedelta(days=1),
            location="Online",
        )
        second = self.session(
            self.math,
            self.anna,
            "Übungsblatt 5",
            later,
            location="Raum C12",
        )
        third = self.session(
            self.web,
            self.anna,
            "Gruppenreview",
            later + timedelta(hours=4),
            location="Raum B3",
        )
        self.accept(first, self.anna)
        self.accept(first, self.clara)
        self.accept(second, self.ben)
        self.accept(second, self.clara)
        self.accept(third, self.ben)
        self.accept(third, self.clara)

        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertContains(response, "Django Views")
        self.assertContains(response, "Online")
        self.assertContains(response, "Übungsblatt 5")
        self.assertContains(response, "Raum C12")
        self.assertContains(response, "Gruppenreview")
        self.assertContains(response, "Raum B3")
        self.assertContains(response, "Angewandte Mathematik")
        self.assertContains(response, "Agile Webentwicklung")
        self.assertNotContains(response, "Es stehen keine angenommenen Termine an.")
        self.assertLess(content.index("Django Views"), content.index("Übungsblatt 5"))
        self.assertLess(content.index("Übungsblatt 5"), content.index("Gruppenreview"))

    def test_shows_only_the_next_three_accepted_sessions(self):
        titles = ("Eins", "Zwei", "Drei", "Vier")
        for index, title in enumerate(titles):
            session = self.session(
                self.math,
                self.anna,
                title,
                self.now + timedelta(days=index + 1),
            )
            self.accept(session, self.ben)
            self.accept(session, self.clara)

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Eins")
        self.assertContains(response, "Zwei")
        self.assertContains(response, "Drei")
        self.assertNotContains(response, "Vier")

    def test_hides_open_declined_blocked_and_past_sessions(self):
        start = self.now + timedelta(days=1)
        self.session(self.math, self.anna, "Offen", start)
        declined = self.session(self.math, self.anna, "Fällt aus", start)
        self.decline(declined, self.ben)
        self.decline(declined, self.clara)
        self.session(
            self.math,
            self.anna,
            "Nebenjob",
            start,
            kind=Session.KIND_BLOCKIERT,
        )
        past = self.session(
            self.math,
            self.anna,
            "Gestern",
            self.now - timedelta(days=2),
            end=self.now - timedelta(days=2, hours=-2),
        )
        self.accept(past, self.ben)
        self.accept(past, self.clara)

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Es stehen keine angenommenen Termine an.")
        self.assertNotContains(response, "Offen")
        self.assertNotContains(response, "Fällt aus")
        self.assertNotContains(response, "Nebenjob")
        self.assertNotContains(response, "Gestern")

    def test_mixed_session_appears_only_after_creator_accepts_it(self):
        session = self.session(
            self.math,
            self.anna,
            "Klausurvorbereitung",
            self.now + timedelta(days=1),
            location="Lernraum 2",
        )
        self.accept(session, self.ben)
        self.decline(session, self.clara)

        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Klausurvorbereitung")

        session.display_override = Session.DISPLAY_ANGENOMMEN
        session.save(update_fields=["display_override"])

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Klausurvorbereitung")
        self.assertContains(response, "Lernraum 2")

    def test_declined_member_does_not_see_a_forced_session(self):
        session = self.session(
            self.math,
            self.anna,
            "Klausurvorbereitung",
            self.now + timedelta(days=1),
        )
        self.accept(session, self.ben)
        self.decline(session, self.clara)
        session.display_override = Session.DISPLAY_ANGENOMMEN
        session.save(update_fields=["display_override"])

        self.client.force_login(self.clara)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Klausurvorbereitung")
