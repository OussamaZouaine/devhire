# Intégrer la connexion Google à DevHire

Ce guide explique, étape par étape, comment activer le bouton **« Continuer avec Google »** sur la page de connexion.
Le code est déjà en place (via `django-allauth`). Il reste seulement à créer des identifiants dans la Google Cloud
Console puis à les ajouter au fichier `.env`.

> Durée estimée : 10 à 15 minutes. Il faut un compte Google.

---

## Comment ça marche dans le projet

| Élément | Où | Rôle |
|---|---|---|
| `django-allauth[socialaccount]` | `requirements.txt` | Gère le protocole OAuth 2.0 avec Google |
| `allauth.socialaccount.providers.google` | `INSTALLED_APPS` dans `config/settings.py` | Active le fournisseur Google |
| `SOCIALACCOUNT_PROVIDERS["google"]` | `config/settings.py` | Lit `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` depuis `.env` |
| `path("auth/", include("allauth.urls"))` | `config/urls.py` | Expose les URL de connexion et de retour (callback) |
| `SocialAccountAdapter` | `accounts/adapters.py` | Un utilisateur qui s'inscrit avec Google devient **candidat** |
| Bouton Google | `templates/accounts/login.html` | Affiché **uniquement** si `GOOGLE_CLIENT_ID` est renseigné |

Le parcours de l'utilisateur :

```
Clic « Continuer avec Google »
   → /auth/google/login/                (DevHire redirige vers Google)
   → écran de consentement Google       (l'utilisateur choisit son compte)
   → /auth/google/login/callback/       (Google renvoie vers DevHire avec un code)
   → compte créé ou retrouvé par email  → utilisateur connecté
```

Si un compte DevHire existe déjà avec la même adresse email, il est relié automatiquement
(`SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True`). Sinon, un nouveau compte **candidat** est créé.
Les recruteurs continuent de s'inscrire avec le formulaire classique, car il faut créer leur entreprise.

---

## Étape 1 — Créer un projet Google Cloud

1. Ouvrez la console : <https://console.cloud.google.com/>.
2. En haut de la page, cliquez sur le **sélecteur de projet**, puis sur **Nouveau projet**.
3. Nom du projet : `DevHire` (ou un autre nom). Laissez « Aucune organisation » si vous n'en avez pas.
4. Cliquez sur **Créer**, attendez quelques secondes, puis **sélectionnez** ce projet dans le sélecteur.

## Étape 2 — Configurer l'écran de consentement OAuth

C'est la page que Google montre à l'utilisateur (« DevHire souhaite accéder à votre compte Google »).

1. Menu ☰ → **API et services** → **Écran de consentement OAuth**. Dans les versions récentes de la console, ce menu
   s'appelle **Google Auth Platform** → **Branding**.
2. Cliquez sur **Commencer** (ou **Configurer**).
3. **Informations sur l'application** :
   - Nom de l'application : `DevHire`
   - Adresse email d'assistance : votre adresse
4. **Audience** : choisissez **Externe**, pour que n'importe quel compte Google puisse se connecter.
5. **Coordonnées** : votre adresse email.
6. Acceptez les conditions, puis cliquez sur **Créer**.
7. **Accès aux données (Scopes)** : ajoutez `openid`, `.../auth/userinfo.email` et `.../auth/userinfo.profile`.
   Ce sont les scopes non sensibles que demande le projet (`"SCOPE": ["profile", "email"]`).
8. **Utilisateurs de test** : tant que l'application est en mode **Test**, seuls les comptes listés ici peuvent se
   connecter. Ajoutez votre adresse Gmail et celles des membres du jury ou de l'équipe.

