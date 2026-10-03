import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_candidate_sections_cleanup"),
        ("jobs", "0001_initial"),
        ("matching", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="joboffer",
            name="company",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="job_offers",
                to="accounts.company",
            ),
        ),
        migrations.AddField(
            model_name="joboffer",
            name="skills",
            field=models.ManyToManyField(
                blank=True,
                related_name="job_offers",
                to="matching.skill",
                verbose_name="compétences requises",
            ),
        ),
    ]
