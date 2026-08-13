"""
Skyjo Manager - Platform générique de gestion de scores pour jeux de société

Architecture multi-jeux (Phase 1):
- Authentification centralisée (users)
- Groupes de joueurs partagés entre les jeux
- Chaque jeu gère ses propres tables (skyjo_games, skyjo_players, skyjo_rounds, etc.)
- Hub d'accueil commun
"""

import os
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, session, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

# Import core modules
from core.db import get_db, init_db, close_db_connection, format_ts, format_date_fr, normalize_name
from core.auth import require_auth, get_current_user, is_admin, get_user_group_ids

# Import game blueprints
from games.skyjo.routes import skyjo_bp

from export_to_onedrive import export_all_to_onedrive

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_MODE = os.environ.get('FLASK_ENV', 'development') == 'development'

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'change-me')

# === BLUEPRINT & FILTRES JINJA ===
app.register_blueprint(skyjo_bp)
app.jinja_env.filters['format_ts'] = format_ts
app.jinja_env.filters['format_date_fr'] = format_date_fr

# =============================================================================
# BASE DE DONNÉES
# =============================================================================
# get_db, init_db, normalize_name, format_ts, format_date_fr : importés de core.db
# require_auth, get_current_user, is_admin, get_user_group_ids : importés de core.auth


# Ensure DB schema exists at import time (works with Flask 3 and Gunicorn boots)
# En mode dev, on peut réinitialiser la base avec RESET_DB=1
with app.app_context():
    reset_db = os.environ.get('RESET_DB', '0') == '1'
    init_db(reset=reset_db)

app.teardown_appcontext(close_db_connection)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect('/familyboardgame/')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            db.execute('UPDATE users SET last_login = ? WHERE id = ?',
                       (datetime.now(timezone.utc).isoformat(), user['id']))
            db.commit()
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['player_name'] or user['email']
            return redirect('/familyboardgame/')
        else:
            flash('Email ou mot de passe incorrect')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect('/familyboardgame/')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        player_name = request.form.get('player_name', '').strip()

        # Validations
        if not email or '@' not in email:
            flash('Adresse email invalide')
            return render_template('register.html')

        if not player_name:
            flash('Le nom de joueur est obligatoire')
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

        # Détecter si ce nom existe déjà comme joueur dans des groupes (comparaison normalisée)
        player_match_confirmed = request.form.get('player_match_confirmed', '0')
        canonical_player_name = player_name  # sera écrasé si match trouvé
        if player_name and player_match_confirmed != '1':
            player_name_normalized = normalize_name(player_name)
            all_members = db.execute('''
                SELECT DISTINCT gm.player_name, pg.name as group_name,
                       (SELECT MAX(g.created_at) FROM skyjo_games g
                        JOIN skyjo_players p ON p.game_id = g.id
                        WHERE g.group_id = gm.group_id AND p.name = gm.player_name
                       ) as last_game
                FROM group_members gm
                JOIN player_groups pg ON pg.id = gm.group_id
                WHERE gm.user_id IS NULL
            ''').fetchall()
            existing_players = [r for r in all_members
                                if normalize_name(r['player_name']) == player_name_normalized]
            print(f"DEBUG interstitiel: player_name={player_name!r} normalized={player_name_normalized!r} all_members={len(all_members)} matches={len(existing_players)}")
            if existing_players:
                # Nom canonique = celui de la base (avec la bonne casse/accents)
                canonical_player_name = existing_players[0]['player_name']
                return render_template('register.html',
                    player_match=existing_players,
                    form_email=email,
                    form_player_name=canonical_player_name)

        # Créer le compte (avec le nom canonique issu de la base si match trouvé)
        password_hash = generate_password_hash(password)
        now = datetime.now(timezone.utc).isoformat()
        cur = db.cursor()
        cur.execute(
            'INSERT INTO users (email, password_hash, player_name, created_at) VALUES (?, ?, ?, ?)',
            (email, password_hash, canonical_player_name or None, now)
        )
        db.commit()
        new_user_id = cur.lastrowid

        # Rattacher l'historique des parties au nouveau compte
        if canonical_player_name:
            db.execute(
                'UPDATE group_members SET user_id = ? WHERE player_name = ? AND user_id IS NULL',
                (new_user_id, canonical_player_name)
            )
            # Ajouter l'utilisateur dans group_users pour chaque groupe historique
            historic_groups = db.execute(
                'SELECT DISTINCT group_id FROM group_members WHERE player_name = ?',
                (canonical_player_name,)
            ).fetchall()
            for row in historic_groups:
                existing = db.execute(
                    'SELECT id FROM group_users WHERE group_id = ? AND user_id = ?',
                    (row['group_id'], new_user_id)
                ).fetchone()
                if not existing:
                    db.execute(
                        'INSERT INTO group_users (group_id, user_id, role) VALUES (?, ?, ?)',
                        (row['group_id'], new_user_id, 'member')
                    )
            db.commit()

        # Connexion automatique
        session['user_id'] = new_user_id
        session['user_email'] = email
        session['user_name'] = canonical_player_name or email
        flash('Compte créé avec succès !')
        return redirect('/familyboardgame/')

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté')
    return redirect('/familyboardgame/login')


