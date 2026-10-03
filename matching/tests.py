from django.test import SimpleTestCase, TestCase

from core.factories import make_candidate, make_offer, make_recruiter, pdf_file

from . import engine
from .cv_parser import detect_skills, extract_text
from .fields import SkillListField
from .models import Skill
from .services import match, rank_applications, recommend_offers, top_candidates


class EngineTests(SimpleTestCase):
    def test_tokenize_lowercases_strips_accents_and_stop_words(self):
        self.assertEqual(
            engine.tokenize("Le Développeur Python et les API"),
            ["developpeur", "python", "api"],
        )

    def test_tokenize_keeps_technical_tokens(self):
        tokens = engine.tokenize("C++, C#, Node.js et Vue.js")
        self.assertIn("c++", tokens)
        self.assertIn("c#", tokens)
        self.assertIn("node.js", tokens)

    def test_skill_overlap(self):
        score, matched, missing = engine.skill_overlap(["python", "Docker"], ["Python", "Django", "Docker", "SQL"])
        self.assertEqual(score, 0.5)
        self.assertEqual(matched, ["Python", "Docker"])
        self.assertEqual(missing, ["Django", "SQL"])

    def test_skill_overlap_without_offer_skills(self):
        self.assertEqual(engine.skill_overlap(["Python"], []), (0.0, [], []))

    def test_cosine_identical_and_disjoint_documents(self):
        model = engine.TfidfModel(["python django api", "react typescript", "java spring"])
        self.assertAlmostEqual(model.similarity("python django", "python django"), 1.0)
        self.assertEqual(model.similarity("python django", "react typescript"), 0.0)
        self.assertEqual(model.similarity("", "python"), 0.0)

    def test_rare_terms_weigh_more(self):
        model = engine.TfidfModel(["python django", "python flask", "python fastapi", "rust tokio"])
        self.assertGreater(model.idf["django"], model.idf["python"])

    def test_combine_weights_skills_and_text(self):
        result = engine.combine(["Python"], ["Python", "Django"], text_similarity=0.5)
        self.assertEqual(result.skill_score, 50)
        self.assertEqual(result.text_score, 50)
        self.assertEqual(result.score, round((0.7 * 0.5 + 0.3 * 0.5) * 100))
        self.assertEqual(result.level, "medium")

    def test_combine_without_offer_skills_uses_text_only(self):
        result = engine.combine(["Python"], [], text_similarity=0.8)
        self.assertEqual(result.score, 80)
        self.assertEqual(result.level, "high")
        self.assertEqual(engine.combine([], [], 0.1).level, "low")


class CvParserTests(SimpleTestCase):
    def test_detect_skills_whole_words_only(self):
        found = detect_skills("Expert Python, Django et Node.js. Excellent en C++.", known_skills=["Kubernetes"])
        self.assertEqual(found, ["C++", "Django", "Node.js", "Python"])
        self.assertNotIn("Excel", found)

    def test_detect_skills_on_empty_text(self):
        self.assertEqual(detect_skills(""), [])

    def test_extract_text_from_pdf(self):
        self.assertIn("Kubernetes", extract_text(pdf_file(text="Docker Kubernetes AWS")))

    def test_extract_text_from_invalid_pdf_returns_empty_string(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.assertEqual(extract_text(SimpleUploadedFile("cv.pdf", b"not a pdf")), "")


class SkillTests(TestCase):
    def test_get_or_create_is_case_insensitive(self):
        first = Skill.objects.get_or_create_by_name("Django")
        second = Skill.objects.get_or_create_by_name("  django ")
        self.assertEqual(first, second)
        self.assertEqual(str(first), "Django")

    def test_skill_list_field(self):
        field = SkillListField()
        skills = field.clean("Python, python ; Docker,, ")
        self.assertEqual([skill.name for skill in skills], ["Python", "Docker"])
        self.assertEqual(field.prepare_value(skills), "Python, Docker")
        self.assertEqual(field.prepare_value(None), "")

    def test_skill_list_field_rejects_long_names(self):
        from django import forms

        with self.assertRaises(forms.ValidationError):
            SkillListField().clean("x" * 61)


class MatchingServiceTests(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter()
        self.django_offer = make_offer(
            self.recruiter,
            skills=["Python", "Django", "PostgreSQL"],
            title="Développeur Django",
            description="API REST en Django et PostgreSQL",
        )
        self.react_offer = make_offer(
            self.recruiter,
            skills=["React", "TypeScript"],
            title="Développeur React",
            description="Interfaces React",
        )
        self.alice = make_candidate("alice", skills=["Python", "Django"], headline="Développeuse Django")

    def test_match_prefers_the_relevant_offer(self):
        profile = self.alice.get_candidate_profile()
        self.assertGreater(match(profile, self.django_offer).score, match(profile, self.react_offer).score)
        self.assertEqual(match(profile, self.django_offer).missing_skills, ["PostgreSQL"])

    def test_recommendations_are_sorted_and_exclude_applied_offers(self):
        from core.factories import make_application

        profile = self.alice.get_candidate_profile()
        results = recommend_offers(profile)
        self.assertEqual(results[0][0], self.django_offer)
        make_application(self.alice, self.django_offer)
        self.assertNotIn(self.django_offer, [offer for offer, _ in recommend_offers(profile)])

    def test_rank_applications_and_top_candidates(self):
        from applications.models import Application
        from core.factories import make_application

        bob = make_candidate("bob", skills=["React"])
        make_application(bob, self.django_offer)
        make_application(self.alice, self.django_offer)
        ranked = rank_applications(self.django_offer, Application.objects.filter(job_offer=self.django_offer))
        self.assertEqual(ranked[0].candidate.user, self.alice)

        carol = make_candidate("carol", skills=["Django", "PostgreSQL"])
        suggestions = [candidate.user for candidate, _ in top_candidates(self.django_offer)]
        self.assertEqual(suggestions, [carol])
