from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from kalender.feed import upcoming_accepted_for_user
from lerngruppen.forms import GroupCreateForm
from lerngruppen.models import LearningGroup

from .forms import AccountDeleteForm, ProfileForm, SignUpForm


def home_context(user, form=None):
    return {
        "form": form or GroupCreateForm(),
        "groups": LearningGroup.for_member(user),
        "upcoming": upcoming_accepted_for_user(user),
    }


def _safe_next(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ""


def root(request):
    if request.user.is_authenticated:
        return redirect("home")
    return redirect("login")


def landing(request):
    next_url = _safe_next(request)
    if request.user.is_authenticated:
        return redirect(next_url or "home")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            if next_url:
                login(
                    request,
                    user,
                    backend="django.contrib.auth.backends.ModelBackend",
                )
                messages.success(request, "Konto erstellt.")
                return redirect(next_url)
            messages.success(request, "Konto erstellt. Du kannst dich jetzt einloggen.")
            return redirect("login")
    else:
        form = SignUpForm()

    return render(request, "landing.html", {"form": form, "next": next_url})


def _profile_page(request, form=None, delete_form=None):
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form or ProfileForm(instance=request.user),
            "delete_form": delete_form or AccountDeleteForm(request.user),
        },
    )


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Name gespeichert.")
            return redirect("profile")
        return _profile_page(request, form=form)

    return _profile_page(request)


@login_required
@require_POST
def delete_account(request):
    form = AccountDeleteForm(request.user, request.POST)
    if not form.is_valid():
        return _profile_page(request, delete_form=form)

    user = request.user
    logout(request)
    user.delete()
    messages.success(request, "Konto gelöscht.")
    return redirect("login")


@login_required
def home(request):
    response = render(request, "accounts/home.html", home_context(request.user))
    response["Cache-Control"] = "no-store"
    return response
