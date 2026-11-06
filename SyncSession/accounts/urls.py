from django.contrib.auth.views import LoginView
from django.urls import path

from .forms import LoginForm
from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("home/", views.home, name="home"),
    path("konto/", views.profile, name="profile"),
    path("konto/loeschen/", views.delete_account, name="delete_account"),
    path(
        "accounts/login/",
        LoginView.as_view(authentication_form=LoginForm),
        name="login",
    ),
]
