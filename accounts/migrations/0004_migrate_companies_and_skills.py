from django.db import migrations
from django.utils.text import slugify


def _get_skill(Skill, name):
    name = " ".join(name.split())
    slug = slugify(name) or name.lower()
    skill, _ = Skill.objects.get_or_create(slug=slug, defaults={"name": name})
    return skill


def forwards(apps, schema_editor):
    Company = apps.get_model("accounts", "Company")
    RecruiterProfile = apps.get_model("accounts", "RecruiterProfile")
    CandidateProfile = apps.get_model("accounts", "CandidateProfile")
    Skill = apps.get_model("matching", "Skill")

    used_slugs = set()
    for profile in RecruiterProfile.objects.all():
        base = slugify(profile.company_name) or "entreprise"
        slug, index = base, 2
        while slug in used_slugs:
            slug, index = f"{base}-{index}", index + 1
        used_slugs.add(slug)
        company = Company.objects.create(
            name=profile.company_name,
            slug=slug,
            logo=profile.company_logo,
            description=profile.company_description,
            website=profile.website,
        )
        profile.company = company
        profile.company_role = "admin"
        profile.save(update_fields=["company", "company_role"])

    for profile in CandidateProfile.objects.exclude(skills=""):
        for name in profile.skills.replace(";", ",").split(","):
            if name.strip():
                profile.skill_set.add(_get_skill(Skill, name.strip()[:60]))


def backwards(apps, schema_editor):
    RecruiterProfile = apps.get_model("accounts", "RecruiterProfile")
    CandidateProfile = apps.get_model("accounts", "CandidateProfile")
    for profile in RecruiterProfile.objects.select_related("company"):
        profile.company_name = profile.company.name
        profile.company_logo = profile.company.logo
        profile.company_description = profile.company.description
        profile.website = profile.company.website
        profile.save()
    for profile in CandidateProfile.objects.all():
        profile.skills = ", ".join(skill.name for skill in profile.skill_set.all())
        profile.save(update_fields=["skills"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_company_add_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
