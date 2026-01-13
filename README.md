# 🎯 Skyjo Manager

Application web de gestion de parties de Skyjo avec suivi des scores, statistiques détaillées et système d'authentification à deux niveaux.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Flask](https://img.shields.io/badge/flask-3.0.0-lightgrey)

## ✨ Fonctionnalités

### 🎮 Gestion de parties
- Création de parties pour **Skyjo** et **Skyjo Action**
- Suivi des scores par manche en temps réel
- Détection automatique de fin de partie (score ≥ 100)
- Commentaires sur les parties
- Recherche de parties par date
- Affichage des parties en cours et terminées

### 📊 Statistiques avancées
- Statistiques par type de jeu (Skyjo / Skyjo Action)
- Podium des meilleurs joueurs
- Scores moyens, médians, meilleur et pire par joueur
- "Boss des coups de bol" : meilleur score unique
- "Looser du pire" : pire score unique
- Compteurs de parties et manches jouées

### 🔐 Système d'authentification
- **Code 1666 (Interne)** : Accès complet
  - Création de parties (taguées 'int')
  - Consultation de toutes les parties
  - Accès aux statistiques
  - Export vers Excel/OneDrive

- **Code 1664 (Externe)** : Accès limité
  - Création de parties (taguées 'ext')
  - Consultation uniquement des parties 'ext'
  - Pas d'accès aux statistiques

### 📱 Interface responsive
- Design Metro UI inspiré de Windows Phone Lumia
- Tuiles colorées avec dégradés
- Optimisé mobile et desktop
- Bandeau d'en-tête avec logo Skyjo
- Bouton retour intégré
- Fond dégradé arc-en-ciel

### 📄 Règles du jeu
- Consultation des règles PDF intégrée
- Règles pour Skyjo et Skyjo Action

### 📤 Export de données
- Export vers Excel (.xlsx)
- Export automatique vers OneDrive (optionnel)

## 🚀 Installation

### Prérequis

- Python 3.10 ou supérieur
- Apache 2.4+ (pour la production)
- Git

### Installation locale (développement)

```bash
# Cloner le dépôt
git clone https://github.com/VOTRE-USERNAME/skyjo-manager.git
cd skyjo-manager

# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Créer le fichier de configuration
cp .env.example .env
nano .env  # Modifier FLASK_SECRET

# Lancer l'application
python app.py
```

L'application sera accessible sur `http://localhost:5000`

### Installation en production

Voir [INSTALL.md](INSTALL.md) pour les instructions détaillées de déploiement sur VPS avec Apache et Gunicorn.

## 📋 Configuration

### Variables d'environnement (`.env`)

```bash
# Clé secrète Flask (obligatoire en production)
FLASK_SECRET=votre_cle_secrete_aleatoire_tres_longue

# Chemin OneDrive pour l'export (optionnel)
ONEDRIVE_PATH=/path/to/onedrive/folder
```

### Structure des fichiers

```
skyjo-manager/
├── app.py                      # Application Flask principale
├── export_to_onedrive.py       # Module d'export Excel
├── requirements.txt            # Dépendances Python
├── .env                        # Configuration (non versionné)
├── .env.example               # Exemple de configuration
├── skyjo.db                   # Base de données SQLite (non versionnée)
├── static/
│   └── style.css              # Styles CSS
├── templates/
│   ├── index.html             # Page d'accueil
│   ├── login.html             # Page de connexion
│   ├── new_game.html          # Création de partie
│   ├── game.html              # Vue détaillée d'une partie
│   ├── stats_menu.html        # Menu des statistiques
│   └── stats_detail.html      # Statistiques détaillées
├── images/
│   ├── article-skyjo-bandeau-bis.webp  # Bannière principale
│   └── 88-skyjo-regle.pdf              # Règles du jeu
├── README.md                  # Ce fichier
├── INSTALL.md                 # Guide d'installation production
└── CHANGELOG.md               # Historique des versions
```

## 🎮 Utilisation

### Connexion

Accédez à l'application et entrez l'un des codes :
- **1666** : Accès interne complet
- **1664** : Accès externe limité

### Créer une partie

