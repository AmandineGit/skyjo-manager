#!/usr/bin/env python3
"""
Script de normalisation des noms de joueurs
============================================
Ce script fusionne les joueurs avec des noms similaires (accents, casse différente).

Usage:
    python3 normalize_players.py [--dry-run] [--db-path /chemin/vers/skyjo.db]

Options:
    --dry-run    Affiche les actions sans les exécuter
    --db-path    Chemin vers la base de données (défaut: skyjo.db)
"""

import sqlite3
import argparse
import unicodedata
import os
from datetime import datetime
from collections import defaultdict

DEFAULT_DB_PATH = 'skyjo.db'


def normalize_name(name):
    """
    Normalise un nom en supprimant les accents et en mettant en minuscules.
    Utilisé pour détecter les doublons.
    """
    # Supprimer les accents
    nfkd = unicodedata.normalize('NFKD', name)
    without_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    # Mettre en minuscules et supprimer les espaces en trop
    return without_accents.lower().strip()


def find_duplicates(conn):
    """
    Trouve les joueurs avec des noms similaires.
    Retourne un dict: nom_normalisé -> [liste des variantes]
    """
    cur = conn.cursor()

    # Récupérer tous les noms de joueurs uniques
    cur.execute('SELECT DISTINCT name FROM players ORDER BY name')
    all_names = [row[0] for row in cur.fetchall()]

    # Grouper par nom normalisé
    groups = defaultdict(list)
    for name in all_names:
        normalized = normalize_name(name)
        groups[normalized].append(name)

    # Ne garder que les groupes avec plusieurs variantes
    duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    return duplicates


def choose_canonical_name(variants):
    """
    Choisit le nom canonique parmi les variantes.
    Préfère le nom avec la première lettre en majuscule et les accents.
    """
    # Trier par: majuscule en premier, puis par longueur (plus long = plus d'accents)
    def score(name):
        has_upper = name[0].isupper() if name else False
        has_accents = any(unicodedata.combining(c) for c in unicodedata.normalize('NFD', name))
        return (has_upper, has_accents, len(name))

    return max(variants, key=score)


def merge_players(conn, old_name, new_name, dry_run=False):
    """
    Fusionne un joueur vers un autre nom.
    Met à jour toutes les tables concernées.
    """
    cur = conn.cursor()

    # Compter les occurrences
    cur.execute('SELECT COUNT(*) FROM players WHERE name = ?', (old_name,))
    players_count = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM rounds WHERE player_name = ?', (old_name,))
    rounds_count = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM group_members WHERE player_name = ?', (old_name,))
    members_count = cur.fetchone()[0]

    print(f"  '{old_name}' -> '{new_name}'")
    print(f"    - players: {players_count} enregistrements")
    print(f"    - rounds: {rounds_count} enregistrements")
    print(f"    - group_members: {members_count} enregistrements")

    if not dry_run:
        # Mettre à jour la table players
        cur.execute('UPDATE players SET name = ? WHERE name = ?', (new_name, old_name))

        # Mettre à jour la table rounds
        cur.execute('UPDATE rounds SET player_name = ? WHERE player_name = ?', (new_name, old_name))

        # Mettre à jour la table group_members (si elle existe)
        try:
            cur.execute('UPDATE group_members SET player_name = ? WHERE player_name = ?', (new_name, old_name))
        except sqlite3.OperationalError:
            pass  # Table n'existe pas encore

        conn.commit()
        print(f"    ✓ Fusionné")
    else:
        print(f"    [DRY-RUN] Non modifié")


def main():
    parser = argparse.ArgumentParser(description='Normalisation des noms de joueurs')
    parser.add_argument('--dry-run', action='store_true', help='Affiche les actions sans les exécuter')
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH, help='Chemin vers la base de données')
    args = parser.parse_args()

    print("=" * 60)
    print("NORMALISATION DES NOMS DE JOUEURS")
    print("=" * 60)
    print(f"Base de données: {args.db_path}")
    print(f"Mode: {'DRY-RUN (simulation)' if args.dry_run else 'RÉEL'}")

    if not os.path.exists(args.db_path):
        print(f"\n❌ Erreur: Base de données non trouvée: {args.db_path}")
        return 1

    # Sauvegarder la base avant modification
    if not args.dry_run:
        backup_path = f"{args.db_path}.backup.normalize.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n📦 Sauvegarde: {backup_path}")
        import shutil
        shutil.copy2(args.db_path, backup_path)

    conn = sqlite3.connect(args.db_path)

    try:
        # Trouver les doublons
        print("\n" + "=" * 60)
        print("RECHERCHE DES DOUBLONS")
        print("=" * 60)

        duplicates = find_duplicates(conn)

        if not duplicates:
            print("\n✅ Aucun doublon détecté !")
            return 0

        print(f"\nDoublons détectés ({len(duplicates)} groupes):")
        for normalized, variants in duplicates.items():
            canonical = choose_canonical_name(variants)
            print(f"  - {variants} -> '{canonical}'")

        # Confirmation
        if not args.dry_run:
            print("\n" + "=" * 60)
            response = input("Voulez-vous fusionner ces joueurs ? (oui/non): ")
            if response.lower() not in ['oui', 'o', 'yes', 'y']:
                print("Fusion annulée.")
                return 0

        # Fusionner les doublons
        print("\n" + "=" * 60)
        print("FUSION DES JOUEURS")
        print("=" * 60)

        for normalized, variants in duplicates.items():
            canonical = choose_canonical_name(variants)
            for variant in variants:
                if variant != canonical:
                    merge_players(conn, variant, canonical, args.dry_run)

        print("\n" + "=" * 60)
        if args.dry_run:
            print("DRY-RUN terminé. Relancez sans --dry-run pour appliquer.")
        else:
            print("✅ Fusion terminée !")
            print("\nN'oubliez pas de relancer la migration si nécessaire.")

        return 0

    finally:
        conn.close()


if __name__ == '__main__':
    exit(main())
