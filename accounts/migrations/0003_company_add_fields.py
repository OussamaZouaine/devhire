import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_candidateprofile_cv"),
        ("matching", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="nom")),
                ("slug", models.SlugField(blank=True, max_length=220, unique=True)),
                ("logo", models.ImageField(blank=True, null=True, upload_to="logos/", verbose_name="logo")),
                ("description", models.TextField(blank=True, verbose_name="description")),
                ("website", models.URLField(blank=True, verbose_name="site web")),
                ("location", models.CharField(blank=True, max_length=100, verbose_name="siège")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"], "verbose_name": "Entreprise"},
        ),
        migrations.AddField(
            model_name="recruiterprofile",
            name="company",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="recruiters",
                to="accounts.company",
            ),
        ),
        migrations.AddField(
            model_name="recruiterprofile",
            name="company_role",
            field=models.CharField(
                choices=[("admin", "Administrateur"), ("member", "Recruteur")],
                default="admin",
                max_length=20,
                verbose_name="rôle dans l'entreprise",
            ),
        ),
        migrations.AddField(
            model_name="recruiterprofile",
            name="job_title",
            field=models.CharField(blank=True, max_length=100, verbose_name="fonction"),
        ),
        migrations.AddField(
            model_name="candidateprofile",
            name="skill_set",
            field=models.ManyToManyField(blank=True, related_name="candidates", to="matching.skill"),
        ),
    ]
