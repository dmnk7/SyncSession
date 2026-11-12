from datetime import timedelta, timezone as datetime_timezone

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone
from icalendar import Calendar

from lerngruppen.models import LearningGroup, Membership

from .colors import (
    CONSENSUS_BACKGROUND,
    CONSENSUS_COLOR,
    DECLINED_BACKGROUND,
    DECLINED_COLOR,
    EVENT_COLORS,
    background_for_user,
    color_for_user,
)
from .models import Attendance, Session


def iso(moment):
    return moment.isoformat()


class CalendarTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner", password="pw-owner-123456")
        cls.member = User.objects.create_user("member", password="pw-member-123456")
        cls.stranger = User.objects.create_user("stranger", password="pw-stranger-123")
        cls.group = LearningGroup.objects.create(
            name="Testgruppe",
            created_by=cls.owner,
        )
        Membership.objects.create(group=cls.group, user=cls.owner)
        Membership.objects.create(group=cls.group, user=cls.member)

    def setUp(self):
        self.now = timezone.now()
        self.start = self.now.replace(hour=18, minute=0, second=0, microsecond=0)
        self.end = self.start + timedelta(hours=2)

    def login(self, user):
        client = Client()
        client.force_login(user)
        return client

    def payload(self, **overrides):
        data = {
            "title": "Lernen",
            "location": "Online",
            "start": iso(self.start),
            "end": iso(self.end),
        }
        data.update(overrides)
        return data

    def create_session(self, created_by, **overrides):
        return Session.objects.create(
            group=self.group,
            title=overrides.get("title", "Lernen"),
            location=overrides.get("location", ""),
            start=overrides.get("start", self.start),
            end=overrides.get("end", self.end),
            kind=overrides.get("kind", Session.KIND_VORSCHLAG),
            created_by=created_by,
        )


class SessionListTests(CalendarTestCase):
    def test_requires_login(self):
        response = self.client.get(f"/gruppen/{self.group.pk}/termine/")
        self.assertEqual(response.status_code, 302)

    def test_non_member_gets_no_list(self):
        response = self.login(self.stranger).get(
            f"/gruppen/{self.group.pk}/termine/"
        )
        self.assertEqual(response.status_code, 403)

    def test_member_sees_sessions_with_edit_flag(self):
        own = self.create_session(self.member)
        other = self.create_session(self.owner, title="Anderer Termin")

        response = self.login(self.member).get(
            f"/gruppen/{self.group.pk}/termine/"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        by_id = {item["id"]: item for item in data}
        self.assertTrue(by_id[own.id]["editable"])
        self.assertFalse(by_id[other.id]["editable"])
        self.assertEqual(by_id[own.id]["created_by"], "member")
        self.assertIn("update_url", by_id[own.id])
        self.assertIn("delete_url", by_id[own.id])

    def test_range_filter_excludes_old_sessions(self):
        old = self.create_session(self.owner, start=self.now - timedelta(days=30),
                                  end=self.now - timedelta(days=30, hours=-2))
        current = self.create_session(self.owner)

        client = self.login(self.member)
        response = client.get(
            f"/gruppen/{self.group.pk}/termine/",
            {
                "start": iso(self.now - timedelta(days=1)),
                "end": iso(self.now + timedelta(days=1)),
            },
        )

        ids = [item["id"] for item in response.json()]
        self.assertIn(current.id, ids)
        self.assertNotIn(old.id, ids)


class SessionStatusTests(CalendarTestCase):
    def status(self, client):
        response = client.get(f"/gruppen/{self.group.pk}/termine/status/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_requires_login(self):
        response = self.client.get(f"/gruppen/{self.group.pk}/termine/status/")
        self.assertEqual(response.status_code, 302)

    def test_non_member_gets_no_status(self):
        response = self.login(self.stranger).get(
            f"/gruppen/{self.group.pk}/termine/status/"
        )
        self.assertEqual(response.status_code, 403)

    def test_member_gets_timestamp_and_member_count(self):
        self.create_session(self.owner)

        data = self.status(self.login(self.member))

        self.assertIsNotNone(data["updated_at"])
        self.assertEqual(data["member_count"], 2)

    def test_attendance_change_bumps_timestamp(self):
        session = self.create_session(self.owner)
        before = self.status(self.login(self.member))["updated_at"]

        Attendance.objects.create(
            session=session,
            user=self.member,
            status="abgesagt",
        )

        after = self.status(self.login(self.member))["updated_at"]
        self.assertGreater(after, before)

    def test_new_membership_changes_member_count(self):
        client = self.login(self.member)
        before = self.status(client)["member_count"]

        late = User.objects.create_user("spaeter", password="pw-spaeter-123456")
        Membership.objects.create(group=self.group, user=late)

        after = self.status(client)
        self.assertEqual(after["member_count"], before + 1)

    def test_calendar_page_exposes_status_url(self):
        response = self.login(self.member).get(f"/gruppen/{self.group.pk}/")
        self.assertContains(
            response, f"/gruppen/{self.group.pk}/termine/status/"
        )


class SessionCreateTests(CalendarTestCase):
    def test_member_can_create(self):
        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Session.objects.count(), 1)
        session = Session.objects.get()
        self.assertEqual(session.created_by, self.member)
        self.assertEqual(session.kind, Session.KIND_VORSCHLAG)
        self.assertEqual(response.json()["sessions"][0]["title"], "Lernen")

    def test_non_member_cannot_create(self):
        response = self.login(self.stranger).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Session.objects.count(), 0)

    def test_end_before_start_is_rejected(self):
        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.payload(end=iso(self.start - timedelta(minutes=30))),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Session.objects.count(), 0)

    def test_missing_title_is_rejected(self):
        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.payload(title=""),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.json()["errors"])


