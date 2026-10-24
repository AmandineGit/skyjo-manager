# Changelog

## [Non publié]

### Qwirkle
- Nouveau jeu **Qwirkle** sous `/familyboardgame/qwirkle/` : saisie tour par tour avec rotation automatique des joueurs,
  compteur de Qwirkles par tour (plusieurs possibles sur une même pose, +6 points chacun ajoutés automatiquement) et échange de tuiles, feuille de score avec modification d'un tour, annulation du dernier tour,
  fin de partie avec bonus de 6 points, règles officielles en images (calcul des points et exemples compris), stats en dalles et page par joueur
- Feuille de score en grille (noms des joueurs en en-tête, totaux en bas), lisible sur mobile, largeur limitée sur PC
- Stockage dans les tables génériques existantes (une ligne par tour) : aucune nouvelle table

### Refactoring et tests
- Routes communes des jeux génériques regroupées dans `core/game_routes.py` (liste des parties, nouvelle partie,
  suppression, règles, statistiques, page joueur) : chaque jeu ne garde que sa page de partie et sa saisie
- Ajout / annulation de score communs (`core/sessions.py`), dalles de palmarès et profil joueur communs (`core/stats.py`)
- Templates communs `_game_index.html` (liste des parties) et `_game_stats.html` (page de stats étendue par chaque jeu)
- Anciens tests Skyjo v1, cassés depuis le découpage en modules, remplacés par `tests/test_skyjo.py` (dont doublement
  du finisher et fin à 100 points) ; nouveau `tests/test_games_common.py` ; toute la suite passe avec `python -m pytest`
- Imports inutilisés supprimés (pyflakes propre)
- Flip 7 : la liste des parties indique tous les joueurs à égalité en tête

### Corrections
- Groupes : le compte admin n'apparaît plus dans « Comptes liés » (il y était rattaché à la création d'un groupe
  et par la migration v1) et n'est plus ajouté comme propriétaire des nouveaux groupes ; il voit toujours tous les groupes
- Flip 7 : sur mobile, l'historique des manches affiche de nouveau le nom du joueur dans chaque carte (`data-label`)

### Mantis
- Nouveau jeu **Mantis** sous `/familyboardgame/mantis/` : compteur en direct (cartes marquées, vols réussis, ✏️ correction,
  ↶ annulation), règle maison « jusqu'à épuisement de la pioche » avec départage au tank en cas d'égalité,
  repère du seuil officiel (sprinteur), règles en images, stats en dalles et page par joueur
- Stockage dans les tables génériques existantes (journal d'actions dans `session_scores`) : aucune nouvelle table

### Plateforme
- Liste des jeux génériques centralisée dans `games/registry.py`, lue par le hub, le menu des statistiques et les groupes
- Accès communs aux parties génériques regroupés dans `core/sessions.py` (Flip 7 et Mantis)
- En-tête « Family board games » commun (`templates/_hub_header.html`) sur l'accueil, les statistiques, les groupes et le profil,
  sans bandeau Skyjo
- Pages de connexion, d'inscription et de mot de passe : nom « Family board games » et manette 🎮 à la place de Skyjo

### Flip 7
- Nouveau jeu **Flip 7** sous `/familyboardgame/flip7/` : saisie par manche (chiffres, bonus, ×2, Flip 7, Stop, Doublon) avec calcul automatique,
  fin à 200 points avec manche de départage en cas d'égalité, modification de manche, règles en images, statistiques et palmarès
- Tables génériques `game_sessions`, `session_players`, `session_scores` (créées au démarrage, aucune table existante modifiée)
- Logique « joueurs + groupe » de la création de partie extraite dans `core/groups.py`, partagée avec Skyjo
- Autocomplétion et détection de doublons des noms : incluent les joueurs Flip 7
- Stats Flip 7 en dalles Metro comme Skyjo (podium, palmarès, parties, joueurs) et page de stats par joueur
- Hub : tuile Flip 7, images des jeux (`SkyjoAcceuil.png`, `Flip7.webp`) et compteur de parties tous jeux confondus
- Menu des statistiques : images des jeux à la place des icônes (`SkyjoStat.png`, `SkyjoActionStat.png`, `Flip7.webp`)

### Groupes
- « Mes groupes » : nombre de parties par jeu au lieu d'un total Skyjo seul
- Détail d'un groupe : dernières parties tous jeux confondus (jeu et joueurs indiqués), un bouton de nouvelle partie par jeu

### Déploiement
- Déploiement automatique par GitHub Actions (rsync, comme les autres sites du VPS) avec sauvegarde de la base avant chaque déploiement ; `deploy.sh` supprimé

### Nettoyage
- Dépôt nettoyé : suppression des scripts de migration déjà appliqués (`migrate_production.py`, `migrate_to_skyjo_tables.py`, `update_skyjo_queries.py`, `test_migration.py`), de `app_backup_phase1.py` et des pages de démo statiques
- Scripts de maintenance regroupés dans `scripts/`
- Documentation refondue : README, INSTALL et CHANGELOG à jour ; `STRUCTURE.md`, `DEMARRAGE_RAPIDE.md`, `RECAP_GITHUB.md` et `MIGRATION_PHASE1.5.md` supprimés

## [3.0.0] - 2026-08-13 — Architecture multi-jeux

### Architecture
- Découpage en modules : `core/` (base de données, authentification) et `games/skyjo/` (blueprint Flask)
- Hub d'accueil commun listant les jeux disponibles
- Séparation des URLs publiques :
  - `/familyboardgame/` : hub, connexion, profil, groupes, statistiques, administration
  - `/skyjo/` : le jeu Skyjo (réécrit vers `/play/` côté Gunicorn)

### Base de données
- Tables Skyjo renommées : `games` → `skyjo_games`, `players` → `skyjo_players`, `rounds` → `skyjo_rounds` (migration appliquée en production, historique préservé)
- Ajout de `player_groups.rename_permission`

## [2.2.0] - 2026-05-10
- Création de partie possible sans groupe existant (groupe créé à la volée)
- Permissions d'édition : partie terminée → admin uniquement ; partie en cours → tout utilisateur connecté
- Suppression de partie réservée à l'admin, avec confirmation
- Terminer une partie sans manche la supprime
- « Mot de passe oublié » remplacé par une invitation à contacter l'administrateur

## [2.1.0] - 2026-05-03
- Nom de joueur unifié : `player_name` remplace `display_name`
- Rattachement de l'historique à l'inscription (insensible aux accents et à la casse)
- Un joueur voit tous les groupes où il apparaît
- Gestion des groupes réservée à l'admin ; panneau d'administration (mots de passe, noms)
- Script `normalize_players.py` de fusion des noms similaires
- Champ `users.last_login`

## [2.0.0] - 2026-01
- **Cassant** : comptes utilisateurs (email / mot de passe) à la place des codes d'accès 1666 / 1664
- Groupes de joueurs, statistiques filtrées par groupe
- Option « finisher » avec doublement automatique des points
- Statistiques individuelles par joueur

## [1.0.0] - 2026-01-13
- Version initiale : gestion des parties Skyjo et Skyjo Action, scores par manche, fin de partie à 100 points
- Statistiques par type de jeu (podium, moyenne, médiane, meilleur / pire score)
- Règles PDF intégrées, commentaires, recherche par date, export
- Accès par codes (1666 interne / 1664 externe)
- Interface Metro UI responsive
