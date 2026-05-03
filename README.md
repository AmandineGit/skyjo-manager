# Skyjo Manager

Application web de gestion de parties de Skyjo avec suivi des scores, statistiques détaillées et système multi-utilisateurs.

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Flask](https://img.shields.io/badge/flask-3.0.0-lightgrey)

## Fonctionnalités

### Gestion de parties
- Création de parties pour **Skyjo** et **Skyjo Action**
- Suivi des scores par manche en temps réel
- Détection automatique de fin de partie (score ≥ 100)
- Option "Finisher" pour identifier qui termine chaque manche
- Règle de doublement automatique : si le finisher n'a pas le meilleur score, ses points sont doublés
- Édition des scores après validation
- Recherche de parties par date

### Groupes de joueurs
- Groupes créés et gérés par l'administrateur
- Chaque joueur voit automatiquement les groupes dans lesquels il apparaît
- Chargement automatique des membres lors de la sélection d'un groupe
- Ajout automatique des nouveaux joueurs au groupe lors d'une partie

### Comptes joueurs
- **Nom de joueur unique** : un seul identifiant sert à la fois de nom d'affichage et de nom dans les parties
- À l'inscription, si le nom saisi correspond à un joueur existant dans des groupes, l'application propose de **rattacher l'historique** des parties à ce nouveau compte
- Validation anti-doublon avec normalisation des accents (`Léo` ↔ `Leo`)
- Visibilité des groupes : un joueur voit tous les groupes où il a déjà joué, même avant la création de son compte

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
- Inscription avec détection automatique de joueurs existants
- Profil utilisateur avec modification du mot de passe
- Réinitialisation de mot de passe par email (lien affiché en mode dev)
- Traçage de la dernière connexion

### Panneau d'administration
- Accessible sur `/admin` pour `admin@skyjo.local`
- Liste de tous les utilisateurs avec dernière connexion
- Réinitialisation du mot de passe de n'importe quel utilisateur
- Correction du nom de joueur
- Gestion complète des groupes (création, renommage, membres)

### Interface responsive
- Design Metro UI inspiré de Windows Phone
- Tuiles colorées avec dégradés
- Optimisé mobile et desktop

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

> **Note** : en mode dev, les routes ne sont pas préfixées par `/skyjo/`.

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

## Fusion des joueurs

Si des joueurs existent sous des noms légèrement différents (`Leo` / `Léo`), utilisez le script de normalisation :

```bash
# Simulation
python3 normalize_players.py --dry-run

# Appliquer (crée une sauvegarde automatique)
python3 normalize_players.py
```

Le script :
1. Trouve les noms similaires dans `group_members` et `players` (insensible aux accents et à la casse)
2. Renomme vers la forme canonique (majuscule + accents) dans toutes les tables
3. Déduplique les entrées dans `group_members`
4. Propage les `user_id` et ajoute les utilisateurs dans `group_users` pour leurs groupes historiques

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
├── normalize_players.py        # Script de fusion des joueurs similaires
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
│   ├── admin.html              # Panneau d'administration
│   ├── groups.html             # Liste des groupes
│   ├── group_detail.html       # Détail d'un groupe
│   ├── group_new.html          # Création de groupe (admin)
│   ├── new_game.html           # Création de partie
│   ├── game.html               # Vue d'une partie
│   ├── stats_menu.html         # Menu des statistiques
│   ├── stats_detail.html       # Statistiques par type
│   └── player_stats.html       # Statistiques d'un joueur
└── images/
    ├── 88-skyjo-regle.pdf          # Règles Skyjo
    └── skyjo_action_regles_fr.pdf  # Règles Skyjo Action
```

## Utilisation

### Première connexion

1. Créez un compte via "S'inscrire" en choisissant votre nom de joueur
2. Si votre nom correspond à un joueur existant dans des groupes, rattachez votre historique
3. Vos groupes et parties apparaissent automatiquement

### Créer une partie (admin)

1. Connectez-vous avec `admin@skyjo.local`
2. Cliquez sur "Nouvelle partie"
3. Choisissez le type de jeu (Skyjo / Skyjo Action)
4. Sélectionnez un groupe existant
5. Ajoutez les joueurs (jusqu'à 10) et créez la partie

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

### Schéma v2.1

```sql
-- Utilisateurs
users (
    id, email, password_hash, player_name,
    created_at, last_login, reset_token, reset_token_expires
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

-- Règles PDF par type de jeu
game_rules (
    id, game_type, rules_pdf
)
```

## API

| Route | Description |
|-------|-------------|
| `GET /api/players/search?q=` | Recherche de joueurs pour autocomplétion |
| `GET /api/players/check-duplicate?name=` | Vérifie si un nom similaire existe |
| `GET /api/groups/<id>/members` | Liste des membres d'un groupe |
| `GET /api/groups/suggest?players=` | Suggestion de groupes selon les joueurs |

## Sécurité

- Mots de passe hashés avec Werkzeug (PBKDF2)
- Sessions Flask sécurisées
- Filtrage des données par utilisateur/groupe
- Tokens de réinitialisation avec expiration (1h)
- Gestion des groupes réservée à l'administrateur
- Validation anti-doublon des noms (normalisée accents/casse)

## Déploiement

### Mise à jour

```bash
cd /var/www/skyjo
git pull
sudo systemctl restart gunicorn-skyjo
```

### Logs

```bash
sudo journalctl -u gunicorn-skyjo -f
```

## Changelog

### v2.1.0 (2026-05-03)
- **Nom de joueur unifié** : suppression de `display_name`, `player_name` sert à la fois d'identifiant et de nom dans les parties
- **Rattachement de l'historique** : à l'inscription, proposition de lier un compte à des parties existantes (insensible aux accents)
- **Visibilité des groupes** : un joueur voit tous les groupes où il apparaît dans `group_members`, même sans être dans `group_users`
- **Gestion des groupes admin-only** : création et modification réservées à `admin@skyjo.local`
- **Panneau admin** : réinitialisation de mot de passe et correction des noms pour tous les utilisateurs
- **`normalize_players.py`** : script de fusion des noms similaires avec propagation des comptes
- Ajout du champ `last_login` sur les utilisateurs
- Correction de l'URL des règles Skyjo Action en production

### v2.0.0 (2026-01-13)
- **Breaking** : remplacement des codes d'accès par des comptes utilisateurs
- Ajout des groupes de joueurs
- Statistiques filtrées par groupe/utilisateur
- Option finisher avec doublement automatique
- Statistiques individuelles par joueur
- Script de migration pour les données existantes

### v1.0.0
- Version initiale avec codes d'accès 1666/1664

---

Développé avec Flask et SQLite
