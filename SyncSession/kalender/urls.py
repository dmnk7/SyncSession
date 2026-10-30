from django.urls import path

from . import views

urlpatterns = [
    path("gruppen/<int:pk>/", views.group_calendar, name="group_calendar"),
    path("gruppen/<int:pk>/termine/", views.session_list, name="session_list"),
    path("gruppen/<int:pk>/termine/neu/", views.session_create, name="session_create"),
    path(
        "gruppen/<int:pk>/termine/<int:session_id>/",
        views.session_update,
        name="session_update",
    ),
    path(
        "gruppen/<int:pk>/termine/<int:session_id>/loeschen/",
        views.session_delete,
        name="session_delete",
    ),
    path(
        "gruppen/<int:pk>/termine/<int:session_id>/zusage/",
        views.session_attendance,
        name="session_attendance",
    ),
    path(
        "gruppen/<int:pk>/termine/<int:session_id>/darstellung/",
        views.session_resolution,
        name="session_resolution",
    ),
]
