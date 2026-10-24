# Installation en production

Installation de Family Board Game sur un VPS Ubuntu/Debian, derrière Apache.
Configuration actuelle : `digital-pragma.fr`, application dans `/var/www/skyjo`, Gunicorn sur `127.0.0.1:8000`.

## 1. Prérequis

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip apache2 git certbot python3-certbot-apache
sudo a2enmod proxy proxy_http headers ssl
```

## 2. Code et environnement Python

```bash
cd /var/www
sudo git clone https://github.com/AmandineGit/skyjo-manager.git skyjo
cd skyjo

sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt

sudo cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # à reporter dans FLASK_SECRET
sudo nano .env

sudo chown -R www-data:www-data /var/www/skyjo
sudo chmod 640 .env
```

La base `skyjo.db` est créée automatiquement au premier démarrage.

## 3. Service Gunicorn

`/etc/systemd/system/gunicorn-skyjo.service` :

```ini
[Unit]
Description=Gunicorn - Family Board Game
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/skyjo
EnvironmentFile=/var/www/skyjo/.env
Environment="PATH=/var/www/skyjo/venv/bin"
ExecStart=/var/www/skyjo/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/gunicorn/skyjo_access.log \
    --error-logfile /var/log/gunicorn/skyjo_error.log \
    app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /var/log/gunicorn && sudo chown www-data:www-data /var/log/gunicorn
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn-skyjo
curl -I http://127.0.0.1:8000/login   # doit répondre 200
```

## 4. Apache

Dans le VirtualHost du site, deux règles pointent vers la même instance Gunicorn :

```apache
ProxyPreserveHost On

# Hub et pages communes
ProxyPass        /familyboardgame http://127.0.0.1:8000/
ProxyPassReverse /familyboardgame http://127.0.0.1:8000/

# Jeu Skyjo (blueprint monté sur /play côté Flask)
ProxyPass        /skyjo http://127.0.0.1:8000/play
ProxyPassReverse /skyjo http://127.0.0.1:8000/play
```

Quand un nouveau jeu aura son propre préfixe public, il faudra ajouter une paire de règles du même type.

```bash
sudo apachectl configtest
sudo systemctl reload apache2
sudo certbot --apache -d digital-pragma.fr   # si le certificat n'existe pas encore
```

## 5. Mises à jour

Depuis `/var/www/skyjo` :

```bash
./deploy.sh
```

Le script sauvegarde la base (`backup_AAAAMMJJ_HHMMSS.db`), fait un `git pull`, met à jour les dépendances et redémarre `gunicorn-skyjo`.

Restaurer une sauvegarde :

```bash
sudo systemctl stop gunicorn-skyjo
sudo -u www-data cp backup_AAAAMMJJ_HHMMSS.db skyjo.db
sudo systemctl start gunicorn-skyjo
```

## 6. Premier compte administrateur

Le compte admin est celui dont l'email est `admin@skyjo.local` (voir `core/auth.py`). Créez-le via la page d'inscription, puis changez son mot de passe si nécessaire.

## Dépannage

| Symptôme                 | Piste                                                                                       |
|--------------------------|----------------------------------------------------------------------------------------------|
| Service qui ne démarre pas | `sudo journalctl -u gunicorn-skyjo -n 50` et `/var/log/gunicorn/skyjo_error.log`          |
| 502 Bad Gateway          | Gunicorn arrêté ou sur un autre port : `sudo ss -tlnp \| grep 8000`                          |
| 404 sur `/skyjo/…`       | Vérifier que la règle Apache `/skyjo` pointe bien vers `/play`                               |
| Base verrouillée / en lecture seule | `sudo chown www-data:www-data skyjo.db` (et le dossier, pour le journal SQLite)     |

```bash
sudo systemctl restart gunicorn-skyjo
sudo journalctl -u gunicorn-skyjo -f
sudo tail -f /var/log/apache2/error.log
```
