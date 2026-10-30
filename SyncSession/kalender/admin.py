from django.contrib import admin

from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "group",
        "start",
        "end",
        "kind",
        "display_override",
        "created_by",
    )
    list_filter = ("kind", "group")
    search_fields = ("title", "location", "group__name")
