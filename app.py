"""
Skyjo Manager - Application de gestion de parties Skyjo

Architecture:
- Authentification par compte utilisateur (email/mot de passe)
- Groupes de joueurs partagés entre utilisateurs
- Statistiques par groupe et globales

Tables principales:
- users: Comptes utilisateurs
- player_groups: Groupes de joueurs
- group_members: Membres (joueurs) d'un groupe
- group_users: Utilisateurs ayant accès à un groupe
- games: Parties (liées à un groupe)
- players: Joueurs participant à une partie
- rounds: Scores par manche
"""

import os
import sqlite3
import unicodedata
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (
    Flask, g, render_template, request, redirect,
    url_for, flash, send_from_directory, session, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

from export_to_onedrive import export_all_to_onedrive

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'skyjo.db')
DEV_MODE = os.environ.get('FLASK_ENV', 'development') == 'development'

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'change-me')

# =============================================================================
# UTILITAIRES
# =============================================================================


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


# =============================================================================
# AUTHENTIFICATION
# =============================================================================
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect('/skyjo/login')
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Récupère l'utilisateur connecté depuis la session."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    db = get_db()
    return db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()


def is_admin(user):
    """Vérifie si l'utilisateur est l'administrateur."""
    if not user:
        return False
    return user['email'] == 'admin@skyjo.local'


def get_user_group_ids(user):
    """
    Récupère les IDs des groupes accessibles par l'utilisateur.
    L'admin a accès à tous les groupes.
    """
    db = get_db()
    if is_admin(user):
        # Admin voit tous les groupes
        groups = db.execute('SELECT id FROM player_groups').fetchall()
    else:
        # Utilisateur normal voit uniquement ses groupes
        groups = db.execute('''
            SELECT pg.id FROM player_groups pg
            JOIN group_users gu ON pg.id = gu.group_id
            WHERE gu.user_id = ?
        ''', (user['id'],)).fetchall()
    return [g['id'] for g in groups]


# =============================================================================
# FILTRES JINJA
# =============================================================================


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


app.jinja_env.filters['format_ts'] = format_ts
app.jinja_env.filters['format_date_fr'] = format_date_fr


