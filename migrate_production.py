#!/usr/bin/env python3
"""
Script de migration Skyjo - Production
======================================
Ce script migre la base de données existante vers le nouveau schéma avec :
- Création des tables users, player_groups, group_members, group_users
- Création d'un compte administrateur pour gérer l'historique
- Création automatique de groupes basés sur les combinaisons de joueurs existantes
- Association des parties existantes à leurs groupes respectifs

Usage:
    python3 migrate_production.py [--dry-run] [--db-path /chemin/vers/skyjo.db]

Options:
    --dry-run    Affiche les actions sans les exécuter
    --db-path    Chemin vers la base de données (défaut: skyjo.db)
"""

import sqlite3
import argparse
import hashlib
import os
from datetime import datetime
from collections import defaultdict

# Configuration par défaut
DEFAULT_DB_PATH = 'skyjo.db'
ADMIN_EMAIL = 'admin@skyjo.local'
ADMIN_PASSWORD = 'changeme123'  # À CHANGER après migration !


def get_password_hash(password):
    """Hash du mot de passe compatible avec Werkzeug."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)


def analyze_database(conn):
    """Analyse la base de données existante."""
    cur = conn.cursor()

    print("\n" + "="*60)
    print("ANALYSE DE LA BASE DE DONNÉES")
    print("="*60)

    # Tables existantes
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\nTables existantes: {', '.join(tables)}")

    # Vérifier si migration déjà faite
    new_tables = ['users', 'player_groups', 'group_members', 'group_users']
    existing_new_tables = [t for t in new_tables if t in tables]
    if existing_new_tables:
        print(f"\n⚠️  Tables du nouveau schéma déjà présentes: {existing_new_tables}")

        # Vérifier si des données existent
        for table in existing_new_tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"   - {table}: {count} enregistrements")

        return None  # Migration déjà effectuée

    # Statistiques des parties
    cur.execute("SELECT COUNT(*) FROM games")
    total_games = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM rounds")
    total_rounds = cur.fetchone()[0]

    cur.execute("SELECT DISTINCT name FROM players ORDER BY name")
    all_players = [r[0] for r in cur.fetchall()]

    print(f"\nStatistiques actuelles:")
    print(f"  - Parties: {total_games}")
    print(f"  - Rounds: {total_rounds}")
    print(f"  - Joueurs uniques: {len(all_players)}")
    print(f"  - Noms: {', '.join(all_players)}")

    # Trouver les combinaisons de joueurs
    # Note: GROUP_CONCAT avec ORDER BY n'est pas supporté dans les anciennes versions de SQLite
    cur.execute('''
        SELECT game_id, GROUP_CONCAT(name) as player_combo
        FROM (SELECT game_id, name FROM players ORDER BY game_id, name)
        GROUP BY game_id
    ''')

    combos = defaultdict(list)
    for r in cur.fetchall():
        combos[r[1]].append(r[0])

    print(f"\nGroupes de joueurs détectés ({len(combos)}):")
    for combo, games in sorted(combos.items(), key=lambda x: -len(x[1])):
        print(f"  - {combo} ({len(games)} parties)")

    return {
        'tables': tables,
        'total_games': total_games,
        'total_rounds': total_rounds,
        'all_players': all_players,
        'player_combos': combos
    }


def create_new_tables(conn, dry_run=False):
    """Crée les nouvelles tables."""
    cur = conn.cursor()

    print("\n" + "="*60)
    print("CRÉATION DES NOUVELLES TABLES")
    print("="*60)

    tables_sql = [
        ("users", '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                player_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reset_token TEXT,
                reset_token_expires TEXT
            )
        '''),
        ("player_groups", '''
            CREATE TABLE IF NOT EXISTS player_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        '''),
        ("group_members", '''
            CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                user_id INTEGER,
                FOREIGN KEY (group_id) REFERENCES player_groups(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        '''),
        ("group_users", '''
            CREATE TABLE IF NOT EXISTS group_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                FOREIGN KEY (group_id) REFERENCES player_groups(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        '''),
    ]

    for table_name, sql in tables_sql:
        print(f"  Création de la table '{table_name}'...", end=" ")
        if not dry_run:
            cur.execute(sql)
            print("✓")
        else:
            print("[DRY-RUN]")

    # Ajouter colonnes à games si nécessaire
    cur.execute("PRAGMA table_info(games)")
    existing_cols = [r[1] for r in cur.fetchall()]

    if 'group_id' not in existing_cols:
        print(f"  Ajout de la colonne 'group_id' à 'games'...", end=" ")
        if not dry_run:
            cur.execute("ALTER TABLE games ADD COLUMN group_id INTEGER REFERENCES player_groups(id)")
            print("✓")
        else:
            print("[DRY-RUN]")

    if 'created_by' not in existing_cols:
        print(f"  Ajout de la colonne 'created_by' à 'games'...", end=" ")
        if not dry_run:
            cur.execute("ALTER TABLE games ADD COLUMN created_by INTEGER REFERENCES users(id)")
            print("✓")
        else:
            print("[DRY-RUN]")

    if not dry_run:
        conn.commit()


def create_admin_user(conn, dry_run=False):
    """Crée le compte administrateur."""
    cur = conn.cursor()

    print("\n" + "="*60)
    print("CRÉATION DU COMPTE ADMINISTRATEUR")
    print("="*60)

    print(f"  Email: {ADMIN_EMAIL}")
    print(f"  Mot de passe: {ADMIN_PASSWORD}")
    print(f"  ⚠️  CHANGEZ CE MOT DE PASSE APRÈS LA MIGRATION !")

    if not dry_run:
        password_hash = get_password_hash(ADMIN_PASSWORD)
        cur.execute('''
            INSERT INTO users (email, password_hash, display_name, created_at)
            VALUES (?, ?, 'Administrateur', ?)
        ''', (ADMIN_EMAIL, password_hash, datetime.now().isoformat()))
        admin_id = cur.lastrowid
        conn.commit()
        print(f"  Compte créé avec ID: {admin_id}")
        return admin_id
    else:
        print("  [DRY-RUN] Compte non créé")
        return 1


def create_groups_from_history(conn, analysis, admin_id, dry_run=False):
    """Crée les groupes basés sur l'historique des parties."""
    cur = conn.cursor()

    print("\n" + "="*60)
    print("CRÉATION DES GROUPES HISTORIQUES")
    print("="*60)

    combos = analysis['player_combos']
    group_mapping = {}  # combo -> group_id

    for i, (combo, game_ids) in enumerate(sorted(combos.items(), key=lambda x: -len(x[1])), 1):
        players = combo.split(',')

        # Générer un nom de groupe basé sur les joueurs
        if len(players) <= 3:
            group_name = " & ".join(players)
        else:
            group_name = f"{players[0]}, {players[1]} et {len(players)-2} autres"

        print(f"\n  Groupe {i}: '{group_name}'")
        print(f"    Joueurs: {', '.join(players)}")
        print(f"    Parties: {len(game_ids)}")

        if not dry_run:
            # Créer le groupe
            cur.execute('''
                INSERT INTO player_groups (name, created_by, created_at)
                VALUES (?, ?, ?)
            ''', (group_name, admin_id, datetime.now().isoformat()))
            group_id = cur.lastrowid

            # Ajouter les membres
            for player_name in players:
                cur.execute('''
                    INSERT INTO group_members (group_id, player_name)
                    VALUES (?, ?)
                ''', (group_id, player_name))

            # Associer l'admin au groupe
            cur.execute('''
                INSERT INTO group_users (group_id, user_id, role)
                VALUES (?, ?, 'owner')
            ''', (group_id, admin_id))

            group_mapping[combo] = group_id
            print(f"    → Groupe créé avec ID: {group_id}")
        else:
            group_mapping[combo] = i  # ID fictif pour dry-run
            print(f"    → [DRY-RUN] Groupe non créé")

    if not dry_run:
        conn.commit()

    return group_mapping


