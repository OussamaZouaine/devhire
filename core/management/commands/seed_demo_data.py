from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from accounts.models import User
from applications.models import Application
from jobs.models import JobOffer

DEMO_PASSWORD = "devhire123"

FAKE_PDF = b"%PDF-1.4\n%DevHire demo CV\n"


class Command(BaseCommand):
    help = "Crée des utilisateurs, offres et candidatures de démonstration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprime les données de démo existantes avant de recréer.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self._clear_demo_data()

        recruiters = self._create_recruiters()
        candidates = self._create_candidates()
        offers = self._create_job_offers(recruiters)
        self._create_applications(candidates, offers)

        self.stdout.write(self.style.SUCCESS("Données de démonstration créées avec succès."))
        self.stdout.write("")
        self.stdout.write("Comptes recruteurs (mot de passe : devhire123) :")
        self.stdout.write("  - recruiter1 / TechNova")
        self.stdout.write("  - recruiter2 / GreenLabs")
        self.stdout.write("")
        self.stdout.write("Comptes candidats (mot de passe : devhire123) :")
        self.stdout.write("  - candidate1 (Alice Martin)")
        self.stdout.write("  - candidate2 (Bob Dupont)")
        self.stdout.write("  - candidate3 (Chloé Bernard)")

    def _clear_demo_data(self):
        demo_usernames = [
            "recruiter1",
            "recruiter2",
            "candidate1",
            "candidate2",
            "candidate3",
        ]
        deleted, _ = User.objects.filter(username__in=demo_usernames).delete()
        self.stdout.write(f"Supprimé {deleted} enregistrement(s) de démo.")

    def _create_recruiters(self):
        recruiters = []
        companies = [
            ("recruiter1", "TechNova", "recruteur@technova.demo"),
            ("recruiter2", "GreenLabs", "recruteur@greenlabs.demo"),
        ]
        for username, company, email in companies:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "role": User.Role.RECRUITER,
                    "first_name": company,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            profile = user.get_recruiter_profile()
            profile.company_name = company
            profile.company_description = f"{company} recrute des talents tech."
            profile.website = f"https://{username}.demo"
            profile.save()
            recruiters.append(profile)
            action = "créé" if created else "existant"
            self.stdout.write(f"  Recruteur {username} ({action})")
        return recruiters

    def _create_candidates(self):
        candidates = []
        people = [
            ("candidate1", "Alice", "Martin", "alice@demo.dev"),
            ("candidate2", "Bob", "Dupont", "bob@demo.dev"),
            ("candidate3", "Chloé", "Bernard", "chloe@demo.dev"),
        ]
        locations = ["Paris", "Lyon", "Remote"]
        skills = [
            "Python, Django, PostgreSQL",
            "JavaScript, React, Node.js",
            "Java, Spring, Docker",
        ]
        for index, (username, first, last, email) in enumerate(people):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "role": User.Role.CANDIDATE,
                    "first_name": first,
                    "last_name": last,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            profile = user.get_candidate_profile()
            profile.phone = f"06 12 34 5{index} 0"
            profile.location = locations[index]
            profile.skills = skills[index]
            profile.bio = f"Développeur(se) passionné(e) — profil de démo {first}."
            if not profile.cv:
                profile.cv.save(
                    f"cv_{username}.pdf",
                    ContentFile(FAKE_PDF),
                    save=False,
                )
            profile.save()
            candidates.append(profile)
            action = "créé" if created else "existant"
            self.stdout.write(f"  Candidat {username} ({action})")
        return candidates

    def _create_job_offers(self, recruiters):
        offers_data = [
            {
                "recruiter": recruiters[0],
                "title": "Développeur Django",
                "description": "Rejoignez l'équipe backend pour construire une plateforme SaaS en Django.",
                "location": "Paris",
                "contract_type": JobOffer.ContractType.CDI,
                "keywords": "django, python, api",
                "salary_min": 42000,
                "salary_max": 52000,
            },
            {
                "recruiter": recruiters[0],
                "title": "DevOps Engineer",
                "description": "Automatisation CI/CD, Docker, monitoring et déploiements cloud.",
                "location": "Remote",
                "contract_type": JobOffer.ContractType.CDI,
                "keywords": "devops, docker, aws",
                "salary_min": 45000,
                "salary_max": 58000,
            },
            {
                "recruiter": recruiters[0],
                "title": "Stage Développeur Full Stack",
                "description": "Stage de 6 mois sur une application web Django + React.",
                "location": "Paris",
                "contract_type": JobOffer.ContractType.STAGE,
                "keywords": "stage, django, react",
            },
            {
                "recruiter": recruiters[1],
                "title": "Développeur React",
                "description": "Construire des interfaces modernes pour notre produit green-tech.",
                "location": "Lyon",
                "contract_type": JobOffer.ContractType.CDD,
                "keywords": "react, typescript, frontend",
                "salary_min": 38000,
                "salary_max": 46000,
            },
            {
                "recruiter": recruiters[1],
                "title": "Freelance Data Engineer",
                "description": "Mission de 3 mois sur pipelines de données et ETL.",
                "location": "Remote",
                "contract_type": JobOffer.ContractType.FREELANCE,
                "keywords": "data, python, etl",
                "salary_min": 500,
                "salary_max": 700,
            },
        ]

        offers = []
        for data in offers_data:
            offer, created = JobOffer.objects.get_or_create(
                recruiter=data["recruiter"],
                title=data["title"],
                defaults=data,
            )
            offers.append(offer)
            action = "créée" if created else "existante"
            self.stdout.write(f"  Offre « {offer.title} » ({action})")
        return offers

    def _create_applications(self, candidates, offers):
        applications_data = [
            (candidates[0], offers[0], Application.Status.PENDING, "Motivée par Django."),
            (candidates[1], offers[0], Application.Status.ACCEPTED, "Expérience backend solide."),
            (candidates[2], offers[0], Application.Status.REJECTED, ""),
            (candidates[0], offers[3], Application.Status.PENDING, "Intéressée par le green-tech."),
            (candidates[1], offers[1], Application.Status.PENDING, "Passionné DevOps."),
        ]

        for candidate, offer, status, cover_letter in applications_data:
            application, created = Application.objects.get_or_create(
                candidate=candidate,
                job_offer=offer,
                defaults={
                    "status": status,
                    "cover_letter": cover_letter,
                },
            )
            if not created and application.status != status:
                application.status = status
                application.cover_letter = cover_letter
                application.save()
            action = "créée" if created else "existante"
            self.stdout.write(
                f"  Candidature {candidate.user.username} -> {offer.title} ({action})"
            )
