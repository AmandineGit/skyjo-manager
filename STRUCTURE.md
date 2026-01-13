# Structure du projet Skyjo Manager

```
skyjo-manager/
│
├── 📄 app.py                          # Application Flask principale
├── 📄 export_to_onedrive.py           # Module d'export Excel/OneDrive
│
├── 📋 Configuration
│   ├── .env                           # Configuration sensible (non versionné)
│   ├── .env.example                   # Exemple de configuration
│   ├── .gitignore                     # Fichiers exclus du Git
│   └── requirements.txt               # Dépendances Python
│
├── 📚 Documentation
│   ├── README.md                      # Documentation principale
│   ├── INSTALL.md                     # Guide d'installation production
│   ├── CHANGELOG.md                   # Historique des versions
│   └── STRUCTURE.md                   # Ce fichier
│
├── 🛠️ Scripts
│   └── deploy.sh                      # Script de déploiement automatique
│
├── 🗄️ Base de données
│   └── skyjo.db                       # Base SQLite (non versionnée)
│
├── 🎨 Frontend
│   ├── static/
│   │   └── style.css                  # Styles CSS Metro UI
│   │
│   └── templates/
│       ├── index.html                 # Page d'accueil
│       ├── login.html                 # Page de connexion
│       ├── new_game.html              # Création de partie
│       ├── game.html                  # Vue détaillée partie
│       ├── stats_menu.html            # Menu des stats
│       └── stats_detail.html          # Stats détaillées
│
├── 🖼️ Ressources
│   └── images/
│       ├── article-skyjo-bandeau-bis.webp   # Bannière principale
│       ├── LogoSkyjo.webp                    # Logo Skyjo
│       └── 88-skyjo-regle.pdf                # Règles du jeu
│
└── 🐍 Environnement Python
    └── venv/                          # Environnement virtuel (non versionné)
```

## Fichiers principaux

### Backend

- **app.py** : Application Flask avec toutes les routes
  - Routes d'authentification (`/login`, `/logout`)
  - Routes de gestion de parties (`/`, `/new`, `/game/<id>`)
  - Routes de statistiques (`/stats`, `/stats/<type>`)
  - Routes utilitaires (`/export`, `/rules/<type>`)

- **export_to_onedrive.py** : Export des données vers Excel/OneDrive
  - Génération de fichiers Excel
  - Export vers OneDrive si configuré

### Frontend

- **templates/** : Templates Jinja2
  - `index.html` : Liste des parties + recherche
  - `login.html` : Page d'authentification
  - `new_game.html` : Formulaire création partie
  - `game.html` : Affichage détaillé + saisie scores
  - `stats_menu.html` : Sélection type de jeu
  - `stats_detail.html` : Statistiques complètes

- **static/style.css** : Styles CSS
  - Design Metro UI
  - Responsive mobile/desktop
  - Dégradés et animations

### Configuration

- **.env** : Variables d'environnement sensibles
  - `FLASK_SECRET` : Clé secrète Flask
  - `ONEDRIVE_PATH` : Chemin OneDrive (optionnel)

- **requirements.txt** : Dépendances Python
  - Flask 3.0.0
  - Gunicorn 21.2.0
  - Pandas 2.1.4
  - OpenPyXL 3.1.2
  - python-dotenv 1.0.0

## Base de données SQLite

### Tables

1. **games** : Parties de jeu
   - id, created_at, type, comments, finished, access_type

2. **players** : Joueurs d'une partie
   - id, game_id, name

3. **rounds** : Manches jouées
   - id, game_id, round_number, player_name, score, created_at

4. **game_rules** : Règles PDF par type de jeu
   - id, game_type, rules_pdf

## Flux de données

### Authentification
```
User → /login → Session → / (accès selon niveau)
                ↓
         access_level: 'int' ou 'ext'
```

### Création de partie
```
User → /new → Form → /game/<id>
                ↓
         DB: games + players
         + access_type selon user
```

### Enregistrement scores
```
User → /game/<id> → Form → /submit_round/<id>
                                    ↓
                         DB: rounds + vérif score ≥ 100
                                    ↓
                         Redirect → /game/<id>
```

### Statistiques
```
User (int) → /stats → Choix type → /stats/<type>
                                        ↓
                         Pandas: calculs stats
                                        ↓
                         Template: affichage
```

## Sécurité

### Authentification
- Session Flask avec cookie sécurisé
- Décorateurs `@require_auth` et `@require_internal_access`
- Codes d'accès en dur dans app.py (1666, 1664)

### Filtrage des données
- Filtrage SQL selon `access_level` de la session
- Parties taguées avec `access_type` ('int' ou 'ext')
- Utilisateurs 'ext' ne voient que leurs parties

### Fichiers sensibles
- `.env` exclu du Git
- `*.db` exclu du Git
- Permissions strictes (640 pour .env, 750 pour répertoires)

## Déploiement

### Environnement de production
```
Client → Apache (reverse proxy) → Gunicorn → Flask App
         HTTPS/SSL                127.0.0.1:8000
```

### Processus de mise à jour
```
Dev → Git push → VPS → deploy.sh → Backup DB → Git pull → Restart
```

## Maintenance

### Logs
- Apache : `/var/log/apache2/skyjo_*.log`
- Gunicorn : `/var/log/gunicorn/skyjo_*.log`
- Systemd : `journalctl -u gunicorn-skyjo`

### Backups
- Manuels : `cp skyjo.db backup_$(date +%Y%m%d).db`
- Auto : Script cron quotidien

### Monitoring
- Service : `systemctl status gunicorn-skyjo`
- Ressources : `htop`, `df -h`
- Connexions : `netstat -tlnp | grep 8000`
