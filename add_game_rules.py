#!/usr/bin/env python3
"""
Script pour ajouter ou modifier les règles d'un type de jeu
Usage:
    python3 add_game_rules.py "Nom du Jeu" "fichier-regles.pdf"
    python3 add_game_rules.py --list
"""

import sys
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'skyjo.db')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')


def list_rules():
    """Affiche toutes les règles configurées"""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.execute('SELECT game_type, rules_pdf FROM game_rules ORDER BY game_type')

    print("\n=== Règles configurées ===")
    print(f"{'Type de jeu':<25} | {'Fichier PDF'}")
    print("-" * 60)

    rows = cur.fetchall()
    if not rows:
        print("Aucune règle configurée")
    else:
        for row in rows:
            print(f"{row['game_type']:<25} | {row['rules_pdf']}")

    db.close()
    print()


def add_or_update_rule(game_type, pdf_filename):
    """Ajoute ou met à jour une règle pour un type de jeu"""

    # Vérifier que le fichier PDF existe
    pdf_path = os.path.join(IMAGES_DIR, pdf_filename)
    if not os.path.exists(pdf_path):
        print(f"❌ Erreur : Le fichier {pdf_path} n'existe pas")
        print(f"   Placez d'abord votre PDF dans le dossier : {IMAGES_DIR}")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)

    # Vérifier si le type de jeu existe déjà
    cur = db.execute('SELECT rules_pdf FROM game_rules WHERE game_type = ?', (game_type,))
    existing = cur.fetchone()

    if existing:
        # Mise à jour
        old_pdf = existing[0]
        db.execute('UPDATE game_rules SET rules_pdf = ? WHERE game_type = ?',
                   (pdf_filename, game_type))
        db.commit()
        print(f"✅ Règle mise à jour pour '{game_type}'")
        print(f"   Ancien fichier : {old_pdf}")
        print(f"   Nouveau fichier : {pdf_filename}")
    else:
        # Insertion
        db.execute('INSERT INTO game_rules (game_type, rules_pdf) VALUES (?, ?)',
                   (game_type, pdf_filename))
        db.commit()
        print(f"✅ Règle ajoutée pour '{game_type}'")
        print(f"   Fichier : {pdf_filename}")

    db.close()

    print(f"\n💡 N'oubliez pas d'ajouter '{game_type}' dans le formulaire de nouvelle partie")
    print(f"   Fichier à modifier : templates/new_game.html")
    print(f"   Ligne à ajouter : <option value=\"{game_type}\">{game_type}</option>")


def main():
    if len(sys.argv) == 1:
        print("Usage:")
        print(f"  {sys.argv[0]} \"Nom du Jeu\" \"fichier-regles.pdf\"")
        print(f"  {sys.argv[0]} --list")
        sys.exit(1)

    if sys.argv[1] == '--list' or sys.argv[1] == '-l':
        list_rules()
    elif len(sys.argv) == 3:
        game_type = sys.argv[1]
        pdf_filename = sys.argv[2]
        add_or_update_rule(game_type, pdf_filename)
    else:
        print("❌ Erreur : Nombre d'arguments invalide")
        print(f"Usage: {sys.argv[0]} \"Nom du Jeu\" \"fichier-regles.pdf\"")
        sys.exit(1)


if __name__ == '__main__':
    main()
