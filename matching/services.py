"""Database-facing helpers built on top of matching.engine."""

from collections.abc import Iterable

from django.db.models import Prefetch, QuerySet

from accounts.models import CandidateProfile
from jobs.models import JobOffer

from .engine import MatchResult, TfidfModel, combine
from .models import Skill

SKILLS_PREFETCH = Prefetch("skills", queryset=Skill.objects.only("id", "name"))


def _corpus_model(extra_documents: Iterable[str] = ()) -> TfidfModel:
    """IDF is learnt on all open offers, so rare (specific) words weigh more."""
    offers = JobOffer.objects.open().prefetch_related(SKILLS_PREFETCH)
    documents = [offer.matching_document() for offer in offers]
    documents.extend(extra_documents)
    return TfidfModel(documents)


def _prefetched_candidate(candidate: CandidateProfile) -> CandidateProfile:
    return (
        CandidateProfile.objects.prefetch_related(SKILLS_PREFETCH, "experiences", "educations")
        .select_related("user")
        .get(pk=candidate.pk)
    )


def match(candidate: CandidateProfile, offer: JobOffer, model: TfidfModel | None = None) -> MatchResult:
    candidate_doc = candidate.matching_document()
    model = model or _corpus_model([candidate_doc])
    similarity = model.similarity(candidate_doc, offer.matching_document())
    return combine(candidate.skill_names, offer.skill_names, similarity)


def recommend_offers(
    candidate: CandidateProfile,
    limit: int = 6,
    min_score: int = 1,
) -> list[tuple[JobOffer, MatchResult]]:
    """Open offers the candidate has not applied to, best match first."""
    candidate = _prefetched_candidate(candidate)
    candidate_doc = candidate.matching_document()
    offers = list(
        JobOffer.objects.open()
        .exclude(applications__candidate=candidate)
        .select_related("company")
        .prefetch_related(SKILLS_PREFETCH)
    )
    model = TfidfModel([offer.matching_document() for offer in offers] + [candidate_doc])
    scored = [
        (
            offer,
            combine(
                candidate.skill_names, offer.skill_names, model.similarity(candidate_doc, offer.matching_document())
            ),
        )
        for offer in offers
    ]
    scored = [item for item in scored if item[1].score >= min_score]
    scored.sort(key=lambda item: (item[1].score, item[0].created_at), reverse=True)
    return scored[:limit]


def score_offers_for_candidate(candidate: CandidateProfile, offers: Iterable[JobOffer]) -> dict[int, MatchResult]:
    """Match results for a page of offers (used to show the score on search results)."""
    candidate = _prefetched_candidate(candidate)
    candidate_doc = candidate.matching_document()
    offers = list(offers)
    model = _corpus_model([candidate_doc])
    return {
        offer.pk: combine(
            candidate.skill_names,
            offer.skill_names,
            model.similarity(candidate_doc, offer.matching_document()),
        )
        for offer in offers
    }


def rank_applications(offer: JobOffer, applications: QuerySet) -> list:
    """Attach `.match` to every application and sort by score (best first)."""
    applications = list(
        applications.select_related("candidate__user").prefetch_related(
            Prefetch("candidate__skills", queryset=Skill.objects.only("id", "name")),
            "candidate__experiences",
            "candidate__educations",
        )
    )
    documents = [application.candidate.matching_document() for application in applications]
    model = _corpus_model(documents)
    offer_doc = offer.matching_document()
    offer_skills = offer.skill_names
    for application, document in zip(applications, documents, strict=True):
        application.match = combine(
            application.candidate.skill_names,
            offer_skills,
            model.similarity(document, offer_doc),
        )
    applications.sort(key=lambda application: application.match.score, reverse=True)
    return applications


def top_candidates(offer: JobOffer, limit: int = 5) -> list[tuple[CandidateProfile, MatchResult]]:
    """Best matching candidates on the platform who have not applied yet (talent sourcing)."""
    offer_skill_ids = list(offer.skills.values_list("id", flat=True))
    candidates = CandidateProfile.objects.exclude(applications__job_offer=offer).select_related("user")
    if offer_skill_ids:
        candidates = candidates.filter(skills__in=offer_skill_ids).distinct()
    candidates = list(candidates.prefetch_related(SKILLS_PREFETCH, "experiences", "educations")[:200])
    documents = [candidate.matching_document() for candidate in candidates]
    model = _corpus_model(documents)
    offer_doc = offer.matching_document()
    scored = [
        (candidate, combine(candidate.skill_names, offer.skill_names, model.similarity(document, offer_doc)))
        for candidate, document in zip(candidates, documents, strict=True)
    ]
    scored.sort(key=lambda item: item[1].score, reverse=True)
    return [item for item in scored if item[1].score > 0][:limit]
