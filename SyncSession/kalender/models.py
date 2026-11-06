from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Session(models.Model):
    KIND_VORSCHLAG = "vorschlag"
    KIND_BLOCKIERT = "blockiert"
    KIND_CHOICES = [
        (KIND_VORSCHLAG, "Vorschlag"),
        (KIND_BLOCKIERT, "Geblockte Zeit"),
    ]

    group = models.ForeignKey(
        "lerngruppen.LearningGroup",
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name="Lerngruppe",
    )
    title = models.CharField("Titel", max_length=120)
    location = models.CharField(
        "Ort",
        max_length=120,
        blank=True,
        help_text="z. B. Online oder Raum",
    )
    start = models.DateTimeField("Beginn")
    end = models.DateTimeField("Ende")
    kind = models.CharField(
        "Art",
        max_length=20,
        choices=KIND_CHOICES,
        default=KIND_VORSCHLAG,
    )
    DISPLAY_ANGENOMMEN = "angenommen"
    DISPLAY_ABGESAGT = "abgesagt"
    DISPLAY_CHOICES = [
        (DISPLAY_ANGENOMMEN, "Angenommen"),
        (DISPLAY_ABGESAGT, "Abgesagt"),
    ]
    display_override = models.CharField(
        "Festgelegte Darstellung",
        max_length=12,
        blank=True,
        default="",
        choices=DISPLAY_CHOICES,
        help_text=(
            "Nur bei gemischten Rückmeldungen: der Ersteller legt fest, "
            "ob der Termin als angenommen oder abgesagt erscheint."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")),
                name="session_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.group})"

    def clean(self):
        super().clean()
        if self.start is not None and self.end is not None:
            if self.end <= self.start:
                raise ValidationError(
                    {"end": "Das Ende muss nach dem Beginn liegen."}
                )


STATUS_ZUGESAGT = "zugesagt"
STATUS_ABGESAGT = "abgesagt"


class Attendance(models.Model):
    STATUS_CHOICES = [
        (STATUS_ZUGESAGT, "Zugesagt"),
        (STATUS_ABGESAGT, "Abgesagt"),
    ]

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="attendances",
        verbose_name="Termin",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_attendances",
        verbose_name="Mitglied",
    )
    status = models.CharField(
        "Status",
        max_length=10,
        choices=STATUS_CHOICES,
    )
    start = models.DateTimeField(
        "Teilnahme ab",
        null=True,
        blank=True,
        help_text="Bei Teil-Zusage: ab dieser Zeit.",
    )
    end = models.DateTimeField(
        "Teilnahme bis",
        null=True,
        blank=True,
        help_text="Bei Teil-Zusage: bis zu dieser Zeit.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "user"],
                name="unique_session_attendance",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=STATUS_ABGESAGT,
                        start__isnull=True,
                        end__isnull=True,
                    )
                    | models.Q(
                        status=STATUS_ZUGESAGT,
                        start__isnull=False,
                        end__isnull=False,
                    )
                ),
                name="attendance_status_times",
            ),
        ]

    def __str__(self):
        return f"{self.user} {self.status} für {self.session}"
