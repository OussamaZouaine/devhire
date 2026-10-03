from django import forms

from .models import Skill


class SkillListField(forms.CharField):
    """
    Comma-separated text input mapped to a list of Skill objects.
    Unknown skills are created on the fly.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("help_text", "Séparées par des virgules (ex. : Python, Django, SQL)")
        kwargs.setdefault(
            "widget",
            forms.TextInput(attrs={"placeholder": "Python, Django, SQL...", "list": "skill-suggestions"}),
        )
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return ", ".join(str(getattr(skill, "name", skill)) for skill in value)

    def clean(self, value):
        value = super().clean(value)
        names = []
        seen = set()
        for raw in (value or "").replace(";", ",").split(","):
            name = " ".join(raw.split())
            if not name:
                continue
            if len(name) > 60:
                raise forms.ValidationError(f"« {name[:20]}… » est trop long (60 caractères max).")
            if name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)
        return [Skill.objects.get_or_create_by_name(name) for name in names]