> Pour une démo ou une soutenance, le mode **Test** suffit (jusqu'à 100 utilisateurs de test). Pour ouvrir à tout le
> monde, cliquez sur **Publier l'application**. Avec les seuls scopes email et profil, aucune vérification par Google
> n'est nécessaire.

## Étape 3 — Créer les identifiants OAuth (Client ID et Secret)

1. Menu ☰ → **API et services** → **Identifiants**. Dans la nouvelle console : **Google Auth Platform** → **Clients**.
2. **+ Créer des identifiants** → **ID client OAuth**.
3. Type d'application : **Application Web**.
4. Nom : `DevHire Web`.
5. **Origines JavaScript autorisées** : ajoutez l'adresse de chaque environnement utilisé.

   | Environnement | Origine |
   |---|---|
   | `runserver` local | `http://127.0.0.1:8000` et `http://localhost:8000` |
   | Docker | `http://localhost:8000` |
   | Production | `https://votre-domaine.com` |

6. **URI de redirection autorisés**, la partie importante :

   ```
   http://127.0.0.1:8000/auth/google/login/callback/
   http://localhost:8000/auth/google/login/callback/
   https://votre-domaine.com/auth/google/login/callback/
   ```

   ⚠️ L'URI doit correspondre **exactement** : même protocole (`http` ou `https`), même hôte (`127.0.0.1` n'est pas
   `localhost`), même port, et **la barre oblique finale**.

7. Cliquez sur **Créer**. Une fenêtre affiche l'**ID client** et le **Code secret du client**. Copiez-les, ou
   téléchargez le JSON.

> Le secret est confidentiel : ne le committez jamais. Il va uniquement dans `.env`, qui est ignoré par Git.

## Étape 4 — Ajouter les identifiants au projet

Dans le fichier `.env` à la racine du projet :

```env
GOOGLE_CLIENT_ID=1234567890-abcdefg.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxx
SITE_URL=http://127.0.0.1:8000
```

Redémarrez le serveur (`python manage.py runserver`, ou `docker compose up -d --build` avec Docker).
Aucune migration ni configuration dans l'admin Django n'est nécessaire : les identifiants sont lus directement depuis
les settings.

## Étape 5 — Tester

1. Ouvrez <http://127.0.0.1:8000/compte/connexion/>.
2. Le bouton **« Continuer avec Google »** apparaît au-dessus du formulaire.
3. Cliquez dessus, choisissez un compte Google (un **utilisateur de test** si l'application est en mode Test).
4. Vous revenez sur DevHire, connecté en tant que **candidat**.
5. Vérifiez dans l'admin (`/admin/` → *Comptes sociaux*) que le compte Google est bien rattaché à l'utilisateur.

---

## Dépannage

| Erreur | Cause | Solution |
|---|---|---|
| `Error 400: redirect_uri_mismatch` | L'URI de callback n'est pas déclarée **à l'identique** | Copier l'URI affichée dans le détail de l'erreur et l'ajouter dans **URI de redirection autorisés** (attention à `localhost` / `127.0.0.1` et au `/` final). La prise en compte peut prendre quelques minutes. |
| `Error 403: access_denied` | Application en mode Test et compte non autorisé | Ajouter l'adresse dans **Utilisateurs de test**, ou publier l'application |
| Le bouton Google n'apparaît pas | `GOOGLE_CLIENT_ID` vide ou serveur non redémarré | Vérifier `.env` puis relancer le serveur |
| `invalid_client` | ID ou secret mal copié (espace, guillemets) | Recopier les valeurs sans guillemets dans `.env` |
| Redirection vers `http` au lieu de `https` en production | Django ne sait pas qu'il est derrière un proxy HTTPS | Mettre `HTTPS=True` dans `.env` (active `SECURE_PROXY_SSL_HEADER`) et transmettre l'en-tête `X-Forwarded-Proto` depuis le proxy |
| Page « Sign in via Google » intermédiaire | Comportement par défaut d'allauth | Déjà désactivé par `SOCIALACCOUNT_LOGIN_ON_GET = True` |

## Aller plus loin

- **Rôle recruteur via Google** : modifiez `accounts/adapters.py` (`populate_user`) pour proposer un choix de rôle
  après la première connexion, par exemple avec une redirection vers une page « Je suis candidat / recruteur ».
- **Récupérer la photo de profil** : `sociallogin.account.extra_data["picture"]` contient l'URL de l'avatar Google.
- **Autres fournisseurs** (GitHub, LinkedIn) : ajoutez `allauth.socialaccount.providers.github` ou `.openid_connect`
  dans `INSTALLED_APPS` et une entrée dans `SOCIALACCOUNT_PROVIDERS` sur le même modèle.
