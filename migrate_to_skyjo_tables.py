#!/usr/bin/env python3
"""
Script de migration : renommer les tables Skyjo pour supporter une architecture multi-jeux

Changements effectués :
  - games → skyjo_games
  - players → skyjo_players
  - rounds → skyjo_rounds

⚠️ À utiliser sur une COPIE de la DB avant déploiement en prod !
"""

import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path

DB_PATH = 'skyjo.db'

def backup_db():
    """Créer un backup de la DB avant migration."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'{DB_PATH}.backup_{timestamp}'
    shutil.copy2(DB_PATH, backup_path)
    print(f"✓ Backup créé : {backup_path}")
    return backup_path

def get_db():
    """Connexion à la DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def table_exists(conn, table_name):
    """Vérifier si une table existe."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def rename_table(conn, old_name, new_name):
    """Renommer une table."""
    if not table_exists(conn, old_name):
        print(f"⚠️  Table {old_name} n'existe pas (déjà migrée ?)")
        return False
    
    if table_exists(conn, new_name):
        print(f"⚠️  Table {new_name} existe déjà, skip")
        return False
    
    cursor = conn.cursor()
    cursor.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
    conn.commit()
    print(f"✓ Table renommée : {old_name} → {new_name}")
    return True

def migrate(db_path=DB_PATH, confirm=True):
    """Effectuer la migration."""
    print("=" * 60)
    print("Migration Skyjo Manager - Renommage tables")
    print("=" * 60)
    
    # Vérifier l'existence du fichier DB
    if not os.path.exists(db_path):
        print(f"✗ DB non trouvée : {db_path}")
        return False
    
    # Backup
    print("\n📋 Étape 1/3 : Backup...")
    backup_path = backup_db()
    
    # Connexion
    print("\n📋 Étape 2/3 : Renommage des tables...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # Renommer les tables
        migrations = [
            ('games', 'skyjo_games'),
            ('players', 'skyjo_players'),
            ('rounds', 'skyjo_rounds'),
        ]
        
        migrated_count = 0
        for old_name, new_name in migrations:
            if rename_table(conn, old_name, new_name):
                migrated_count += 1
        
        # Ajouter colonne rename_permission si nécessaire
        print("\n📋 Étape 3/3 : Vérifier colonnes...")
        cursor = conn.cursor()
        
        # Vérifier et ajouter rename_permission à player_groups
        cursor.execute("PRAGMA table_info(player_groups)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'rename_permission' not in columns:
            cursor.execute(
                "ALTER TABLE player_groups ADD COLUMN rename_permission TEXT DEFAULT 'owner'"
            )
            conn.commit()
            print("✓ Colonne rename_permission ajoutée à player_groups")
        else:
            print("✓ Colonne rename_permission existe déjà")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("✓ Migration TERMINÉE avec succès !")
        print("=" * 60)
        print(f"\nRésumé:")
        print(f"  - Tables renommées : {migrated_count}")
        print(f"  - Backup : {backup_path}")
        print(f"\n⚠️  Backup conservé pour rollback si nécessaire")
        return True
        
    except Exception as e:
        print(f"\n✗ Erreur lors de la migration : {e}")
        conn.close()
        print(f"💾 Rollback en cours...")
        shutil.copy2(backup_path, DB_PATH)
        print(f"✓ DB restaurée depuis backup")
        return False

if __name__ == '__main__':
    import sys
    
    # Demander confirmation
    print("⚠️  CE SCRIPT VA MODIFIER VOTRE BASE DE DONNÉES")
    print(f"DB cible : {DB_PATH}")
    print("\nUn backup sera créé avant la migration.")
    response = input("\nContinuer ? (oui/non) : ").strip().lower()
    
    if response not in ('oui', 'yes', 'y', 'o'):
        print("Migration annulée.")
        sys.exit(0)
    
    success = migrate()
    sys.exit(0 if success else 1)
