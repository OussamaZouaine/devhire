from django.db import migrations
from django.utils.text import slugify


def forwards(apps, schema_editor):
    JobOffer = apps.get_model("jobs", "JobOffer")
    Skill = apps.get_model("matching", "Skill")

    for offer in JobOffer.objects.select_related("recruiter"):
        offer.company_id = offer.recruiter.company_id
        offer.save(update_fields=["company"])
        for raw in (offer.keywords or "").replace(";", ",").split(","):
            name = " ".join(raw.split())[:60]
            if not name:
                continue
            slug = slugify(name) or name.lower()
            skill, _ = Skill.objects.get_or_create(slug=slug, defaults={"name": name})
            offer.skills.add(skill)


def backwards(apps, schema_editor):
    JobOffer = apps.get_model("jobs", "JobOffer")
    for offer in JobOffer.objects.all():
        offer.keywords = ", ".join(skill.name for skill in offer.skills.all())[:255]
        offer.save(update_fields=["keywords"])


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0002_joboffer_company_skills_add"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
