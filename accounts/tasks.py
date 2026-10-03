from celery import shared_task

from matching.cv_parser import extract_text

from .models import CandidateProfile


@shared_task
def extract_cv_text(profile_id: int) -> int:
    """Store the CV text so it can be used by the matching and skill suggestions."""
    profile = CandidateProfile.objects.filter(pk=profile_id).first()
    if profile is None or not profile.cv:
        return 0
    with profile.cv.open("rb") as file:
        text = extract_text(file)
    CandidateProfile.objects.filter(pk=profile_id).update(cv_text=text)
    return len(text)