def associate_games_to_groups(conn, group_mapping, admin_id, dry_run=False):
    """Associe chaque partie à son groupe."""
    cur = conn.cursor()

    print("\n" + "="*60)
    print("ASSOCIATION DES PARTIES AUX GROUPES")
    print("="*60)

    # Récupérer toutes les parties avec leurs joueurs
    cur.execute('''
        SELECT game_id, GROUP_CONCAT(name) as player_combo
        FROM (SELECT game_id, name FROM players ORDER BY game_id, name)
        GROUP BY game_id
    ''')

    games_updated = 0
    for r in cur.fetchall():
        game_id = r[0]
        combo = r[1]
        group_id = group_mapping.get(combo)

        if group_id:
            if not dry_run:
                cur.execute('''
                    UPDATE games SET group_id = ?, created_by = ?
                    WHERE id = ?
                ''', (group_id, admin_id, game_id))
            games_updated += 1

    if not dry_run:
        conn.commit()

    print(f"  {games_updated} parties associées à leurs groupes")
    if dry_run:
        print("  [DRY-RUN] Aucune modification effectuée")


def verify_migration(conn):
    """Vérifie que la migration s'est bien passée."""
    cur = conn.cursor()

    print("\n" + "="*60)
    print("VÉRIFICATION DE LA MIGRATION")
    print("="*60)

    # Compter les éléments
    cur.execute("SELECT COUNT(*) FROM users")
    print(f"  Utilisateurs: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM player_groups")
    print(f"  Groupes: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM group_members")
    print(f"  Membres de groupes: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM group_users")
    print(f"  Accès aux groupes: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM games WHERE group_id IS NOT NULL")
    games_with_group = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM games")
    total_games = cur.fetchone()[0]
    print(f"  Parties avec groupe: {games_with_group}/{total_games}")

    if games_with_group == total_games:
        print("\n✅ Migration réussie !")
    else:
        print(f"\n⚠️  {total_games - games_with_group} parties sans groupe")


