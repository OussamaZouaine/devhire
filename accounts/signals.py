from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CandidateProfile, RecruiterProfile, User


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance: User, created: bool, **kwargs) -> None:
    """Create the matching profile when a user is created."""
    if not created:
        return

    if instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.RECRUITER:
        RecruiterProfile.objects.get_or_create(
            user=instance,
            defaults={"company_name": f"Entreprise de {instance.username}"},
        )
