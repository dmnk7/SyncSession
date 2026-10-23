from django.contrib import admin

from .models import Invite, LearningGroup, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(LearningGroup)
class LearningGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "members_can_invite", "created_at")
    inlines = [MembershipInline]


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("group", "token", "created_by", "expires_at", "created_at")
    readonly_fields = ("token",)