# =============================================================================
# BASE DE DONNÉES
# =============================================================================


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db(reset=False):
    """
    Initialise la base de données.
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
        DROP TABLE IF EXISTS rounds;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS games;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS game_rules;
        ''')
        db.commit()

    # Créer les tables
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
        reset_token_expires TEXT
    );

    -- Groupes de joueurs
    CREATE TABLE IF NOT EXISTS player_groups (
        id INTEGER PRIMARY KEY,
        name TEXT,
        created_by INTEGER,
        created_at TEXT,
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

    -- Parties
    CREATE TABLE IF NOT EXISTS games (
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

    -- Joueurs d'une partie
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY,
        game_id INTEGER,
        name TEXT,
        FOREIGN KEY (game_id) REFERENCES games(id)
    );

    -- Rounds (manches)
    CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY,
        game_id INTEGER,
        round_number INTEGER,
        player_name TEXT,
        score INTEGER,
        created_at TEXT,
        is_finisher INTEGER DEFAULT 0,
        FOREIGN KEY (game_id) REFERENCES games(id)
    );

    -- Règles des jeux
    CREATE TABLE IF NOT EXISTS game_rules (
        id INTEGER PRIMARY KEY,
        game_type TEXT UNIQUE,
        rules_pdf TEXT
    );
    ''')
    db.commit()

    # Migration : ajouter group_id et created_by à games si manquants
    cur = db.execute("PRAGMA table_info(games)")
    cols = [r['name'] for r in cur.fetchall()]
    if 'group_id' not in cols:
        db.execute("ALTER TABLE games ADD COLUMN group_id INTEGER")
        db.commit()
    if 'created_by' not in cols:
        db.execute("ALTER TABLE games ADD COLUMN created_by INTEGER")
        db.commit()

    # Migration : fusionner display_name dans player_name
    cur = db.execute("PRAGMA table_info(users)")
    user_cols = [r['name'] for r in cur.fetchall()]
    if 'display_name' in user_cols:
        db.execute('''
            UPDATE users SET player_name = display_name
            WHERE player_name IS NULL AND display_name IS NOT NULL
        ''')
        db.commit()

    # Initialize default game rules
    cur = db.execute("SELECT COUNT(*) as cnt FROM game_rules")
    if cur.fetchone()['cnt'] == 0:
        db.execute("INSERT INTO game_rules (game_type, rules_pdf) VALUES (?, ?)",
                   ('Skyjo', '88-skyjo-regle.pdf'))
        db.execute("INSERT INTO game_rules (game_type, rules_pdf) VALUES (?, ?)",
                   ('Skyjo Action', '88-skyjo-regle.pdf'))
        db.commit()

# Ensure DB schema exists at import time (works with Flask 3 and Gunicorn boots)
# En mode dev, on peut réinitialiser la base avec RESET_DB=1
with app.app_context():
    reset_db = os.environ.get('RESET_DB', '0') == '1'
    init_db(reset=reset_db)

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def get_totals(game_id):
    db = get_db()
    cur = db.execute(
        'SELECT player_name, SUM(score) as total FROM rounds WHERE game_id=? GROUP BY player_name',
        (game_id,)
    )
    return {row['player_name']: row['total'] for row in cur.fetchall()}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect('/skyjo/')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['player_name'] or user['email']
            return redirect('/skyjo/')
        else:
            flash('Email ou mot de passe incorrect')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect('/skyjo/')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        player_name = request.form.get('player_name', '').strip()

        # Validations
        if not email or '@' not in email:
            flash('Adresse email invalide')
            return render_template('register.html')

        if len(password) < 6:
            flash('Le mot de passe doit contenir au moins 6 caractères')
            return render_template('register.html')

        if password != password_confirm:
            flash('Les mots de passe ne correspondent pas')
            return render_template('register.html')

        db = get_db()

        # Vérifier si l'email exact existe déjà
        existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('Cette adresse email est déjà utilisée')
            return render_template('register.html')

        # Vérifier si un email similaire existe (avec/sans accents)
        email_normalized = normalize_name(email)
        all_emails = db.execute('SELECT email FROM users').fetchall()
        similar_emails = []
        for u in all_emails:
            if normalize_name(u['email']) == email_normalized and u['email'] != email:
                similar_emails.append(u['email'])
        if similar_emails:
            flash(f'Un email similaire existe déjà : {", ".join(similar_emails)}. '
                  f'Vérifiez l\'orthographe de votre email.')
            return render_template('register.html')

        # Vérifier si un autre utilisateur a un player_name similaire
        if player_name:
            player_name_normalized = normalize_name(player_name)
            existing_users = db.execute('SELECT player_name FROM users').fetchall()
            similar_names = []
            for u in existing_users:
                if u['player_name'] and normalize_name(u['player_name']) == player_name_normalized:
                    similar_names.append(u['player_name'])
            if similar_names:
                flash(f'Un utilisateur avec un nom similaire existe déjà : {", ".join(similar_names)}. '
                      f'Ajoutez une distinction (ex: initiale du nom de famille).')
                return render_template('register.html')

        # Créer le compte
        password_hash = generate_password_hash(password)
        now = datetime.now(timezone.utc).isoformat()
        cur = db.cursor()
        cur.execute(
            'INSERT INTO users (email, password_hash, player_name, created_at) VALUES (?, ?, ?, ?)',
            (email, password_hash, player_name or None, now)
        )
        db.commit()
        new_user_id = cur.lastrowid

        # Rattacher l'historique des parties au nouveau compte
        if player_name:
            db.execute(
                'UPDATE group_members SET user_id = ? WHERE player_name = ? AND user_id IS NULL',
                (new_user_id, player_name)
            )
            db.commit()

        # Connexion automatique
        session['user_id'] = new_user_id
        session['user_email'] = email
        session['user_name'] = player_name or email
        flash('Compte créé avec succès !')
        return redirect('/skyjo/')

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté')
    return redirect('/skyjo/login')


@app.route('/profile', methods=['GET', 'POST'])
@require_auth
def profile():
    user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')
        db = get_db()

        if action == 'update_profile':
            player_name = request.form.get('player_name', '').strip()

            # Vérifier si un autre utilisateur a un player_name similaire
            if player_name:
                player_name_normalized = normalize_name(player_name)
                existing_users = db.execute(
                    'SELECT id, player_name FROM users WHERE id != ?',
                    (user['id'],)
                ).fetchall()
                similar_names = []
                for u in existing_users:
                    if u['player_name'] and normalize_name(u['player_name']) == player_name_normalized:
                        similar_names.append(u['player_name'])
                if similar_names:
                    flash(f'Un utilisateur avec un nom similaire existe déjà : {", ".join(similar_names)}. '
                          f'Ajoutez une distinction (ex: initiale du nom).')
                    return redirect('/skyjo/profile')

            db.execute(
                'UPDATE users SET player_name = ? WHERE id = ?',
                (player_name or None, user['id'])
            )
            db.commit()

            # Rattacher l'historique des parties au compte
            if player_name:
                db.execute(
                    'UPDATE group_members SET user_id = ? WHERE player_name = ? AND user_id IS NULL',
                    (user['id'], player_name)
                )
                db.commit()

            session['user_name'] = player_name or user['email']
            flash('Profil mis à jour')

        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            new_password_confirm = request.form.get('new_password_confirm', '')

            if not check_password_hash(user['password_hash'], current_password):
                flash('Mot de passe actuel incorrect')
            elif len(new_password) < 6:
                flash('Le nouveau mot de passe doit contenir au moins 6 caractères')
            elif new_password != new_password_confirm:
                flash('Les nouveaux mots de passe ne correspondent pas')
            else:
                password_hash = generate_password_hash(new_password)
                db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                           (password_hash, user['id']))
                db.commit()
                flash('Mot de passe modifié avec succès')

        return redirect('/skyjo/profile')

    return render_template('profile.html', user=user)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user:
            # Générer un token de réinitialisation
            token = secrets.token_urlsafe(32)
            expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

            db.execute(
                'UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE id = ?',
                (token, expires, user['id'])
            )
            db.commit()

            reset_url = f"/skyjo/reset-password/{token}"

            if DEV_MODE:
                # En dev, afficher le lien dans un message flash
                flash(f'[DEV] Lien de réinitialisation : {reset_url}')
            else:
                # En prod, envoyer par email (TODO: configurer SMTP)
                flash('Si cette adresse existe, un email de réinitialisation a été envoyé')
        else:
            # Ne pas révéler si l'email existe ou non
            flash('Si cette adresse existe, un email de réinitialisation a été envoyé')

    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    db = get_db()
    user = db.execute(
        'SELECT * FROM users WHERE reset_token = ?', (token,)
    ).fetchone()

    if not user:
        flash('Lien de réinitialisation invalide ou expiré')
        return redirect('/skyjo/login')

    # Vérifier l'expiration
    if user['reset_token_expires']:
        expires = datetime.fromisoformat(user['reset_token_expires'])
        if datetime.now(timezone.utc) > expires:
            flash('Lien de réinitialisation expiré')
            return redirect('/skyjo/forgot-password')

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        new_password_confirm = request.form.get('new_password_confirm', '')

        if len(new_password) < 6:
            flash('Le mot de passe doit contenir au moins 6 caractères')
        elif new_password != new_password_confirm:
            flash('Les mots de passe ne correspondent pas')
        else:
            password_hash = generate_password_hash(new_password)
            db.execute(
                'UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL WHERE id = ?',
                (password_hash, user['id'])
            )
            db.commit()
            flash('Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter.')
            return redirect('/skyjo/login')

    return render_template('reset_password.html', token=token)

@app.route('/')
@require_auth
def index():
    db = get_db()
    user = get_current_user()

    # Get optional date filter from query params
    search_date = request.args.get('date')

    # Récupérer les groupes de l'utilisateur
    user_groups = db.execute('''
        SELECT pg.id FROM player_groups pg
        JOIN group_users gu ON pg.id = gu.group_id
        WHERE gu.user_id = ?
    ''', (user['id'],)).fetchall()
    group_ids = [g['id'] for g in user_groups]

    if search_date:
        # When searching by date, show all games for that date
        if group_ids:
            placeholders = ','.join('?' * len(group_ids))
            games = db.execute(
                f'SELECT id, created_at, type, finished, group_id FROM games WHERE DATE(created_at) = ? AND (group_id IN ({placeholders}) OR created_by = ?) ORDER BY id DESC',
                (search_date, *group_ids, user['id'])
            ).fetchall()
        else:
            games = db.execute(
                'SELECT id, created_at, type, finished, group_id FROM games WHERE DATE(created_at) = ? AND created_by = ? ORDER BY id DESC',
                (search_date, user['id'])
            ).fetchall()
    else:
        # Default: show only ongoing games
        if group_ids:
            placeholders = ','.join('?' * len(group_ids))
            games = db.execute(
                f'SELECT id, created_at, type, finished, group_id FROM games WHERE finished = 0 AND (group_id IN ({placeholders}) OR created_by = ?) ORDER BY id DESC',
                (*group_ids, user['id'])
            ).fetchall()
        else:
            games = db.execute(
                'SELECT id, created_at, type, finished, group_id FROM games WHERE finished = 0 AND created_by = ? ORDER BY id DESC',
                (user['id'],)
            ).fetchall()

    # Ensure created_at is formatted server-side
    games_list = []
    for g in games:
        gd = dict(g)
        gd['created_display'] = format_date_fr(gd.get('created_at'))
        games_list.append(gd)

    return render_template('index.html', games=games_list, search_date=search_date, user=user)


@app.route('/api/players/search')
@require_auth
def search_players():
    """
    API pour rechercher des joueurs existants.
    Retourne les noms similaires (avec/sans accents) pour l'autocomplétion.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    db = get_db()
    # Récupère tous les noms de joueurs uniques
    all_players = db.execute(
        'SELECT DISTINCT name FROM players ORDER BY name'
    ).fetchall()

    # Normalise la requête pour la comparaison
    query_normalized = normalize_name(query)

    # Trouve les correspondances (comparaison sans accents)
    matches = []
    for row in all_players:
        name = row['name']
        if query_normalized in normalize_name(name):
            matches.append(name)

    return jsonify(matches[:10])  # Limite à 10 suggestions


