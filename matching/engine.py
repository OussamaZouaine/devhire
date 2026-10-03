"""
Candidate ↔ job offer matching algorithms (pure Python, no ML dependency).

Two complementary signals are combined:

1. Skill overlap — share of the skills required by the offer that the
   candidate has:  |S_candidate ∩ S_offer| / |S_offer|

2. Text similarity — cosine similarity between the TF-IDF vectors of the
   candidate document (bio, skills, experiences, CV text) and the offer
   document (title, description, skills).

       tf(t, d)  = count(t, d) / len(d)
       idf(t)    = ln((1 + N) / (1 + df(t))) + 1          (smoothed)
       w(t, d)   = tf(t, d) × idf(t)
       cos(a, b) = Σ a_t·b_t / (‖a‖ · ‖b‖)

The final score is a weighted average (see SKILL_WEIGHT), expressed in %.
"""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

SKILL_WEIGHT = 0.7
TEXT_WEIGHT = 1 - SKILL_WEIGHT

STOP_WORDS = frozenset(
    """
    a au aux avec ce ces cette dans de des du elle en et eux il ils je la le les
    leur lui ma mais me meme mes moi mon ne nos notre nous on ou par pas pour qu
    que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous c d j l
    m n s t y ete etre avoir est sont plus tres tout tous toute toutes chez afin
    sans sous entre vers comme ainsi aussi bien peut doit leurs
    the and or of to in for on with at by from an is are be as this that it its
    we you your our will can have has into about over more than
    """.split()  # noqa: SIM905
)

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.]*[a-z0-9+#]|[a-z0-9]")


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    """Lowercase, remove accents and stop words. Keeps tokens like c++, c#, node.js."""
    text = strip_accents((text or "").lower())
    return [token for token in TOKEN_RE.findall(text) if len(token) > 1 and token not in STOP_WORDS]


def skill_overlap(candidate_skills: Iterable[str], offer_skills: Iterable[str]) -> tuple[float, list[str], list[str]]:
    """Return (score 0..1, matched skills, missing skills)."""
    candidate_set = {skill.lower() for skill in candidate_skills}
    offer_list = list(dict.fromkeys(offer_skills))
    if not offer_list:
        return 0.0, [], []
    matched = [skill for skill in offer_list if skill.lower() in candidate_set]
    missing = [skill for skill in offer_list if skill.lower() not in candidate_set]
    return len(matched) / len(offer_list), matched, missing


class TfidfModel:
    """Minimal TF-IDF vectorizer fitted on a corpus of documents."""

    def __init__(self, documents: Iterable[str]):
        tokenized = [tokenize(doc) for doc in documents]
        self.document_count = len(tokenized)
        document_frequency: Counter[str] = Counter()
        for tokens in tokenized:
            document_frequency.update(set(tokens))
        self.idf = {term: math.log((1 + self.document_count) / (1 + df)) + 1 for term, df in document_frequency.items()}
        self._default_idf = math.log(1 + self.document_count) + 1

    def vectorize(self, text: str) -> dict[str, float]:
        tokens = tokenize(text)
        if not tokens:
            return {}
        counts = Counter(tokens)
        length = len(tokens)
        return {term: (count / length) * self.idf.get(term, self._default_idf) for term, count in counts.items()}

    @staticmethod
    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        if len(a) > len(b):
            a, b = b, a
        dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
        norm_a = math.sqrt(sum(w * w for w in a.values()))
        norm_b = math.sqrt(sum(w * w for w in b.values()))
        if not norm_a or not norm_b:
            return 0.0
        return dot / (norm_a * norm_b)

    def similarity(self, text_a: str, text_b: str) -> float:
        return self.cosine(self.vectorize(text_a), self.vectorize(text_b))


@dataclass
class MatchResult:
    score: int
    skill_score: int
    text_score: int
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)

    @property
    def level(self) -> str:
        if self.score >= 70:
            return "high"
        if self.score >= 40:
            return "medium"
        return "low"


def combine(
    candidate_skills: list[str],
    offer_skills: list[str],
    text_similarity: float,
) -> MatchResult:
    overlap, matched, missing = skill_overlap(candidate_skills, offer_skills)
    if offer_skills:
        raw = SKILL_WEIGHT * overlap + TEXT_WEIGHT * text_similarity
    else:
        raw = text_similarity
    return MatchResult(
        score=round(min(raw, 1.0) * 100),
        skill_score=round(overlap * 100),
        text_score=round(text_similarity * 100),
        matched_skills=matched,
        missing_skills=missing,
    )
