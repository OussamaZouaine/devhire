from django.db import migrations

OLD_TO_NEW = {"pending": "received", "accepted": "hired"}
NEW_TO_OLD = {
    "received": "pending",
    "shortlisted": "pending",
    "interview": "pending",
    "technical_test": "pending",
    "offer": "pending",
    "hired": "accepted",
    "withdrawn": "rejected",
}


def forwards(apps, schema_editor):
    Application = apps.get_model("applications", "Application")
    History = apps.get_model("applications", "ApplicationStatusHistory")
    for old, new in OLD_TO_NEW.items():
        Application.objects.filter(status=old).update(status=new)
    # Seed the history so analytics have a starting point for existing applications.
    History.objects.bulk_create(
        History(
            application=application,
            from_status="",
            to_status=application.status,
            changed_at=application.applied_at,
        )
        for application in Application.objects.all()
    )


def backwards(apps, schema_editor):
    Application = apps.get_model("applications", "Application")
    for new, old in NEW_TO_OLD.items():
        Application.objects.filter(status=new).update(status=old)


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0002_pipeline_history_notes_interviews"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