@app.route('/api/players/check-duplicate')
@require_auth
def check_player_duplicate():
    """
    API pour vérifier si un nom de joueur existe déjà (avec ou sans accents).
    Utilisé pour alerter l'utilisateur avant de créer un doublon.

    Params:
        name: Le nom à vérifier
        group_id: (optionnel) ID du groupe pour limiter la recherche

    Returns:
        JSON avec:
        - exists: True si un nom similaire existe
        - similar_names: Liste des noms similaires trouvés
        - message: Message à afficher à l'utilisateur
    """
    name = request.args.get('name', '').strip()
    group_id = request.args.get('group_id')

    if not name:
        return jsonify({'exists': False, 'similar_names': [], 'message': ''})

    db = get_db()
    name_normalized = normalize_name(name)

    # Chercher les noms similaires dans tous les joueurs ou dans un groupe spécifique
    if group_id:
        all_players = db.execute('''
            SELECT DISTINCT player_name as name FROM group_members WHERE group_id = ?
            UNION
            SELECT DISTINCT name FROM players p
            JOIN games g ON p.game_id = g.id
            WHERE g.group_id = ?
        ''', (group_id, group_id)).fetchall()
    else:
        all_players = db.execute(
            'SELECT DISTINCT name FROM players ORDER BY name'
        ).fetchall()

    # Trouver les noms qui ont la même normalisation
    similar_names = []
    for row in all_players:
        existing_name = row['name']
        if normalize_name(existing_name) == name_normalized and existing_name != name:
            similar_names.append(existing_name)

    if similar_names:
        return jsonify({
            'exists': True,
            'similar_names': similar_names,
            'message': f"Un joueur similaire existe déjà : {', '.join(similar_names)}. "
                       f"Si c'est la même personne, utilisez le nom existant. "
                       f"Si c'est une personne différente, ajoutez une distinction (ex: initiale du nom)."
        })

    return jsonify({'exists': False, 'similar_names': [], 'message': ''})


# ==================== GESTION DES GROUPES ====================

@app.route('/groups')
@require_auth
def groups_list():
    """Liste des groupes de l'utilisateur."""
    user = get_current_user()
    db = get_db()

    # Récupérer tous les groupes où l'utilisateur est membre
    groups = db.execute('''
        SELECT pg.*, gu.role,
               (SELECT COUNT(*) FROM group_members WHERE group_id = pg.id) as member_count,
               (SELECT COUNT(*) FROM games WHERE group_id = pg.id) as game_count
        FROM player_groups pg
        JOIN group_users gu ON pg.id = gu.group_id
        WHERE gu.user_id = ?
        ORDER BY pg.name
    ''', (user['id'],)).fetchall()

    return render_template('groups.html', groups=groups, user=user)


@app.route('/groups/new', methods=['GET', 'POST'])
@require_auth
def groups_new():
    """Créer un nouveau groupe."""
    user = get_current_user()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        members = request.form.get('members', '').strip()

        if not name:
            flash('Le nom du groupe est requis')
            return render_template('group_new.html', user=user)

        db = get_db()
        now = datetime.now(timezone.utc).isoformat()

        # Créer le groupe
        cur = db.cursor()
        cur.execute(
            'INSERT INTO player_groups (name, created_by, created_at) VALUES (?, ?, ?)',
            (name, user['id'], now)
        )
        group_id = cur.lastrowid

        # Ajouter l'utilisateur comme owner
        cur.execute(
            'INSERT INTO group_users (group_id, user_id, role) VALUES (?, ?, ?)',
            (group_id, user['id'], 'owner')
        )

        # Ajouter les membres
        if members:
            member_list = [m.strip() for m in members.split(',') if m.strip()]
            for member_name in member_list:
                cur.execute(
                    'INSERT INTO group_members (group_id, player_name) VALUES (?, ?)',
                    (group_id, member_name)
                )

        db.commit()
        flash(f'Groupe "{name}" créé avec succès !')
        return redirect(f'/skyjo/groups/{group_id}')

    return render_template('group_new.html', user=user)


@app.route('/groups/<int:group_id>')
@require_auth
def group_detail(group_id):
    """Détail d'un groupe."""
    user = get_current_user()
    db = get_db()

    # Vérifier que l'utilisateur a accès au groupe
    access = db.execute(
        'SELECT * FROM group_users WHERE group_id = ? AND user_id = ?',
        (group_id, user['id'])
    ).fetchone()

    if not access:
        flash('Vous n\'avez pas accès à ce groupe')
        return redirect('/skyjo/groups')

    group = db.execute('SELECT * FROM player_groups WHERE id = ?', (group_id,)).fetchone()
    members = db.execute(
        'SELECT * FROM group_members WHERE group_id = ? ORDER BY player_name',
        (group_id,)
    ).fetchall()
    users = db.execute('''
        SELECT u.*, gu.role
        FROM users u
        JOIN group_users gu ON u.id = gu.user_id
        WHERE gu.group_id = ?
        ORDER BY gu.role DESC, u.player_name
    ''', (group_id,)).fetchall()
    games = db.execute('''
        SELECT g.*,
               (SELECT GROUP_CONCAT(name) FROM players WHERE game_id = g.id) as player_names
        FROM games g
        WHERE g.group_id = ?
        ORDER BY g.created_at DESC
        LIMIT 10
    ''', (group_id,)).fetchall()

    return render_template('group_detail.html',
                           group=group, members=members, users=users,
                           games=games, user=user, user_role=access['role'])