class SessionUpdateTests(CalendarTestCase):
    def test_creator_can_move_own_session(self):
        session = self.create_session(self.member)
        new_start = self.start + timedelta(days=1)
        new_end = new_start + timedelta(hours=1)

        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/",
            self.payload(start=iso(new_start), end=iso(new_end)),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.start, new_start)
        self.assertEqual(session.end, new_end)

    def test_creator_of_group_cannot_move_foreign_session(self):
        session = self.create_session(self.member)

        response = self.login(self.owner).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/",
            self.payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_member_cannot_move_foreign_session(self):
        session = self.create_session(self.owner)

        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/",
            self.payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_non_member_cannot_update(self):
        session = self.create_session(self.member)

        response = self.login(self.stranger).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/",
            self.payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)


class SessionDeleteTests(CalendarTestCase):
    def test_creator_can_delete_own_session(self):
        session = self.create_session(self.member)

        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/loeschen/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(Session.objects.count(), 0)

    def test_group_creator_cannot_delete_foreign_session(self):
        session = self.create_session(self.member)

        response = self.login(self.owner).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/loeschen/"
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Session.objects.count(), 1)

    def test_non_member_cannot_delete(self):
        session = self.create_session(self.member)

        response = self.login(self.stranger).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/loeschen/"
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Session.objects.count(), 1)


