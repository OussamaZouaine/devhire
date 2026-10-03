# DevHire

Plateforme de recrutement Django (MVT) pour projet académique — candidats, recruteurs, entreprises, offres d'emploi,
matching intelligent, pipeline de recrutement, tests techniques, messagerie, statistiques et API REST.

## Stack

- **Python** 3.12+ / **Django** 5.2 LTS
- **PostgreSQL** (recherche plein texte en français)
- **Bootstrap 5** + django-crispy-forms, **HTMX** (notifications et messagerie en direct), **SortableJS** (Kanban),
  **Chart.js** (statistiques)
- **Django REST Framework** + JWT + **drf-spectacular** (Swagger)
- **Celery** + **Redis** (emails, analyse des CV, alertes emploi) — optionnels en développement
- **django-allauth** (connexion et inscription Google), **pypdf** (lecture des CV), **WhiteNoise**
- **Docker** / docker compose, **GitHub Actions** (CI)

## Fonctionnalités

### Candidats
- Inscription / connexion classique ou **avec Google** (compte créé en un clic), mot de passe oublié
- Profil complet : titre, compétences, CV PDF, **expériences, formations, langues**, taux de complétion
- **Analyse du CV** : le texte du PDF est extrait et les compétences détectées sont proposées
- **Score de compatibilité** avec chaque offre (détail : compétences communes / manquantes)
- **Recommandations** d'offres personnalisées
- Recherche avec filtres (mots-clés, ville, contrat, télétravail, expérience, salaire, compétence) et tri
- **Favoris** et **alertes emploi** (email quotidien des nouvelles offres)
- Suivi de candidature : étapes, historique, entretiens (**export .ics**), test technique, retrait
- **Messagerie** avec le recruteur et **notifications** en direct

