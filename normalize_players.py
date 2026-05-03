#!/usr/bin/env python3
"""
Fusion des joueurs avec des noms similaires
============================================
Cherche les noms quasi-identiques (accents, casse) dans group_members et players,
choisit un nom canonique, renomme partout, déduplique, et propage les user_id.

Usage:
    python3 normalize_players.py [--dry-run] [--db-path /chemin/vers/skyjo.db]
"""

import sqlite3
import argparse
import unicodedata
import os
import shutil
from datetime import datetime
from collections import defaultdict


def normalize_name(name):
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def choose_canonical(variants):
    """Préfère majuscule initiale + accents, puis longueur décroissante."""
    def score(name):
        has_upper = name[0].isupper() if name else False
        ascii_len = len(name.encode('ascii', 'ignore'))
        has_accents = ascii_len < len(name)
        return (has_upper, has_accents, len(name))
    return max(variants, key=score)


def find_duplicates(conn):
    """
    Retourne les groupes de noms similaires trouvés dans group_members ET players.
    """
    cur = conn.cursor()
    all_names = set()

    cur.execute('SELECT DISTINCT player_name FROM group_members WHERE player_name IS NOT NULL')
    all_names.update(row[0] for row in cur.fetchall())

    cur.execute('SELECT DISTINCT name FROM players WHERE name IS NOT NULL')
    all_names.update(row[0] for row in cur.fetchall())

    groups = defaultdict(set)
    for name in all_names:
        groups[normalize_name(name)].add(name)

    return {k: sorted(v) for k, v in groups.items() if len(v) > 1}


def rename_everywhere(conn, old_name, canonical, dry_run):
    cur = conn.cursor()

    cur.execute('SELECT COUNT(*) FROM players WHERE name = ?', (old_name,))
    pc = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM rounds WHERE player_name = ?', (old_name,))
    rc = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM group_members WHERE player_name = ?', (old_name,))
    mc = cur.fetchone()[0]

    print(f"    '{old_name}' -> '{canonical}'  "
          f"({pc} parties, {rc} rounds, {mc} membres de groupe)")

    if not dry_run:
        cur.execute('UPDATE players SET name = ? WHERE name = ?', (canonical, old_name))
        cur.execute('UPDATE rounds SET player_name = ? WHERE player_name = ?', (canonical, old_name))
        cur.execute('UPDATE group_members SET player_name = ? WHERE player_name = ?', (canonical, old_name))
        conn.commit()


def deduplicate_group_members(conn, dry_run):
    """
    Après renommage, un groupe peut avoir deux entrées pour le même joueur.
    Garde celle avec user_id (ou la plus ancienne) et supprime le doublon.
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT group_id, player_name, COUNT(*) as cnt
        FROM group_members
        GROUP BY group_id, player_name
        HAVING cnt > 1
    ''')
    dupes = cur.fetchall()

    if not dupes:
        print("    Aucun doublon dans group_members.")
        return

    for group_id, player_name, cnt in dupes:
        # user_id IS NOT NULL en premier, puis id croissant
        cur.execute('''
            SELECT id, user_id FROM group_members
            WHERE group_id = ? AND player_name = ?
            ORDER BY CASE WHEN user_id IS NULL THEN 1 ELSE 0 END, id ASC
        ''', (group_id, player_name))
        rows = cur.fetchall()
        keep_id = rows[0][0]
        delete_ids = [r[0] for r in rows[1:]]
        print(f"    Groupe {group_id}, '{player_name}': "
              f"garde id={keep_id}, supprime {delete_ids}")
        if not dry_run:
            for did in delete_ids:
                cur.execute('DELETE FROM group_members WHERE id = ?', (did,))

    if not dry_run:
        conn.commit()


def propagate_user_ids(conn, dry_run):
    """
    Si un joueur est lié à un compte dans un groupe mais pas dans un autre,
    propage le user_id aux entrées sans compte.
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT DISTINCT player_name, user_id
        FROM group_members
        WHERE user_id IS NOT NULL
    ''')
    linked = cur.fetchall()

    count = 0
    for player_name, user_id in linked:
        cur.execute('''
            SELECT COUNT(*) FROM group_members
            WHERE player_name = ? AND user_id IS NULL
        ''', (player_name,))
        n = cur.fetchone()[0]
        if n > 0:
            print(f"    '{player_name}' (user_id={user_id}): "
                  f"rattache {n} entrée(s) sans compte")
            if not dry_run:
                cur.execute('''
                    UPDATE group_members SET user_id = ?
                    WHERE player_name = ? AND user_id IS NULL
                ''', (user_id, player_name))
                count += n

    if not dry_run and count:
        conn.commit()

    if count == 0 and dry_run is False:
        print("    Aucune propagation nécessaire.")


def main():
    parser = argparse.ArgumentParser(description='Fusion des joueurs similaires')
    parser.add_argument('--dry-run', action='store_true',
                        help='Affiche les actions sans les exécuter')
    parser.add_argument('--db-path', default='skyjo.db',
                        help='Chemin vers la base de données')
    args = parser.parse_args()

    print("=" * 60)
    print("FUSION DES JOUEURS (noms similaires)")
    print("=" * 60)
    print(f"Base : {args.db_path}")
    print(f"Mode : {'DRY-RUN (simulation)' if args.dry_run else 'RÉEL'}\n")

    if not os.path.exists(args.db_path):
        print(f"Erreur : fichier introuvable : {args.db_path}")
        return 1

    if not args.dry_run:
        backup = f"{args.db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(args.db_path, backup)
        print(f"Sauvegarde créée : {backup}\n")

    conn = sqlite3.connect(args.db_path)

    # --- Détection ---
    duplicates = find_duplicates(conn)

    if not duplicates:
        print("Aucun doublon détecté.")
        conn.close()
        return 0

    print(f"{len(duplicates)} groupe(s) de noms similaires :\n")
    for variants in duplicates.values():
        canonical = choose_canonical(variants)
        others = [v for v in variants if v != canonical]
        print(f"  '{canonical}'  <--  {others}")

    # --- Confirmation ---
    if not args.dry_run:
        print()
        r = input("Appliquer la fusion ? (oui/non) : ").strip().lower()
        if r not in ('oui', 'o', 'yes', 'y'):
            print("Annulé.")
            conn.close()
            return 0

    # --- Renommage ---
    print("\n--- Renommage ---")
    for variants in duplicates.values():
        canonical = choose_canonical(variants)
        for v in variants:
            if v != canonical:
                rename_everywhere(conn, v, canonical, args.dry_run)

    # --- Déduplication group_members ---
    print("\n--- Déduplication group_members ---")
    deduplicate_group_members(conn, args.dry_run)

    # --- Propagation user_id ---
    print("\n--- Propagation des comptes utilisateurs ---")
    propagate_user_ids(conn, args.dry_run)

    conn.close()

    print()
    if args.dry_run:
        print("Dry-run terminé. Relancez sans --dry-run pour appliquer.")
    else:
        print("Fusion terminée.")
    return 0


if __name__ == '__main__':
    exit(main())
