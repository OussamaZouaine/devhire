from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CandidateProfile, Company, RecruiterProfile, User


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance: User, created: bool, **kwargs) -> None:
    """Create the matching profile when a user is created."""
    if not created:
        return

    if instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.RECRUITER:
        pending = getattr(instance, "_pending_company", None)
        if pending:
            company, company_role = pending
        else:
            company = Company.objects.create(name=f"Entreprise de {instance.username}")
            company_role = RecruiterProfile.CompanyRole.ADMIN
        RecruiterProfile.objects.get_or_create(
            user=instance,
            defaults={"company": company, "company_role": company_role},
        )
