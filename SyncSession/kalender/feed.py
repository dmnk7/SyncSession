from collections import defaultdict
from datetime import timedelta, timezone as datetime_timezone

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from icalendar import Calendar, Event
from icalendar.prop import vDuration, vText

from lerngruppen.models import LearningGroup, Membership

from .models import STATUS_ABGESAGT, Session
from .views import _consensus_range, _member_ids_for_session, _reply_tally

UPCOMING_LIMIT = 3


def accepted_bounds(session, memberships, attendances):
    """Zeitraum eines akzeptierten Termins, sonst None.

    Geblockte Zeiten gehören nicht ins Abo. Ein Vorschlag gilt als
    akzeptiert, wenn alle anderen Mitglieder zugesagt haben, oder wenn
    der Ersteller eine gemischte Rückmeldung als angenommen festlegt.
    """
    if session.kind != Session.KIND_VORSCHLAG:
        return None
    by_user = {attendance.user_id: attendance for attendance in attendances}
    member_ids = _member_ids_for_session(session, memberships, by_user)
    _, _, reply_state = _reply_tally(session, member_ids, by_user)
    if (
        reply_state == "gemischt"
        and session.display_override == Session.DISPLAY_ANGENOMMEN
    ):
        return session.start, session.end
    if reply_state != "angenommen":
        return None
    return _consensus_range(session, member_ids, by_user)


def upcoming_accepted_for_user(user):
    """Nächste angenommene Termine über alle Lerngruppen des Nutzers.

    Geblockte, offene, abgesagte und bereits beendete Termine bleiben
    draußen. Pro Gruppe können mehrere Termine vorkommen; gezeigt werden
    die nächsten drei nach Beginn. Wer selbst abgesagt hat, muss nicht
    erscheinen und sieht den Termin nicht.
    """
    now = timezone.now()
    sessions = list(
        Session.objects.filter(
            group__memberships__user=user,
            kind=Session.KIND_VORSCHLAG,
            end__gt=now,
        )
        .select_related("group", "created_by")
        .prefetch_related("attendances")
        .distinct()
        .order_by("start")
    )
    if not sessions:
        return []

    memberships_by_group = defaultdict(list)
    for membership in Membership.objects.filter(
        group_id__in={session.group_id for session in sessions}
    ):
        memberships_by_group[membership.group_id].append(membership)

    upcoming = []
    for session in sessions:
        attendances = list(session.attendances.all())
        bounds = accepted_bounds(
            session, memberships_by_group[session.group_id], attendances
        )
        if bounds is None:
            continue
        own = next(
            (
                attendance
                for attendance in attendances
                if attendance.user_id == user.id
            ),
            None,
        )
        if own is not None and own.status == STATUS_ABGESAGT:
            continue
        start, end = bounds
        if end <= now:
            continue
        upcoming.append(
            {
                "session": session,
                "group": session.group,
                "start": timezone.localtime(start),
                "end": timezone.localtime(end),
            }
        )
        if len(upcoming) >= UPCOMING_LIMIT:
            break
    return upcoming


def _as_utc(moment):
    return moment.astimezone(datetime_timezone.utc)


def _last_modified(session, attendances):
    latest = session.updated_at
    for attendance in attendances:
        if attendance.updated_at > latest:
            latest = attendance.updated_at
    return latest


def build_calendar(group, memberships, sessions):
    calendar = Calendar()
    calendar.add("prodid", "-//SyncSession//Lerngruppe//DE")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", group.name)
    calendar.add(
        "x-wr-caldesc",
        f"Akzeptierte Termine der Lerngruppe {group.name}",
    )
    refresh = vDuration(timedelta(hours=1))
    refresh.params["VALUE"] = "DURATION"
    calendar.add("refresh-interval", refresh)
    calendar.add("x-published-ttl", vText("PT1H"))

    published = timezone.now()
    for session in sessions:
        attendances = list(session.attendances.all())
        bounds = accepted_bounds(session, memberships, attendances)
        if bounds is None:
            continue
        start, end = bounds
        event = Event()
        event.add("uid", f"session-{session.pk}@syncsession")
        event.add("summary", session.title)
        event.add("dtstart", _as_utc(start))
        event.add("dtend", _as_utc(end))
        event.add("dtstamp", _as_utc(published))
        event.add("last-modified", _as_utc(_last_modified(session, attendances)))
        if session.location:
            event.add("location", session.location)
        event.add("description", f"Lerngruppe {group.name}")
        calendar.add_component(event)
    return calendar


def calendar_response(token):
    group = get_object_or_404(LearningGroup, calendar_token=token)
    memberships = list(group.memberships.all())
    sessions = group.sessions.prefetch_related("attendances").order_by("start")
    calendar = build_calendar(group, memberships, sessions)
    response = HttpResponse(
        calendar.to_ical(),
        content_type="text/calendar; charset=utf-8",
    )
    response["Content-Disposition"] = 'inline; filename="termine.ics"'
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
