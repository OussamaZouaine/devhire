import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_candidate_sections_cleanup"),
        ("jobs", "0003_migrate_company_and_keywords"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="joboffer",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="job_offers",
                to="accounts.company",
            ),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="recruiter",
            field=models.ForeignKey(
                help_text="Recruteur qui a publié l'offre",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="job_offers",
                to="accounts.recruiterprofile",
            ),
        ),
        migrations.RemoveField(model_name="joboffer", name="keywords"),
        migrations.AddField(
            model_name="joboffer",
            name="remote_policy",
            field=models.CharField(
                choices=[("onsite", "Sur site"), ("hybrid", "Hybride"), ("remote", "Télétravail complet")],
                default="onsite",
                max_length=20,
                verbose_name="télétravail",
            ),
        ),
        migrations.AddField(
            model_name="joboffer",
            name="experience_level",
            field=models.CharField(
                choices=[
                    ("junior", "Junior (0-2 ans)"),
                    ("mid", "Confirmé (2-5 ans)"),
                    ("senior", "Senior (5+ ans)"),
                    ("lead", "Lead / Expert"),
                ],
                default="junior",
                max_length=20,
                verbose_name="niveau d'expérience",
            ),
        ),
        migrations.AddField(
            model_name="joboffer",
            name="deadline",
            field=models.DateField(blank=True, null=True, verbose_name="date limite de candidature"),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="contract_type",
            field=models.CharField(
                choices=[
                    ("CDI", "CDI"),
                    ("CDD", "CDD"),
                    ("Stage", "Stage"),
                    ("Alternance", "Alternance"),
                    ("Freelance", "Freelance"),
                ],
                default="CDI",
                max_length=20,
                verbose_name="type de contrat",
            ),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="title",
            field=models.CharField(max_length=200, verbose_name="titre"),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="location",
            field=models.CharField(max_length=100, verbose_name="localisation"),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="salary_min",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="salaire min. (€/an)"),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="salary_max",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="salaire max. (€/an)"),
        ),
        migrations.AlterField(
            model_name="joboffer",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="active"),
        ),
        migrations.AlterModelOptions(
            name="joboffer",
            options={"ordering": ["-created_at"], "verbose_name": "Offre d'emploi"},
        ),
        migrations.CreateModel(
            name="SavedJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_jobs",
                        to="accounts.candidateprofile",
                    ),
                ),
                (
                    "job_offer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_by",
                        to="jobs.joboffer",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("candidate", "job_offer"), name="unique_saved_job")
                ],
            },
        ),
        migrations.CreateModel(
            name="JobAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="nom de l'alerte")),
                ("query", models.CharField(blank=True, max_length=200, verbose_name="mots-clés")),
                ("location", models.CharField(blank=True, max_length=100, verbose_name="localisation")),
                (
                    "contract_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("CDI", "CDI"),
                            ("CDD", "CDD"),
                            ("Stage", "Stage"),
                            ("Alternance", "Alternance"),
                            ("Freelance", "Freelance"),
                        ],
                        max_length=20,
                        verbose_name="type de contrat",
                    ),
                ),
                (
                    "remote_policy",
                    models.CharField(
                        blank=True,
                        choices=[("onsite", "Sur site"), ("hybrid", "Hybride"), ("remote", "Télétravail complet")],
                        max_length=20,
                        verbose_name="télétravail",
                    ),
                ),
                ("salary_min", models.PositiveIntegerField(blank=True, null=True, verbose_name="salaire minimum")),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="job_alerts",
                        to="accounts.candidateprofile",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Alerte emploi"},
        ),
        migrations.CreateModel(
            name="JobOfferView",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(max_length=40)),
                ("viewed_on", models.DateField(default=django.utils.timezone.localdate)),
                (
                    "job_offer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="views",
                        to="jobs.joboffer",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["job_offer", "viewed_on"], name="jobs_view_offer_day_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("job_offer", "session_key", "viewed_on"),
                        name="unique_offer_view_per_session_per_day",
                    )
                ],
            },
        ),
    ]
