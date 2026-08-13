"""
Utilitaires de base de données partagés entre tous les jeux.
"""
import os
import sqlite3
import unicodedata
from datetime import datetime, timezone
from flask import g

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'skyjo.db')


def normalize_name(name):
    """
    Normalise un nom en retirant les accents pour la comparaison.
    Utilisé pour suggérer des noms existants similaires.
    Ex: 'Hélène' -> 'helene', 'François' -> 'francois'
    """
    if not name:
        return name
    normalized = unicodedata.normalize('NFD', name)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower()


def get_db():
    """Obtient la connexion SQLite (partagée dans le contexte de la requête)."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


def close_db_connection(exception):
    """À appeler dans @app.teardown_appcontext."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db(reset=False):
    """
    Initialise la base de données avec toutes les tables communes et jeu-spécifiques.
    Si reset=True, supprime toutes les données (mode test).
    """
    db = get_db()
    cur = db.cursor()

    if reset:
        # Mode test : supprimer toutes les tables existantes
        cur.executescript('''
        DROP TABLE IF EXISTS group_users;
        DROP TABLE IF EXISTS group_members;
        DROP TABLE IF EXISTS player_groups;
        DROP TABLE IF EXISTS skyjo_rounds;
        DROP TABLE IF EXISTS skyjo_players;
        DROP TABLE IF EXISTS skyjo_games;
        DROP TABLE IF EXISTS rounds;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS games;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS game_rules;
        ''')
        db.commit()

    # Créer les tables communes
    cur.executescript('''
    -- Utilisateurs
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        display_name TEXT,
        player_name TEXT,
        created_at TEXT,
        reset_token TEXT,
        reset_token_expires TEXT,
        last_login TEXT
    );

    -- Groupes de joueurs (partagés entre les jeux)
    CREATE TABLE IF NOT EXISTS player_groups (
        id INTEGER PRIMARY KEY,
        name TEXT,
        created_by INTEGER,
        created_at TEXT,
        rename_permission TEXT DEFAULT 'owner',
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    -- Membres d'un groupe (joueurs)
    CREATE TABLE IF NOT EXISTS group_members (
        id INTEGER PRIMARY KEY,
        group_id INTEGER,
        player_name TEXT,
        user_id INTEGER,
        FOREIGN KEY (group_id) REFERENCES player_groups(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    -- Utilisateurs ayant accès à un groupe (partage)
    CREATE TABLE IF NOT EXISTS group_users (
        id INTEGER PRIMARY KEY,
        group_id INTEGER,
        user_id INTEGER,
        role TEXT DEFAULT 'member',
        FOREIGN KEY (group_id) REFERENCES player_groups(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    -- Parties de Skyjo
    CREATE TABLE IF NOT EXISTS skyjo_games (
        id INTEGER PRIMARY KEY,
        created_at TEXT,
        type TEXT,
        comments TEXT,
        finished INTEGER DEFAULT 0,
        group_id INTEGER,
        created_by INTEGER,
        FOREIGN KEY (group_id) REFERENCES player_groups(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    -- Joueurs d'une partie Skyjo
    CREATE TABLE IF NOT EXISTS skyjo_players (
        id INTEGER PRIMARY KEY,
        game_id INTEGER,
        name TEXT,
        FOREIGN KEY (game_id) REFERENCES skyjo_games(id)
    );

    -- Rounds (manches) Skyjo
    CREATE TABLE IF NOT EXISTS skyjo_rounds (
        id INTEGER PRIMARY KEY,
        game_id INTEGER,
        round_number INTEGER,
        player_name TEXT,
        score INTEGER,
        created_at TEXT,
        is_finisher INTEGER DEFAULT 0,
        FOREIGN KEY (game_id) REFERENCES skyjo_games(id)
    );

    -- Règles des jeux
    CREATE TABLE IF NOT EXISTS game_rules (
        id INTEGER PRIMARY KEY,
        game_type TEXT UNIQUE,
        rules_pdf TEXT
    );
    ''')
    db.commit()

    # Migrations pour les colonnes manquantes
    _apply_migrations(db)

    # Initialize default game rules
    cur = db.execute("SELECT COUNT(*) as cnt FROM game_rules")
    if cur.fetchone()['cnt'] == 0:
        db.execute("INSERT INTO game_rules (game_type, rules_pdf) VALUES (?, ?)",
                   ('Skyjo', '88-skyjo-regle.pdf'))
        db.execute("INSERT INTO game_rules (game_type, rules_pdf) VALUES (?, ?)",
                   ('Skyjo Action', '88-skyjo-regle.pdf'))
        db.commit()


def _apply_migrations(db):
    """Applique les migrations de schéma manquantes."""
    cur = db.cursor()

    # Vérifier et ajouter les colonnes manquantes dans player_groups
    cur = db.execute("PRAGMA table_info(player_groups)")
    cols = [r['name'] for r in cur.fetchall()]
    if 'rename_permission' not in cols:
        db.execute("ALTER TABLE player_groups ADD COLUMN rename_permission TEXT DEFAULT 'owner'")
        db.commit()

    # Vérifier et ajouter les colonnes manquantes dans users
    cur = db.execute("PRAGMA table_info(users)")
    user_cols = [r['name'] for r in cur.fetchall()]
    if 'last_login' not in user_cols:
        db.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
        db.commit()

    # Migration : fusionner display_name dans player_name
    if 'display_name' in user_cols:
        db.execute('''
            UPDATE users SET player_name = display_name
            WHERE player_name IS NULL AND display_name IS NOT NULL
        ''')
        db.commit()


def get_totals(game_id, table_name='skyjo_rounds'):
    """
    Récupère les totaux de points pour une partie.
    
    Args:
        game_id: ID de la partie
        table_name: Nom de la table des rounds (par défaut 'skyjo_rounds')
    
    Returns:
        Dict {player_name: total_score}
    """
    db = get_db()
    cur = db.execute(
        f'SELECT player_name, SUM(score) as total FROM {table_name} WHERE game_id=? GROUP BY player_name',
        (game_id,)
    )
    return {row['player_name']: row['total'] for row in cur.fetchall()}


# Filtres Jinja
def format_ts(value):
    """Formate un timestamp ISO en 'DD/MM/YYYY à HHhMM'."""
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        # Format: 11/01/2026 à 18h05
        return dt.strftime('%d/%m/%Y à %Hh%M')
    except Exception:
        return value


def format_date_fr(value):
    """Formate une date ISO en 'DD mois YYYY' en français."""
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"
    except Exception:
        return value