1. Cliquez sur "Nouvelle partie"
2. Choisissez le type de jeu (Skyjo / Skyjo Action)
3. Ajoutez les joueurs (jusqu'à 10)
4. Ajoutez un commentaire (optionnel)
5. Créez la partie

### Enregistrer des scores

1. Ouvrez une partie en cours
2. Pour chaque manche, entrez les scores de chaque joueur
3. Cliquez sur "Enregistrer la manche"
4. La partie se termine automatiquement quand un joueur atteint 100 points

### Consulter les statistiques

1. Cliquez sur "Stats" (accès interne uniquement)
2. Choisissez le type de jeu
3. Consultez le podium et les statistiques détaillées

## 🛠️ Technologies utilisées

### Backend
- **Flask 3.0** : Framework web Python
- **SQLite** : Base de données légère
- **Pandas** : Analyse de données pour les statistiques
- **Gunicorn** : Serveur WSGI pour la production

### Frontend
- **HTML5** / **CSS3**
- **Metro UI Design** : Interface inspirée de Windows Phone
- Design responsive natif (sans framework)

### Infrastructure
- **Apache** : Reverse proxy
- **systemd** : Gestion du service
- **Let's Encrypt** : Certificat SSL

## 📊 Base de données

### Schéma

```sql
-- Table des parties
games (
    id INTEGER PRIMARY KEY,
    created_at TEXT,
    type TEXT,
    comments TEXT,
    finished INTEGER DEFAULT 0,
    access_type TEXT DEFAULT 'int'
)

-- Table des joueurs
players (
    id INTEGER PRIMARY KEY,
    game_id INTEGER,
    name TEXT
)

-- Table des manches
rounds (
    id INTEGER PRIMARY KEY,
    game_id INTEGER,
    round_number INTEGER,
    player_name TEXT,
    score INTEGER,
    created_at TEXT
)

-- Table des règles
game_rules (
    id INTEGER PRIMARY KEY,
    game_type TEXT UNIQUE,
    rules_pdf TEXT
)
```

## 🔒 Sécurité

- Authentification par code d'accès en session
- Filtrage des données par niveau d'accès
- Protection CSRF via Flask
- Headers de sécurité configurés (X-Frame-Options, X-Content-Type-Options)
- Fichiers sensibles exclus du dépôt (.env, *.db)
- Permissions strictes sur les fichiers en production

## 🚢 Déploiement

### Mise à jour rapide

```bash
cd /var/www/skyjo
sudo /var/www/skyjo/deploy.sh
```

Le script `deploy.sh` effectue :
1. Backup automatique de la base de données
2. Pull du code depuis GitHub
3. Mise à jour des dépendances
4. Redémarrage du service
5. Vérification du statut

### Backup manuel

```bash
# Backup de la base de données
cp /var/www/skyjo/skyjo.db ~/backup_skyjo_$(date +%Y%m%d).db

# Backup complet
tar -czf ~/skyjo_backup_$(date +%Y%m%d).tar.gz /var/www/skyjo --exclude='venv' --exclude='__pycache__'
```

## 📝 Historique des versions

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique complet des modifications.

## 🤝 Contribution

Ce projet est à usage personnel. Les contributions ne sont pas acceptées pour le moment.

## 📄 Licence

© 2026 - Usage personnel uniquement

## 🐛 Dépannage

### Le service ne démarre pas

```bash
# Vérifier le statut
sudo systemctl status gunicorn-skyjo

# Consulter les logs
sudo journalctl -u gunicorn-skyjo -n 50
sudo tail -f /var/log/gunicorn/skyjo_error.log
```

### Erreur de base de données

```bash
# Vérifier les permissions
ls -la /var/www/skyjo/skyjo.db
sudo chown www-data:www-data /var/www/skyjo/skyjo.db
sudo chmod 640 /var/www/skyjo/skyjo.db
```

### Code d'accès refusé

Vérifier que les codes sont bien définis dans `app.py` :
```python
ACCESS_CODE_INTERNAL = '1666'
ACCESS_CODE_EXTERNAL = '1664'
```

## 📞 Support

Pour toute question ou problème, consulter la documentation dans le répertoire `docs/` ou créer une issue sur GitHub.

---

Développé avec ❤️ pour les joueurs de Skyjo
