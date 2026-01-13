# 🚀 Démarrage rapide - Skyjo Manager

## 📦 1. Mettre sur GitHub (5 minutes)

```bash
cd /var/www/skyjo

# Nettoyer les anciens fichiers (optionnel)
rm -f AJOUT_REGLES.md README_REGLES.md CHANGELOG_REGLES.md README_STATS_V2.md \
      CHANGELOG_METRO_TILES.md MOBILE_OPTIMIZATIONS.md BACK_BUTTON_UPDATE.md \
      HOME_UX_IMPROVEMENTS.md FICHIERS_A_SUPPRIMER.txt \
      QUICK_GUIDE_STATS.txt QUICK_START_REGLES.txt

# Initialiser Git
git init
git add .
git commit -m "Initial commit - Skyjo Manager v1.0.0"

# Créer un dépôt sur GitHub (via navigateur)
# https://github.com/new
# Nom: skyjo-manager
# Privé: OUI

# Pousser vers GitHub (remplacer TON-USERNAME)
git remote add origin https://github.com/TON-USERNAME/skyjo-manager.git
git branch -M main
git push -u origin main
```

## 🌐 2. Déployer sur VPS Ionos (20 minutes)

```bash
# SSH vers ton VPS
ssh ton-user@ton-vps.com

# Cloner le dépôt
cd /var/www
sudo git clone https://github.com/TON-USERNAME/skyjo-manager.git skyjo
cd skyjo

# Installer
sudo python3 -m venv venv
sudo chown -R www-data:www-data venv
sudo -u www-data venv/bin/pip install -r requirements.txt

# Configurer
sudo cp .env.example .env
sudo nano .env
# Modifier FLASK_SECRET avec une clé aléatoire

# Permissions
sudo chown -R www-data:www-data /var/www/skyjo
sudo chmod 750 /var/www/skyjo
sudo chmod 640 /var/www/skyjo/.env
```

**Créer le service** `/etc/systemd/system/gunicorn-skyjo.service` :
```ini
[Unit]
Description=Gunicorn instance to serve Skyjo
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/skyjo
Environment="PATH=/var/www/skyjo/venv/bin"
ExecStart=/var/www/skyjo/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
# Démarrer
sudo mkdir -p /var/log/gunicorn
sudo chown www-data:www-data /var/log/gunicorn
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-skyjo
sudo systemctl start gunicorn-skyjo
```

**Configurer Apache** `/etc/apache2/sites-available/skyjo.conf` :
```apache
<VirtualHost *:80>
    ServerName skyjo.ton-domaine.com
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

```bash
# Activer
sudo a2enmod proxy proxy_http headers
sudo a2ensite skyjo
sudo systemctl reload apache2

# SSL
sudo certbot --apache -d skyjo.ton-domaine.com
```

**Configurer DNS chez Ionos** :
- Type: A
- Nom: skyjo
- Valeur: IP de ton VPS

## 🔄 3. Mettre à jour (1 minute)

```bash
# Sur VPS
sudo /var/www/skyjo/deploy.sh
```

## 🎯 URLs

- **Code interne** : 1666 (accès complet)
- **Code externe** : 1664 (accès limité)
- **Production** : https://skyjo.ton-domaine.com

## 📚 Documentation complète

- `README.md` - Vue d'ensemble
- `INSTALL.md` - Installation détaillée
- `CHANGELOG.md` - Historique
- `STRUCTURE.md` - Architecture
- `RECAP_GITHUB.md` - Guide GitHub complet

---

**C'est tout !** 🎉
