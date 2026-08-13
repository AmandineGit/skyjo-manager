# Skyjo Manager

## Contexte
Application Flask de gestion de scores, initialement dédiée au jeu Skyjo.
Déployée en prod sur digital-pragma.fr (Gunicorn + Apache reverse proxy, préfixe /skyjo/).

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
⚠️ Le schéma actuel est pensé pour Skyjo uniquement (voir app.py / skyjo.db).
Avant d'ajouter un nouveau jeu, réfléchir à une structure générique
(ex: table `games`, `sessions`, `scores` flexible) plutôt que dupliquer
la logique Skyjo. Ne pas migrer le schéma existant sans validation explicite,
l'historique de parties doit être préservé.

## Environnement de dev local (WSL2 Ubuntu, ThinkPad)
- venv Python dans `venv/`
- Lancer en local :
```bash
  source venv/bin/activate
  gunicorn --bind 127.0.0.1:5000 app:app
```
- Test local via Apache reverse proxy : http://localhost/skyjo/ (avec le / final)
- Config Apache locale : /etc/apache2/sites-available/000-default.conf
  (ProxyPass /skyjo/ vers 127.0.0.1:5000/)

## Déploiement
- Prod : Gunicorn (service systemd) sur 127.0.0.1:8000, proxifié par Apache
- Déploiement via `deploy.sh` (voir contenu du script pour le détail du flux)

## Conventions
- Réponds en français
- Messages de commit en français, concis
- Toujours proposer `git status` avant `git add`
- Avant toute modification de schéma de base de données, signaler explicitement
  l'impact sur les données existantes
