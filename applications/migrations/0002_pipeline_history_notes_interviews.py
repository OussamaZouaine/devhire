import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

STATUS_CHOICES = [
    ("received", "Reçue"),
    ("shortlisted", "Présélectionnée"),
    ("interview", "Entretien"),
    ("technical_test", "Test technique"),
    ("offer", "Proposition"),
    ("hired", "Embauché(e)"),
    ("rejected", "Refusée"),
    ("withdrawn", "Retirée"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0001_initial"),
        ("jobs", "0004_joboffer_fields_savedjob_jobalert_jobofferview"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="application",
            name="status",
            field=models.CharField(choices=STATUS_CHOICES, default="received", max_length=20),
        ),
        migrations.AddField(
            model_name="application",
            name="match_score",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Calculé au moment de la candidature (0-100).",
                null=True,
                verbose_name="score de compatibilité",
            ),
        ),
        migrations.AddField(
            model_name="application",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(name="application", unique_together=set()),
        migrations.AddConstraint(
            model_name="application",
            constraint=models.UniqueConstraint(
                fields=("candidate", "job_offer"),
                name="unique_application_per_offer",
            ),
        ),
        migrations.CreateModel(
            name="ApplicationStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_status", models.CharField(blank=True, choices=STATUS_CHOICES, max_length=20)),
                ("to_status", models.CharField(choices=STATUS_CHOICES, max_length=20)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("changed_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history",
                        to="applications.application",
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["changed_at"], "verbose_name": "Historique de statut"},
        ),
        migrations.CreateModel(
            name="RecruiterNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(verbose_name="note")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="applications.application",
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Interview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scheduled_at", models.DateTimeField(verbose_name="date et heure")),
                ("duration_minutes", models.PositiveSmallIntegerField(default=45, verbose_name="durée (minutes)")),
                (
                    "mode",
                    models.CharField(
                        choices=[("video", "Visioconférence"), ("onsite", "Sur place"), ("phone", "Téléphone")],
                        default="video",
                        max_length=20,
                        verbose_name="format",
                    ),
                ),
                (
                    "location",
                    models.CharField(
                        blank=True,
                        help_text="Adresse, lien de visio ou numéro de téléphone",
                        max_length=255,
                        verbose_name="lieu ou lien",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="informations pour le candidat")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interviews",
                        to="applications.application",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["scheduled_at"], "verbose_name": "Entretien"},
        ),
    ]
