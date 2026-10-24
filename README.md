# Family Board Game

Application web de suivi de scores et de statistiques pour jeux de société.
Initialement dédiée à **Skyjo**, elle est devenue multi-jeux : **Skyjo** et **Flip 7**.

![Python](https://img.shields.io/badge/python-3.10+-green)
![Flask](https://img.shields.io/badge/flask-3.0.0-lightgrey)

En production sur `digital-pragma.fr` (Gunicorn + Apache en reverse proxy).

## Fonctionnalités

### Plateforme commune (`/familyboardgame/`)
- **Hub d'accueil** listant les jeux disponibles, chacun avec son image
- **Comptes joueurs** (email / mot de passe) : un nom de joueur unique sert d'identifiant et de nom dans les parties
- **Rattachement de l'historique** à l'inscription si le nom correspond à un joueur existant (insensible aux accents et à la casse : `Léo` ↔ `Leo`)
- **Groupes de joueurs** partagés entre les jeux ; un joueur voit tous les groupes où il apparaît.
  Chaque groupe affiche son nombre de parties par jeu, ses dernières parties tous jeux confondus,
  et permet de lancer une partie de n'importe quel jeu
- **Statistiques** filtrées par groupe, avec un menu illustré par jeu : dalles (podium, palmarès…),
  tableau détaillé et page individuelle par joueur (dont co-joueurs fréquents)
- **Administration** (`admin@skyjo.local`) : utilisateurs, réinitialisation de mot de passe, correction des noms, gestion des groupes
- Interface Metro UI responsive (mobile + desktop)

### Skyjo (`/skyjo/`)
- Parties **Skyjo** et **Skyjo Action**
- Saisie des scores manche par manche, édition après coup
- Option **Finisher** : si le joueur qui termine la manche n'a pas le meilleur score, ses points sont doublés
- Fin de partie automatique à 100 points
- Règles du jeu en PDF intégrées
- Permissions : partie en cours modifiable par tout utilisateur connecté, partie terminée par l'admin uniquement

### Flip 7 (`/familyboardgame/flip7/`)
- Saisie par joueur et par manche : chiffres, bonus, cases **×2**, **🎯 Flip 7**, **✋ Stop**, **💥 Doublon** ; total calculé automatiquement
  (`chiffres × 2 si ×2 + bonus + 15 si Flip 7`, 0 si doublon)
- Fin de partie à 200 points, le plus haut total gagne ; en cas d'égalité en tête, manche de départage entre les ex aequo
- Modification d'une manche, mêmes permissions que Skyjo
- Règles affichées en images (`images/ReglesFlip7-*.png`)
- Statistiques en dalles, sur le modèle de Skyjo : podium des victoires, palmarès (Kamikaze, Manche de rêve,
  Roi du Flip 7, Banquier, Prudent, Multiplicateur), parties et joueurs actifs ; les palmarès en pourcentage
  ne retiennent que les joueurs ayant au moins 5 manches
- Page de stats par joueur : moyenne et médiane, victoires, meilleure manche, taux de stops et de doublons,
  Flip 7, ×2, ancienneté, co-joueurs fréquents

## Architecture

```
skyjo-manager/
├── app.py                  # Application Flask : hub, auth, groupes, stats, admin
├── core/
│   ├── db.py               # Connexion SQLite, création du schéma, migrations légères
│   ├── auth.py             # require_auth, get_current_user, is_admin, get_user_group_ids
│   └── groups.py           # Joueurs + groupe à la création d'une partie (tous jeux)
├── games/
│   ├── skyjo/
│   │   └── routes.py       # Blueprint Skyjo (préfixe interne /play)
│   └── flip7/
│       ├── routes.py       # Blueprint Flip 7 (préfixe interne /flip7)
│       ├── scoring.py      # Règles de score, sans Flask
│       └── stats.py        # Calcul des statistiques, sans Flask
├── templates/              # Templates Jinja (communs + Skyjo), templates/flip7/ pour Flip 7
├── static/style.css        # Styles Metro UI
├── images/                 # Logos et règles PDF
├── scripts/                # Scripts de maintenance (voir plus bas)
├── tests/                  # Tests pytest
├── export_to_onedrive.py   # Export (stub pour l'instant)
├── .github/workflows/      # Déploiement automatique (GitHub Actions)
└── skyjo.db                # Base SQLite (non versionnée)
```

### Routage des URLs

Apache expose deux préfixes publics qui pointent vers la même instance Gunicorn :

| URL publique          | Côté Gunicorn | Contenu                                             |
|-----------------------|---------------|-----------------------------------------------------|
| `/familyboardgame/…`  | `/…`          | Hub, connexion, profil, groupes, stats, admin       |
| `/familyboardgame/flip7/…` | `/flip7/…` | Blueprint Flip 7 (sous le préfixe commun, aucune règle Apache dédiée) |
| `/skyjo/…`            | `/play/…`     | Blueprint Skyjo : liste des parties, nouvelle partie, saisie des scores |

Les liens dans le code et les templates utilisent donc les URLs publiques en dur (`/familyboardgame/…`, `/skyjo/…`).
Lancée directement sans Apache, l'application répond sur `/` et `/play/`.

### Ajouter un jeu

Sur le modèle de Flip 7 :
1. un blueprint dans `games/<jeu>/` (préfixe interne `/<jeu>`, donc servi sous `/familyboardgame/<jeu>/`), enregistré dans `app.py` ;
2. une entrée dans `games_list` (route `hub` de `app.py`) et dans le menu des statistiques ;
3. les données dans les tables génériques `game_sessions` / `session_players` / `session_scores`, avec `game_slug` propre au jeu
   et le détail spécifique d'une manche en JSON dans `session_scores.details` : pas de nouvelle table ;
4. le formulaire `templates/new_game.html` est réutilisable (paramètres `single_type`, `form_action`, `home_url`, `rules_url`, `body_class`).

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

-- Jeux génériques (Flip 7, et les suivants)
game_sessions   (id, game_slug, variant, group_id, created_by, created_at, finished, comments)
session_players (id, session_id, player_name, position)
session_scores  (id, session_id, round_number, player_name, score, details, created_at)
                -- details : JSON propre au jeu, ex. Flip 7 {"numbers", "bonus", "x2", "flip7", "stop", "bust"}

-- Skyjo (historique, pas encore migré vers les tables génériques)
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

Pour le développement, recharger automatiquement le code **et** les templates / CSS / JS
(`--reload` seul ne surveille que les `.py`, Flask garde les templates en cache) :

```bash
gunicorn --bind 127.0.0.1:5000 --reload \
  $(find templates static -name '*.html' -o -name '*.css' -o -name '*.js' | sed 's/^/--reload-extra-file /') \
  app:app
```

Ne pas tester directement sur `http://127.0.0.1:5000/familyboardgame/…` : le préfixe est retiré par Apache,
Gunicorn seul répond 404. Passer par http://localhost/….

Accès via Apache local (config `/etc/apache2/sites-available/skyjo-local.conf`, mêmes règles qu'en prod mais vers le port 5000) :
- http://localhost/familyboardgame/ (hub, Flip 7 sous `/familyboardgame/flip7/`)
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
python -m pytest tests/test_flip7.py
```

⚠️ Les anciens tests Skyjo (`tests/test_*` hors Flip 7) ne sont plus à jour depuis le découpage en modules
(ils référencent `app.DB_PATH` et les anciennes tables `rounds`).

## Scripts de maintenance

| Script                          | Usage |
|---------------------------------|-------|
| `scripts/add_game_rules.py`     | `python3 scripts/add_game_rules.py "Nom du jeu" fichier.pdf` (PDF placé dans `images/`), ou `--list` |
| `scripts/normalize_players.py`  | Fusionne les joueurs aux noms quasi identiques. `--dry-run` pour simuler ; crée une sauvegarde avant d'écrire. Option `--db-path` |

Images (dossier `images/`, servi sous `/familyboardgame/images/`) : `SkyjoAcceuil.png` et `Flip7.webp` (hub),
`SkyjoStat.png`, `SkyjoActionStat.png` et `Flip7.webp` (menu des statistiques), `Flip7-quatro.webp` (bandeau des pages Flip 7),
`ReglesFlip7-*.png` (règles Flip 7), PDF de règles Skyjo.

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

Mise à jour : automatique à chaque push sur `main` (`.github/workflows/deploy.yml`) :
sauvegarde de la base dans `backups/`, copie des fichiers par rsync, redémarrage de `gunicorn-skyjo`.
Le suivi des déploiements se fait dans l'onglet **Actions** du dépôt GitHub.

```bash
sudo journalctl -u gunicorn-skyjo -f   # logs
```

## Historique

Voir [CHANGELOG.md](CHANGELOG.md).