def main():
    parser = argparse.ArgumentParser(description='Migration Skyjo vers nouveau schéma')
    parser.add_argument('--dry-run', action='store_true', help='Affiche les actions sans les exécuter')
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH, help='Chemin vers la base de données')
    args = parser.parse_args()

    print("="*60)
    print("MIGRATION SKYJO - PRODUCTION")
    print("="*60)
    print(f"Base de données: {args.db_path}")
    print(f"Mode: {'DRY-RUN (simulation)' if args.dry_run else 'RÉEL'}")

    if not os.path.exists(args.db_path):
        print(f"\n❌ Erreur: Base de données non trouvée: {args.db_path}")
        return 1

    # Sauvegarder la base avant modification
    if not args.dry_run:
        backup_path = f"{args.db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n📦 Sauvegarde: {backup_path}")
        import shutil
        shutil.copy2(args.db_path, backup_path)

    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Analyser la base existante
        analysis = analyze_database(conn)

        if analysis is None:
            print("\n⚠️  La migration semble déjà avoir été effectuée.")
            print("Si vous voulez recommencer, supprimez les tables:")
            print("  users, player_groups, group_members, group_users")
            return 0

        if analysis['total_games'] == 0:
            print("\n⚠️  Aucune partie dans la base de données.")
            print("Création des tables uniquement...")
            create_new_tables(conn, args.dry_run)
            return 0

        # Confirmation
        if not args.dry_run:
            print("\n" + "="*60)
            response = input("Voulez-vous continuer la migration ? (oui/non): ")
            if response.lower() not in ['oui', 'o', 'yes', 'y']:
                print("Migration annulée.")
                return 0

        # Exécuter la migration
        create_new_tables(conn, args.dry_run)
        admin_id = create_admin_user(conn, args.dry_run)
        group_mapping = create_groups_from_history(conn, analysis, admin_id, args.dry_run)
        associate_games_to_groups(conn, group_mapping, admin_id, args.dry_run)

        if not args.dry_run:
            verify_migration(conn)

        print("\n" + "="*60)
        print("PROCHAINES ÉTAPES")
        print("="*60)
        print(f"1. Connectez-vous avec: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print("2. Changez le mot de passe admin via /profile")
        print("3. Les groupes peuvent être renommés via /groups/<id>")
        print("4. Créez de nouveaux comptes utilisateurs pour les autres joueurs")

        return 0

    finally:
        conn.close()


if __name__ == '__main__':
    exit(main())