class CalendarViewTests(CalendarTestCase):
    def test_member_gets_calendar_page(self):
        response = self.login(self.member).get(f"/gruppen/{self.group.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="kalender"')
        self.assertContains(
            response, "fullcalendar@6.1.15/index.global.min.js"
        )
        self.assertContains(response, "js/kalender.js")
        self.assertContains(response, f"/gruppen/{self.group.pk}/termine/")

    def test_non_member_is_redirected(self):
        response = self.login(self.stranger).get(f"/gruppen/{self.group.pk}/")
        self.assertEqual(response.status_code, 302)

    def test_settings_page_reachable(self):
        response = self.login(self.member).get(
            f"/gruppen/{self.group.pk}/einstellungen/"
        )
        self.assertEqual(response.status_code, 200)


class AttendanceTests(CalendarTestCase):
    def zusage(self, client, session, **overrides):
        payload = {
            "status": "zugesagt",
            "start": iso(self.start),
            "end": iso(self.end),
        }
        payload.update(overrides)
        return client.post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/zusage/",
            payload,
            content_type="application/json",
        )

    def test_member_can_accept_full_session(self):
        session = self.create_session(self.owner)

        response = self.zusage(self.login(self.member), session)

        self.assertEqual(response.status_code, 200)
        attendance = Attendance.objects.get(session=session, user=self.member)
        self.assertEqual(attendance.status, "zugesagt")
        self.assertEqual(attendance.start, self.start)
        self.assertEqual(attendance.end, self.end)

    def test_member_can_accept_partial_session(self):
        session = self.create_session(self.owner)
        portion_start = self.start + timedelta(minutes=30)
        portion_end = self.end - timedelta(minutes=30)

        response = self.zusage(
            self.login(self.member),
            session,
            start=iso(portion_start),
            end=iso(portion_end),
        )

        self.assertEqual(response.status_code, 200)
        attendance = Attendance.objects.get(session=session, user=self.member)
        self.assertEqual(attendance.start, portion_start)
        self.assertEqual(attendance.end, portion_end)

    def test_partial_outside_session_is_rejected(self):
        session = self.create_session(self.owner)

        response = self.zusage(
            self.login(self.member),
            session,
            start=iso(self.start - timedelta(hours=1)),
            end=iso(self.end + timedelta(hours=1)),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_decline_stores_no_times(self):
        session = self.create_session(self.owner)

        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/zusage/",
            {"status": "abgesagt"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        attendance = Attendance.objects.get(session=session, user=self.member)
        self.assertEqual(attendance.status, "abgesagt")
        self.assertIsNone(attendance.start)
        self.assertIsNone(attendance.end)

    def test_decline_overwrites_previous_acceptance(self):
        session = self.create_session(self.owner)
        self.zusage(self.login(self.member), session)

        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/zusage/",
            {"status": "abgesagt"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 1)
        attendance = Attendance.objects.get(session=session, user=self.member)
        self.assertIsNone(attendance.start)

    def test_attendance_for_block_is_rejected(self):
        session = self.create_session(self.member, kind=Session.KIND_BLOCKIERT)

        response = self.zusage(self.login(self.member), session)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_past_session_cannot_be_accepted_or_declined(self):
        yesterday = timezone.localtime() - timedelta(days=1)
        start = yesterday.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        session = self.create_session(self.owner, start=start, end=end)
        client = self.login(self.member)

        accept = self.zusage(client, session, start=iso(start), end=iso(end))
        decline = client.post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/zusage/",
            {"status": "abgesagt"},
            content_type="application/json",
        )

        self.assertEqual(accept.status_code, 400)
        self.assertEqual(decline.status_code, 400)
        self.assertEqual(Attendance.objects.count(), 0)
        listed = client.get(f"/gruppen/{self.group.pk}/termine/")
        match = next(item for item in listed.json() if item["id"] == session.id)
        self.assertFalse(match["can_respond"])

    def test_session_earlier_today_can_still_be_answered(self):
        now = timezone.localtime()
        start = now.replace(hour=0, minute=10, second=0, microsecond=0)
        end = start + timedelta(minutes=20)
        session = self.create_session(self.owner, start=start, end=end)

        response = self.zusage(
            self.login(self.member),
            session,
            start=iso(start),
            end=iso(end),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Attendance.objects.filter(session=session, user=self.member).exists()
        )

    def test_non_member_cannot_accept(self):
        session = self.create_session(self.owner)

        response = self.zusage(self.login(self.stranger), session)

        self.assertEqual(response.status_code, 403)

    def test_list_contains_attendances(self):
        session = self.create_session(self.owner)
        Attendance.objects.create(
            session=session,
            user=self.owner,
            status="zugesagt",
            start=self.start,
            end=self.end,
        )
        Attendance.objects.create(
            session=session,
            user=self.member,
            status="abgesagt",
        )

        response = self.login(self.member).get(
            f"/gruppen/{self.group.pk}/termine/"
        )

        data = response.json()[0]
        self.assertEqual(len(data["attendances"]), 2)
        self.assertEqual(data["my_attendance"]["status"], "abgesagt")


class BlockTests(CalendarTestCase):
    def block_payload(self, **overrides):
        data = {
            "title": "Nicht verfügbar",
            "location": "",
            "kind": "blockiert",
            "start": iso(self.start),
            "end": iso(self.end),
            "repeat_weeks": 1,
        }
        data.update(overrides)
        return data

    def test_block_without_repeat_creates_one(self):
        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.block_payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(Session.objects.get().kind, Session.KIND_BLOCKIERT)

    def test_block_with_weekly_repeat_creates_series(self):
        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.block_payload(repeat_weeks=3),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        sessions = Session.objects.order_by("start")
        self.assertEqual(sessions.count(), 3)
        starts = list(sessions.values_list("start", flat=True))
        self.assertEqual(starts[1], starts[0] + timedelta(weeks=1))
        self.assertEqual(starts[2], starts[0] + timedelta(weeks=2))

    def test_repeat_is_ignored_for_proposals(self):
        self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.payload(kind="vorschlag", repeat_weeks=5),
            content_type="application/json",
        )
        self.assertEqual(Session.objects.count(), 1)

    def test_repeat_is_capped(self):
        self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.block_payload(repeat_weeks=99),
            content_type="application/json",
        )
        self.assertEqual(Session.objects.count(), 26)

    def test_unknown_kind_is_rejected(self):
        response = self.login(self.member).post(
            f"/gruppen/{self.group.pk}/termine/neu/",
            self.payload(kind="sonstiges"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Session.objects.count(), 0)

    def test_blocks_are_flagged_in_list(self):
        block = self.create_session(self.member, kind=Session.KIND_BLOCKIERT)

        response = self.login(self.owner).get(
            f"/gruppen/{self.group.pk}/termine/"
        )

        data = response.json()[0]
        self.assertEqual(data["id"], block.pk)
        self.assertIn("session-blockiert", data["className"])
        self.assertNotIn("own", data["className"])
        self.assertEqual(data["attendances"], [])
        self.assertIsNone(data["my_attendance"])


class ColorTests(CalendarTestCase):
    def test_events_carry_creator_color(self):
        own = self.create_session(self.member)
        other = self.create_session(self.owner, title="Anderer")

        response = self.login(self.member).get(
            f"/gruppen/{self.group.pk}/termine/"
        )

        by_id = {item["id"]: item for item in response.json()}
        self.assertEqual(
            by_id[own.id]["borderColor"], color_for_user(self.member.id)
        )
        self.assertEqual(
            by_id[other.id]["borderColor"], color_for_user(self.owner.id)
        )
        self.assertNotEqual(
            by_id[own.id]["borderColor"], by_id[other.id]["borderColor"]
        )

    def test_event_background_is_lighter_than_border(self):
        session = self.create_session(self.member)

        response = self.login(self.member).get(
            f"/gruppen/{self.group.pk}/termine/"
        )

        data = response.json()[0]
        self.assertNotEqual(data["backgroundColor"], data["borderColor"])
        self.assertEqual(
            data["backgroundColor"], background_for_user(self.member.id)
        )

    def test_own_events_are_flagged(self):
        own = self.create_session(self.member)

        response = self.login(self.member).get(
            f"/gruppen/{self.group.pk}/termine/"
        )

        self.assertIn("own", response.json()[0]["className"])


class ConsensusTests(CalendarTestCase):
    def accept(self, user, session, start=None, end=None):
        Attendance.objects.update_or_create(
            session=session,
            user=user,
            defaults={
                "status": "zugesagt",
                "start": start or self.start,
                "end": end or self.end,
            },
        )

    def fetch_events(self, client):
        response = client.get(f"/gruppen/{self.group.pk}/termine/")
        self.assertEqual(response.status_code, 200)
        return sorted(response.json(), key=lambda item: item["start"])

    def test_session_accepted_by_all_is_single_green_event(self):
        session = self.create_session(self.owner)
        self.accept(self.member, session)

        data = self.fetch_events(self.login(self.owner))

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["className"], "session-konsens")
        self.assertEqual(data[0]["borderColor"], CONSENSUS_COLOR)
        self.assertEqual(data[0]["backgroundColor"], CONSENSUS_BACKGROUND)
        self.assertTrue(data[0]["editable"])

    def test_partially_accepted_session_is_split_into_segments(self):
        session = self.create_session(self.owner)
        self.accept(
            self.member,
            session,
            start=self.start + timedelta(hours=1),
            end=self.end,
        )

        data = self.fetch_events(self.login(self.member))

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["className"], "session-vorschlag")
        self.assertEqual(data[0]["borderColor"], color_for_user(self.owner.id))
        self.assertEqual(
            data[0]["start"], session.start.isoformat()
        )
        self.assertEqual(
            data[0]["end"], (self.start + timedelta(hours=1)).isoformat()
        )
        self.assertEqual(data[1]["className"], "session-konsens")
        self.assertFalse(data[0]["editable"])
        self.assertFalse(data[1]["editable"])

    def test_declined_by_everyone_else_uses_decline_style(self):
        session = self.create_session(self.owner)
        Attendance.objects.create(
            session=session,
            user=self.member,
            status="abgesagt",
        )

        data = self.fetch_events(self.login(self.member))

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["className"], "session-abgesagt")
        self.assertEqual(data[0]["borderColor"], DECLINED_COLOR)
        self.assertEqual(data[0]["backgroundColor"], DECLINED_BACKGROUND)
        self.assertEqual(data[0]["reply_state"], "abgesagt")

    def test_member_joining_later_keeps_an_accepted_session(self):
        session = self.create_session(self.owner)
        self.accept(self.member, session)
        late = User.objects.create_user("spaeter", password="pw-spaeter-123456")
        Membership.objects.create(group=self.group, user=late)

        data = self.fetch_events(self.login(self.owner))

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["className"], "session-konsens")
        self.assertEqual(data[0]["reply_state"], "angenommen")

    def test_member_joining_later_keeps_a_declined_session(self):
        session = self.create_session(self.owner)
        Attendance.objects.create(
            session=session,
            user=self.member,
            status="abgesagt",
        )
        late = User.objects.create_user("spaeter2", password="pw-spaeter-123456")
        Membership.objects.create(group=self.group, user=late)

        data = self.fetch_events(self.login(self.owner))

        self.assertEqual(data[0]["className"], "session-abgesagt own")
        self.assertEqual(data[0]["reply_state"], "abgesagt")

    def test_later_member_counts_after_replying(self):
        session = self.create_session(self.owner)
        self.accept(self.member, session)
        late = User.objects.create_user("spaeter3", password="pw-spaeter-123456")
        Membership.objects.create(group=self.group, user=late)
        Attendance.objects.create(
            session=session,
            user=late,
            status="abgesagt",
        )

        data = self.fetch_events(self.login(self.owner))

        self.assertEqual(data[0]["reply_state"], "gemischt")
        self.assertIn("session-vorschlag", data[0]["className"])

    def test_segments_share_session_context(self):
        session = self.create_session(self.owner)
        self.accept(
            self.member,
            session,
            start=self.start,
            end=self.end - timedelta(hours=1),
        )

        data = self.fetch_events(self.login(self.member))

        self.assertEqual(len(data), 2)
        for segment in data:
            self.assertEqual(segment["id"], session.pk)
            self.assertEqual(
                segment["session_start"], session.start.isoformat()
            )
            self.assertEqual(segment["session_end"], session.end.isoformat())
            self.assertEqual(segment["attendance_url"], data[0]["attendance_url"])