@app.route('/groups/<int:group_id>/edit', methods=['POST'])
@require_auth
def group_edit(group_id):
    """Modifier un groupe."""
    user = get_current_user()
    db = get_db()

    # Vérifier que l'utilisateur est owner du groupe
    access = db.execute(
        'SELECT * FROM group_users WHERE group_id = ? AND user_id = ? AND role = ?',
        (group_id, user['id'], 'owner')
    ).fetchone()

    if not access:
        flash('Vous n\'avez pas les droits pour modifier ce groupe')
        return redirect(f'/skyjo/groups/{group_id}')

    action = request.form.get('action')

    if action == 'rename':
        new_name = request.form.get('name', '').strip()
        if new_name:
            db.execute('UPDATE player_groups SET name = ? WHERE id = ?', (new_name, group_id))
            db.commit()
            flash('Groupe renommé')

    elif action == 'add_member':
        member_name = request.form.get('member_name', '').strip()
        if member_name:
            db.execute(
                'INSERT INTO group_members (group_id, player_name) VALUES (?, ?)',
                (group_id, member_name)
            )
            db.commit()
            flash(f'{member_name} ajouté au groupe')

    elif action == 'remove_member':
        member_id = request.form.get('member_id')
        if member_id:
            db.execute('DELETE FROM group_members WHERE id = ?', (member_id,))
            db.commit()
            flash('Membre retiré du groupe')

    elif action == 'invite_user':
        email = request.form.get('email', '').strip().lower()
        if email:
            invited_user = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if invited_user:
                existing = db.execute(
                    'SELECT id FROM group_users WHERE group_id = ? AND user_id = ?',
                    (group_id, invited_user['id'])
                ).fetchone()
                if not existing:
                    db.execute(
                        'INSERT INTO group_users (group_id, user_id, role) VALUES (?, ?, ?)',
                        (group_id, invited_user['id'], 'member')
                    )
                    db.commit()
                    flash(f'Utilisateur invité au groupe')
                else:
                    flash('Cet utilisateur fait déjà partie du groupe')
            else:
                flash('Aucun utilisateur trouvé avec cet email')

    return redirect(f'/skyjo/groups/{group_id}')


@app.route('/api/groups/suggest')
@require_auth
def api_groups_suggest():
    """API pour suggérer des groupes basés sur les joueurs sélectionnés."""
    user = get_current_user()
    db = get_db()

    # Récupérer les noms des joueurs depuis la query
    player_names = request.args.get('players', '').split(',')
    player_names = [p.strip() for p in player_names if p.strip()]

    if not player_names:
        return jsonify([])

    # Récupérer les groupes de l'utilisateur contenant ces joueurs
    user_groups = db.execute('''
        SELECT pg.id, pg.name,
               (SELECT COUNT(*) FROM group_members gm
                WHERE gm.group_id = pg.id AND gm.player_name IN ({placeholders})) as matching_members,
               (SELECT COUNT(*) FROM group_members WHERE group_id = pg.id) as total_members
        FROM player_groups pg
        JOIN group_users gu ON pg.id = gu.group_id
        WHERE gu.user_id = ?
        HAVING matching_members > 0
        ORDER BY matching_members DESC, total_members ASC
        LIMIT 5
    '''.format(placeholders=','.join('?' * len(player_names))),
        (*player_names, user['id'])
    ).fetchall()

    return jsonify([{
        'id': g['id'],
        'name': g['name'],
        'matching': g['matching_members'],
        'total': g['total_members']
    } for g in user_groups])


@app.route('/api/groups/<int:group_id>/members')
@require_auth
def api_group_members(group_id):
    """API pour récupérer les membres d'un groupe."""
    user = get_current_user()
    db = get_db()

    # Vérifier que l'utilisateur a accès au groupe
    access = db.execute(
        'SELECT 1 FROM group_users WHERE group_id = ? AND user_id = ?',
        (group_id, user['id'])
    ).fetchone()

    if not access:
        return jsonify([])

    members = db.execute(
        'SELECT player_name FROM group_members WHERE group_id = ? ORDER BY player_name',
        (group_id,)
    ).fetchall()

    return jsonify([m['player_name'] for m in members])


