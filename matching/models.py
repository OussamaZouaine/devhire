from django.db import models
from django.utils.text import slugify


def normalize_skill_name(name: str) -> str:
    return " ".join(name.strip().split())


class SkillQuerySet(models.QuerySet):
    def get_or_create_by_name(self, name: str) -> "Skill":
        """Case-insensitive lookup so "Django" and "django" are the same skill."""
        name = normalize_skill_name(name)
        slug = slugify(name) or name.lower()
        skill, _ = self.get_or_create(slug=slug, defaults={"name": name})
        return skill


class Skill(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=80, unique=True)

    objects = SkillQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "Compétence"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = normalize_skill_name(self.name)
        if not self.slug:
            self.slug = slugify(self.name) or self.name.lower()
        super().save(*args, **kwargs)