class MixedReplyTests(CalendarTestCase):
    def setUp(self):
        super().setUp()
        self.third = User.objects.create_user("third", password="pw-third-123456")
        Membership.objects.create(group=self.group, user=self.third)

    def accept(self, user, session):
        Attendance.objects.update_or_create(
            session=session,
            user=user,
            defaults={
                "status": "zugesagt",
                "start": self.start,
                "end": self.end,
            },
        )

    def decline(self, user, session):
        Attendance.objects.update_or_create(
            session=session,
            user=user,
            defaults={"status": "abgesagt", "start": None, "end": None},
        )

    def fetch(self, user):
        response = self.login(user).get(f"/gruppen/{self.group.pk}/termine/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def resolve(self, user, session, display):
        return self.login(user).post(
            f"/gruppen/{self.group.pk}/termine/{session.pk}/darstellung/",
            {"display": display},
            content_type="application/json",
        )

    def test_past_mixed_session_cannot_be_resolved(self):
        yesterday = timezone.localtime() - timedelta(days=1)
        start = yesterday.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        session = self.create_session(self.owner, start=start, end=end)
        self.accept(self.member, session)
        self.decline(self.third, session)

        response = self.resolve(self.owner, session, "angenommen")

        self.assertEqual(response.status_code, 400)
        session.refresh_from_db()
        self.assertEqual(session.display_override, "")

    def test_mixed_replies_stay_a_dashed_proposal_with_counts(self):
        session = self.create_session(self.owner)
        self.accept(self.member, session)
        self.decline(self.third, session)

        data = self.fetch(self.owner)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["className"], "session-vorschlag own")
        self.assertEqual(data[0]["reply_state"], "gemischt")
        self.assertEqual(data[0]["accepted_count"], 1)
        self.assertEqual(data[0]["declined_count"], 1)
        self.assertEqual(data[0]["display_override"], "")
        self.assertEqual(data[0]["borderColor"], color_for_user(self.owner.id))

    def test_pending_reply_keeps_a_single_decline_open(self):
        session = self.create_session(self.owner)
        self.decline(self.member, session)

        data = self.fetch(self.owner)

        self.assertEqual(data[0]["reply_state"], "offen")
        self.assertEqual(data[0]["className"], "session-vorschlag own")
        self.assertEqual(data[0]["accepted_count"], 0)
        self.assertEqual(data[0]["declined_count"], 1)

    def test_creator_can_show_mixed_session_as_accepted(self):
        session = self.create_session(self.owner)
        self.accept(self.member, session)
        self.decline(self.third, session)

        response = self.resolve(self.owner, session, "angenommen")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["className"], "session-konsens")
        self.assertEqual(response.json()["borderColor"], CONSENSUS_COLOR)
        self.assertEqual(response.json()["display_override"], "angenommen")
        self.assertEqual(response.json()["reply_state"], "gemischt")
        session.refresh_from_db()
        self.assertEqual(session.display_override, "angenommen")

    def test_creator_can_show_mixed_session_as_declined(self):
        session = self.create_session(self.owner)
        self.accept(self.member, session)
        self.decline(self.third, session)

        response = self.resolve(self.owner, session, "abgesagt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["className"], "session-abgesagt own")
        self.assertEqual(response.json()["borderColor"], DECLINED_COLOR)
        self.assertEqual(response.json()["backgroundColor"], DECLINED_BACKGROUND)

    def test_creator_can_reopen_a_mixed_session(self):
        session = self.create_session(self.owner, title="Offen")
        session.display_override = "angenommen"
        session.save(update_fields=["display_override"])
        self.accept(self.member, session)
        self.decline(self.third, session)

        response = self.resolve(self.owner, session, "")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["className"], "session-vorschlag own")
        self.assertEqual(response.json()["display_override"], "")

    def test_other_member_cannot_set_the_display(self):
        session = self.create_session(self.owner)
        self.accept(self.member, session)
        self.decline(self.third, session)

        response = self.resolve(self.member, session, "angenommen")

        self.assertEqual(response.status_code, 403)
        session.refresh_from_db()
        self.assertEqual(session.display_override, "")

    def test_display_is_rejected_when_replies_are_not_mixed(self):
        session = self.create_session(self.owner)
        self.accept(self.member, session)
        self.accept(self.third, session)

        response = self.resolve(self.owner, session, "abgesagt")

        self.assertEqual(response.status_code, 400)
        session.refresh_from_db()
        self.assertEqual(session.display_override, "")

    def test_unanimous_accept_ignores_an_old_override(self):
        session = self.create_session(self.owner)
        session.display_override = "abgesagt"
        session.save(update_fields=["display_override"])
        self.accept(self.member, session)
        self.accept(self.third, session)

        data = self.fetch(self.member)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["className"], "session-konsens")
        self.assertEqual(data[0]["reply_state"], "angenommen")
        self.assertEqual(data[0]["borderColor"], CONSENSUS_COLOR)