@app.route('/new', methods=['GET', 'POST'])
@require_auth
def new_game():
    user = get_current_user()
    db = get_db()
    cur = db.cursor()
    now = datetime.now(timezone.utc).isoformat()

    # Récupérer les groupes de l'utilisateur
    user_groups = db.execute('''
        SELECT pg.id, pg.name
        FROM player_groups pg
        JOIN group_users gu ON pg.id = gu.group_id
        WHERE gu.user_id = ?
        ORDER BY pg.name
    ''', (user['id'],)).fetchall()

    # Si l'utilisateur n'a pas de groupe, en créer un par défaut
    if not user_groups:
        default_name = f"Groupe de {user['player_name'] or user['email'].split('@')[0]}"
        cur.execute(
            'INSERT INTO player_groups (name, created_by, created_at) VALUES (?, ?, ?)',
            (default_name, user['id'], now)
        )
        new_group_id = cur.lastrowid
        cur.execute(
            'INSERT INTO group_users (group_id, user_id, role) VALUES (?, ?, ?)',
            (new_group_id, user['id'], 'owner')
        )
        db.commit()
        # Recharger les groupes
        user_groups = db.execute('''
            SELECT pg.id, pg.name
            FROM player_groups pg
            JOIN group_users gu ON pg.id = gu.group_id
            WHERE gu.user_id = ?
            ORDER BY pg.name
        ''', (user['id'],)).fetchall()

    if request.method == 'POST':
        game_type = request.form.get('type') or 'Skyjo'
        comments = request.form.get('comments') or ''
        group_id = request.form.get('group_id')
        create_new_group = request.form.get('create_new_group')
        new_group_name = request.form.get('new_group_name', '').strip()

        # Collect players from player_1..player_10 fields if present
        players = []
        for i in range(1, 11):
            p = request.form.get(f'player_{i}')
            if p and p.strip():
                players.append(p.strip())
        # Fallback to legacy comma-separated field
        if not players:
            players_raw = request.form.get('players') or ''
            players = [p.strip() for p in players_raw.split(',') if p.strip()]
        if not players:
            flash('Ajoutez au moins un joueur (au moins 1).')
            return redirect('/skyjo/new')

        # Vérifier les doublons de noms dans la liste des joueurs soumis
        # (deux joueurs avec le même nom normalisé dans la même partie)
        normalized_players = {}
        duplicates_in_form = []
        for p in players:
            p_normalized = normalize_name(p)
            if p_normalized in normalized_players:
                duplicates_in_form.append((normalized_players[p_normalized], p))
            else:
                normalized_players[p_normalized] = p

        if duplicates_in_form:
            dup_msg = ', '.join([f'"{a}" et "{b}"' for a, b in duplicates_in_form])
            flash(f'Noms de joueurs identiques détectés : {dup_msg}. '
                  f'Si ce sont des personnes différentes, ajoutez une distinction (ex: initiale du nom).')
            return redirect('/skyjo/new')

        # Créer un nouveau groupe si demandé
        if create_new_group:
            # Générer un nom automatique si non fourni
            if not new_group_name:
                count = db.execute(
                    'SELECT COUNT(*) as c FROM player_groups WHERE created_by = ?',
                    (user['id'],)
                ).fetchone()['c']
                new_group_name = f"Groupe {count + 1}"
            cur.execute(
                'INSERT INTO player_groups (name, created_by, created_at) VALUES (?, ?, ?)',
                (new_group_name, user['id'], now)
            )
            group_id = cur.lastrowid
            # Ajouter l'utilisateur comme owner
            cur.execute(
                'INSERT INTO group_users (group_id, user_id, role) VALUES (?, ?, ?)',
                (group_id, user['id'], 'owner')
            )
            # Ajouter les joueurs au groupe
            for p in players:
                cur.execute(
                    'INSERT INTO group_members (group_id, player_name) VALUES (?, ?)',
                    (group_id, p)
                )
        elif group_id:
            # Ajouter les nouveaux joueurs au groupe existant s'ils n'y sont pas déjà
            existing_members = db.execute(
                'SELECT player_name FROM group_members WHERE group_id = ?',
                (group_id,)
            ).fetchall()
            existing_names = {m['player_name'].lower() for m in existing_members}
            for p in players:
                if p.lower() not in existing_names:
                    cur.execute(
                        'INSERT INTO group_members (group_id, player_name) VALUES (?, ?)',
                        (group_id, p)
                    )

        # Si pas de groupe sélectionné, utiliser le premier groupe de l'utilisateur
        if not group_id:
            group_id = user_groups[0]['id']
            # Ajouter les joueurs à ce groupe
            existing_members = db.execute(
                'SELECT player_name FROM group_members WHERE group_id = ?',
                (group_id,)
            ).fetchall()
            existing_names = {m['player_name'].lower() for m in existing_members}
            for p in players:
                if p.lower() not in existing_names:
                    cur.execute(
                        'INSERT INTO group_members (group_id, player_name) VALUES (?, ?)',
                        (group_id, p)
                    )

        # Créer la partie (group_id est toujours défini maintenant)
        cur.execute(
            'INSERT INTO games (created_at, type, comments, group_id, created_by) VALUES (?, ?, ?, ?, ?)',
            (now, game_type, comments, group_id, user['id'])
        )
        game_id = cur.lastrowid

        for p in players:
            cur.execute('INSERT INTO players (game_id, name) VALUES (?, ?)', (game_id, p))

        db.commit()
        return redirect(f"/skyjo/game/{game_id}")

    # GET: récupérer le type de jeu et le groupe depuis les paramètres URL
    default_type = request.args.get('type', None)
    # Groupe présélectionné uniquement si passé en paramètre URL (depuis page groupe)
    default_group_id = request.args.get('group', None)

    return render_template('new_game.html',
                           default_type=default_type,
                           user_groups=user_groups,
                           default_group_id=default_group_id,
                           user=user)

@app.route('/game/<int:game_id>', methods=['GET'])
@require_auth
def game_view(game_id):
    db = get_db()
    game = db.execute('SELECT * FROM games WHERE id=?', (game_id,)).fetchone()
    players = db.execute('SELECT name FROM players WHERE game_id=?', (game_id,)).fetchall()
    player_names = [p['name'] for p in players]
    totals = get_totals(game_id)

    # Récupère les rounds et regroupe par numéro de round en matrice
    rows = db.execute('SELECT round_number, player_name, score, created_at, is_finisher FROM rounds WHERE game_id=? ORDER BY round_number, id', (game_id,)).fetchall()
    rounds_by_num = {}
    for r in rows:
        n = r['round_number']
        if n not in rounds_by_num:
            rounds_by_num[n] = {'round': n, 'scores': {}, 'timestamp': None, 'finisher': None}
        rounds_by_num[n]['scores'][r['player_name']] = r['score']
        if r['is_finisher'] == 1:
            rounds_by_num[n]['finisher'] = r['player_name']
        if r['created_at']:
            ts = r['created_at']
            if rounds_by_num[n]['timestamp'] is None or ts > rounds_by_num[n]['timestamp']:
                rounds_by_num[n]['timestamp'] = ts

    # Calculer si le finisher a eu son score doublé
    for round_data in rounds_by_num.values():
        finisher = round_data['finisher']
        if finisher and finisher in round_data['scores']:
            scores = round_data['scores']
            finisher_score = scores[finisher]
            # Calculer le score minimum de TOUS les joueurs
            min_score = min(scores.values())
            # Le score a été doublé si finisher_score > min_score ET finisher_score est positif
            # (le doublement a déjà été appliqué en base)
            if finisher_score > min_score and finisher_score > 0:
                round_data['was_doubled'] = True
            else:
                round_data['was_doubled'] = False
        else:
            round_data['was_doubled'] = False

    rounds_matrix = [rounds_by_num[n] for n in sorted(rounds_by_num.keys())]

    return render_template('game.html', game=game, players=player_names, totals=totals, rounds_matrix=rounds_matrix)

