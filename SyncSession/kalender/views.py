import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from lerngruppen.models import LearningGroup

from .colors import (
    CONSENSUS_BACKGROUND,
    CONSENSUS_COLOR,
    DECLINED_BACKGROUND,
    DECLINED_COLOR,
    background_for_user,
    color_for_user,
)
from .models import (
    STATUS_ABGESAGT,
    STATUS_ZUGESAGT,
    Attendance,
    Session,
)

MAX_REPEAT_WEEKS = 26


def _json_error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _user_display(user):
    return user.get_full_name() or user.username


def _can_respond(session):
    """Zusagen gehen nur für den heutigen Tag und die Zukunft."""
    start = timezone.localtime(session.start)
    return start.date() >= timezone.localdate()


def _parse_datetime(value):
    value = (value or "").strip()
    if not value:
        return None, "Datum fehlt."
    moment = parse_datetime(value)
    if moment is None:
        return None, "Ungültiges Datum."
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment, None


def _read_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}"), None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _json_error("Ungültige Anfrage.")


def _parse_session_fields(data):
    start, error = _parse_datetime(data.get("start"))
    if error:
        return None, {"start": [error]}
    end, error = _parse_datetime(data.get("end"))
    if error:
        return None, {"end": [error]}

    errors = {}
    title = str(data.get("title") or "").strip()
    if not title:
        errors["title"] = ["Bitte gib einen Titel an."]
    location = str(data.get("location") or "").strip()
    if end <= start:
        errors.setdefault("end", []).append(
            "Das Ende muss nach dem Beginn liegen."
        )

    if errors:
        return None, errors
    return {"title": title, "location": location, "start": start, "end": end}, None


def _attendance_data(attendance):
    data = {"user": _user_display(attendance.user), "status": attendance.status}
    if attendance.start is not None:
        data["start"] = attendance.start.isoformat()
        data["end"] = attendance.end.isoformat()
    return data


def _member_ids_for_session(session, memberships, attendances_by_user):
    """Mitglieder, die den Stand eines Termins bestimmen.

    Wer der Gruppe erst nach dem Termin beigetreten ist und noch nicht
    geantwortet hat, lässt einen schon festgelegten Stand unverändert.
    """
    ids = []
    for membership in memberships:
        user_id = membership.user_id
        replied = user_id in attendances_by_user
        joined_later = (
            session.created_at is not None
            and membership.joined_at > session.created_at
        )
        if user_id != session.created_by_id and joined_later and not replied:
            continue
        ids.append(user_id)
    return ids


def _reply_tally(session, member_ids, attendances_by_user):
    """Zählt Zusagen und Absagen der anderen Mitglieder.

    Der Ersteller zählt nicht mit. „angenommen“ und „abgesagt“ gelten nur,
    wenn jede andere gezählte Person dieselbe Rückmeldung gegeben hat.
    Sobald beides vorkommt, ist der Stand „gemischt“.
    """
    accepted = 0
    declined = 0
    others = 0
    for user_id in member_ids:
        if user_id == session.created_by_id:
            continue
        others += 1
        attendance = attendances_by_user.get(user_id)
        if attendance is None:
            continue
        if attendance.status == STATUS_ZUGESAGT:
            accepted += 1
        elif attendance.status == STATUS_ABGESAGT:
            declined += 1

    if accepted == others:
        state = "angenommen"
    elif others > 0 and declined == others:
        state = "abgesagt"
    elif accepted and declined:
        state = "gemischt"
    else:
        state = "offen"
    return accepted, declined, state


