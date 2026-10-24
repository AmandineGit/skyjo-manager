# Skyjo Manager

## Contexte
Application Flask « Family board games » de gestion de scores, initialement dédiée au jeu Skyjo,
aujourd'hui multi-jeux : Skyjo, Flip 7, Mantis, Qwirkle.
Déployée en prod sur digital-pragma.fr (Gunicorn + Apache reverse proxy,
préfixes /familyboardgame/ pour la plateforme et les nouveaux jeux, /skyjo/ pour Skyjo).

## Objectif d'évolution
Transformer l'app en plateforme générique de gestion de scores/statistiques
pour plusieurs jeux de société, Skyjo devenant un jeu parmi d'autres.

Approche progressive, pas de sur-ingénierie :
1. Usage perso/communautaire d'abord (valider l'usage réel avant tout objectif commercial)
2. Passage en PWA (manifest.json + service worker) pour une installation mobile
   sans passer par les stores
3. Évaluation d'un objectif commercial et/ou d'une app native plus tard,
   seulement si l'usage le justifie

## Schéma de données
Voir core/db.py. Les nouveaux jeux utilisent les tables génériques
game_sessions / session_players / session_scores (game_slug + détail JSON dans details) :
ne pas créer de tables par jeu. Skyjo reste sur ses tables historiques skyjo_*.
Ne pas migrer le schéma existant (dont Skyjo vers les tables génériques) sans validation explicite,
l'historique de parties doit être préservé.

## Environnement de dev local (WSL2 Ubuntu, ThinkPad)
- venv Python dans `venv/`
- Lancer en local :
```bash
  source venv/bin/activate
  gunicorn --bind 127.0.0.1:5000 app:app
```
- Serveur de dev avec rechargement des templates/CSS/JS : voir README (« Développement local »),
  `--reload` seul ne recharge pas les templates
- Test local via Apache reverse proxy (pas directement sur :5000, le préfixe /familyboardgame est retiré par Apache) :
  http://localhost/familyboardgame/ (hub, pages communes) et http://localhost/skyjo/ (jeu Skyjo)
- Config Apache locale : /etc/apache2/sites-available/skyjo-local.conf
  (ProxyPass /familyboardgame -> 127.0.0.1:5000/, /skyjo -> 127.0.0.1:5000/play)

## Architecture
- `app.py` : routes communes (hub, auth, groupes, stats, admin), servies sous /familyboardgame/
- `core/` : db.py (schéma + migrations légères au démarrage), auth.py, groups.py (joueurs + groupe
  à la création de partie), sessions.py (accès communs aux parties génériques), game_routes.py
  (routes communes : liste, nouvelle partie, suppression, règles, stats), stats.py (dalles, profil joueur)
- `games/<jeu>/` : un blueprint par jeu (Skyjo : préfixe interne /play ; Flip 7, Mantis, Qwirkle : /<jeu>,
  servis sous /familyboardgame/<jeu>/ sans règle Apache dédiée), règles de score et stats sans Flask
- `games/registry.py` : liste des jeux génériques lue par le hub, les stats et les groupes ;
  ajouter un jeu = blueprint + entrée dans le registre (voir README « Ajouter un jeu »)
- Pages communes : en-tête `templates/_hub_header.html` + `<body class="hub-page">` (pas de bandeau de jeu)
- Piège CSS : `.rounds-table` passe en cartes sur mobile (thead masqué) ; chaque `td` doit avoir un `data-label`
- Tests : `python -m pytest` (base temporaire, jamais skyjo.db) ; ajouter un scénario par nouveau jeu
  dans tests/test_games_common.py
- `scripts/` : scripts de maintenance ponctuels
- Les liens utilisent les URLs publiques en dur (/familyboardgame/..., /skyjo/...)

## Déploiement
- Prod : Gunicorn (service systemd) sur 127.0.0.1:8000, proxifié par Apache
- Déploiement automatique par GitHub Actions à chaque push sur main
  (`.github/workflows/deploy.yml` : backup DB, rsync, restart gunicorn-skyjo) ;
  détail et prérequis serveur dans INSTALL.md

## Conventions
- Réponds en français
- Messages de commit en français, concis
- Toujours proposer `git status` avant `git add`
- Avant toute modification de schéma de base de données, signaler explicitement
  l'impact sur les données existantes
