from django.urls import path

from . import views

urlpatterns = [
    path("gruppen/neu/", views.create_group, name="create_group"),
    path("gruppen/<int:pk>/", views.group_detail, name="group_detail"),
    path("gruppen/<int:pk>/einladen-toggle/", views.toggle_invite_setting, name="toggle_invite_setting"),
    path(
        "gruppen/<int:pk>/mitglieder/<int:user_id>/entfernen/",
        views.remove_member,
        name="remove_member",
    ),
    path("gruppen/<int:pk>/loeschen/", views.delete_group, name="delete_group"),
    path("gruppen/<int:pk>/verlassen/", views.leave_group, name="leave_group"),
    path("gruppen/<int:pk>/einladen/", views.create_invite, name="create_invite"),
    path(
        "gruppen/<int:pk>/einladen/<int:invite_id>/",
        views.invite_detail,
        name="invite_detail",
    ),
    path("join/<str:token>/", views.join, name="join"),
]
