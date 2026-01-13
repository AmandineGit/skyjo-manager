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
    echo "🌐 Accessible sur votre domaine configuré"
else
    echo "❌ Erreur : le service n'a pas démarré correctement"
    echo "📋 Consulter les logs :"
    echo "   sudo journalctl -u gunicorn-skyjo -n 50"
    exit 1
fi

echo "================================"
echo "✨ Déploiement terminé avec succès"
