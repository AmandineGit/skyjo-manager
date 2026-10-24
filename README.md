# Family Board Game

Application web de suivi de scores et de statistiques pour jeux de société.
Initialement dédiée à **Skyjo**, elle est devenue multi-jeux : **Skyjo**, **Flip 7**, **Mantis** et **Qwirkle**.

![Python](https://img.shields.io/badge/python-3.10+-green)
![Flask](https://img.shields.io/badge/flask-3.0.0-lightgrey)

En production sur `digital-pragma.fr` (Gunicorn + Apache en reverse proxy).

## Fonctionnalités

### Plateforme commune (`/familyboardgame/`)
- **Hub d'accueil** listant les jeux disponibles, chacun avec son image
- **En-tête commun** (menu utilisateur, titre « Family board games ») sur l'accueil, les statistiques, les groupes et le profil ;
  les pages d'un jeu gardent le bandeau de leur jeu
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
- Statistiques en dalles : podium des victoires, palmarès (Kamikaze, Manche de rêve, Roi du Flip 7, Banquier,
  Prudent, Multiplicateur), parties et joueurs actifs ; les palmarès en pourcentage ne retiennent que les joueurs
  ayant au moins 5 manches
- Page de stats par joueur : moyenne et médiane, victoires, meilleure manche, taux de stops et de doublons,
  Flip 7, ×2, ancienneté, co-joueurs fréquents

### Mantis (`/familyboardgame/mantis/`)
- **Règle maison** : on ne s'arrête pas à 10 cartes, on joue jusqu'à épuisement de la pioche ; le plus de cartes
  dans la pile de score gagne. En cas d'égalité en tête, départage au nombre de cartes dans le **tank**
  (règle officielle « pioche vide »), sinon ex aequo
- **Compteur en direct** pendant la partie, par joueur : nombre de cartes marquées (✓ Marquer), **🦐 Vol réussi**
  (compté pour les stats, sans effet sur le score), **✏️ Corriger** (saisie directe des cartes et des vols)
- **↶ Annuler la dernière action**, déroulé horodaté de la partie
- Repère du seuil officiel (10 cartes, 15 à deux) : le premier à le franchir est « 🏃 le sprinteur »
- **🏁 Pioche vide : fin de partie** ; reprise d'une partie terminée réservée à l'admin
- Règles affichées en images (`images/MantisRegle*.png`)
- Statistiques en dalles : podium des victoires, Gros Coup, Pickpocket, Sprinteur, Collectionneur, parties et joueurs ;
  page de stats par joueur (moyenne et médiane de cartes, victoires, meilleure partie, gros coup, vols, sprints,
  ancienneté, co-joueurs fréquents)

### Qwirkle (`/familyboardgame/qwirkle/`)
- **Saisie tour par tour** : on entre les points du joueur dont c'est le tour, la main passe automatiquement
  au suivant ; toucher la carte d'un joueur le désigne comme joueur en cours
- On saisit les **points des lignes** (1 par tuile) ; le compteur **⭐ Qwirkle** ajoute automatiquement **6 points par Qwirkle**
  (une même pose peut terminer plusieurs lignes de 6), avec le total du tour affiché en direct ; bouton **🔄 Échange de tuiles** (0 point)
- **Feuille de score** façon papier : grille tours × joueurs avec le nom des joueurs en en-tête et les totaux en bas,
  lisible aussi sur mobile (largeur limitée sur PC) ; toucher un score pour le **✏️ modifier**, **↶ Annuler le dernier tour**
- **🏁 Fin de partie** : bonus de 6 points au joueur qui a vidé sa main en premier (ou « personne » si partie bloquée) ;
  le plus haut score gagne, égalité = ex aequo ; reprise d'une partie terminée réservée à l'admin
- Règles officielles en images (`images/ReglesQwirkle*.png` : déroulement, calcul des points, fin de partie, exemples)
- Statistiques en dalles : podium, Roi du Qwirkle, Gros Tour, Régulier (moyenne par tour, 5 tours minimum),
  Finisseur, Brasseur (échanges), parties et joueurs ; page de stats par joueur

## Architecture

```
skyjo-manager/
├── app.py                  # Application Flask : hub, auth, groupes, stats, admin
├── core/
│   ├── db.py               # Connexion SQLite, création du schéma, migrations légères
│   ├── auth.py             # require_auth, get_current_user, is_admin, get_user_group_ids
│   ├── groups.py           # Joueurs + groupe à la création d'une partie (tous jeux)
│   ├── sessions.py         # Accès communs aux parties génériques (droits, création, ajout/annulation de score, données de stats)
│   ├── game_routes.py      # Routes communes des jeux génériques (liste, nouvelle partie, suppression, règles, stats)
│   └── stats.py            # Briques de stats communes (dalle de palmarès, profil joueur)
├── games/
│   ├── registry.py         # Liste des jeux génériques (nom, URL, image) lue par le hub, les stats et les groupes
│   ├── skyjo/
│   │   └── routes.py       # Blueprint Skyjo (préfixe interne /play)
│   ├── flip7/
│   │   ├── routes.py       # Blueprint Flip 7 (préfixe interne /flip7)
│   │   ├── scoring.py      # Règles de score, sans Flask
│   │   └── stats.py        # Calcul des statistiques, sans Flask
│   ├── mantis/
│   │   ├── routes.py       # Blueprint Mantis (préfixe interne /mantis)
│   │   ├── scoring.py      # Journal d'actions rejoué, gagnant et départage, sans Flask
│   │   └── stats.py        # Calcul des statistiques, sans Flask
│   └── qwirkle/
│       ├── routes.py       # Blueprint Qwirkle (préfixe interne /qwirkle)
│       ├── scoring.py      # Tours rejoués, feuille de score, joueur suivant, sans Flask
│       └── stats.py        # Calcul des statistiques, sans Flask
├── templates/              # Templates Jinja : communs + Skyjo à la racine, un sous-dossier par jeu générique ;
│                           # _hub_header.html (en-tête des pages communes), _game_index.html (liste des parties)
│                           # et _game_stats.html (page de stats que chaque jeu étend)
├── static/                 # style.css (Metro UI), flip7.js (calcul en direct des manches Flip 7)
├── images/                 # Images des jeux et règles
├── scripts/                # Scripts de maintenance (voir plus bas)
├── tests/                  # Tests pytest
├── export_to_onedrive.py   # Export (stub pour l'instant)
├── .github/workflows/      # Déploiement automatique (GitHub Actions)
└── skyjo.db                # Base SQLite (non versionnée)
```

### Routage des URLs

Apache expose deux préfixes publics qui pointent vers la même instance Gunicorn :

| URL publique                 | Côté Gunicorn | Contenu                                             |
|------------------------------|---------------|-----------------------------------------------------|
| `/familyboardgame/…`         | `/…`          | Hub, connexion, profil, groupes, stats, admin       |
| `/familyboardgame/flip7/…`   | `/flip7/…`    | Blueprint Flip 7                                    |
| `/familyboardgame/mantis/…`  | `/mantis/…`   | Blueprint Mantis                                    |
| `/familyboardgame/qwirkle/…` | `/qwirkle/…`  | Blueprint Qwirkle                                   |
| `/skyjo/…`                   | `/play/…`     | Blueprint Skyjo : liste des parties, nouvelle partie, saisie des scores |

Les nouveaux jeux sont servis sous le préfixe commun `/familyboardgame/` : aucune règle Apache à ajouter.
Les liens dans le code et les templates utilisent les URLs publiques en dur (`/familyboardgame/…`, `/skyjo/…`).
Lancée directement sans Apache, l'application répond sur `/`, `/flip7/`, `/mantis/`, `/qwirkle/` et `/play/`.

### Ajouter un jeu

Sur le modèle de Flip 7 (score par manche), Mantis (compteur en direct) ou Qwirkle (tour par tour) :
1. `games/<jeu>/scoring.py` et `stats.py` : règles et statistiques, sans Flask (`compute_stats`, `compute_player_stats` ;
   `core/stats.py` fournit `award` pour les dalles et `player_profile` pour la page joueur) ;
2. `games/<jeu>/routes.py` : un blueprint (préfixe interne `/<jeu>`, donc servi sous `/familyboardgame/<jeu>/`) avec la page
   de partie et la saisie propres au jeu, puis `add_common_routes(...)` (`core/game_routes.py`) qui ajoute la liste des parties,
   la nouvelle partie, la suppression admin, les règles, les stats et la page joueur ; l'enregistrer dans `app.py` ;
3. une entrée dans `games/registry.py` (slug, nom, URL, image) : le jeu apparaît alors dans le hub, le menu des statistiques
   et les pages de groupes ;
4. les données dans les tables génériques `game_sessions` / `session_players` / `session_scores`, avec `game_slug` propre au jeu
   et le détail spécifique en JSON dans `session_scores.details` : pas de nouvelle table (`core/sessions.py` : `insert_score`,
   `next_round_number`, `delete_last_score`…) ;
5. templates dans `templates/<jeu>/` : `game.html`, `rules.html`, `player_stats.html` et `stats.html` (qui étend `_game_stats.html`
   et ne définit que ses colonnes et résumés) ; la liste des parties et le formulaire de nouvelle partie sont communs ;
6. un bandeau propre au jeu via `body.<jeu>::before` dans `static/style.css` ;
7. un scénario dans `tests/test_games_common.py` (`FIRST_SCORE`) et un fichier `tests/test_<jeu>.py` ;
8. attention aux tableaux de classe `rounds-table` : sur mobile, ils sont transformés en cartes et l'en-tête est masqué ;
   chaque cellule doit porter un `data-label` (nom du joueur…), sinon utiliser un tableau dédié (comme la feuille Qwirkle).

## Base de données

SQLite (`skyjo.db`). Le schéma est créé ou complété au démarrage par `core/db.py` (`init_db`, puis `_apply_migrations` pour les colonnes ajoutées après coup).

```sql
-- Commun à tous les jeux
users          (id, email, password_hash, display_name*, player_name,
                created_at, reset_token, reset_token_expires, last_login)
player_groups  (id, name, created_by, created_at, rename_permission)
group_members  (id, group_id, player_name, user_id)   -- joueurs d'un groupe
group_users    (id, group_id, user_id, role)          -- comptes ayant accès au groupe
game_rules     (id, game_type, rules_pdf)             -- PDF de règles par type de jeu (Skyjo)

-- Jeux génériques (Flip 7, Mantis, Qwirkle, et les suivants)
game_sessions   (id, game_slug, variant, group_id, created_by, created_at, finished, comments)
session_players (id, session_id, player_name, position)
session_scores  (id, session_id, round_number, player_name, score, details, created_at)

-- Skyjo (historique, pas encore migré vers les tables génériques)
skyjo_games    (id, created_at, type, comments, finished, group_id, created_by)
skyjo_players  (id, game_id, name)
skyjo_rounds   (id, game_id, round_number, player_name, score, created_at, is_finisher)
```

Utilisation de `session_scores` selon le jeu :

| Jeu    | Une ligne =                       | `score`                         | `details` (JSON) |
|--------|-----------------------------------|---------------------------------|------------------|
| Flip 7 | le résultat d'un joueur sur une manche | points de la manche        | `numbers`, `bonus`, `x2`, `flip7`, `stop`, `bust` |
| Mantis | une action, dans l'ordre (`round_number` = n° d'action) | cartes ajoutées à la pile (0 pour un vol) | `type` : `score`, `steal`, `fix` (+ `steals`), `tank` (+ `tank`) |
| Qwirkle | un tour, dans l'ordre (`round_number` = n° de tour joué) | total du tour, bonus Qwirkle compris (6 pour le bonus de fin) | `type` : `turn` (+ `points` des lignes, `qwirkles` = nombre, `swap`) ou `bonus` |

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
(`--reload` seul ne surveille que les `.py`, Flask garde les templates en cache ;
relancer la commande après avoir créé un nouveau fichier de template) :

```bash
gunicorn --bind 127.0.0.1:5000 --reload \
  $(find templates static -name '*.html' -o -name '*.css' -o -name '*.js' | sed 's/^/--reload-extra-file /') \
  app:app
```

Ne pas tester directement sur `http://127.0.0.1:5000/familyboardgame/…` : le préfixe est retiré par Apache,
Gunicorn seul répond 404. Passer par http://localhost/….

Accès via Apache local (config `/etc/apache2/sites-available/skyjo-local.conf`, mêmes règles qu'en prod mais vers le port 5000) :
- http://localhost/familyboardgame/ (hub ; les jeux génériques sous `/familyboardgame/<jeu>/`)
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

Chaque test travaille sur une base temporaire (`core.db.DB_PATH` remplacé), jamais sur `skyjo.db` :
`test_skyjo.py`, `test_flip7.py`, `test_mantis.py`, `test_qwirkle.py`, et `test_games_common.py`
qui vérifie les routes communes (liste, droits, suppression admin, stats) pour chaque jeu du registre.

## Images

Dossier `images/`, servi sous `/familyboardgame/images/` :

| Usage                    | Skyjo                                   | Flip 7               | Mantis                         | Qwirkle               |
|--------------------------|-----------------------------------------|----------------------|--------------------------------|-----------------------|
| Tuile du hub             | `SkyjoAcceuil.png`                      | `Flip7.webp`         | `Mantis.jpg`                   | `qwirkle.png`         |
| Menu des statistiques    | `SkyjoStat.png`, `SkyjoActionStat.png`  | `Flip7.webp`         | `Mantis.jpg`                   | `qwirkle.png`         |
| Bandeau des pages du jeu | `article-skyjo-bandeau-bis.webp`        | `Flip7-quatro.webp`  | `mantis-materiel-de-jeu.png`   | `Qwirkle-bandeau.png` |
| Règles                   | PDF (`88-skyjo-regle.pdf`, `skyjo_action_regles_fr.pdf`) | `ReglesFlip7-*.png` | `MantisRegle*.png` | `ReglesQwirkle*.png` |

Les fichiers `*:Zone.Identifier` créés par Windows lors d'une copie vers WSL sont ignorés par git et peuvent être supprimés.

## Scripts de maintenance

| Script                          | Usage |
|---------------------------------|-------|
| `scripts/add_game_rules.py`     | `python3 scripts/add_game_rules.py "Nom du jeu" fichier.pdf` (PDF placé dans `images/`), ou `--list` — règles PDF de Skyjo |
| `scripts/normalize_players.py`  | Fusionne les joueurs aux noms quasi identiques. `--dry-run` pour simuler ; crée une sauvegarde avant d'écrire. Option `--db-path` |

Les anciens scripts de migration (v1 → v2, passage aux tables `skyjo_*`) ont déjà été appliqués en production ; ils restent consultables dans l'historique git.

## API (blueprint Skyjo, utilisée par tous les formulaires de nouvelle partie)

| Route                                       | Description                                 |
|---------------------------------------------|---------------------------------------------|
| `GET /skyjo/api/players/search?q=`          | Autocomplétion des joueurs (tous jeux)      |
| `GET /skyjo/api/players/check-duplicate?name=` | Détection d'un nom similaire existant (tous jeux) |
| `GET /skyjo/api/groups/<id>/members`        | Membres d'un groupe                         |
| `GET /skyjo/api/groups/suggest?players=`    | Groupes suggérés selon les joueurs          |

## Production et déploiement

Installation complète du serveur : voir [INSTALL.md](INSTALL.md).

Mise à jour : automatique à chaque push sur `main` (`.github/workflows/deploy.yml`) :
sauvegarde de la base dans `backups/`, copie des fichiers par rsync, redémarrage de `gunicorn-skyjo`.
Les nouvelles tables éventuelles sont créées au redémarrage (`init_db`), sans toucher aux données existantes.
Le suivi des déploiements se fait dans l'onglet **Actions** du dépôt GitHub.

```bash
sudo journalctl -u gunicorn-skyjo -f   # logs
```

## Historique

Voir [CHANGELOG.md](CHANGELOG.md).
