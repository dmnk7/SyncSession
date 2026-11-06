from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kalender", "0003_session_display_override"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
