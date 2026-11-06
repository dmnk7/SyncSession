import secrets

from django.db import migrations, models

import lerngruppen.models


def fill_calendar_tokens(apps, schema_editor):
    LearningGroup = apps.get_model("lerngruppen", "LearningGroup")
    for group in LearningGroup.objects.all():
        group.calendar_token = secrets.token_urlsafe(32)
        group.save(update_fields=["calendar_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("lerngruppen", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="learninggroup",
            name="calendar_token",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.RunPython(fill_calendar_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="learninggroup",
            name="calendar_token",
            field=models.CharField(
                default=lerngruppen.models.new_calendar_token,
                editable=False,
                max_length=64,
                unique=True,
            ),
        ),
    ]