@app.route('/submit_round/<int:game_id>', methods=['POST'])
@require_auth
def submit_round(game_id):
    db = get_db()
    game = db.execute('SELECT * FROM games WHERE id=?', (game_id,)).fetchone()
    if not game:
        flash('Partie introuvable')
        return redirect('/skyjo/')
    if game['finished']:
        flash('La partie est déjà terminée')
        return redirect(f"/skyjo/game/{game_id}")

    cur = db.execute('SELECT MAX(round_number) as m FROM rounds WHERE game_id=?', (game_id,)).fetchone()
    next_round = (cur['m'] or 0) + 1
    players = db.execute('SELECT name FROM players WHERE game_id=?', (game_id,)).fetchall()

    # Récupérer qui a terminé la manche
    finisher = request.form.get('finisher')

    # Collecter les scores de la manche
    round_scores = {}
    for p in players:
        name = p['name']
        s = request.form.get('score_' + name)
        try:
            val = int(s)
        except Exception:
            val = 0
        round_scores[name] = val

    # Appliquer la règle du doublement si un finisher est défini
    doubled_player = None
    if finisher and finisher in round_scores:
        # Trouver le score minimum de tous les joueurs
        min_score = min(round_scores.values())
        finisher_score = round_scores[finisher]

        # Le finisher doit avoir STRICTEMENT le plus petit score pour éviter le doublement
        # Donc on double si : finisher_score >= min_score ET (finisher_score > min_score OU il y a égalité)
        # Simplifié : doubler si finisher_score > min_score OU (finisher_score == min_score ET un autre joueur a aussi min_score)
        has_strictly_smallest = finisher_score == min_score and list(round_scores.values()).count(min_score) == 1

        # Si le finisher n'a PAS strictement le plus petit score ET que son score est positif
        if not has_strictly_smallest and finisher_score > 0:
            round_scores[finisher] = finisher_score * 2
            doubled_player = finisher

    # Insérer les rounds avec les scores (possiblement doublés)
    for p in players:
        name = p['name']
        score = round_scores[name]
        is_finisher = 1 if name == finisher else 0

        db.execute('INSERT INTO rounds (game_id, round_number, player_name, score, created_at, is_finisher) VALUES (?, ?, ?, ?, ?, ?)',
                   (game_id, next_round, name, score, datetime.now(timezone.utc).isoformat(), is_finisher))

    db.commit()

    # Message de doublement
    if doubled_player:
        flash(f'⚠️ {doubled_player} a terminé mais n\'a pas le meilleur score : points doublés ! ({round_scores[doubled_player]//2} × 2 = {round_scores[doubled_player]})', 'warning')

    # Vérifier si quelqu'un atteint 100 points
    totals = get_totals(game_id)
    for total in totals.values():
        if total >= 100:
            db.execute('UPDATE games SET finished=1 WHERE id=?', (game_id,))
            db.commit()
            flash('Un joueur a atteint 100 points — la partie est terminée.')
            break

    return redirect(f"/skyjo/game/{game_id}")

@app.route('/terminate/<int:game_id>', methods=['POST'])
@require_auth
def terminate(game_id):
    db = get_db()
    db.execute('UPDATE games SET finished=1 WHERE id=?', (game_id,))
    db.commit()
    flash('Partie terminée manuellement.')
    return redirect(f"/skyjo/game/{game_id}")

@app.route('/edit_round/<int:game_id>/<int:round_number>', methods=['POST'])
@require_auth
def edit_round(game_id, round_number):
    try:
        data = request.get_json()
        if not data or 'scores' not in data:
            return {'success': False, 'error': 'Données manquantes'}, 400

        scores = data['scores']
        finisher = data.get('finisher', None)  # Peut être None ou une chaîne vide
        db = get_db()

        # Vérifier que le round existe
        existing = db.execute(
            'SELECT COUNT(*) as cnt FROM rounds WHERE game_id=? AND round_number=?',
            (game_id, round_number)
        ).fetchone()

        if existing['cnt'] == 0:
            return {'success': False, 'error': 'Round introuvable'}, 404

        # Appliquer la règle de doublement si nécessaire
        round_scores = scores.copy()
        if finisher and finisher in round_scores:
            # Trouver le score minimum de tous les joueurs
            min_score = min(round_scores.values())
            finisher_score = round_scores[finisher]

            # Le finisher doit avoir STRICTEMENT le plus petit score pour éviter le doublement
            has_strictly_smallest = finisher_score == min_score and list(round_scores.values()).count(min_score) == 1

            # Si le finisher n'a PAS strictement le plus petit score ET que son score est positif
            if not has_strictly_smallest and finisher_score > 0:
                round_scores[finisher] = finisher_score * 2

        # Mettre à jour les scores et le is_finisher
        for player, original_score in scores.items():
            # Utiliser le score doublé si applicable
            final_score = round_scores[player]
            is_finisher = 1 if player == finisher else 0

            db.execute(
                'UPDATE rounds SET score=?, is_finisher=? WHERE game_id=? AND round_number=? AND player_name=?',
                (final_score, is_finisher, game_id, round_number, player)
            )

        db.commit()

        # Vérifier si un joueur a maintenant atteint 100 points
        totals = get_totals(game_id)
        should_finish = any(total >= 100 for total in totals.values())

        if should_finish:
            db.execute('UPDATE games SET finished=1 WHERE id=?', (game_id,))
            db.commit()

        return {'success': True, 'finished': should_finish}

    except Exception as e:
        return {'success': False, 'error': str(e)}, 500

@app.route('/export')
@require_auth
def export_route():
    try:
        path = export_all_to_onedrive()
        flash('Export effectué: ' + path)
    except Exception as e:
        flash('Erreur export: ' + str(e))
    return redirect('/skyjo/')

@app.route('/stats')
@require_auth
def stats_menu():
    """Menu de sélection des statistiques par type de jeu"""
    user = get_current_user()
    db = get_db()

    # Récupérer le filtre groupe depuis les paramètres
    group_id = request.args.get('group')

    # Récupérer les groupes accessibles (tous pour admin, ses groupes pour utilisateur normal)
    accessible_group_ids = get_user_group_ids(user)

    # Récupérer les groupes de l'utilisateur pour le sélecteur
    if is_admin(user):
        user_groups = db.execute('''
            SELECT id, name FROM player_groups ORDER BY name
        ''').fetchall()
    else:
        user_groups = db.execute('''
            SELECT pg.id, pg.name
            FROM player_groups pg
            JOIN group_users gu ON pg.id = gu.group_id
            WHERE gu.user_id = ?
            ORDER BY pg.name
        ''', (user['id'],)).fetchall()

    # Si pas de groupes accessibles, retourner une page vide
    if not accessible_group_ids:
        return render_template('stats_menu.html',
                              game_types=[],
                              games_count={},
                              rounds_count={},
                              user_groups=[],
                              selected_group=None,
                              group_id=None)

    # Construire la clause WHERE pour le filtre groupe
    # Si un groupe spécifique est demandé, vérifier qu'il est accessible
    if group_id:
        if int(group_id) not in accessible_group_ids:
            flash('Vous n\'avez pas accès à ce groupe')
            return redirect('/skyjo/stats')
        group_filter = " AND g.group_id = ?"
        group_params = (int(group_id),)
    else:
        # Filtrer par tous les groupes accessibles
        placeholders = ','.join('?' * len(accessible_group_ids))
        group_filter = f" AND g.group_id IN ({placeholders})"
        group_params = tuple(accessible_group_ids)

    # Récupérer tous les types de jeux qui ont été joués
    game_types = db.execute(f'''
        SELECT DISTINCT g.type FROM games g
        WHERE g.type IS NOT NULL {group_filter}
        ORDER BY g.type
    ''', group_params).fetchall()
    game_types = [row['type'] for row in game_types]

    # Compter le nombre de parties et rounds par type
    games_count = {}
    rounds_count = {}
    for game_type in game_types:
        count_games = db.execute(f'''
            SELECT COUNT(*) as cnt FROM games g WHERE g.type = ? {group_filter}
        ''', (game_type,) + group_params).fetchone()
        games_count[game_type] = count_games['cnt']

        count_rounds = db.execute(f'''
            SELECT COUNT(*) as cnt FROM rounds
            WHERE game_id IN (SELECT id FROM games g WHERE g.type = ? {group_filter})
        ''', (game_type,) + group_params).fetchone()
        rounds_count[game_type] = count_rounds['cnt']

    # Récupérer le nom du groupe sélectionné
    selected_group = None
    if group_id:
        selected_group = db.execute('SELECT * FROM player_groups WHERE id = ?', (group_id,)).fetchone()

    return render_template('stats_menu.html',
                          game_types=game_types,
                          games_count=games_count,
                          rounds_count=rounds_count,
                          user_groups=user_groups,
                          selected_group=selected_group,
                          group_id=group_id)

