#!/usr/bin/env python
"""Füllt eine leere Datenbank mit der lokalen Demo."""

import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SyncSession.settings")

USERS = (
    {
        "username": "anna",
        "first_name": "Anna",
        "last_name": "Adler",
        "password": "Raumplan-48",
    },
    {
        "username": "ben",
        "first_name": "Ben",
        "last_name": "Berger",
        "password": "Tafelbild-48",
    },
    {
        "username": "clara",
        "first_name": "Clara",
        "last_name": "Conrad",
        "password": "Skriptseite-48",
    },
    {
        "username": "david",
        "first_name": "David",
        "last_name": "Dahl",
        "password": "Pausenzeit-48",
    },
)


def week_slot(weekday, hour, minute):
    from django.utils import timezone

    now = timezone.localtime()
    monday = now - timedelta(days=now.weekday())
    moment = monday.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return moment + timedelta(days=weekday)


def create_user(User, data):
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    user = User(
        username=data["username"],
        first_name=data["first_name"],
        last_name=data["last_name"],
    )
    try:
        validate_password(data["password"], user)
    except ValidationError as error:
        raise SystemExit(
            f"Passwort für {data['username']} wird nicht akzeptiert: {error.messages}"
        ) from error
    user.set_password(data["password"])
    user.save()
    return user


def add_session(Session, group, user, title, start, end, location="", kind=None, display=""):
    if kind is None:
        kind = Session.KIND_VORSCHLAG
    session = Session(
        group=group,
        created_by=user,
        title=title,
        location=location,
        start=start,
        end=end,
        kind=kind,
        display_override=display,
    )
    session.full_clean()
    session.save()
    return session


def accept(session, user):
    from kalender.models import STATUS_ZUGESAGT, Attendance

    Attendance.objects.create(
        session=session,
        user=user,
        status=STATUS_ZUGESAGT,
        start=session.start,
        end=session.end,
    )


def decline(session, user):
    from kalender.models import STATUS_ABGESAGT, Attendance

    Attendance.objects.create(
        session=session,
        user=user,
        status=STATUS_ABGESAGT,
    )


def add_invite(group, user):
    import secrets

    from lerngruppen.models import Invite

    Invite.objects.create(
        group=group,
        token=secrets.token_urlsafe(32),
        created_by=user,
        expires_at=Invite.expiry_from_now(),
    )


def seed():
    from django.contrib.auth import get_user_model
    from django.db import transaction

    from kalender.models import Session
    from lerngruppen.models import LearningGroup, Membership

    User = get_user_model()
    if User.objects.exists() or LearningGroup.objects.exists():
        raise SystemExit(
            "Die Datenbank ist nicht leer. Das Skript füllt nur eine leere Datenbank."
        )

    with transaction.atomic():
        anna = create_user(User, USERS[0])
        ben = create_user(User, USERS[1])
        clara = create_user(User, USERS[2])
        david = create_user(User, USERS[3])
        everyone = (anna, ben, clara, david)

        math = LearningGroup.objects.create(
            name="Angewandte Mathematik",
            created_by=anna,
            members_can_invite=False,
        )
        web = LearningGroup.objects.create(
            name="Agile Webentwicklung mit Python",
            created_by=ben,
            members_can_invite=True,
        )
        for group in (math, web):
            for user in everyone:
                Membership.objects.create(group=group, user=user)
            add_invite(group, group.created_by)

        sheet = add_session(
            Session,
            math,
            anna,
            "Übungsblatt 5",
            week_slot(1, 10, 0),
            week_slot(1, 12, 0),
            "Raum C12",
        )
        for user in (ben, clara, david):
            accept(sheet, user)

        exam = add_session(
            Session,
            math,
            ben,
            "Klausurvorbereitung",
            week_slot(2, 14, 0),
            week_slot(2, 16, 0),
            "Lernraum 2",
        )
        accept(exam, clara)
        decline(exam, david)

        office = add_session(
            Session,
            math,
            clara,
            "Sprechstunde Analysis",
            week_slot(3, 9, 0),
            week_slot(3, 10, 0),
            "Online",
        )
        for user in (anna, ben, david):
            decline(office, user)

        add_session(
            Session,
            math,
            david,
            "Nebenjob",
            week_slot(4, 16, 0),
            week_slot(4, 18, 0),
            kind=Session.KIND_BLOCKIERT,
        )

        views = add_session(
            Session,
            web,
            ben,
            "Django Views",
            week_slot(0, 16, 0),
            week_slot(0, 18, 0),
            "Online",
        )
        for user in (anna, clara, david):
            accept(views, user)

        review = add_session(
            Session,
            web,
            anna,
            "Gruppenreview",
            week_slot(2, 18, 0),
            week_slot(2, 19, 30),
            "Raum B3",
            display=Session.DISPLAY_ANGENOMMEN,
        )
        accept(review, david)
        decline(review, clara)

        add_session(
            Session,
            web,
            david,
            "Deployment üben",
            week_slot(3, 11, 0),
            week_slot(3, 12, 30),
            "Online",
        )
        add_session(
            Session,
            web,
            clara,
            "Pendeln",
            week_slot(1, 8, 0),
            week_slot(1, 9, 0),
            kind=Session.KIND_BLOCKIERT,
        )

    print("Demo angelegt. Zugänge stehen in DEMO_USER.md.")


if __name__ == "__main__":
    import django

    django.setup()
    seed()
