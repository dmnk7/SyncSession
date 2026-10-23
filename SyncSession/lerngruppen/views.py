import io
import secrets

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode

from .forms import GroupCreateForm, InviteSettingsForm
from .models import Invite, LearningGroup, Membership


def _require_member(request, group):
    if group.is_member(request.user):
        return None
    messages.error(
        request,
        f"Du gehörst nicht mehr zur Lerngruppe „{group.name}“.",
    )
    return redirect("home")


def _qr_svg(url):
    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage)
    stream = io.BytesIO()
    image.save(stream)
    svg = stream.getvalue().decode()
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[-1].strip()
    return svg


@login_required
def create_group(request):
    if request.method != "POST":
        return redirect("home")

    form = GroupCreateForm(request.POST)
    if form.is_valid():
        group = form.save(commit=False)
        group.created_by = request.user
        group.save()
        Membership.objects.create(group=group, user=request.user)
        messages.success(request, f"Lerngruppe „{group.name}“ erstellt.")
        return redirect("group_detail", pk=group.pk)

    groups = LearningGroup.for_member(request.user)
    return render(
        request,
        "accounts/home.html",
        {"form": form, "groups": groups},
    )


@login_required
def group_detail(request, pk):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _require_member(request, group)
    if denied:
        return denied

    members = group.memberships.select_related("user").order_by("joined_at")
    return render(
        request,
        "lerngruppen/detail.html",
        {
            "group": group,
            "members": members,
            "settings_form": InviteSettingsForm(instance=group),
            "can_invite": group.user_can_invite(request.user),
            "is_creator": group.created_by_id == request.user.id,
        },
    )


@login_required
def toggle_invite_setting(request, pk):
    group = get_object_or_404(LearningGroup, pk=pk)
    if group.created_by_id != request.user.id:
        return HttpResponseForbidden("Nur der Ersteller kann diese Einstellung ändern.")
    if request.method != "POST":
        return redirect("group_detail", pk=group.pk)
    form = InviteSettingsForm(request.POST, instance=group)
    if form.is_valid():
        form.save()
    return redirect("group_detail", pk=group.pk)


@login_required
def remove_member(request, pk, user_id):
    group = get_object_or_404(LearningGroup, pk=pk)
    if group.created_by_id != request.user.id:
        return HttpResponseForbidden("Nur der Ersteller kann Mitglieder entfernen.")
    if request.method != "POST":
        return redirect("group_detail", pk=group.pk)
    if user_id == group.created_by_id:
        return HttpResponseForbidden("Der Ersteller kann nicht entfernt werden.")
    membership = get_object_or_404(Membership, group=group, user_id=user_id)
    name = membership.user.get_full_name() or membership.user.username
    membership.delete()
    messages.success(request, f"{name} wurde aus der Gruppe entfernt.")
    return redirect("group_detail", pk=group.pk)


@login_required
def delete_group(request, pk):
    group = get_object_or_404(LearningGroup, pk=pk)
    if group.created_by_id != request.user.id:
        return HttpResponseForbidden("Nur der Ersteller kann die Gruppe löschen.")
    if request.method != "POST":
        return redirect("group_detail", pk=group.pk)
    name = group.name
    group.delete()
    messages.success(request, f"Lerngruppe „{name}“ wurde gelöscht.")
    return redirect("home")


@login_required
def leave_group(request, pk):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _require_member(request, group)
    if denied:
        return denied
    if group.created_by_id == request.user.id:
        return HttpResponseForbidden("Als Ersteller kannst du die Gruppe nur löschen.")
    if request.method != "POST":
        return redirect("group_detail", pk=group.pk)
    Membership.objects.filter(group=group, user=request.user).delete()
    messages.success(request, f"Du hast die Lerngruppe „{group.name}“ verlassen.")
    return redirect("home")


@login_required
def create_invite(request, pk):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _require_member(request, group)
    if denied:
        return denied
    if not group.user_can_invite(request.user):
        return HttpResponseForbidden("Du darfst für diese Gruppe keine Einladungen erzeugen.")
    if request.method != "POST":
        return redirect("group_detail", pk=group.pk)

    invite = Invite.objects.create(
        group=group,
        token=secrets.token_urlsafe(32),
        created_by=request.user,
        expires_at=Invite.expiry_from_now(),
    )
    return redirect("invite_detail", pk=group.pk, invite_id=invite.pk)


@login_required
def invite_detail(request, pk, invite_id):
    group = get_object_or_404(LearningGroup, pk=pk)
    denied = _require_member(request, group)
    if denied:
        return denied
    if not group.user_can_invite(request.user):
        return HttpResponseForbidden("Du darfst Einladungen dieser Gruppe nicht sehen.")

    invite = get_object_or_404(Invite, pk=invite_id, group=group)
    join_url = request.build_absolute_uri(reverse("join", args=[invite.token]))
    return render(
        request,
        "lerngruppen/invite.html",
        {
            "group": group,
            "invite": invite,
            "join_url": join_url,
            "qr_svg": _qr_svg(join_url),
        },
    )


def join(request, token):
    invite = (
        Invite.objects.filter(token=token)
        .select_related("group", "group__created_by")
        .first()
    )
    if invite is None or invite.is_expired():
        messages.error(
            request,
            "Dieser Einladungslink ist ungültig oder abgelaufen.",
        )
        if request.user.is_authenticated:
            return redirect("home")
        return redirect("landing")

    group = invite.group
    already_member = group.is_member(request.user)

    if request.method == "POST":
        if not request.user.is_authenticated:
            login_url = reverse("login")
            query = urlencode({"next": request.path})
            return redirect(f"{login_url}?{query}")
        if already_member:
            return redirect("group_detail", pk=group.pk)
        Membership.objects.get_or_create(group=group, user=request.user)
        messages.success(
            request,
            f"Du bist der Lerngruppe „{group.name}“ beigetreten.",
        )
        return redirect("group_detail", pk=group.pk)

    members = group.memberships.select_related("user").order_by("joined_at")
    return render(
        request,
        "lerngruppen/join.html",
        {
            "invite": invite,
            "group": group,
            "members": members,
            "already_member": already_member,
        },
    )
