from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import SignUpForm


def landing(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Konto erstellt. Du kannst dich jetzt einloggen.")
            return redirect("login")
    else:
        form = SignUpForm()

    return render(request, "landing.html", {"form": form})


@login_required
def home(request):
    return render(request, "accounts/home.html")
