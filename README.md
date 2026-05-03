# Skyjo Manager

Application web de gestion de parties de Skyjo avec suivi des scores, statistiques détaillées et système multi-utilisateurs.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Flask](https://img.shields.io/badge/flask-3.0.0-lightgrey)

## Fonctionnalités

### Gestion de parties
- Création de parties pour **Skyjo** et **Skyjo Action**
- Suivi des scores par manche en temps réel
- Détection automatique de fin de partie (score >= 100)
- Option "Finisher" pour identifier qui termine chaque manche
- Règle de doublement automatique : si le finisher n'a pas le meilleur score, ses points sont doublés
- Édition des scores après validation
- Recherche de parties par date

### Groupes de joueurs
- Création de groupes de joueurs (famille, amis, collègues...)
- Partage de groupes entre utilisateurs
- Chargement automatique des membres lors de la sélection d'un groupe
- Ajout automatique des nouveaux joueurs au groupe

### Statistiques avancées
- Statistiques par type de jeu (Skyjo / Skyjo Action)
- **Filtrage par groupe** : chaque utilisateur ne voit que les stats de ses groupes
- **Admin** (`admin@skyjo.local`) : accès à toutes les statistiques
- Podium des meilleurs joueurs (moyenne la plus basse)
- Scores moyens, médians, meilleur et pire par joueur
- "Boss des coups de bol" : meilleur score unique
- "Looser du pire" : pire score unique
- "Le précoce" : joueur qui double le plus souvent (finisher sans meilleur score)
- Statistiques individuelles par joueur :
  - Moyenne et médiane
  - Top et Flop (meilleur/pire round)
  - Pourcentage de finisher
  - Co-joueurs fréquents
  - Date de première partie

### Système d'authentification
- **Comptes utilisateurs** avec email/mot de passe
- Inscription et connexion
- Profil utilisateur avec modification du mot de passe
- Réinitialisation de mot de passe par email (lien affiché en mode dev)
- Chaque utilisateur ne voit que les parties de ses groupes

### Interface responsive
- Design Metro UI inspiré de Windows Phone
- Tuiles colorées avec dégradés
- Optimisé mobile et desktop
- Boutons d'action avec dégradés colorés

### Export de données
- Export vers Excel (.xlsx)
- Export automatique vers OneDrive (optionnel)

## Installation

### Prérequis

- Python 3.10 ou supérieur
- Apache 2.4+ avec mod_proxy (pour la production)
- Git

### Installation locale (développement)

```bash
# Cloner le dépôt
git clone https://github.com/AmandineGit/skyjo-manager.git
cd skyjo-manager

# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python app.py
```

L'application sera accessible sur `http://localhost:5000`

### Installation en production

Voir [INSTALL.md](INSTALL.md) pour les instructions détaillées.

## Migration depuis la v1

Si vous avez une base de données existante (v1 avec codes 1666/1664), utilisez le script de migration :

```bash
# Tester en mode dry-run
python3 migrate_production.py --dry-run

# Exécuter la migration
python3 migrate_production.py
```

Le script :
1. Crée les nouvelles tables (users, player_groups, group_members, group_users)
2. Crée un compte admin (`admin@skyjo.local` / `changeme123`)
3. Analyse les parties existantes et crée des groupes basés sur les combinaisons de joueurs
4. Associe chaque partie historique à son groupe

**Changez le mot de passe admin immédiatement après la migration !**

## Configuration

### Variables d'environnement

```bash
# Clé secrète Flask (obligatoire en production)
FLASK_SECRET=votre_cle_secrete_aleatoire

# Mode développement (affiche les liens de reset password)
FLASK_ENV=development

# Chemin OneDrive pour l'export (optionnel)
ONEDRIVE_PATH=/path/to/onedrive/folder
```

### Structure des fichiers

```
skyjo-manager/
├── app.py                      # Application Flask principale
├── migrate_production.py       # Script de migration v1 -> v2
├── export_to_onedrive.py       # Module d'export Excel
├── requirements.txt            # Dépendances Python
├── skyjo.db                    # Base de données SQLite
├── static/
│   └── style.css               # Styles CSS
├── templates/
│   ├── index.html              # Page d'accueil
│   ├── login.html              # Connexion
│   ├── register.html           # Inscription
│   ├── profile.html            # Profil utilisateur
│   ├── forgot_password.html    # Mot de passe oublié
│   ├── reset_password.html     # Réinitialisation mot de passe
│   ├── groups.html             # Liste des groupes
│   ├── group_detail.html       # Détail d'un groupe
│   ├── group_new.html          # Création de groupe
│   ├── new_game.html           # Création de partie
│   ├── game.html               # Vue d'une partie
│   ├── stats_menu.html         # Menu des statistiques
│   ├── stats_detail.html       # Statistiques par type
│   └── player_stats.html       # Statistiques d'un joueur
├── images/
│   └── 88-skyjo-regle.pdf      # Règles du jeu
└── README.md
```

## Utilisation

### Première connexion

1. Créez un compte via "S'inscrire"
2. Créez votre premier groupe lors de la création d'une partie
3. Les joueurs sont automatiquement ajoutés au groupe

### Créer une partie

1. Cliquez sur "Nouvelle partie"
2. Choisissez le type de jeu (Skyjo / Skyjo Action)
3. Sélectionnez un groupe existant ou créez-en un nouveau
4. Ajoutez les joueurs (jusqu'à 10)
5. Créez la partie

### Enregistrer des scores

1. Ouvrez une partie en cours
2. Entrez les scores de chaque joueur
3. Cochez "Finisher" pour le joueur qui a terminé la manche
4. Si le finisher n'a pas le meilleur score, ses points sont automatiquement doublés
5. La partie se termine quand un joueur atteint 100 points

### Consulter les statistiques

1. Cliquez sur "Statistiques"
2. Filtrez par groupe si nécessaire
3. Choisissez le type de jeu
4. Cliquez sur un joueur pour voir ses stats détaillées

## Base de données

### Schéma v2

```sql
-- Utilisateurs
users (
    id, email, password_hash, display_name, player_name,
    created_at, reset_token, reset_token_expires
)

-- Groupes de joueurs
player_groups (
    id, name, created_by, created_at
)

-- Membres d'un groupe
group_members (
    id, group_id, player_name, user_id
)

-- Utilisateurs ayant accès à un groupe
group_users (
    id, group_id, user_id, role
)

-- Parties (liées à un groupe)
games (
    id, created_at, type, comments, finished,
    group_id, created_by
)

-- Joueurs d'une partie
players (
    id, game_id, name
)

-- Rounds avec option finisher
rounds (
    id, game_id, round_number, player_name,
    score, created_at, is_finisher
)
```

## API

### Endpoints disponibles

| Route | Description |
|-------|-------------|
| `GET /api/players/search?q=` | Recherche de joueurs pour autocomplétion |
| `GET /api/groups/<id>/members` | Liste des membres d'un groupe |
| `GET /api/groups/suggest?players=` | Suggestion de groupes |

## Sécurité

- Mots de passe hashés avec Werkzeug (PBKDF2)
- Sessions Flask sécurisées
- Filtrage des données par utilisateur/groupe
- Tokens de réinitialisation avec expiration (1h)
- Protection contre l'accès aux groupes non autorisés

## Déploiement

### Mise à jour

```bash
cd /var/www/skyjo
git pull origin main
sudo systemctl restart gunicorn-skyjo
```

### Logs

```bash
# Logs du service
sudo journalctl -u gunicorn-skyjo -f

# Logs d'erreur
sudo tail -f /var/log/gunicorn/skyjo_error.log
```

## Changelog

### v2.0.0 (2026-05-03)
- **Breaking** : Remplacement des codes d'accès par des comptes utilisateurs
- Ajout des groupes de joueurs
- Statistiques filtrées par groupe/utilisateur
- Option finisher avec doublement automatique
- Statistiques individuelles par joueur
- Script de migration pour les données existantes

### v1.0.0
- Version initiale avec codes d'accès 1666/1664

---

Développé avec Flask et SQLite
