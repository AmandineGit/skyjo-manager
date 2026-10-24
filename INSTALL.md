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

## 5. Déploiement automatique (GitHub Actions)

Chaque push sur `main` déclenche `.github/workflows/deploy.yml`, qui se connecte en SSH au VPS et :
1. sauvegarde `skyjo.db` dans `backups/skyjo_AAAAMMJJ_HHMMSS.db` (si la sauvegarde échoue, rien n'est déployé) ;
2. copie le code par rsync avec `--delete`, **sans jamais toucher** à : `*.db*`, `backups/`, `exports/`, `venv/`, `.env`, `.git` ; les fichiers de `images/` absents du dépôt sont conservés ;
3. redémarre `gunicorn-skyjo` et vérifie qu'il tourne.

### Prérequis sur le serveur (une seule fois)

L'utilisateur SSH (`REMOTE_USER`) doit pouvoir écrire dans `/var/www/skyjo`, lire la base et redémarrer le service :

```bash
# Accès en écriture par le groupe de l'utilisateur de déploiement (ici amandine)
sudo chgrp -R amandine /var/www/skyjo
sudo chmod -R g+rwX /var/www/skyjo
sudo find /var/www/skyjo -type d -exec chmod g+s {} +

# Redémarrage du service sans mot de passe, et uniquement cette commande
echo 'amandine ALL=(root) NOPASSWD: /usr/bin/systemctl restart gunicorn-skyjo' | sudo tee /etc/sudoers.d/skyjo-deploy
sudo chmod 440 /etc/sudoers.d/skyjo-deploy
sudo visudo -c
```

### Secrets GitHub

Dans le dépôt GitHub : *Settings → Secrets and variables → Actions*, mêmes secrets que pour les autres sites :
`SSH_PRIVATE_KEY`, `REMOTE_HOST`, `REMOTE_USER`.

### Dépendances Python

Le déploiement ne lance pas `pip install`. Si `requirements.txt` change :

```bash
cd /var/www/skyjo
sudo -u www-data venv/bin/pip install -r requirements.txt
sudo systemctl restart gunicorn-skyjo
```

### Restaurer une sauvegarde

```bash
sudo systemctl stop gunicorn-skyjo
sudo -u www-data cp backups/skyjo_AAAAMMJJ_HHMMSS.db skyjo.db
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
