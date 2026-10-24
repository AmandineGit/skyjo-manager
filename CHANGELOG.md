# Changelog

## [Non publié]

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
- « Mes groupes » : nombre de parties par jeu (Skyjo, Skyjo Action, Flip 7) au lieu d'un total Skyjo seul
- Détail d'un groupe : dernières parties tous jeux confondus (jeu et joueurs indiqués), boutons de nouvelle partie Skyjo et Flip 7

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