def _session_events(session, request_user, group_pk, attendances, memberships):
    """Baut die Kalender-Events eines Termins.

    Stimmen alle anderen zu, bleibt der Termin grün und durchgezogen,
    bei Teil-Zusagen nur in der gemeinsamen Zeit. Sagen alle anderen ab,
    ist er durchgestrichen. Sind Zusagen und Absagen gemischt, bleibt er
    gestrichelt, bis der Ersteller die Darstellung festlegt.
    """
    attendances = list(attendances)
    by_user = {attendance.user_id: attendance for attendance in attendances}
    member_ids = _member_ids_for_session(session, memberships, by_user)
    own = session.created_by_id == request_user.id

    attendance_list = []
    my_attendance = None
    accepted_count = 0
    declined_count = 0
    reply_state = ""
    display_override = ""
    if session.kind != Session.KIND_BLOCKIERT:
        for attendance in attendances:
            data = _attendance_data(attendance)
            attendance_list.append(data)
            if attendance.user_id == request_user.id:
                my_attendance = data
        accepted_count, declined_count, reply_state = _reply_tally(
            session, member_ids, by_user
        )
        display_override = session.display_override

    base = {
        "id": session.id,
        "title": session.title,
        "kind": session.kind,
        "location": session.location,
        "session_start": session.start.isoformat(),
        "session_end": session.end.isoformat(),
        "created_by": _user_display(session.created_by),
        "own": own,
        "attendances": attendance_list,
        "my_attendance": my_attendance,
        "accepted_count": accepted_count,
        "declined_count": declined_count,
        "reply_state": reply_state,
        "display_override": display_override,
        "can_respond": _can_respond(session),
        "update_url": reverse("session_update", args=[group_pk, session.id]),
        "delete_url": reverse("session_delete", args=[group_pk, session.id]),
        "attendance_url": reverse(
            "session_attendance", args=[group_pk, session.id]
        ),
        "resolution_url": reverse(
            "session_resolution", args=[group_pk, session.id]
        ),
    }

    border = color_for_user(session.created_by_id)
    background = background_for_user(session.created_by_id)
    proposal_class = (
        "session-vorschlag own" if own else "session-vorschlag"
    )

    if session.kind == Session.KIND_BLOCKIERT:
        return [
            dict(
                base,
                start=session.start.isoformat(),
                end=session.end.isoformat(),
                borderColor=border,
                backgroundColor=background,
                className=(
                    "session-blockiert own" if own else "session-blockiert"
                ),
                editable=own,
            )
        ]

    effective = display_override if reply_state == "gemischt" else ""
    if reply_state == "abgesagt" or effective == Session.DISPLAY_ABGESAGT:
        return [
            dict(
                base,
                start=session.start.isoformat(),
                end=session.end.isoformat(),
                borderColor=DECLINED_COLOR,
                backgroundColor=DECLINED_BACKGROUND,
                className="session-abgesagt own" if own else "session-abgesagt",
                editable=own,
            )
        ]
    if effective == Session.DISPLAY_ANGENOMMEN:
        return [
            dict(
                base,
                start=session.start.isoformat(),
                end=session.end.isoformat(),
                borderColor=CONSENSUS_COLOR,
                backgroundColor=CONSENSUS_BACKGROUND,
                className="session-konsens",
                editable=own,
            )
        ]

    consensus = _consensus_range(session, member_ids, by_user)
    if consensus is None:
        return [
            dict(
                base,
                start=session.start.isoformat(),
                end=session.end.isoformat(),
                borderColor=border,
                backgroundColor=background,
                className=proposal_class,
                editable=own,
            )
        ]

    low, high = consensus
    if low == session.start and high == session.end:
        return [
            dict(
                base,
                start=session.start.isoformat(),
                end=session.end.isoformat(),
                borderColor=CONSENSUS_COLOR,
                backgroundColor=CONSENSUS_BACKGROUND,
                className="session-konsens",
                editable=own,
            )
        ]

    events = []
    if session.start < low:
        events.append(
            dict(
                base,
                start=session.start.isoformat(),
                end=low.isoformat(),
                borderColor=border,
                backgroundColor=background,
                className=proposal_class,
                editable=False,
            )
        )
    events.append(
        dict(
            base,
            start=low.isoformat(),
            end=high.isoformat(),
            borderColor=CONSENSUS_COLOR,
            backgroundColor=CONSENSUS_BACKGROUND,
            className="session-konsens",
            editable=False,
        )
    )
    if high < session.end:
        events.append(
            dict(
                base,
                start=high.isoformat(),
                end=session.end.isoformat(),
                borderColor=border,
                backgroundColor=background,
                className=proposal_class,
                editable=False,
            )
        )
    return events


def _consensus_range(session, member_ids, attendances_by_user):
    """Zeitraum, den alle Mitglieder zugesagt haben (oder None).

    Der Ersteller des Vorschlags zählt als für den ganzen Termin zugesagt.
    """
    low = session.start
    high = session.end
    for user_id in member_ids:
        if user_id == session.created_by_id:
            continue
        attendance = attendances_by_user.get(user_id)
        if attendance is None or attendance.status != STATUS_ZUGESAGT:
            return None
        low = max(low, attendance.start)
        high = min(high, attendance.end)
        if low >= high:
            return None
    return low, high


def _memberships(group):
    return list(group.memberships.all())


