# DevHire

Plateforme de recrutement Django (MVT) pour projet académique — candidats, recruteurs, offres d'emploi et candidatures.

## Stack

- **Python** 3.12+
- **Django** 5.2 LTS
- **SQLite** (développement)
- **Bootstrap 5** + django-crispy-forms
- **WhiteNoise** (fichiers statiques)
- **Pillow** (logos entreprise)

## Structure des apps

```
devhire/
├── config/          # settings, urls racine
├── accounts/        # User custom, profils Candidat/Recruteur, auth
├── jobs/            # Offres d'emploi (CRUD recruteur)
├── applications/    # Candidatures et gestion des statuts
├── core/            # Recherche d'offres (accueil), dashboard candidat
├── templates/       # Templates globaux
├── static/          # Fichiers statiques
└── media/           # CVs et logos uploadés
```

## Installation

### 1. Cloner et entrer dans le projet

```bash
cd devhire
```

### 2. Environnement virtuel

```bash
python -m venv venv

# Windows (Git Bash / PowerShell)
source venv/Scripts/activate

# Linux / macOS
source venv/bin/activate
```

### 3. Dépendances

```bash
pip install -r requirements.txt
```

### 4. Variables d'environnement

```bash
cp .env.example .env
```

Éditez `.env` et définissez au minimum `SECRET_KEY` et `DEBUG`.

### 5. Base de données

```bash
python manage.py migrate
```

### 6. Superuser (accès admin)

```bash
python manage.py createsuperuser
```

### 7. Données de démonstration (recommandé pour la soutenance)

```bash
python manage.py seed_demo_data
```

Pour réinitialiser les données de démo :

```bash
python manage.py seed_demo_data --clear
```

**Comptes de démo** (mot de passe : `devhire123`) :

| Rôle | Identifiant |
|------|-------------|
| Recruteur | `recruiter1`, `recruiter2` |
| Candidat | `candidate1`, `candidate2`, `candidate3` |

### 8. Lancer le serveur

```bash
python manage.py runserver
```

Ouvrez [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

## Fichiers statiques (production)

```bash
python manage.py collectstatic --noinput
```

WhiteNoise sert les fichiers depuis `staticfiles/` en production.

## Tests

```bash
python manage.py test core.tests
```

## Fonctionnalités principales

- Inscription / connexion séparée **Candidat** / **Recruteur**
- Recruteur : publier, modifier, activer/désactiver des offres
- Candidat : profil + CV PDF, postuler, suivre ses candidatures
- Recherche d'offres par mots-clés, localisation et type de contrat
- Recruteur : consulter les candidatures, accepter / refuser
- Téléchargement sécurisé des CV (pas d'accès direct à `/media/cvs/`)

## URLs utiles

| URL | Description |
|-----|-------------|
| `/` | Recherche d'offres |
| `/compte/connexion/` | Connexion |
| `/compte/inscription/` | Inscription |
| `/offres/mes-offres/` | Dashboard recruteur |
| `/mes-candidatures/` | Dashboard candidat |
| `/admin/` | Administration Django |

## Déploiement (rappel)

En production, configurez dans `.env` :

```env
DEBUG=False
SECRET_KEY=<clé-générée-aléatoirement>
ALLOWED_HOSTS=votredomaine.com,www.votredomaine.com
```

Puis `collectstatic` et servez l'application via Gunicorn/uWSGI + reverse proxy.
