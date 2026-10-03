import random
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Company, Education, Experience, Language, RecruiterProfile, User
from applications.models import Application, ApplicationStatusHistory, Interview, RecruiterNote
from assessments.models import Choice, Question, Quiz
from core.pdf import demo_pdf
from jobs.models import JobAlert, JobOffer, JobOfferView, SavedJob
from matching.engine import combine
from matching.models import Skill
from matching.services import match
from messaging.models import Message

DEMO_PASSWORD = "devhire123"

DEMO_USERNAMES = [
    "recruiter1",
    "recruiter2",
    "recruiter3",
    "candidate1",
    "candidate2",
    "candidate3",
    "candidate4",
]
DEMO_COMPANIES = ["TechNova", "GreenLabs"]


def skills(*names: str) -> list[Skill]:
    return [Skill.objects.get_or_create_by_name(name) for name in names]


class Command(BaseCommand):
    help = "Crée des entreprises, utilisateurs, offres, candidatures, tests et messages de démonstration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprime les données de démo existantes avant de recréer.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)
        if options["clear"]:
            self._clear_demo_data()

        companies = self._create_companies()
        recruiters = self._create_recruiters(companies)
        candidates = self._create_candidates()
        offers = self._create_job_offers(recruiters)
        self._create_quiz(offers[0])
        applications = self._create_applications(candidates, offers, recruiters)
        self._create_engagement(candidates, offers, applications, recruiters)

        self.stdout.write(self.style.SUCCESS("Données de démonstration créées avec succès."))
        self.stdout.write("")
        self.stdout.write(f"Mot de passe de tous les comptes : {DEMO_PASSWORD}")
        self.stdout.write(
            "  Recruteurs : recruiter1 (admin TechNova), recruiter3 (TechNova), recruiter2 (admin GreenLabs)"
        )
        self.stdout.write("  Candidats  : candidate1 (Alice), candidate2 (Bob), candidate3 (Chloé), candidate4 (David)")

    def _clear_demo_data(self):
        Application.objects.filter(candidate__user__username__in=DEMO_USERNAMES).delete()
        JobOffer.objects.filter(company__name__in=DEMO_COMPANIES).delete()
        deleted, _ = User.objects.filter(username__in=DEMO_USERNAMES).delete()
        Company.objects.filter(name__in=DEMO_COMPANIES, recruiters__isnull=True).delete()
        self.stdout.write(f"Supprimé {deleted} enregistrement(s) de démo.")

    def _create_companies(self):
        data = [
            (
                "TechNova",
                "Paris",
                "https://technova.demo",
                "TechNova édite une plateforme SaaS B2B utilisée par 2 000 entreprises. "
                "Équipe produit de 40 personnes, stack Python / React, culture du test et du déploiement continu.",
            ),
            (
                "GreenLabs",
                "Lyon",
                "https://greenlabs.demo",
                "GreenLabs mesure et réduit l'empreinte carbone des industriels grâce à la donnée. "
                "Start-up à impact de 25 personnes, full remote possible.",
            ),
        ]
        companies = {}
        for name, location, website, description in data:
            company, _ = Company.objects.get_or_create(name=name)
            company.location = location
            company.website = website
            company.description = description
            company.save()
            companies[name] = company
        return companies

    def _user(self, username, email, role, first_name, last_name="", company=None, company_role=None):
        user = User.objects.filter(username=username).first()
        created = user is None
        if created:
            user = User(username=username, email=email, role=role, first_name=first_name, last_name=last_name)
            if company is not None:
                user._pending_company = (company, company_role)
            user.set_password(DEMO_PASSWORD)
            user.save()
        self.stdout.write(f"  {username} ({'créé' if created else 'existant'})")
        return user

    def _create_recruiters(self, companies):
        admin = RecruiterProfile.CompanyRole.ADMIN
        member = RecruiterProfile.CompanyRole.MEMBER
        rows = [
            ("recruiter1", "sarah@technova.demo", "Sarah", "Lemoine", "TechNova", admin, "Talent Acquisition Manager"),
            ("recruiter3", "karim@technova.demo", "Karim", "Haddad", "TechNova", member, "Engineering Manager"),
            ("recruiter2", "julie@greenlabs.demo", "Julie", "Moreau", "GreenLabs", admin, "CTO"),
        ]
        recruiters = {}
        for username, email, first, last, company_name, role, job_title in rows:
            user = self._user(username, email, User.Role.RECRUITER, first, last, companies[company_name], role)
            profile = user.get_recruiter_profile()
            profile.company = companies[company_name]
            profile.company_role = role
            profile.job_title = job_title
            profile.save()
            recruiters[username] = profile
        return recruiters

    def _create_candidates(self):
        rows = [
            {
                "username": "candidate1",
                "first": "Alice",
                "last": "Martin",
                "email": "alice@demo.dev",
                "headline": "Développeuse back-end Python / Django",
                "years": 3,
                "location": "Paris",
                "skills": ["Python", "Django", "PostgreSQL", "REST", "Docker", "Git"],
                "bio": "Développeuse back-end passionnée par les API propres et les tests automatisés.",
                "cv": "Alice Martin - Python Django PostgreSQL Docker REST API Celery Redis Git CI/CD",
                "experiences": [
                    ("Développeuse Python", "DataCorp", date(2022, 9, 1), None, "API REST Django, PostgreSQL, Celery.")
                ],
                "education": [("EPITA", "Diplôme d'ingénieur", "Informatique", 2017, 2022)],
                "languages": [("Français", Language.Level.NATIVE), ("Anglais", Language.Level.C1)],
            },
            {
                "username": "candidate2",
                "first": "Bob",
                "last": "Dupont",
                "email": "bob@demo.dev",
                "headline": "Développeur front-end React",
                "years": 2,
                "location": "Lyon",
                "skills": ["JavaScript", "TypeScript", "React", "Node.js", "CSS"],
                "bio": "Développeur front-end, j'aime les interfaces accessibles et performantes.",
                "cv": "Bob Dupont - JavaScript TypeScript React Next.js Node.js HTML CSS Figma Jest",
                "experiences": [
                    ("Développeur front-end", "WebAgency", date(2023, 1, 15), None, "Applications React et TypeScript.")
                ],
                "education": [("Université Lyon 1", "Master", "Informatique", 2018, 2023)],
                "languages": [("Français", Language.Level.NATIVE), ("Anglais", Language.Level.B2)],
            },
            {
                "username": "candidate3",
                "first": "Chloé",
                "last": "Bernard",
                "email": "chloe@demo.dev",
                "headline": "Ingénieure DevOps",
                "years": 5,
                "location": "Remote",
                "skills": ["Docker", "Kubernetes", "AWS", "Terraform", "Python", "Linux"],
                "bio": "Ingénieure DevOps / SRE, automatisation et fiabilité des plateformes cloud.",
                "cv": "Chloe Bernard - DevOps Docker Kubernetes AWS Terraform Ansible Linux Python GitHub Actions",
                "experiences": [
                    ("Ingénieure DevOps", "CloudFirst", date(2021, 3, 1), None, "Kubernetes, Terraform, AWS."),
                    ("Administratrice systèmes", "HébergeTout", date(2019, 6, 1), date(2021, 2, 28), "Linux, Ansible."),
                ],
                "education": [("INSA Lyon", "Diplôme d'ingénieur", "Réseaux", 2014, 2019)],
                "languages": [
                    ("Français", Language.Level.NATIVE),
                    ("Anglais", Language.Level.C1),
                    ("Espagnol", Language.Level.B1),
                ],
            },
            {
                "username": "candidate4",
                "first": "David",
                "last": "Nguyen",
                "email": "david@demo.dev",
                "headline": "Data engineer",
                "years": 4,
                "location": "Lyon",
                "skills": ["Python", "SQL", "ETL", "Spark", "Pandas", "Airflow"],
                "bio": "Data engineer : pipelines de données, qualité et modélisation.",
                "cv": "David Nguyen - Python SQL ETL Spark Pandas Airflow PostgreSQL Docker Power BI",
                "experiences": [
                    ("Data engineer", "RetailData", date(2020, 10, 1), None, "Pipelines Spark et Airflow.")
                ],
                "education": [("Université Paris-Saclay", "Master", "Data science", 2015, 2020)],
                "languages": [("Français", Language.Level.NATIVE), ("Anglais", Language.Level.B2)],
            },
        ]
        candidates = {}
        for row in rows:
            user = self._user(row["username"], row["email"], User.Role.CANDIDATE, row["first"], row["last"])
            profile = user.get_candidate_profile()
            profile.headline = row["headline"]
            profile.years_of_experience = row["years"]
            profile.location = row["location"]
            profile.bio = row["bio"]
            profile.phone = "06 12 34 56 78"
            profile.cv_text = row["cv"]
            if not profile.cv:
                profile.cv.save(f"cv_{row['username']}.pdf", ContentFile(demo_pdf(row["cv"])), save=False)
            profile.save()
            profile.skills.set(skills(*row["skills"]))
            profile.experiences.all().delete()
            for title, company, start, end, description in row["experiences"]:
                Experience.objects.create(
                    candidate=profile,
                    title=title,
                    company=company,
                    start_date=start,
                    end_date=end,
                    description=description,
                )
            profile.educations.all().delete()
            for school, degree, field, start, end in row["education"]:
                Education.objects.create(
                    candidate=profile,
                    school=school,
                    degree=degree,
                    field_of_study=field,
                    start_year=start,
                    end_year=end,
                )
            profile.languages.all().delete()
            for name, level in row["languages"]:
                Language.objects.create(candidate=profile, name=name, level=level)
            candidates[row["username"]] = profile
        return candidates

    def _create_job_offers(self, recruiters):
        today = timezone.localdate()
        rows = [
            (
                "recruiter1",
                "Développeur Django",
                "Paris",
                JobOffer.ContractType.CDI,
                JobOffer.RemotePolicy.HYBRID,
                JobOffer.ExperienceLevel.MID,
                ["Python", "Django", "PostgreSQL", "REST", "Docker"],
                42000,
                52000,
                30,
                "Rejoignez l'équipe back-end pour construire notre plateforme SaaS en Django. "
                "Vous concevrez des API REST, optimiserez les requêtes PostgreSQL et participerez aux revues de code.",
            ),
            (
                "recruiter3",
                "DevOps Engineer",
                "Remote",
                JobOffer.ContractType.CDI,
                JobOffer.RemotePolicy.REMOTE,
                JobOffer.ExperienceLevel.SENIOR,
                ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD"],
                50000,
                62000,
                45,
                "Automatisation CI/CD, infrastructure as code avec Terraform, Kubernetes sur AWS et monitoring.",
            ),
            (
                "recruiter1",
                "Stage Développeur Full Stack",
                "Paris",
                JobOffer.ContractType.STAGE,
                JobOffer.RemotePolicy.ONSITE,
                JobOffer.ExperienceLevel.JUNIOR,
                ["Python", "Django", "React", "Git"],
                None,
                None,
                20,
                "Stage de 6 mois sur notre application web Django + React, encadré par un développeur senior.",
            ),
            (
                "recruiter2",
                "Développeur React",
                "Lyon",
                JobOffer.ContractType.CDD,
                JobOffer.RemotePolicy.HYBRID,
                JobOffer.ExperienceLevel.MID,
                ["React", "TypeScript", "JavaScript", "CSS"],
                38000,
                46000,
                None,
                "Construire des interfaces modernes et accessibles pour notre produit green-tech.",
            ),
            (
                "recruiter2",
                "Data Engineer",
                "Lyon",
                JobOffer.ContractType.CDI,
                JobOffer.RemotePolicy.REMOTE,
                JobOffer.ExperienceLevel.MID,
                ["Python", "SQL", "ETL", "Spark", "Airflow"],
                45000,
                55000,
                60,
                "Concevoir nos pipelines de données carbone : ingestion, qualité, modélisation et exposition.",
            ),
            (
                "recruiter2",
                "Alternance Data Analyst",
                "Lyon",
                JobOffer.ContractType.ALTERNANCE,
                JobOffer.RemotePolicy.HYBRID,
                JobOffer.ExperienceLevel.JUNIOR,
                ["SQL", "Python", "Power BI", "Excel"],
                None,
                None,
                40,
                "Alternance de 2 ans : tableaux de bord, analyses ad hoc et automatisation des rapports.",
            ),
            (
                "recruiter3",
                "Lead Développeur Python",
                "Paris",
                JobOffer.ContractType.CDI,
                JobOffer.RemotePolicy.HYBRID,
                JobOffer.ExperienceLevel.LEAD,
                ["Python", "Django", "Celery", "Redis", "PostgreSQL"],
                65000,
                80000,
                None,
                "Encadrer une équipe de 5 développeurs, définir l'architecture et garantir la qualité du code.",
            ),
        ]
        offers = []
        for (
            username,
            title,
            location,
            contract,
            remote,
            level,
            skill_names,
            smin,
            smax,
            deadline_days,
            description,
        ) in rows:
            recruiter = recruiters[username]
            offer, created = JobOffer.objects.update_or_create(
                company=recruiter.company,
                title=title,
                defaults={
                    "recruiter": recruiter,
                    "description": description,
                    "location": location,
                    "contract_type": contract,
                    "remote_policy": remote,
                    "experience_level": level,
                    "salary_min": smin,
                    "salary_max": smax,
                    "deadline": today + timedelta(days=deadline_days) if deadline_days else None,
                    "is_active": True,
                },
            )
            offer.skills.set(skills(*skill_names))
            offers.append(offer)
            self.stdout.write(f"  Offre « {title} » ({'créée' if created else 'mise à jour'})")
        return offers

    def _create_quiz(self, offer):
        quiz, _ = Quiz.objects.update_or_create(
            job_offer=offer,
            defaults={
                "title": "QCM Python / Django",
                "instructions": "5 questions sur Python et Django. Une seule bonne réponse par question.",
                "time_limit_minutes": 10,
            },
        )
        quiz.questions.all().delete()
        questions = [
            ("Quelle commande crée les fichiers de migration ?", ["makemigrations", "migrate", "sqlmigrate"], 0),
            ("Quel ORM lookup fait une recherche insensible à la casse ?", ["contains", "icontains", "exact"], 1),
            ("Comment éviter le problème N+1 sur une ForeignKey ?", ["prefetch_related", "select_related", "only"], 1),
            ("Quel type Python est immuable ?", ["list", "dict", "tuple"], 2),
            (
                "Quel middleware protège contre les attaques CSRF ?",
                ["CsrfViewMiddleware", "SecurityMiddleware", "CommonMiddleware"],
                0,
            ),
        ]
        for order, (text, choices, correct) in enumerate(questions, start=1):
            question = Question.objects.create(quiz=quiz, text=text, order=order)
            for index, choice in enumerate(choices):
                Choice.objects.create(question=question, text=choice, is_correct=index == correct)

    def _create_applications(self, candidates, offers, recruiters):
        S = Application.Status
        rows = [
            ("candidate1", 0, [S.SHORTLISTED, S.INTERVIEW], "Motivée par Django et les API REST.", 9),
            ("candidate2", 0, [S.REJECTED], "Je souhaite évoluer vers le back-end.", 12),
            ("candidate4", 0, [], "", 2),
            ("candidate3", 1, [S.SHORTLISTED, S.TECHNICAL_TEST, S.OFFER], "Expérience Kubernetes en production.", 15),
            ("candidate1", 6, [], "Intéressée par le rôle de lead.", 1),
            ("candidate2", 3, [S.SHORTLISTED, S.INTERVIEW, S.OFFER, S.HIRED], "Le green-tech me tient à cœur.", 20),
            ("candidate4", 4, [S.SHORTLISTED], "Spark et Airflow au quotidien.", 6),
            ("candidate1", 2, [], "", 3),
        ]
        now = timezone.now()
        applications = []
        for username, offer_index, steps, cover_letter, days_ago in rows:
            candidate = candidates[username]
            offer = offers[offer_index]
            application = Application.objects.filter(candidate=candidate, job_offer=offer).first()
            if application is None:
                applied_at = now - timedelta(days=days_ago)
                application = Application.objects.create(
                    candidate=candidate,
                    job_offer=offer,
                    cover_letter=cover_letter,
                    match_score=match(candidate, offer).score,
                )
                Application.objects.filter(pk=application.pk).update(applied_at=applied_at)
                ApplicationStatusHistory.objects.create(
                    application=application,
                    from_status="",
                    to_status=S.RECEIVED,
                    changed_by=candidate.user,
                    changed_at=applied_at,
                )
                recruiter_user = offer.recruiter.user if offer.recruiter else None
                for step_index, status in enumerate(steps, start=1):
                    previous = application.status
                    application.status = status
                    application.save(update_fields=["status"])
                    ApplicationStatusHistory.objects.create(
                        application=application,
                        from_status=previous,
                        to_status=status,
                        changed_by=recruiter_user,
                        changed_at=applied_at + timedelta(days=step_index * max(1, days_ago // (len(steps) + 1))),
                    )
            applications.append(application)
        return applications

    def _create_engagement(self, candidates, offers, applications, recruiters):
        # Offer views spread over the last 30 days (analytics).
        today = timezone.localdate()
        for offer in offers:
            for days_ago in range(30):
                for visitor in range(random.randint(0, 6)):
                    JobOfferView.objects.get_or_create(
                        job_offer=offer,
                        session_key=f"demo-{offer.pk}-{days_ago}-{visitor}",
                        viewed_on=today - timedelta(days=days_ago),
                    )

        alice_django = applications[0]
        if not alice_django.interviews.exists():
            Interview.objects.create(
                application=alice_django,
                scheduled_at=timezone.now() + timedelta(days=3, hours=2),
                duration_minutes=60,
                mode=Interview.Mode.VIDEO,
                location="https://meet.example.com/devhire-alice",
                notes="Entretien technique avec Karim (Engineering Manager).",
                created_by=recruiters["recruiter1"].user,
            )
        if not alice_django.messages.exists():
            Message.objects.create(
                application=alice_django,
                sender=recruiters["recruiter1"].user,
                body="Bonjour Alice, votre profil nous intéresse ! Êtes-vous disponible cette semaine ?",
            )
            Message.objects.create(
                application=alice_django,
                sender=alice_django.candidate.user,
                body="Bonjour Sarah, avec plaisir. Je suis disponible jeudi ou vendredi.",
            )
        if not alice_django.notes.exists():
            RecruiterNote.objects.create(
                application=alice_django,
                author=recruiters["recruiter3"].user,
                content="Très bon niveau sur l'ORM. À challenger sur Celery.",
            )

        SavedJob.objects.get_or_create(candidate=candidates["candidate1"], job_offer=offers[1])
        SavedJob.objects.get_or_create(candidate=candidates["candidate4"], job_offer=offers[5])
        JobAlert.objects.get_or_create(
            candidate=candidates["candidate1"],
            name="Python à Paris",
            defaults={"query": "Python", "location": "Paris"},
        )
        # Quick sanity output of the matching for the soutenance.
        best = combine(candidates["candidate1"].skill_names, offers[0].skill_names, 0)
        self.stdout.write(f"  Compatibilité compétences Alice <-> Développeur Django : {best.skill_score} %")
