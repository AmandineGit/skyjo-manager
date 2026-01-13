# 📦 Guide d'installation - Skyjo Manager

Guide complet pour installer Skyjo Manager sur un serveur de production (VPS).

## 📋 Table des matières

1. [Prérequis](#prérequis)
2. [Installation sur VPS](#installation-sur-vps)
3. [Configuration Apache](#configuration-apache)
4. [Configuration SSL](#configuration-ssl)
5. [Configuration DNS](#configuration-dns)
6. [Scripts de maintenance](#scripts-de-maintenance)
7. [Dépannage](#dépannage)

---

## Prérequis

### Logiciels requis

- **OS** : Ubuntu 22.04 LTS ou supérieur (ou Debian 11+)
- **Python** : 3.10 ou supérieur
- **Apache** : 2.4 ou supérieur
- **Git** : Pour cloner le dépôt
- **Certbot** : Pour SSL (Let's Encrypt)

### Accès nécessaires

- Accès SSH au serveur
- Droits sudo
- Accès au gestionnaire DNS (Ionos, OVH, etc.)
- Compte GitHub (si dépôt privé)

---

## Installation sur VPS

### 1. Connexion au serveur

```bash
ssh votre-user@votre-serveur.com
```

### 2. Installation des dépendances système

```bash
# Mise à jour du système
sudo apt update
sudo apt upgrade -y

# Installation de Python et dépendances
sudo apt install -y python3 python3-venv python3-pip

# Installation d'Apache et modules
sudo apt install -y apache2 libapache2-mod-proxy-html

# Installation de Git
sudo apt install -y git

# Installation de Certbot pour SSL
sudo apt install -y certbot python3-certbot-apache
```

### 3. Cloner le dépôt

```bash
# Se placer dans /var/www
cd /var/www

# Cloner le dépôt (remplacer par votre URL)
sudo git clone https://github.com/VOTRE-USERNAME/skyjo-manager.git skyjo

# Si dépôt privé, GitHub demandera vos identifiants
# Username: votre-username
# Password: votre-personal-access-token

# Aller dans le répertoire
cd skyjo
```

### 4. Créer l'environnement virtuel Python

```bash
# Créer l'environnement virtuel
sudo python3 -m venv venv

# Changer le propriétaire
sudo chown -R www-data:www-data venv

# Installer les dépendances
sudo -u www-data venv/bin/pip install --upgrade pip
sudo -u www-data venv/bin/pip install -r requirements.txt
```

### 5. Configuration de l'application

```bash
# Copier l'exemple de configuration
sudo cp .env.example .env

# Éditer le fichier .env
sudo nano .env
```

Modifier le contenu de `.env` :

```bash
# Générer une clé secrète aléatoire forte
FLASK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Dans le fichier .env, remplacer par la clé générée
FLASK_SECRET=votre_cle_secrete_generee_ci_dessus

# Optionnel : chemin OneDrive pour export
# ONEDRIVE_PATH=/chemin/vers/onedrive
```

### 6. Définir les permissions

```bash
# Propriétaire www-data pour tous les fichiers
sudo chown -R www-data:www-data /var/www/skyjo

# Permissions du répertoire
sudo chmod 750 /var/www/skyjo

# Permissions du fichier .env (sensible)
sudo chmod 640 /var/www/skyjo/.env

# Créer le répertoire images si nécessaire
sudo mkdir -p /var/www/skyjo/images
sudo chown www-data:www-data /var/www/skyjo/images
sudo chmod 755 /var/www/skyjo/images
```

### 7. Configurer le service Gunicorn

```bash
# Créer le fichier de service systemd
sudo nano /etc/systemd/system/gunicorn-skyjo.service
```

Contenu du fichier :

```ini
[Unit]
Description=Gunicorn instance to serve Skyjo Manager
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/skyjo
Environment="PATH=/var/www/skyjo/venv/bin"
ExecStart=/var/www/skyjo/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/gunicorn/skyjo_access.log \
    --error-logfile /var/log/gunicorn/skyjo_error.log \
    --log-level info \
    app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 8. Créer le répertoire des logs

```bash
# Créer le répertoire
sudo mkdir -p /var/log/gunicorn

# Définir le propriétaire
sudo chown www-data:www-data /var/log/gunicorn

# Permissions
sudo chmod 755 /var/log/gunicorn
```

### 9. Démarrer le service Gunicorn

```bash
# Recharger systemd
sudo systemctl daemon-reload

# Activer le service au démarrage
sudo systemctl enable gunicorn-skyjo

# Démarrer le service
sudo systemctl start gunicorn-skyjo

# Vérifier le statut
sudo systemctl status gunicorn-skyjo

# Devrait afficher "active (running)"
```

### 10. Tester l'application localement

```bash
# Tester que l'application répond
curl http://127.0.0.1:8000/

# Devrait retourner du HTML
```

---

## Configuration Apache

### Option A : Sous-domaine dédié (recommandé)

#### 1. Créer le VirtualHost

```bash
sudo nano /etc/apache2/sites-available/skyjo.conf
```

Contenu :

```apache
<VirtualHost *:80>
    ServerName skyjo.votre-domaine.com
    ServerAdmin admin@votre-domaine.com

    # Proxy vers Gunicorn
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    # Logs
    ErrorLog ${APACHE_LOG_DIR}/skyjo_error.log
    CustomLog ${APACHE_LOG_DIR}/skyjo_access.log combined

    # Headers de sécurité
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
</VirtualHost>
```

### Option B : Sous-répertoire d'un site existant

Si vous préférez `votre-domaine.com/skyjo` :

```bash
sudo nano /etc/apache2/sites-available/votre-site-existant.conf
```

Ajouter dans le VirtualHost existant :

```apache
    # Skyjo sous /skyjo
    ProxyPass /skyjo http://127.0.0.1:8000/
    ProxyPassReverse /skyjo http://127.0.0.1:8000/

    <Location /skyjo>
        ProxyPreserveHost On
    </Location>
```

### 2. Activer les modules Apache

```bash
# Activer les modules nécessaires
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo a2enmod ssl  # Pour SSL plus tard

# Vérifier la configuration
sudo apachectl configtest

# Devrait afficher "Syntax OK"
```

### 3. Activer le site

```bash
# Option A (sous-domaine)
sudo a2ensite skyjo.conf

# Recharger Apache
sudo systemctl reload apache2

# Vérifier le statut
sudo systemctl status apache2
```

### 4. Tester l'accès HTTP

Ouvrir un navigateur et aller sur :
- Option A : `http://skyjo.votre-domaine.com`
- Option B : `http://votre-domaine.com/skyjo`

⚠️ **Important** : À ce stade, c'est HTTP uniquement (pas sécurisé). On va ajouter SSL dans la section suivante.

---

## Configuration SSL

### 1. Obtenir un certificat Let's Encrypt

```bash
# Option A (sous-domaine)
sudo certbot --apache -d skyjo.votre-domaine.com

# Option B (sous-répertoire) - utiliser le domaine principal
sudo certbot --apache -d votre-domaine.com
```

### 2. Suivre les instructions de Certbot

Certbot va vous demander :
1. **Email** : Votre email pour les notifications
2. **Accepter les CGU** : Tapez `Y`
3. **Partager l'email** : `Y` ou `N` selon votre choix
4. **Redirection HTTP → HTTPS** : Tapez `2` (recommandé)

### 3. Vérifier le renouvellement automatique

```bash
# Tester le renouvellement (dry-run)
sudo certbot renew --dry-run

# Le renouvellement automatique est configuré dans :
sudo systemctl status certbot.timer
```

### 4. Tester l'accès HTTPS

Ouvrir un navigateur et aller sur :
- Option A : `https://skyjo.votre-domaine.com`
- Option B : `https://votre-domaine.com/skyjo`

Le cadenas vert doit être visible ✅

---

## Configuration DNS

### Chez Ionos (ou autre registrar)

#### Option A : Sous-domaine

1. Se connecter à l'espace client Ionos
2. Aller dans **Domaines & SSL**
3. Cliquer sur votre domaine
4. Aller dans **DNS**
5. Cliquer sur **Ajouter un enregistrement**
6. Configurer :
   - **Type** : A
   - **Nom d'hôte** : `skyjo`
   - **Pointe vers** : `IP.DE.VOTRE.VPS`
   - **TTL** : `3600` (1 heure)
7. Sauvegarder

#### Option B : Sous-répertoire

Pas de configuration DNS nécessaire si vous utilisez un domaine existant.

### Propagation DNS

La propagation DNS peut prendre de quelques minutes à 48h. Pour vérifier :

```bash
# Vérifier la résolution DNS
dig skyjo.votre-domaine.com

# ou
nslookup skyjo.votre-domaine.com
```

---

## Scripts de maintenance

### Script de déploiement

Créer `/var/www/skyjo/deploy.sh` :

```bash
sudo nano /var/www/skyjo/deploy.sh
```

Contenu :

```bash
#!/bin/bash
echo "🚀 Déploiement Skyjo Manager"
echo "================================"

# Aller dans le répertoire
cd /var/www/skyjo

# Backup de la base de données
if [ -f skyjo.db ]; then
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).db"
    cp skyjo.db "$BACKUP_FILE"
    echo "✅ Backup créé : $BACKUP_FILE"
fi

# Mise à jour du code depuis GitHub
echo "📥 Récupération du code..."
sudo -u www-data git pull origin main

if [ $? -ne 0 ]; then
    echo "❌ Erreur lors du git pull"
    exit 1
fi

# Mise à jour des dépendances Python
echo "📦 Mise à jour des dépendances..."
sudo -u www-data venv/bin/pip install -r requirements.txt

# Redémarrage du service
echo "🔄 Redémarrage du service..."
sudo systemctl restart gunicorn-skyjo

# Attendre un peu
sleep 2

# Vérification
if systemctl is-active --quiet gunicorn-skyjo; then
    echo "✅ Skyjo Manager est en ligne !"
    echo "🌐 Accessible sur : https://skyjo.votre-domaine.com"
else
    echo "❌ Erreur : le service n'a pas démarré correctement"
    echo "📋 Consulter les logs :"
    echo "   sudo journalctl -u gunicorn-skyjo -n 50"
    exit 1
fi

echo "================================"
echo "✨ Déploiement terminé avec succès"
```

Rendre le script exécutable :

```bash
sudo chmod +x /var/www/skyjo/deploy.sh
```

**Utilisation** :

```bash
sudo /var/www/skyjo/deploy.sh
```

### Script de backup

Créer `/usr/local/bin/backup-skyjo.sh` :

```bash
sudo nano /usr/local/bin/backup-skyjo.sh
```

Contenu :

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/skyjo"
DATE=$(date +%Y%m%d_%H%M%S)

# Créer le répertoire de backup
mkdir -p "$BACKUP_DIR"

# Backup de la base de données
cp /var/www/skyjo/skyjo.db "$BACKUP_DIR/skyjo_$DATE.db"

# Garder seulement les 30 derniers backups
cd "$BACKUP_DIR"
ls -t | tail -n +31 | xargs -r rm

echo "✅ Backup créé : $BACKUP_DIR/skyjo_$DATE.db"
```

Rendre exécutable :

```bash
sudo chmod +x /usr/local/bin/backup-skyjo.sh
```

**Automatiser les backups** (quotidien à 3h du matin) :

```bash
sudo crontab -e
```

Ajouter :

```cron
0 3 * * * /usr/local/bin/backup-skyjo.sh
```

---

## Dépannage

### Le service ne démarre pas

```bash
# Vérifier le statut
sudo systemctl status gunicorn-skyjo

# Consulter les logs systemd
sudo journalctl -u gunicorn-skyjo -n 100

# Consulter les logs Gunicorn
sudo tail -f /var/log/gunicorn/skyjo_error.log

# Vérifier les permissions
ls -la /var/www/skyjo/
```

### Erreur 502 Bad Gateway

Le service Gunicorn n'est pas démarré ou inaccessible :

```bash
# Redémarrer le service
sudo systemctl restart gunicorn-skyjo

# Vérifier qu'il écoute sur le bon port
sudo netstat -tlnp | grep 8000
```

### Erreur 403 Forbidden

Problème de permissions :

```bash
# Rétablir les permissions
sudo chown -R www-data:www-data /var/www/skyjo
sudo chmod 750 /var/www/skyjo
```

### Base de données verrouillée

```bash
# Vérifier les permissions de la DB
ls -la /var/www/skyjo/skyjo.db
sudo chown www-data:www-data /var/www/skyjo/skyjo.db
sudo chmod 640 /var/www/skyjo/skyjo.db
```

### Code d'accès refusé

Vérifier que les codes sont bien définis dans `app.py` :

```python
ACCESS_CODE_INTERNAL = '1666'  # Accès complet
ACCESS_CODE_EXTERNAL = '1664'  # Accès limité
```

### Erreur après mise à jour

Restaurer le backup :

```bash
cd /var/www/skyjo
sudo -u www-data cp backup_YYYYMMDD_HHMMSS.db skyjo.db
sudo systemctl restart gunicorn-skyjo
```

---

## Commandes utiles

```bash
# Redémarrer l'application
sudo systemctl restart gunicorn-skyjo

# Voir les logs en temps réel
sudo journalctl -u gunicorn-skyjo -f

# Voir les logs Apache
sudo tail -f /var/log/apache2/skyjo_error.log

# Tester la configuration Apache
sudo apachectl configtest

# Recharger Apache
sudo systemctl reload apache2

# Vérifier l'utilisation des ressources
htop
```

---

## Checklist de mise en production

- [ ] Python 3.10+ installé
- [ ] Apache et modules proxy activés
- [ ] Git installé
- [ ] Dépôt cloné dans /var/www/skyjo
- [ ] Environnement virtuel créé et dépendances installées
- [ ] Fichier .env configuré avec FLASK_SECRET
- [ ] Permissions correctes (www-data)
- [ ] Service gunicorn-skyjo actif
- [ ] VirtualHost Apache configuré
- [ ] DNS configuré et propagé
- [ ] SSL activé avec Let's Encrypt
- [ ] Application accessible en HTTPS
- [ ] Codes d'accès 1666 et 1664 fonctionnels
- [ ] Script de déploiement créé
- [ ] Backups automatiques configurés

---

**Félicitations !** 🎉 Votre application Skyjo Manager est maintenant en production !
