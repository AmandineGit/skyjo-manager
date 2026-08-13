#!/usr/bin/env python3
"""
Test du script de migration sur une copie de DB
"""

import sqlite3
import shutil
import os
from pathlib import Path

def test_migration():
    """Tester la migration sur skyjo_test.db"""
    
    test_db = 'skyjo_test_migration.db'
    
    # Copier skyjo.db pour le test
    if os.path.exists(test_db):
        os.remove(test_db)
    shutil.copy2('skyjo.db', test_db)
    print(f"✓ Copie créée : {test_db}")
    
    # État avant migration
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables_before = [row[0] for row in cursor.fetchall()]
    print(f"\n📊 Tables AVANT : {tables_before}")
    
    # Vérifier colonnes
    cursor.execute("PRAGMA table_info(player_groups)")
    cols_before = {row[1] for row in cursor.fetchall()}
    print(f"Colonnes player_groups : {sorted(cols_before)}")
    
    conn.close()
    
    # Effectuer les migrations
    print("\n🔄 Effectuant les migrations...")
    conn = sqlite3.connect(test_db)
    
    try:
        # Renommer les tables
        migrations = [
            ('games', 'skyjo_games'),
            ('players', 'skyjo_players'),
            ('rounds', 'skyjo_rounds'),
        ]
        
        for old_name, new_name in migrations:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (old_name,)
            )
            if cursor.fetchone():
                cursor.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
                print(f"✓ {old_name} → {new_name}")
            else:
                print(f"⚠️  {old_name} n'existe pas (déjà migrée ?)")
        
        # Ajouter rename_permission
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(player_groups)")
        cols = {row[1] for row in cursor.fetchall()}
        
        if 'rename_permission' not in cols:
            cursor.execute(
                "ALTER TABLE player_groups ADD COLUMN rename_permission TEXT DEFAULT 'owner'"
            )
            print("✓ Colonne rename_permission ajoutée")
        else:
            print("✓ Colonne rename_permission existe déjà")
        
        conn.commit()
        
        # État après migration
        print("\n✓ Migration terminée!")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables_after = [row[0] for row in cursor.fetchall()]
        print(f"📊 Tables APRÈS : {tables_after}")
        
        # Vérifier les changements
        print(f"\n✅ Validations :")
        print(f"  ✓ skyjo_games existe : {'skyjo_games' in tables_after}")
        print(f"  ✓ skyjo_players existe : {'skyjo_players' in tables_after}")
        print(f"  ✓ skyjo_rounds existe : {'skyjo_rounds' in tables_after}")
        print(f"  ✓ games n'existe pas : {'games' not in tables_after}")
        print(f"  ✓ players n'existe pas : {'players' not in tables_after}")
        print(f"  ✓ rounds n'existe pas : {'rounds' not in tables_after}")
        
        cursor.execute("PRAGMA table_info(player_groups)")
        cols_after = {row[1] for row in cursor.fetchall()}
        print(f"  ✓ rename_permission existe : {'rename_permission' in cols_after}")
        
        conn.close()
        
        print(f"\n💾 DB de test conservée : {test_db}")
        return True
        
    except Exception as e:
        print(f"✗ Erreur : {e}")
        conn.close()
        return False

if __name__ == '__main__':
    success = test_migration()
    exit(0 if success else 1)
