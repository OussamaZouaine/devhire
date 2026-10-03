import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_migrate_companies_and_skills"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recruiterprofile",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="recruiters",
                to="accounts.company",
            ),
        ),
        migrations.RemoveField(model_name="recruiterprofile", name="company_name"),
        migrations.RemoveField(model_name="recruiterprofile", name="company_logo"),
        migrations.RemoveField(model_name="recruiterprofile", name="company_description"),
        migrations.RemoveField(model_name="recruiterprofile", name="website"),
        migrations.RemoveField(model_name="candidateprofile", name="skills"),
        migrations.RenameField(model_name="candidateprofile", old_name="skill_set", new_name="skills"),
        migrations.AlterField(
            model_name="candidateprofile",
            name="skills",
            field=models.ManyToManyField(
                blank=True,
                related_name="candidates",
                to="matching.skill",
                verbose_name="compétences",
            ),
        ),
        migrations.AddField(
            model_name="candidateprofile",
            name="headline",
            field=models.CharField(
                blank=True,
                help_text="Ex. : Développeuse Python / Django",
                max_length=120,
                verbose_name="titre du profil",
            ),
        ),
        migrations.AddField(
            model_name="candidateprofile",
            name="years_of_experience",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="années d'expérience"),
        ),
        migrations.AddField(
            model_name="candidateprofile",
            name="cv_text",
            field=models.TextField(
                blank=True,
                editable=False,
                help_text="Texte extrait automatiquement du CV (utilisé pour le matching).",
            ),
        ),
        migrations.AlterField(
            model_name="candidateprofile",
            name="phone",
            field=models.CharField(blank=True, max_length=20, verbose_name="téléphone"),
        ),
        migrations.AlterField(
            model_name="candidateprofile",
            name="location",
            field=models.CharField(blank=True, max_length=100, verbose_name="localisation"),
        ),
        migrations.CreateModel(
            name="Experience",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=150, verbose_name="poste")),
                ("company", models.CharField(max_length=150, verbose_name="entreprise")),
                ("start_date", models.DateField(verbose_name="début")),
                ("end_date", models.DateField(blank=True, help_text="Vide si en cours", null=True, verbose_name="fin")),
                ("description", models.TextField(blank=True)),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="experiences",
                        to="accounts.candidateprofile",
                    ),
                ),
            ],
            options={"ordering": ["-start_date"], "verbose_name": "Expérience"},
        ),
        migrations.CreateModel(
            name="Education",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("school", models.CharField(max_length=150, verbose_name="établissement")),
                ("degree", models.CharField(max_length=150, verbose_name="diplôme")),
                ("field_of_study", models.CharField(blank=True, max_length=150, verbose_name="domaine")),
                ("start_year", models.PositiveSmallIntegerField(verbose_name="année de début")),
                ("end_year", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="année de fin")),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="educations",
                        to="accounts.candidateprofile",
                    ),
                ),
            ],
            options={"ordering": ["-start_year"], "verbose_name": "Formation"},
        ),
        migrations.CreateModel(
            name="Language",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, verbose_name="langue")),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("A1", "A1 — Débutant"),
                            ("A2", "A2 — Élémentaire"),
                            ("B1", "B1 — Intermédiaire"),
                            ("B2", "B2 — Avancé"),
                            ("C1", "C1 — Autonome"),
                            ("C2", "C2 — Maîtrise"),
                            ("native", "Langue maternelle"),
                        ],
                        max_length=10,
                        verbose_name="niveau",
                    ),
                ),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="languages",
                        to="accounts.candidateprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "verbose_name": "Langue",
                "constraints": [
                    models.UniqueConstraint(fields=("candidate", "name"), name="unique_language_per_candidate")
                ],
            },
        ),
        migrations.CreateModel(
            name="CompanyInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                (
                    "role",
                    models.CharField(
                        choices=[("admin", "Administrateur"), ("member", "Recruteur")],
                        default="member",
                        max_length=20,
                    ),
                ),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitations",
                        to="accounts.company",
                    ),
                ),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sent_invitations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
