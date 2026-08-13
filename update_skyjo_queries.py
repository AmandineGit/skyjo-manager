#!/usr/bin/env python3
"""
Script de mise à jour : remplacer les table names après migration DB

À exécuter APRÈS migrate_to_skyjo_tables.py :
  1. python3 migrate_to_skyjo_tables.py
  2. python3 update_skyjo_queries.py

Remplace dans les fichiers Python :
  - FROM games     → FROM skyjo_games
  - FROM players   → FROM skyjo_players
  - FROM rounds    → FROM skyjo_rounds

Aussi dans les templates si nécessaire.
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

# Fichiers à mettre à jour
FILES_TO_UPDATE = [
    'app.py',
    'games/skyjo/routes.py',
]

# Remplacements à effectuer (attention à la casse et contexte)
REPLACEMENTS = [
    # Table names dans les FROM clauses
    (r'\bFROM games\b', 'FROM skyjo_games'),
    (r'\bFROM players\b', 'FROM skyjo_players'),
    (r'\bFROM rounds\b', 'FROM skyjo_rounds'),
    
    # Table names dans les JOIN clauses
    (r'\bJOIN games\b', 'JOIN skyjo_games'),
    (r'\bJOIN players\b', 'JOIN skyjo_players'),
    (r'\bJOIN rounds\b', 'JOIN skyjo_rounds'),
    
    # Table names dans les DELETE/UPDATE clauses
    (r'\bDELETE FROM games\b', 'DELETE FROM skyjo_games'),
    (r'\bDELETE FROM players\b', 'DELETE FROM skyjo_players'),
    (r'\bDELETE FROM rounds\b', 'DELETE FROM skyjo_rounds'),
    
    (r'\bUPDATE games\b', 'UPDATE skyjo_games'),
    (r'\bUPDATE players\b', 'UPDATE skyjo_players'),
    (r'\bUPDATE rounds\b', 'UPDATE skyjo_rounds'),
    
    # Table names dans les IN () subqueries
    (r'\(SELECT.*?FROM games\b', lambda m: m.group(0).replace('FROM games', 'FROM skyjo_games')),
    (r'\(SELECT.*?FROM players\b', lambda m: m.group(0).replace('FROM players', 'FROM skyjo_players')),
    (r'\(SELECT.*?FROM rounds\b', lambda m: m.group(0).replace('FROM rounds', 'FROM skyjo_rounds')),
]

def create_backup(filepath):
    """Créer un backup du fichier avant modification."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'{filepath}.backup_{timestamp}'
    shutil.copy2(filepath, backup_path)
    return backup_path

def update_file(filepath):
    """Mettre à jour un fichier avec les remplacements."""
    print(f"\n📝 Traitement : {filepath}")
    
    if not os.path.exists(filepath):
        print(f"⚠️  Fichier non trouvé : {filepath}")
        return 0, []
    
    # Lire le fichier
    with open(filepath, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    updated_content = original_content
    changes = []
    
    # Appliquer les remplacements
    for pattern, replacement in REPLACEMENTS:
        if callable(replacement):
            # Si c'est une fonction, l'utiliser
            matches = list(re.finditer(pattern, updated_content, re.IGNORECASE))
            for match in matches:
                old_text = match.group(0)
                new_text = replacement(match)
                if old_text != new_text:
                    updated_content = updated_content.replace(old_text, new_text, 1)
                    changes.append(f"  ✓ {old_text} → {new_text}")
        else:
            # Sinon utiliser le remplacement simple
            count = len(re.findall(pattern, updated_content, re.IGNORECASE))
            if count > 0:
                updated_content = re.sub(pattern, replacement, updated_content, flags=re.IGNORECASE)
                changes.append(f"  ✓ {pattern} → {replacement} ({count}x)")
    
    # Écrire si des changements
    if updated_content != original_content:
        # Backup d'abord
        backup_path = create_backup(filepath)
        print(f"  💾 Backup : {backup_path}")
        
        # Écrire le fichier
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"  ✓ {len(changes)} remplacement(s)")
        for change in changes:
            print(change)
        
        return len(changes), backup_path
    else:
        print(f"  ℹ️  Aucun changement nécessaire")
        return 0, None

def update_all_files():
    """Mettre à jour tous les fichiers."""
    print("=" * 60)
    print("Mise à jour des requêtes SQL - Migration vers tables skyjo_*")
    print("=" * 60)
    
    total_changes = 0
    backups = []
    
    for filepath in FILES_TO_UPDATE:
        changes, backup = update_file(filepath)
        total_changes += changes
        if backup:
            backups.append(backup)
    
    # Résumé
    print("\n" + "=" * 60)
    if total_changes > 0:
        print(f"✓ Mise à jour TERMINÉE")
        print(f"  - Fichiers modifiés : {len([f for f in FILES_TO_UPDATE if os.path.exists(f)])}")
        print(f"  - Total remplacements : {total_changes}")
        print(f"  - Backups créés : {len(backups)}")
        if backups:
            print(f"\n💾 Backups (pour rollback si nécessaire):")
            for backup in backups:
                print(f"  - {backup}")
        print("\n✅ Vous pouvez maintenant tester l'app !")
    else:
        print(f"ℹ️  Aucun changement n'était nécessaire")
    print("=" * 60)
    
    return total_changes > 0

if __name__ == '__main__':
    import sys
    
    print("⚠️  CE SCRIPT MET À JOUR LES REQUÊTES SQL")
    print("À exécuter APRÈS migrate_to_skyjo_tables.py\n")
    
    response = input("Continuer ? (oui/non) : ").strip().lower()
    
    if response not in ('oui', 'yes', 'y', 'o'):
        print("Mise à jour annulée.")
        sys.exit(0)
    
    success = update_all_files()
    sys.exit(0 if success else 1)
