from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from kalender.models import Attendance, STATUS_ZUGESAGT, Session

from .models import LearningGroup, Membership


class RemoveMemberTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pw-owner-123456")
        self.member = User.objects.create_user("member", password="pw-member-123456")
        self.group = LearningGroup.objects.create(name="Testgruppe", created_by=self.owner)
        Membership.objects.create(group=self.group, user=self.owner)
        Membership.objects.create(group=self.group, user=self.member)
        start = timezone.now().replace(hour=18, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=2)
        self.member_session = Session.objects.create(
            group=self.group,
            title="Vom Mitglied",
            start=start,
            end=end,
            created_by=self.member,
        )
        self.member_block = Session.objects.create(
            group=self.group,
            title="Block",
            start=start + timedelta(days=1),
            end=end + timedelta(days=1),
            kind=Session.KIND_BLOCKIERT,
            created_by=self.member,
        )
        self.owner_session = Session.objects.create(
            group=self.group,
            title="Vom Ersteller",
            start=start + timedelta(days=2),
            end=end + timedelta(days=2),
            created_by=self.owner,
        )
        Attendance.objects.create(
            session=self.owner_session,
            user=self.member,
            status=STATUS_ZUGESAGT,
            start=self.owner_session.start,
            end=self.owner_session.end,
        )
        self.client.force_login(self.owner)
        self.url = f"/gruppen/{self.group.pk}/mitglieder/{self.member.pk}/entfernen/"

    def test_keeping_sessions_removes_only_the_membership(self):
        response = self.client.post(self.url, {"termine": "behalten"})

        self.assertRedirects(response, f"/gruppen/{self.group.pk}/einstellungen/")
        self.assertFalse(
            Membership.objects.filter(group=self.group, user=self.member).exists()
        )
        self.assertTrue(Session.objects.filter(pk=self.member_session.pk).exists())
        self.assertTrue(Session.objects.filter(pk=self.member_block.pk).exists())
        self.assertTrue(Session.objects.filter(pk=self.owner_session.pk).exists())
        self.assertFalse(Attendance.objects.filter(user=self.member).exists())

    def test_deleting_sessions_removes_that_members_entries(self):
        response = self.client.post(self.url, {"termine": "loeschen"})

        self.assertRedirects(response, f"/gruppen/{self.group.pk}/einstellungen/")
        self.assertFalse(
            Membership.objects.filter(group=self.group, user=self.member).exists()
        )
        self.assertFalse(Session.objects.filter(pk=self.member_session.pk).exists())
        self.assertFalse(Session.objects.filter(pk=self.member_block.pk).exists())
        self.assertTrue(Session.objects.filter(pk=self.owner_session.pk).exists())
        self.assertFalse(Attendance.objects.filter(user=self.member).exists())

    def test_missing_choice_keeps_the_member(self):
        response = self.client.post(self.url, {})

        self.assertRedirects(response, f"/gruppen/{self.group.pk}/einstellungen/")
        self.assertTrue(
            Membership.objects.filter(group=self.group, user=self.member).exists()
        )
        self.assertTrue(Session.objects.filter(pk=self.member_session.pk).exists())