def _member_or_403(request, group):
    if group.is_member(request.user):
        return None
    return _json_error("Du gehörst nicht zu dieser Lerngruppe.", status=403)


@require_GET
def calendar_feed(request, token):
    from .feed import calendar_response

    return calendar_response(token)


@login_required
def group_calendar(request, pk):
    group = get_object_or_404(LearningGroup, pk=pk)
    if not group.is_member(request.user):
        messages.error(
            request,
            f"Du gehörst nicht mehr zur Lerngruppe „{group.name}“.",
        )
        return redirect("home")
    memberships = group.memberships.select_related("user").order_by("joined_at")
    legend = [
        {"name": _user_display(membership.user), "color": color_for_user(membership.user_id)}
        for membership in memberships
    ]
    return render(
        request,
        "kalender/calendar.html",
        {"group": group, "legend": legend},
    )


@require_GET
@login_required
def session_list(request, pk):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _member_or_403(request, group)
    if denied:
        return denied

    sessions = (
        Session.objects.filter(group=group)
        .select_related("created_by")
        .prefetch_related(
            Prefetch(
                "attendances",
                queryset=Attendance.objects.select_related("user"),
            )
        )
        .order_by("start")
    )

    start = parse_datetime(request.GET.get("start", ""))
    end = parse_datetime(request.GET.get("end", ""))
    if start is not None and end is not None:
        sessions = sessions.filter(Q(end__gt=start) & Q(start__lt=end))

    memberships = _memberships(group)
    events = []
    for session in sessions:
        events.extend(
            _session_events(
                session,
                request.user,
                group.pk,
                attendances=list(session.attendances.all()),
                memberships=memberships,
            )
        )
    return JsonResponse(events, safe=False)


@require_GET
@login_required
def session_status(request, pk):
    """Leichter Prüf-Endpunkt fürs Polling.

    Liefert den Zeitpunkt der letzten Änderung an Terminen, Rückmeldungen
    oder Mitgliedern. Der Client refetcht die Events nur, wenn sich dieser
    Wert seit dem letzten Poll geändert hat.
    """
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _member_or_403(request, group)
    if denied:
        return denied

    stamps = [
        stamp
        for stamp in (
            Session.objects.filter(group=group).aggregate(latest=Max("updated_at"))[
                "latest"
            ],
            Attendance.objects.filter(session__group=group).aggregate(
                latest=Max("updated_at")
            )["latest"],
            group.memberships.aggregate(latest=Max("joined_at"))["latest"],
        )
        if stamp is not None
    ]
    return JsonResponse(
        {
            "updated_at": max(stamps).isoformat() if stamps else None,
            "member_count": group.memberships.count(),
        }
    )


def _repeat_weeks(data, kind):
    raw = data.get("repeat_weeks", 1)
    try:
        weeks = int(raw)
    except (TypeError, ValueError):
        weeks = 1
    if kind != Session.KIND_BLOCKIERT:
        return 1
    return max(1, min(weeks, MAX_REPEAT_WEEKS))


@require_POST
@login_required
def session_create(request, pk):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _member_or_403(request, group)
    if denied:
        return denied

    data, error = _read_json_body(request)
    if error:
        return error

    kind = str(data.get("kind") or Session.KIND_VORSCHLAG)
    if kind not in (Session.KIND_VORSCHLAG, Session.KIND_BLOCKIERT):
        return JsonResponse(
            {"errors": {"kind": ["Unbekannte Art des Termins."]}},
            status=400,
        )

    fields, errors = _parse_session_fields(data)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    repeat_weeks = _repeat_weeks(data, kind)

    created = []
    for week in range(repeat_weeks):
        session = Session(
            group=group,
            created_by=request.user,
            kind=kind,
            title=fields["title"],
            location=fields["location"],
            start=fields["start"] + timedelta(weeks=week),
            end=fields["end"] + timedelta(weeks=week),
        )
        session.full_clean()
        session.save()
        created.append(session)

    return JsonResponse(
        {
            "sessions": [
                _session_events(
                    session,
                    request.user,
                    group.pk,
                    attendances=[],
                    memberships=_memberships(group),
                )[0]
                for session in created
            ]
        },
        status=201,
    )


