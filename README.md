# Family Board Game

Application web de suivi de scores et de statistiques pour jeux de société.
Initialement dédiée à **Skyjo**, elle évolue vers une plateforme multi-jeux où Skyjo n'est qu'un jeu parmi d'autres.

![Python](https://img.shields.io/badge/python-3.10+-green)
![Flask](https://img.shields.io/badge/flask-3.0.0-lightgrey)

En production sur `digital-pragma.fr` (Gunicorn + Apache en reverse proxy).

## Fonctionnalités

### Plateforme commune (`/familyboardgame/`)
- **Hub d'accueil** listant les jeux disponibles
- **Comptes joueurs** (email / mot de passe) : un nom de joueur unique sert d'identifiant et de nom dans les parties
- **Rattachement de l'historique** à l'inscription si le nom correspond à un joueur existant (insensible aux accents et à la casse : `Léo` ↔ `Leo`)
- **Groupes de joueurs** partagés entre les jeux ; un joueur voit tous les groupes où il apparaît
- **Statistiques** filtrées par groupe : podium, moyennes, médianes, meilleur/pire score, stats individuelles, co-joueurs fréquents
- **Administration** (`admin@skyjo.local`) : utilisateurs, réinitialisation de mot de passe, correction des noms, gestion des groupes
- Interface Metro UI responsive (mobile + desktop)

### Skyjo (`/skyjo/`)
- Parties **Skyjo** et **Skyjo Action**
- Saisie des scores manche par manche, édition après coup
- Option **Finisher** : si le joueur qui termine la manche n'a pas le meilleur score, ses points sont doublés
- Fin de partie automatique à 100 points
- Règles du jeu en PDF intégrées
- Permissions : partie en cours modifiable par tout utilisateur connecté, partie terminée par l'admin uniquement

## Architecture

```
skyjo-manager/
├── app.py                  # Application Flask : hub, auth, groupes, stats, admin
├── core/
│   ├── db.py               # Connexion SQLite, création du schéma, migrations légères
│   └── auth.py             # require_auth, get_current_user, is_admin, get_user_group_ids
├── games/
│   └── skyjo/
│       └── routes.py       # Blueprint Skyjo (préfixe interne /play)
├── templates/              # Templates Jinja (communs + Skyjo)
├── static/style.css        # Styles Metro UI
├── images/                 # Logos et règles PDF
├── scripts/                # Scripts de maintenance (voir plus bas)
├── tests/                  # Tests pytest
├── export_to_onedrive.py   # Export (stub pour l'instant)
├── deploy.sh               # Déploiement en production
└── skyjo.db                # Base SQLite (non versionnée)
```

### Routage des URLs

Apache expose deux préfixes publics qui pointent vers la même instance Gunicorn :

| URL publique          | Côté Gunicorn | Contenu                                             |
|-----------------------|---------------|-----------------------------------------------------|
| `/familyboardgame/…`  | `/…`          | Hub, connexion, profil, groupes, stats, admin       |
| `/skyjo/…`            | `/play/…`     | Blueprint Skyjo : liste des parties, nouvelle partie, saisie des scores |

Les liens dans le code et les templates utilisent donc les URLs publiques en dur (`/familyboardgame/…`, `/skyjo/…`).
Lancée directement sans Apache, l'application répond sur `/` et `/play/`.

### Ajouter un jeu

Chaque jeu est un blueprint dans `games/<jeu>/`, enregistré dans `app.py`, et doit apparaître dans `games_list` (route `hub` de `app.py`).
⚠️ Le schéma de données est encore propre à Skyjo (tables `skyjo_*`). Un schéma générique est à concevoir avant d'intégrer un deuxième jeu.

## Base de données

SQLite (`skyjo.db`). Le schéma est créé ou complété au démarrage par `core/db.py` (`init_db`, puis `_apply_migrations` pour les colonnes ajoutées après coup).

```sql
-- Commun à tous les jeux
users          (id, email, password_hash, display_name*, player_name,
                created_at, reset_token, reset_token_expires, last_login)
player_groups  (id, name, created_by, created_at, rename_permission)
group_members  (id, group_id, player_name, user_id)   -- joueurs d'un groupe
group_users    (id, group_id, user_id, role)          -- comptes ayant accès au groupe
game_rules     (id, game_type, rules_pdf)             -- PDF de règles par type de jeu

-- Skyjo
skyjo_games    (id, created_at, type, comments, finished, group_id, created_by)
skyjo_players  (id, game_id, name)
skyjo_rounds   (id, game_id, round_number, player_name, score, created_at, is_finisher)
```

\* `display_name` est obsolète (fusionné dans `player_name`), conservé pour ne pas toucher aux données existantes.

## Développement local

Environnement : WSL2 Ubuntu.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

gunicorn --bind 127.0.0.1:5000 app:app
```

Accès via Apache local (config `/etc/apache2/sites-available/skyjo-local.conf`, mêmes règles qu'en prod mais vers le port 5000) :
- http://localhost/familyboardgame/
- http://localhost/skyjo/

Variables d'environnement (voir `.env.example`) :

| Variable       | Rôle                                                        |
|----------------|-------------------------------------------------------------|
| `FLASK_SECRET` | Clé de session, **obligatoire en production**               |
| `FLASK_ENV`    | `development` par défaut (affiche les liens de reset)       |
| `RESET_DB`     | `1` pour recréer la base au démarrage, **efface les données** |

Tests :

```bash
pip install pytest
python -m pytest
```

## Scripts de maintenance

| Script                          | Usage |
|---------------------------------|-------|
| `scripts/add_game_rules.py`     | `python3 scripts/add_game_rules.py "Nom du jeu" fichier.pdf` (PDF placé dans `images/`), ou `--list` |
| `scripts/normalize_players.py`  | Fusionne les joueurs aux noms quasi identiques. `--dry-run` pour simuler ; crée une sauvegarde avant d'écrire. Option `--db-path` |

Les anciens scripts de migration (v1 → v2, passage aux tables `skyjo_*`) ont déjà été appliqués en production ; ils restent consultables dans l'historique git.

## API (blueprint Skyjo)

| Route                                       | Description                                 |
|---------------------------------------------|---------------------------------------------|
| `GET /skyjo/api/players/search?q=`          | Autocomplétion des joueurs                  |
| `GET /skyjo/api/players/check-duplicate?name=` | Détection d'un nom similaire existant    |
| `GET /skyjo/api/groups/<id>/members`        | Membres d'un groupe                         |
| `GET /skyjo/api/groups/suggest?players=`    | Groupes suggérés selon les joueurs          |

## Production et déploiement

Installation complète du serveur : voir [INSTALL.md](INSTALL.md).

Mise à jour : sur le serveur, `./deploy.sh` (sauvegarde de la base, `git pull`, dépendances, redémarrage de `gunicorn-skyjo`).

```bash
sudo journalctl -u gunicorn-skyjo -f   # logs
```

## Historique

Voir [CHANGELOG.md](CHANGELOG.md).