@app.route('/stats/<game_type>')
@require_auth
def stats_detail(game_type):
    """Statistiques détaillées pour un type de jeu spécifique"""
    user = get_current_user()
    db = get_db()
    stats = []
    import pandas as pd

    # Récupérer le filtre groupe depuis les paramètres
    group_id = request.args.get('group')

    # Récupérer les groupes accessibles (tous pour admin, ses groupes pour utilisateur normal)
    accessible_group_ids = get_user_group_ids(user)

    # Récupérer les groupes de l'utilisateur pour le sélecteur
    if is_admin(user):
        user_groups = db.execute('''
            SELECT id, name FROM player_groups ORDER BY name
        ''').fetchall()
    else:
        user_groups = db.execute('''
            SELECT pg.id, pg.name
            FROM player_groups pg
            JOIN group_users gu ON pg.id = gu.group_id
            WHERE gu.user_id = ?
            ORDER BY pg.name
        ''', (user['id'],)).fetchall()

    # Si pas de groupes accessibles, retourner une page vide
    if not accessible_group_ids:
        return render_template('stats_detail.html',
                              game_type=game_type,
                              stats=[],
                              podium=[],
                              worst_single=None,
                              best_single=None,
                              most_doubled=None,
                              total_games=0,
                              total_rounds=0,
                              user_groups=[],
                              selected_group=None,
                              group_id=None)

    # Construire la clause WHERE pour le filtre groupe
    if group_id:
        if int(group_id) not in accessible_group_ids:
            flash('Vous n\'avez pas accès à ce groupe')
            return redirect(f'/skyjo/stats/{game_type}')
        group_filter = " AND g.group_id = ?"
        group_params = (int(group_id),)
    else:
        # Filtrer par tous les groupes accessibles
        placeholders = ','.join('?' * len(accessible_group_ids))
        group_filter = f" AND g.group_id IN ({placeholders})"
        group_params = tuple(accessible_group_ids)

    # Récupérer uniquement les rounds des parties du type spécifié
    query = f'''
        SELECT r.* FROM rounds r
        INNER JOIN games g ON r.game_id = g.id
        WHERE g.type = ? {group_filter}
    '''
    df = pd.read_sql_query(query, db, params=(game_type,) + group_params)

    if not df.empty:
        for name in df['player_name'].unique():
            sub = df[df['player_name'] == name]['score']
            stats.append({
                'player': name,
                'mean': float(sub.mean()),
                'median': float(sub.median()),
                'best': int(sub.min()),
                'worst': int(sub.max()),
                'rounds': int(sub.count())
            })

        # Trier par moyenne croissante pour le podium
        stats.sort(key=lambda x: x['mean'])

    # Podium (top 3)
    podium = stats[:3] if stats else []

    # Trouver le pire score sur un round (Looser du pire)
    worst_single = None
    if not df.empty:
        worst_idx = df['score'].idxmax()
        worst_row = df.loc[worst_idx]
        worst_single = {
            'player': worst_row['player_name'],
            'score': int(worst_row['score']),
            'round_number': int(worst_row['round_number']),
            'game_id': int(worst_row['game_id'])
        }

    # Trouver le meilleur score sur un round (Boss des coups de bol)
    best_single = None
    if not df.empty:
        best_idx = df['score'].idxmin()
        best_row = df.loc[best_idx]
        best_single = {
            'player': best_row['player_name'],
            'score': int(best_row['score']),
            'round_number': int(best_row['round_number']),
            'game_id': int(best_row['game_id'])
        }

    # Compter les parties et rounds totaux
    total_games = db.execute(f'''
        SELECT COUNT(*) as cnt FROM games g WHERE g.type = ? {group_filter}
    ''', (game_type,) + group_params).fetchone()['cnt']
    total_rounds = len(df)

    # Trouver "Le précoce" - joueur qui double le plus souvent
    # Un doublement = finisher qui n'a pas le score minimum du round
    most_doubled = None
    if not df.empty:
        # Requête pour trouver les doublements par joueur
        doubled_query = f'''
            SELECT finisher.player_name, COUNT(*) as doubled_count
            FROM (
                SELECT r.game_id, r.round_number, r.player_name, r.score
                FROM rounds r
                INNER JOIN games g ON r.game_id = g.id
                WHERE g.type = ? AND r.is_finisher = 1 {group_filter}
            ) finisher
            INNER JOIN (
                SELECT r.game_id, r.round_number, MIN(r.score) as min_score
                FROM rounds r
                INNER JOIN games g ON r.game_id = g.id
                WHERE g.type = ? {group_filter}
                GROUP BY r.game_id, r.round_number
            ) mins ON finisher.game_id = mins.game_id
                   AND finisher.round_number = mins.round_number
            WHERE finisher.score > mins.min_score AND finisher.score > 0
            GROUP BY finisher.player_name
            ORDER BY doubled_count DESC
            LIMIT 1
        '''
        doubled_result = db.execute(
            doubled_query,
            (game_type,) + group_params + (game_type,) + group_params
        ).fetchone()
        if doubled_result and doubled_result['doubled_count'] > 0:
            most_doubled = {
                'player': doubled_result['player_name'],
                'count': doubled_result['doubled_count']
            }

    # Récupérer le nom du groupe sélectionné
    selected_group = None
    if group_id:
        selected_group = db.execute('SELECT * FROM player_groups WHERE id = ?', (group_id,)).fetchone()

    return render_template('stats_detail.html',
                          game_type=game_type,
                          stats=stats,
                          podium=podium,
                          worst_single=worst_single,
                          best_single=best_single,
                          most_doubled=most_doubled,
                          total_games=total_games,
                          total_rounds=total_rounds,
                          user_groups=user_groups,
                          selected_group=selected_group,
                          group_id=group_id)


