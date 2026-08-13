# 📋 Guide de Migration - Phase 1.5

## Objectif
Passer de l'ancienne architecture monolithique à une architecture modulaire multi-jeux.

### Changements principaux
- ✅ Architecture modulaire : `core/`, `games/skyjo/`
- ✅ Blueprint Skyjo accessible via `/skyjo/`
- ✅ Renommage tables DB : games → skyjo_games, players → skyjo_players, rounds → skyjo_rounds
- ✅ Nouvelles features : group renaming avec permission checks

---

## 🚀 Processus de Migration

### Préparation

1. **Backup complet avant de commencer** ⚠️
   ```bash
   cp skyjo.db skyjo.db.backup_$(date +%Y%m%d_%H%M%S)
   ```

2. **Vérifier les scripts**
   ```bash
   ls -la migrate_to_skyjo_tables.py
   ls -la update_skyjo_queries.py
   ls -la test_migration.py
   ```

---

### Étape 1 : Migration de la Base de Données

```bash
source venv/bin/activate
python3 migrate_to_skyjo_tables.py
```

**Que fait ce script :**
- Crée un backup de skyjo.db
- Renomme `games` → `skyjo_games`
- Renomme `players` → `skyjo_players`
- Renomme `rounds` → `skyjo_rounds`
- Ajoute colonne `rename_permission` à `player_groups`
- Affiche un rapport détaillé

**Vérification :**
```bash
sqlite3 skyjo.db ".tables"
# Doit afficher : skyjo_games, skyjo_players, skyjo_rounds (pas games, players, rounds)
```

**En cas de problème :**
Le script crée un backup avec timestamp. Restaurer :
```bash
cp skyjo.db.backup_YYYYMMDD_HHMMSS skyjo.db
```

---

### Étape 2 : Mise à Jour des Requêtes SQL

```bash
python3 update_skyjo_queries.py
```

**Que fait ce script :**
- Met à jour app.py (~48 remplacements)
- Met à jour games/skyjo/routes.py (~? remplacements)
- Crée des backups `.backup_YYYYMMDD_HHMMSS` de chaque fichier
- Affiche un rapport détaillé

**Remplacements effectués :**
- `FROM games` → `FROM skyjo_games`
- `FROM players` → `FROM skyjo_players`
- `FROM rounds` → `FROM skyjo_rounds`
- `JOIN games` → `JOIN skyjo_games` (etc.)
- `DELETE FROM games` → `DELETE FROM skyjo_games` (etc.)
- `UPDATE games` → `UPDATE skyjo_games` (etc.)
- Subqueries IN, EXISTS, etc.

**Vérification :**
```bash
grep -c "FROM games" app.py        # Doit être 0 (ou que des commentaires)
grep -c "FROM skyjo_games" app.py  # Doit être ~19
```

**En cas de problème :**
Restaurer les backups :
```bash
mv app.py.backup_YYYYMMDD_HHMMSS app.py
mv games/skyjo/routes.py.backup_YYYYMMDD_HHMMSS games/skyjo/routes.py
```

---

### Étape 3 : Tests en Local

```bash
# Démarrer le serveur en dev
python3 app.py

# Dans un autre terminal
curl http://localhost:5000/
```

**Tests critiques :**
- [ ] Login fonctionne
- [ ] Hub s'affiche (/)
- [ ] Créer partie Skyjo
- [ ] Voir les parties (stats)
- [ ] Renommer groupe avec permissions
- [ ] Pas d'erreurs SQL dans les logs

---

### Étape 4 : Tests Automatisés (optionnel)

```bash
# Tester la migration sur une copie
python3 test_migration.py

# Affichera les changements et créera skyjo_test_migration.db
```

---

### Étape 5 : Déploiement en Production

```bash
# Sur le serveur prod
cd /path/to/skyjo-manager

# Backup prod
cp skyjo.db skyjo.db.backup_prod_$(date +%Y%m%d_%H%M%S)

# Migration DB
source venv/bin/activate
python3 migrate_to_skyjo_tables.py

# Mise à jour requêtes SQL
python3 update_skyjo_queries.py

# Redémarrer le service Gunicorn
sudo systemctl restart skyjo-manager

# Vérifier les logs
journalctl -u skyjo-manager -f

# Tester en prod
curl https://digital-pragma.fr/skyjo/
```

**Vérifications :**
- [ ] Pas d'erreurs 500
- [ ] Login fonctionne
- [ ] Parties Skyjo sont visibles
- [ ] Stats s'affichent
- [ ] Groupes peuvent être renommés

---

## 🔄 Rollback en Cas de Problème

**Rapide (avant redémarrage service):**
```bash
# DB
cp skyjo.db.backup_prod_YYYYMMDD_HHMMSS skyjo.db

# Code
mv app.py.backup_YYYYMMDD_HHMMSS app.py
mv games/skyjo/routes.py.backup_YYYYMMDD_HHMMSS games/skyjo/routes.py

# Redémarrer
sudo systemctl restart skyjo-manager
```

**Complet (revenir au commit avant):**
```bash
# Backup les changes
git stash

# Reset à la version avant migration
git checkout HEAD~1

# Restaurer DB backup
cp skyjo.db.backup_prod_YYYYMMDD_HHMMSS skyjo.db
```

---

## 📊 État Avant/Après

### Avant
```sql
Tables: users, player_groups, group_members, group_users
        games, players, rounds, game_rules
```

### Après
```sql
Tables: users, player_groups, group_members, group_users
        skyjo_games, skyjo_players, skyjo_rounds, game_rules
        
Colonnes: player_groups.rename_permission (contrôle permissions renaming)
```

---

## ✅ Checklist Finale

- [ ] Backup prod créé
- [ ] migrate_to_skyjo_tables.py exécuté ✓
- [ ] update_skyjo_queries.py exécuté ✓
- [ ] Pas d'erreurs dans les scripts
- [ ] Tests locaux OK
- [ ] Service redémarré
- [ ] Tests en prod OK
- [ ] Cleanup backups (optionnel, pour économiser l'espace)

---

## 📞 Support

En cas de problème :
1. Vérifier les logs : `journalctl -u skyjo-manager`
2. Rollback à une version stable
3. Analyser les erreurs SQL (PRAGMA table_info, etc.)
4. Contacter le développeur

---

**Durée estimée :** 10-15 minutes (dont tests)  
**Risque :** Faible (backups automatiques, scripts idempotents)  
**Impact utilisateur :** Aucun (migration transparent)
