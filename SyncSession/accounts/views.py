from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from lerngruppen.forms import GroupCreateForm
from lerngruppen.models import LearningGroup

from .forms import SignUpForm


def _safe_next(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ""


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


@login_required
def home(request):
    response = render(
        request,
        "accounts/home.html",
        {"form": GroupCreateForm(), "groups": LearningGroup.for_member(request.user)},
    )
    response["Cache-Control"] = "no-store"
    return response