@app.route('/stats/<game_type>/player/<player_name>')
@require_auth
def player_stats(game_type, player_name):
    """Statistiques individuelles d'un joueur pour un type de jeu"""
    user = get_current_user()
    db = get_db()
    import pandas as pd

    # Récupérer le filtre groupe depuis les paramètres
    group_id = request.args.get('group')

    # Récupérer les groupes accessibles (tous pour admin, ses groupes pour utilisateur normal)
    accessible_group_ids = get_user_group_ids(user)

    # Si pas de groupes accessibles, rediriger
    if not accessible_group_ids:
        flash('Aucune statistique disponible')
        return redirect(f'/skyjo/stats/{game_type}')

    # Construire la clause WHERE pour le filtre groupe
    if group_id:
        if int(group_id) not in accessible_group_ids:
            flash('Vous n\'avez pas accès à ce groupe')
            return redirect(f'/skyjo/stats/{game_type}')
        group_filter = " AND g.group_id = ?"
        group_params = (int(group_id),)
    else:
        # Filtrer par tous les groupes accessibles
        placeholders = ','.join('?' * len(accessible_group_ids))
        group_filter = f" AND g.group_id IN ({placeholders})"
        group_params = tuple(accessible_group_ids)

    # Récupérer tous les rounds du joueur pour ce type de jeu
    query = f'''
        SELECT r.* FROM rounds r
        INNER JOIN games g ON r.game_id = g.id
        WHERE g.type = ? AND r.player_name = ? {group_filter}
    '''
    df = pd.read_sql_query(query, db, params=(game_type, player_name) + group_params)

    if df.empty:
        flash(f'Aucune statistique pour {player_name} en {game_type}')
        redirect_url = f'/skyjo/stats/{game_type}'
        if group_id:
            redirect_url += f'?group={group_id}'
        return redirect(redirect_url)

    # Statistiques de base
    player_stats_data = {
        'mean': float(df['score'].mean()),
        'median': float(df['score'].median()),
        'best': int(df['score'].min()),
        'worst': int(df['score'].max()),
        'rounds': int(df['score'].count())
    }

    # Meilleur score (top) et pire score (flop)
    best_idx = df['score'].idxmin()
    worst_idx = df['score'].idxmax()
    top_round = df.loc[best_idx]
    flop_round = df.loc[worst_idx]

    top = {
        'score': int(top_round['score']),
        'round_number': int(top_round['round_number']),
        'game_id': int(top_round['game_id'])
    }

    flop = {
        'score': int(flop_round['score']),
        'round_number': int(flop_round['round_number']),
        'game_id': int(flop_round['game_id'])
    }

    # Trouver les 3 joueurs les plus fréquents (co-joueurs)
    # Récupérer toutes les parties où le joueur a participé (filtrées par groupes accessibles)
    games_query = f'''
        SELECT DISTINCT r.game_id FROM rounds r
        INNER JOIN games g ON r.game_id = g.id
        WHERE r.player_name = ? AND g.type = ? {group_filter}
    '''
    games_result = db.execute(games_query, (player_name, game_type) + group_params).fetchall()
    game_ids = [row['game_id'] for row in games_result]

    frequent_players = []
    if game_ids:
        # Compter les co-joueurs (excluant le joueur lui-même)
        placeholders = ','.join('?' * len(game_ids))
        coplayers_query = f'''
            SELECT player_name, COUNT(DISTINCT game_id) as game_count
            FROM rounds
            WHERE game_id IN ({placeholders})
            AND player_name != ?
            GROUP BY player_name
            ORDER BY game_count DESC
            LIMIT 3
        '''
        params = game_ids + [player_name]
        coplayers_result = db.execute(coplayers_query, params).fetchall()
        frequent_players = [{'player': row['player_name'], 'games': row['game_count']} for row in coplayers_result]

    # Calculer le pourcentage de "préciosité" (finisher)
    finisher_count = int(df[df['is_finisher'] == 1]['is_finisher'].count())
    total_rounds = int(df['score'].count())
    precocity_percentage = (finisher_count / total_rounds * 100) if total_rounds > 0 else 0

    # Trouver la date de la première partie du joueur
    first_game_date = None
    if game_ids:
        first_game_query = '''
            SELECT created_at FROM games
            WHERE id IN ({})
            ORDER BY created_at ASC
            LIMIT 1
        '''.format(','.join('?' * len(game_ids)))
        first_game_result = db.execute(first_game_query, game_ids).fetchone()
        if first_game_result:
            first_game_date = first_game_result['created_at']

    return render_template('player_stats.html',
                          game_type=game_type,
                          player_name=player_name,
                          stats=player_stats_data,
                          top=top,
                          flop=flop,
                          frequent_players=frequent_players,
                          precocity_percentage=precocity_percentage,
                          finisher_count=finisher_count,
                          total_rounds=total_rounds,
                          first_game_date=first_game_date,
                          group_id=group_id)


@app.route('/images/<path:filename>')
def image_file(filename):
    # Serve project-level images placed in /var/www/skyjo/images
    return send_from_directory(os.path.join(BASE_DIR, 'images'), filename)

@app.route('/rules/<game_type>')
@require_auth
def get_rules(game_type):
    """Return the PDF rules file path for a given game type"""
    db = get_db()
    rule = db.execute('SELECT rules_pdf FROM game_rules WHERE game_type=?', (game_type,)).fetchone()
    if rule and rule['rules_pdf']:
        return send_from_directory(os.path.join(BASE_DIR, 'images'), rule['rules_pdf'])
    flash('Règles non disponibles pour ce type de jeu')
    return redirect('/skyjo/')

# Application WSGI entrypoint (no dispatcher): keep app at root; Apache proxies /skyjo/ -> http://127.0.0.1:8000/
application = app

if __name__ == '__main__':
    # Initialize the database inside the application context
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