@require_POST
@login_required
def session_update(request, pk, session_id):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _member_or_403(request, group)
    if denied:
        return denied

    session = get_object_or_404(Session, pk=session_id, group=group)
    if session.created_by_id != request.user.id:
        return _json_error(
            "Du kannst nur eigene Vorschläge bearbeiten.", status=403
        )

    data, error = _read_json_body(request)
    if error:
        return error

    fields, errors = _parse_session_fields(data)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    for name, value in fields.items():
        setattr(session, name, value)
    session.full_clean()
    session.save()
    return JsonResponse(
        _session_events(
            session,
            request.user,
            group.pk,
            attendances=list(
                session.attendances.select_related("user")
            ),
            memberships=_memberships(group),
        )[0]
    )


@require_POST
@login_required
def session_delete(request, pk, session_id):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _member_or_403(request, group)
    if denied:
        return denied

    session = get_object_or_404(Session, pk=session_id, group=group)
    if session.created_by_id != request.user.id:
        return _json_error(
            "Du kannst nur eigene Vorschläge löschen.", status=403
        )
    session.delete()
    return HttpResponse(status=204)


@require_POST
@login_required
def session_attendance(request, pk, session_id):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _member_or_403(request, group)
    if denied:
        return denied

    session = get_object_or_404(Session, pk=session_id, group=group)
    if session.kind != Session.KIND_VORSCHLAG:
        return _json_error(
            "Für geblockte Zeiten gibt es keine Zusage.", status=400
        )
    if not _can_respond(session):
        return _json_error(
            "Vergangene Termine kannst du nicht mehr annehmen oder ablehnen.",
            status=400,
        )

    data, error = _read_json_body(request)
    if error:
        return error

    status = str(data.get("status") or "")
    if status == STATUS_ABGESAGT:
        Attendance.objects.update_or_create(
            session=session,
            user=request.user,
            defaults={"status": STATUS_ABGESAGT, "start": None, "end": None},
        )
        attendance = Attendance.objects.get(session=session, user=request.user)
        return JsonResponse(_attendance_data(attendance))

    if status != STATUS_ZUGESAGT:
        return JsonResponse(
            {"errors": {"status": ["Bitte sag zu oder ab."]}}, status=400
        )

    start, error = _parse_datetime(data.get("start"))
    if error:
        return JsonResponse({"errors": {"start": [error]}}, status=400)
    end, error = _parse_datetime(data.get("end"))
    if error:
        return JsonResponse({"errors": {"end": [error]}}, status=400)

    errors = {}
    if end <= start:
        errors.setdefault("end", []).append(
            "Die Zusage muss nach ihrem Beginn enden."
        )
    if start < session.start or end > session.end:
        errors.setdefault("start", []).append(
            "Die Zusage muss innerhalb des Termins liegen."
        )
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    Attendance.objects.update_or_create(
        session=session,
        user=request.user,
        defaults={"status": STATUS_ZUGESAGT, "start": start, "end": end},
    )
    attendance = Attendance.objects.get(session=session, user=request.user)
    return JsonResponse(_attendance_data(attendance))


@require_POST
@login_required
def session_resolution(request, pk, session_id):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _member_or_403(request, group)
    if denied:
        return denied

    session = get_object_or_404(Session, pk=session_id, group=group)
    if session.created_by_id != request.user.id:
        return _json_error(
            "Nur der Ersteller kann die Darstellung festlegen.", status=403
        )
    if session.kind != Session.KIND_VORSCHLAG:
        return _json_error(
            "Für geblockte Zeiten gibt es keine Darstellung.", status=400
        )
    if not _can_respond(session):
        return _json_error(
            "Vergangene Termine kannst du nicht mehr festlegen.",
            status=400,
        )

    data, error = _read_json_body(request)
    if error:
        return error

    display = str(data.get("display") or "")
    if display not in (
        "",
        Session.DISPLAY_ANGENOMMEN,
        Session.DISPLAY_ABGESAGT,
    ):
        return JsonResponse(
            {"errors": {"display": ["Unbekannte Darstellung."]}},
            status=400,
        )

    if display:
        attendances = {
            attendance.user_id: attendance
            for attendance in session.attendances.all()
        }
        _, _, reply_state = _reply_tally(
            session,
            _member_ids_for_session(session, _memberships(group), attendances),
            attendances,
        )
        if reply_state != "gemischt":
            return _json_error(
                "Festlegen geht nur, solange Zusagen und Absagen gemischt sind."
            )

    session.display_override = display
    session.save(update_fields=["display_override"])
    return JsonResponse(
        _session_events(
            session,
            request.user,
            group.pk,
            attendances=list(session.attendances.select_related("user")),
            memberships=_memberships(group),
        )[0]
    )