### Recruteurs et entreprises
- Inscription classique ou **avec Google** (le nom de l'entreprise est demandé après Google)
- **Entreprise** partagée par plusieurs recruteurs : rôles administrateur / recruteur, **invitations par email**
- Page publique de l'entreprise, fiche entreprise avec logo
- Offres : compétences requises, télétravail, niveau, salaire, **date limite**
- **Pipeline Kanban** (glisser-déposer) : Reçue → Présélectionnée → Entretien → Test technique → Proposition → Embauché(e)
  / Refusée, candidats triés par compatibilité, **talents suggérés**
- Fiche candidature : score détaillé, **notes privées d'équipe**, historique, **planification d'entretiens**
- **QCM chronométré** par offre, corrigé automatiquement
- **Statistiques** : vues, taux de conversion, entonnoir, délai de réponse, performance par offre

### Plateforme
- Page publique **Tendances du marché** (offres par ville, compétences en pénurie, salaires)
- **API REST** documentée (Swagger), authentification JWT
- Interface **français / anglais**, charte graphique moderne (voir plus bas)

## Le matching (partie algorithmique)

Le module `matching/engine.py` (Python pur, sans bibliothèque de ML) combine deux mesures :

1. **Recouvrement de compétences** : `|compétences candidat ∩ compétences offre| / |compétences offre|`
2. **Similarité textuelle TF-IDF** entre le profil (titre, bio, compétences, expériences, texte du CV) et l'offre
   (titre, description, compétences) :
   - `tf(t, d) = occurrences(t, d) / longueur(d)`
   - `idf(t) = ln((1 + N) / (1 + df(t))) + 1` — l'IDF est appris sur toutes les offres ouvertes : un mot rare
     (« Kubernetes ») pèse plus qu'un mot courant (« développeur »)
   - `cos(a, b) = Σ aₜ·bₜ / (‖a‖·‖b‖)`

**Score final = 70 % compétences + 30 % similarité textuelle** (100 % texte si l'offre n'a pas de compétences).
Le texte est normalisé : minuscules, accents supprimés, mots vides français et anglais retirés, termes techniques
conservés (`c++`, `node.js`, `c#`).

## Structure des apps

```
devhire/
├── config/          # settings, urls racine, Celery
├── accounts/        # Utilisateurs, profils, entreprises, invitations, parcours candidat
├── matching/        # Compétences, algorithme de matching (TF-IDF), analyse des CV
├── jobs/            # Offres, recherche (plein texte), favoris, alertes, suivi des vues
├── applications/    # Candidatures, pipeline, historique, notes, entretiens
├── assessments/     # QCM chronométrés
├── messaging/       # Messagerie et notifications
├── analytics/       # Statistiques recruteur et tendances du marché
├── api/             # API REST (DRF + JWT + Swagger)
├── core/            # Accueil / recherche, espace candidat, données de démo, traductions
├── templates/       # Templates (rangés par app) + socialaccount/ (inscription Google)
├── locale/          # Traductions (en)
├── static/          # CSS (charte graphique) et logo
├── docs/            # Guides (connexion Google)
├── docker/          # Script de démarrage des conteneurs
└── media/           # CVs et logos uploadés
```

## Installation (sans Docker)

Prérequis : Python 3.12+ et PostgreSQL (installé localement, ou seulement la base via Docker).

```bash
python -m venv venv
source venv/Scripts/activate        # Windows (Git Bash) — Linux/macOS : source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                # puis définir SECRET_KEY et DATABASE_URL
createdb -U postgres devhire        # ou : docker compose up -d db (PostgreSQL sur le port 5433)
python manage.py migrate
python manage.py createsuperuser    # accès /admin/
python manage.py seed_demo_data     # données de démonstration (recommandé pour la soutenance)
python manage.py runserver
```

Ouvrez [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Sans configuration supplémentaire, les emails s'affichent dans
la console et les tâches Celery s'exécutent immédiatement (pas besoin de Redis).

**Comptes de démo** (mot de passe : `devhire123`) :

| Rôle | Identifiant |
|------|-------------|
| Recruteur administrateur | `recruiter1` (TechNova), `recruiter2` (GreenLabs) |
| Recruteur membre | `recruiter3` (TechNova) |
| Candidat | `candidate1` (Alice), `candidate2` (Bob), `candidate3` (Chloé), `candidate4` (David) |

`python manage.py seed_demo_data --clear` réinitialise les données de démo.

### Options

| Variable `.env` | Effet |
|---|---|
| `DATABASE_URL=postgres://user:pass@localhost:5432/devhire` | Base PostgreSQL (obligatoire) |
| `CELERY_BROKER_URL=redis://localhost:6379/0` | Tâches en arrière-plan (lancer `celery -A config worker` et `celery -A config beat`) |
| `EMAIL_BACKEND=...smtp.EmailBackend` + `EMAIL_*` | Envoi réel des emails |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Connexion et inscription avec Google — voir [docs/CONNEXION_GOOGLE.md](docs/CONNEXION_GOOGLE.md) |
| `HTTPS=True` | Cookies sécurisés, HSTS, redirection HTTPS (production) |

Les alertes emploi peuvent aussi être envoyées à la main : `python manage.py shell -c "from jobs.tasks import send_job_alerts; send_job_alerts()"`.

## Charte graphique

| Élément | Valeur |
|---|---|
| Couleur principale (indigo) | `#4f46e5` |
| Accent (violet) | `#7c3aed` — dégradé de marque `#4f46e5 → #7c3aed → #c026d3` |
| Texte / fond | ardoise `#0f172a` / `#f8fafc` |
| Police | [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans) |
| Icônes | [Bootstrap Icons](https://icons.getbootstrap.com/) |

Les couleurs sont définies une seule fois comme variables CSS dans `static/css/app.css`, qui surcharge aussi les
variables de Bootstrap : tous les composants suivent la charte. Le logo est `static/favicon.svg`.

## Docker

Pile complète en une commande : Django (gunicorn), PostgreSQL, Redis, worker Celery et Celery beat.
Prérequis : **Docker Desktop démarré** (`docker info` doit répondre).

```bash
cp .env.example .env                                   # si ce n'est pas déjà fait (SECRET_KEY, Google...)
docker compose up --build -d                           # construit l'image et démarre les 5 services
docker compose exec web python manage.py seed_demo_data
docker compose exec web python manage.py createsuperuser
```

Ouvrez [http://localhost:8000/](http://localhost:8000/). Les migrations sont appliquées automatiquement au démarrage
du conteneur `web`.

| Service | Rôle | Port |
|---|---|---|
| `web` | Django / gunicorn | `8000` |
| `db` | PostgreSQL 17 (utilisateur, mot de passe et base : `devhire`) | `5433` sur la machine hôte |
| `redis` | Broker Celery | — |
| `worker` | Tâches en arrière-plan (emails, analyse des CV) | — |
| `beat` | Planificateur (alertes emploi chaque jour à 8 h) | — |

```bash
docker compose up --build -d     # après une modification du code (le code est copié dans l'image)
docker compose logs -f web       # logs Django — `worker` affiche les emails envoyés
docker compose down              # arrêter (les données sont conservées)
docker compose down -v           # arrêter et supprimer les données (base + fichiers uploadés)
```

Les variables de `.env` (`SECRET_KEY`, `DEBUG`, `GOOGLE_*`...) sont transmises aux conteneurs. La base de données,
elle, est fixée dans `docker-compose.yml` : le `DATABASE_URL` local de `.env` est ignoré dans Docker.

## API REST

Documentation interactive : [/api/docs/](http://127.0.0.1:8000/api/docs/) (Swagger) ou `/api/redoc/`.

```bash
# Obtenir un jeton
curl -X POST http://127.0.0.1:8000/api/auth/token/ -d "username=candidate1&password=devhire123"
# Offres recommandées pour le candidat
curl -H "Authorization: Bearer <access>" http://127.0.0.1:8000/api/offres/recommended/
```

Principales routes : `offres/` (filtres `q`, `location`, `contract_type`, `remote_policy`, `salary_min`, `skill`, `sort`),
`offres/{id}/match/`, `offres/mine/`, `candidatures/` (postuler, `status`, `withdraw`), `notifications/`, `competences/`,
`entreprises/`, `moi/`.

## Connexion Google

Les boutons Google apparaissent automatiquement dès que `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` sont renseignés
dans `.env`.

| Page | Nouvel utilisateur |
|---|---|
| Connexion — « Continuer avec Google » | compte **candidat** créé automatiquement |
| Inscription candidat — « S'inscrire avec Google » | compte **candidat** créé automatiquement |
| Inscription recruteur — « S'inscrire avec Google » | page « Finaliser l'inscription » (nom de l'entreprise), puis compte **recruteur** administrateur |

Un compte existant avec le même email est relié et connecté. Création des identifiants dans la Google Cloud Console,
URI de redirection et dépannage : [docs/CONNEXION_GOOGLE.md](docs/CONNEXION_GOOGLE.md).

## Tests et qualité

```bash
python manage.py test                 # 128 tests
coverage run manage.py test && coverage report   # couverture ≥ 80 % exigée (actuellement 97 %)
ruff check . && ruff format --check .
```

La CI GitHub Actions (`.github/workflows/ci.yml`) lance le lint puis les tests sur **PostgreSQL**, vérifie les
migrations manquantes et les traductions. Les tests créent automatiquement une base `test_devhire`.

## Traductions

L'interface est en français avec une traduction anglaise (sélecteur FR / EN dans la barre de navigation). Les chaînes
des templates sont extraites et compilées sans GNU gettext :

```bash
python manage.py build_translations           # régénère locale/en/LC_MESSAGES/django.po et .mo
python manage.py build_translations --check   # échoue si une chaîne n'est pas traduite
```

Les traductions anglaises sont dans `locale/en/translations.json`. Les messages générés côté Python (notifications,
messages de confirmation) restent en français.

## URLs utiles

| URL | Description |
|-----|-------------|
| `/` | Recherche d'offres |
| `/compte/inscription/` | Inscription (classique ou Google, candidat ou recruteur) |
| `/mes-candidatures/` | Espace candidat |
| `/offres/mes-offres/` | Offres de l'entreprise (recruteur) |
| `/candidatures/offre/<id>/` | Pipeline Kanban d'une offre |
| `/statistiques/recruteur/` | Statistiques recruteur |
| `/statistiques/tendances/` | Tendances du marché |
| `/messagerie/` | Messagerie |
| `/api/docs/` | Documentation de l'API |
| `/admin/` | Administration Django |
