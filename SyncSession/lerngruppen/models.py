from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class LearningGroup(models.Model):
    name = models.CharField("Name", max_length=120)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_learning_groups",
    )
    members_can_invite = models.BooleanField(
        "Alle Mitglieder dürfen einladen",
        default=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Membership",
        related_name="learning_groups",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def for_member(cls, user):
        return cls.objects.filter(memberships__user=user).distinct()

    def is_member(self, user):
        if not user.is_authenticated:
            return False
        return self.memberships.filter(user=user).exists()

    def user_can_invite(self, user):
        if not user.is_authenticated:
            return False
        if self.created_by_id == user.id:
            return True
        if self.members_can_invite:
            return self.is_member(user)
        return False


class Membership(models.Model):
    group = models.ForeignKey(
        LearningGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_group_membership",
            )
        ]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} in {self.group}"


class Invite(models.Model):
    group = models.ForeignKey(
        LearningGroup,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    token = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_invites",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite {self.token} for {self.group}"

    def is_expired(self):
        return timezone.now() >= self.expires_at

    @classmethod
    def expiry_from_now(cls):
        return timezone.now() + timedelta(hours=48)