# === HUB - Accueil commune ===
@app.route('/')
@require_auth
def hub():
    """Page d'accueil avec hub de jeux disponibles"""
    user = get_current_user()
    db = get_db()

    group_ids = get_user_group_ids(user)

    # Nombre total de parties Skyjo accessibles à l'utilisateur
    if group_ids:
        placeholders = ','.join('?' * len(group_ids))
        total_games = db.execute(
            f'SELECT COUNT(*) as cnt FROM skyjo_games WHERE group_id IN ({placeholders}) OR created_by = ?',
            (*group_ids, user['id'])
        ).fetchone()['cnt']
    else:
        total_games = db.execute(
            'SELECT COUNT(*) as cnt FROM skyjo_games WHERE created_by = ?',
            (user['id'],)
        ).fetchone()['cnt']

    games_list = [
        {
            'name': 'Skyjo',
            'icon': '🎲',
            'description': 'Jeu de cartes avec stratégie et défausse',
            'url': '/skyjo/',
        }
    ]

    stats = {
        'total_games': total_games,
    }

    return render_template('hub.html', user=user, games=games_list, stats=stats)


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
                    return redirect('/familyboardgame/profile')

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
                # Ajouter l'utilisateur dans group_users pour chaque groupe historique
                historic_groups = db.execute(
                    'SELECT DISTINCT group_id FROM group_members WHERE player_name = ?',
                    (player_name,)
                ).fetchall()
                for row in historic_groups:
                    existing = db.execute(
                        'SELECT id FROM group_users WHERE group_id = ? AND user_id = ?',
                        (row['group_id'], user['id'])
                    ).fetchone()
                    if not existing:
                        db.execute(
                            'INSERT INTO group_users (group_id, user_id, role) VALUES (?, ?, ?)',
                            (row['group_id'], user['id'], 'member')
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

        return redirect('/familyboardgame/profile')

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

            reset_url = f"/familyboardgame/reset-password/{token}"

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
        return redirect('/familyboardgame/login')

    # Vérifier l'expiration
    if user['reset_token_expires']:
        expires = datetime.fromisoformat(user['reset_token_expires'])
        if datetime.now(timezone.utc) > expires:
            flash('Lien de réinitialisation expiré')
            return redirect('/familyboardgame/forgot-password')

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
            return redirect('/familyboardgame/login')

    return render_template('reset_password.html', token=token)

@app.route('/groups')
@require_auth
def groups_list():
    """Liste des groupes de l'utilisateur."""
    user = get_current_user()
    db = get_db()

    groups = db.execute('''
        SELECT pg.*,
               COALESCE(gu.role, 'player') as role,
               (SELECT COUNT(*) FROM group_members WHERE group_id = pg.id) as member_count,
               (SELECT COUNT(*) FROM skyjo_games WHERE group_id = pg.id) as game_count
        FROM player_groups pg
        LEFT JOIN group_users gu ON pg.id = gu.group_id AND gu.user_id = ?
        WHERE pg.id IN (
            SELECT group_id FROM group_users WHERE user_id = ?
            UNION
            SELECT group_id FROM group_members WHERE user_id = ?
        )
        ORDER BY pg.name
    ''', (user['id'], user['id'], user['id'])).fetchall()

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
        return redirect(f'/familyboardgame/groups/{group_id}')

    return render_template('group_new.html', user=user)


@app.route('/groups/<int:group_id>')
@require_auth
def group_detail(group_id):
    """Détail d'un groupe."""
    user = get_current_user()
    db = get_db()

    # Vérifier l'accès : group_users OU group_members
    has_access = is_admin(user) or db.execute('''
        SELECT 1 FROM group_users WHERE group_id = ? AND user_id = ?
        UNION
        SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?
    ''', (group_id, user['id'], group_id, user['id'])).fetchone()

    if not has_access:
        flash('Vous n\'avez pas accès à ce groupe')
        return redirect('/familyboardgame/groups')

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
               (SELECT GROUP_CONCAT(name) FROM skyjo_players WHERE game_id = g.id) as player_names
        FROM skyjo_games g
        WHERE g.group_id = ?
        ORDER BY g.created_at DESC
        LIMIT 10
    ''', (group_id,)).fetchall()

    # Récupérer le rôle de l'utilisateur dans ce groupe
    user_role_row = db.execute(
        'SELECT role FROM group_users WHERE group_id = ? AND user_id = ?',
        (group_id, user['id'])
    ).fetchone()
    user_role = user_role_row['role'] if user_role_row else None

    return render_template('group_detail.html',
                           group=group, members=members, users=users,
                           games=games, user=user, is_admin=is_admin(user),
                           user_role=user_role)


@app.route('/groups/<int:group_id>/edit', methods=['POST'])
@require_auth
def group_edit(group_id):
    """Modifier un groupe."""
    user = get_current_user()
    db = get_db()

    if not is_admin(user):
        flash('Seul l\'administrateur peut modifier les groupes')
        return redirect(f'/familyboardgame/groups/{group_id}')

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

    return redirect(f'/familyboardgame/groups/{group_id}')


@app.route('/groups/<int:group_id>/rename', methods=['POST'])
@require_auth
def group_rename(group_id):
    """Renommer un groupe avec vérification des permissions."""
    user = get_current_user()
    db = get_db()
    
    # Récupérer le groupe
    group = db.execute('SELECT * FROM player_groups WHERE id = ?', (group_id,)).fetchone()
    if not group:
        flash('Groupe non trouvé')
        return redirect('/familyboardgame/groups')
    
    # Vérifier l'accès à ce groupe
    has_access = is_admin(user) or db.execute('''
        SELECT 1 FROM group_users WHERE group_id = ? AND user_id = ?
        UNION
        SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?
    ''', (group_id, user['id'], group_id, user['id'])).fetchone()
    
    if not has_access:
        flash('Vous n\'avez pas accès à ce groupe')
        return redirect('/familyboardgame/groups')
    
    # Vérifier la permission de renaming
    rename_permission = group['rename_permission'] or 'owner'
    user_role = db.execute(
        'SELECT role FROM group_users WHERE group_id = ? AND user_id = ?',
        (group_id, user['id'])
    ).fetchone()
    user_role = user_role['role'] if user_role else None
    
    can_rename = (
        is_admin(user) or
        (rename_permission == 'all') or
        (rename_permission == 'owner' and user_role == 'owner')
    )
    
    if not can_rename:
        flash('Vous n\'avez pas la permission de renommer ce groupe')
        return redirect(f'/familyboardgame/groups/{group_id}')
    
    # Renommer le groupe
    new_name = request.form.get('name', '').strip()
    if new_name:
        db.execute(
            'UPDATE player_groups SET name = ? WHERE id = ?',
            (new_name, group_id)
        )
        db.commit()
        flash(f'Groupe renommé en "{new_name}"')
    else:
        flash('Le nom du groupe ne peut pas être vide')
    
    return redirect(f'/familyboardgame/groups/{group_id}')

@app.route('/admin')
@require_auth
def admin_panel():
    user = get_current_user()
    if not is_admin(user):
        flash('Accès réservé à l\'administrateur')
        return redirect('/familyboardgame/')
    db = get_db()
    users = db.execute(
        'SELECT id, email, player_name, created_at, last_login FROM users ORDER BY created_at'
    ).fetchall()
    groups = db.execute('''
        SELECT pg.*,
               (SELECT COUNT(*) FROM group_members WHERE group_id = pg.id) as member_count,
               (SELECT COUNT(*) FROM skyjo_games WHERE group_id = pg.id) as game_count
        FROM player_groups pg ORDER BY pg.name
    ''').fetchall()
    return render_template('admin.html', users=users, groups=groups, user=user)


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@require_auth
def admin_reset_password(user_id):
    current_user = get_current_user()
    if not is_admin(current_user):
        flash('Accès réservé à l\'administrateur')
        return redirect('/familyboardgame/')
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 6:
        flash('Le mot de passe doit contenir au moins 6 caractères')
        return redirect('/familyboardgame/admin')
    db = get_db()
    db.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (generate_password_hash(new_password), user_id)
    )
    db.commit()
    target = db.execute('SELECT email, player_name FROM users WHERE id = ?', (user_id,)).fetchone()
    flash(f'Mot de passe réinitialisé pour {target["player_name"] or target["email"]}')
    return redirect('/familyboardgame/admin')


@app.route('/admin/users/<int:user_id>/set-name', methods=['POST'])
@require_auth
def admin_set_player_name(user_id):
    current_user = get_current_user()
    if not is_admin(current_user):
        flash('Accès réservé à l\'administrateur')
        return redirect('/familyboardgame/')
    player_name = request.form.get('player_name', '').strip()
    db = get_db()
    db.execute('UPDATE users SET player_name = ? WHERE id = ?',
               (player_name or None, user_id))
    db.commit()
    flash(f'Nom mis à jour')
    return redirect('/familyboardgame/admin')


@app.route('/export')
@require_auth
def export_route():
    try:
        path = export_all_to_onedrive()
        flash('Export effectué: ' + path)
    except Exception as e:
        flash('Erreur export: ' + str(e))
    return redirect('/familyboardgame/')

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
            WHERE pg.id IN (
                SELECT group_id FROM group_users WHERE user_id = ?
                UNION
                SELECT group_id FROM group_members WHERE user_id = ?
            )
            ORDER BY pg.name
        ''', (user['id'], user['id'])).fetchall()

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
            return redirect('/familyboardgame/stats')
        group_filter = " AND g.group_id = ?"
        group_params = (int(group_id),)
    else:
        # Filtrer par tous les groupes accessibles
        placeholders = ','.join('?' * len(accessible_group_ids))
        group_filter = f" AND g.group_id IN ({placeholders})"
        group_params = tuple(accessible_group_ids)

    # Récupérer tous les types de jeux qui ont été joués
    game_types = db.execute(f'''
        SELECT DISTINCT g.type FROM skyjo_games g
        WHERE g.type IS NOT NULL {group_filter}
        ORDER BY g.type
    ''', group_params).fetchall()
    game_types = [row['type'] for row in game_types]

    # Compter le nombre de parties et rounds par type
    games_count = {}
    rounds_count = {}
    for game_type in game_types:
        count_games = db.execute(f'''
            SELECT COUNT(*) as cnt FROM skyjo_games g WHERE g.type = ? {group_filter}
        ''', (game_type,) + group_params).fetchone()
        games_count[game_type] = count_games['cnt']

        count_rounds = db.execute(f'''
            SELECT COUNT(*) as cnt FROM skyjo_rounds
            WHERE game_id IN (SELECT id FROM skyjo_games g WHERE g.type = ? {group_filter})
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
            WHERE pg.id IN (
                SELECT group_id FROM group_users WHERE user_id = ?
                UNION
                SELECT group_id FROM group_members WHERE user_id = ?
            )
            ORDER BY pg.name
        ''', (user['id'], user['id'])).fetchall()

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
            return redirect(f'/familyboardgame/stats/{game_type}')
        group_filter = " AND g.group_id = ?"
        group_params = (int(group_id),)
    else:
        # Filtrer par tous les groupes accessibles
        placeholders = ','.join('?' * len(accessible_group_ids))
        group_filter = f" AND g.group_id IN ({placeholders})"
        group_params = tuple(accessible_group_ids)

    # Récupérer uniquement les rounds des parties du type spécifié
    query = f'''
        SELECT r.* FROM skyjo_rounds r
        INNER JOIN skyjo_games g ON r.game_id = g.id
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
        SELECT COUNT(*) as cnt FROM skyjo_games g WHERE g.type = ? {group_filter}
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
                FROM skyjo_rounds r
                INNER JOIN skyjo_games g ON r.game_id = g.id
                WHERE g.type = ? AND r.is_finisher = 1 {group_filter}
            ) finisher
            INNER JOIN (
                SELECT r.game_id, r.round_number, MIN(r.score) as min_score
                FROM skyjo_rounds r
                INNER JOIN skyjo_games g ON r.game_id = g.id
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
        return redirect(f'/familyboardgame/stats/{game_type}')

    # Construire la clause WHERE pour le filtre groupe
    if group_id:
        if int(group_id) not in accessible_group_ids:
            flash('Vous n\'avez pas accès à ce groupe')
            return redirect(f'/familyboardgame/stats/{game_type}')
        group_filter = " AND g.group_id = ?"
        group_params = (int(group_id),)
    else:
        # Filtrer par tous les groupes accessibles
        placeholders = ','.join('?' * len(accessible_group_ids))
        group_filter = f" AND g.group_id IN ({placeholders})"
        group_params = tuple(accessible_group_ids)

    # Récupérer tous les rounds du joueur pour ce type de jeu
    query = f'''
        SELECT r.* FROM skyjo_rounds r
        INNER JOIN skyjo_games g ON r.game_id = g.id
        WHERE g.type = ? AND r.player_name = ? {group_filter}
    '''
    df = pd.read_sql_query(query, db, params=(game_type, player_name) + group_params)

    if df.empty:
        flash(f'Aucune statistique pour {player_name} en {game_type}')
        redirect_url = f'/familyboardgame/stats/{game_type}'
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
        SELECT DISTINCT r.game_id FROM skyjo_rounds r
        INNER JOIN skyjo_games g ON r.game_id = g.id
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
            FROM skyjo_rounds
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
            SELECT created_at FROM skyjo_games
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
    # Serve project-level images placed in /var/www/familyboardgame/images
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
    return redirect('/familyboardgame/')

# Application WSGI entrypoint. Routes communes (hub, login, groups, admin, stats...) à la racine
# Flask, exposées via /familyboardgame/ (Apache retire ce préfixe avant de transmettre).
# Routes Skyjo (skyjo_bp, préfixe interne /play) exposées via /skyjo/
# (Apache réécrit /skyjo/... -> gunicorn /play/...).
application = app

if __name__ == '__main__':
    # Initialize the database inside the application context
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
