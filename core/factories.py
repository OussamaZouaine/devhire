"""Small helpers to build test data (used by every app's tests)."""

from itertools import count

from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Company, RecruiterProfile, User
from applications.models import Application, ApplicationStatusHistory
from jobs.models import JobOffer
from matching.models import Skill

from .pdf import demo_pdf

PASSWORD = "TestPass123!"
_sequence = count(1)


def pdf_file(name: str = "cv.pdf", text: str = "Python Django") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, demo_pdf(text), content_type="application/pdf")


def make_company(name: str | None = None) -> Company:
    return Company.objects.create(name=name or f"Company {next(_sequence)}")


def make_recruiter(username: str | None = None, company: Company | None = None, admin: bool = True) -> User:
    username = username or f"recruiter{next(_sequence)}"
    user = User(username=username, email=f"{username}@test.com", role=User.Role.RECRUITER)
    user.set_password(PASSWORD)
    role = RecruiterProfile.CompanyRole.ADMIN if admin else RecruiterProfile.CompanyRole.MEMBER
    user._pending_company = (company or make_company(), role)
    user.save()
    return user


def make_candidate(username: str | None = None, skills=(), with_cv: bool = True, **profile_fields) -> User:
    username = username or f"candidate{next(_sequence)}"
    user = User.objects.create_user(
        username=username,
        email=f"{username}@test.com",
        password=PASSWORD,
        role=User.Role.CANDIDATE,
    )
    profile = user.get_candidate_profile()
    for field, value in profile_fields.items():
        setattr(profile, field, value)
    if with_cv:
        profile.cv = pdf_file()
    profile.save()
    profile.skills.set([Skill.objects.get_or_create_by_name(name) for name in skills])
    return user


def make_offer(recruiter: User, skills=(), **fields) -> JobOffer:
    profile = recruiter.get_recruiter_profile()
    defaults = {
        "title": f"Offre {next(_sequence)}",
        "description": "Description du poste",
        "location": "Paris",
        "contract_type": JobOffer.ContractType.CDI,
    }
    defaults.update(fields)
    offer = JobOffer.objects.create(company=profile.company, recruiter=profile, **defaults)
    offer.skills.set([Skill.objects.get_or_create_by_name(name) for name in skills])
    return offer


def make_application(candidate: User, offer: JobOffer, **fields) -> Application:
    application = Application.objects.create(candidate=candidate.get_candidate_profile(), job_offer=offer, **fields)
    ApplicationStatusHistory.objects.create(
        application=application, from_status="", to_status=application.status, changed_by=candidate
    )
    return application