class MemberColorTests(TestCase):
    def test_no_member_color_is_red_or_the_accepted_green(self):
        palette = [color.lower() for color in EVENT_COLORS]
        self.assertNotIn("#d62728", palette)
        self.assertNotIn(DECLINED_COLOR.lower(), palette)
        self.assertNotIn(CONSENSUS_COLOR.lower(), palette)
        for user_id in range(1, len(EVENT_COLORS) + 1):
            color = color_for_user(user_id).lower()
            self.assertNotEqual(color, DECLINED_COLOR.lower())
            self.assertNotEqual(color, CONSENSUS_COLOR.lower())


class CalendarPageTests(CalendarTestCase):
    def test_page_shows_a_color_legend_without_the_old_hint(self):
        response = self.login(self.owner).get(f"/gruppen/{self.group.pk}/")

        self.assertNotContains(response, "Zeitraum im Raster")
        self.assertContains(
            response, f"background: {color_for_user(self.owner.id)}"
        )
        self.assertContains(
            response, f"background: {color_for_user(self.member.id)}"
        )
        self.assertContains(response, "member")


class CalendarFeedTests(CalendarTestCase):
    def accept(self, user, session, start=None, end=None):
        Attendance.objects.update_or_create(
            session=session,
            user=user,
            defaults={
                "status": "zugesagt",
                "start": start or session.start,
                "end": end or session.end,
            },
        )

    def feed(self):
        self.group.refresh_from_db()
        return self.client.get(f"/abo/{self.group.calendar_token}.ics")

    def events(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/calendar", response["Content-Type"])
        calendar = Calendar.from_ical(response.content)
        return list(calendar.walk("VEVENT"))

    def test_unknown_token_is_not_found(self):
        response = self.client.get("/abo/kein-echter-token.ics")
        self.assertEqual(response.status_code, 404)

    def test_feed_is_public_and_lists_only_accepted_sessions(self):
        accepted = self.create_session(self.owner, title="Akzeptiert", location="Raum 1")
        self.accept(self.member, accepted)
        self.create_session(self.owner, title="Offen")
        declined = self.create_session(self.owner, title="Abgesagt")
        Attendance.objects.create(session=declined, user=self.member, status="abgesagt")
        self.create_session(
            self.owner,
            title="Block",
            kind=Session.KIND_BLOCKIERT,
            start=self.start + timedelta(days=3),
            end=self.end + timedelta(days=3),
        )

        response = self.feed()
        found = self.events(response)

        self.assertEqual([str(event.get("summary")) for event in found], ["Akzeptiert"])
        self.assertEqual(str(found[0].get("location")), "Raum 1")
        self.assertEqual(str(found[0].get("uid")), f"session-{accepted.pk}@syncsession")
        calendar = Calendar.from_ical(response.content)
        self.assertEqual(str(calendar.get("x-wr-calname")), "Testgruppe")

    def test_creator_mark_includes_a_mixed_session(self):
        third = User.objects.create_user("thirdfeed", password="pw-third-123456")
        Membership.objects.create(group=self.group, user=third)
        session = self.create_session(self.owner, title="Festgelegt")
        self.accept(third, session)
        Attendance.objects.create(session=session, user=self.member, status="abgesagt")
        self.assertEqual(self.events(self.feed()), [])
        session.display_override = Session.DISPLAY_ANGENOMMEN
        session.save(update_fields=["display_override"])

        found = self.events(self.feed())

        self.assertEqual(len(found), 1)
        self.assertEqual(
            found[0].decoded("dtstart"),
            self.start.astimezone(datetime_timezone.utc),
        )
        self.assertEqual(
            found[0].decoded("dtend"),
            self.end.astimezone(datetime_timezone.utc),
        )

    def test_partial_acceptance_uses_the_shared_time(self):
        session = self.create_session(self.owner, title="Teilweise")
        shared_start = self.start + timedelta(hours=1)
        self.accept(self.member, session, start=shared_start, end=self.end)

        found = self.events(self.feed())

        self.assertEqual(len(found), 1)
        self.assertEqual(
            found[0].decoded("dtstart"),
            shared_start.astimezone(datetime_timezone.utc),
        )
        self.assertEqual(
            found[0].decoded("dtend"),
            self.end.astimezone(datetime_timezone.utc),
        )

    def test_changes_update_the_same_event_and_deletion_removes_it(self):
        session = self.create_session(self.owner, title="Bewegt")
        self.accept(self.member, session)
        moved_start = self.start + timedelta(days=1)
        moved_end = self.end + timedelta(days=1)
        session.start = moved_start
        session.end = moved_end
        session.save()
        Attendance.objects.filter(session=session).update(
            start=moved_start,
            end=moved_end,
        )

        found = self.events(self.feed())

        self.assertEqual(str(found[0].get("uid")), f"session-{session.pk}@syncsession")
        self.assertEqual(
            found[0].decoded("dtstart"),
            moved_start.astimezone(datetime_timezone.utc),
        )

        session.delete()
        self.assertEqual(self.events(self.feed()), [])

    def test_settings_page_offers_the_subscription(self):
        self.group.refresh_from_db()
        response = self.login(self.member).get(
            f"/gruppen/{self.group.pk}/einstellungen/"
        )
        self.assertContains(response, f"webcal://")
        self.assertContains(response, f"/abo/{self.group.calendar_token}.ics")
        self.assertContains(response, "<svg")
        self.assertNotContains(response, "Google")
        self.assertNotContains(response, "Apple")
