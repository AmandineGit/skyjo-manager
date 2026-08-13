"""
Authentification et autorisation communes à tous les jeux.
"""
from functools import wraps
from flask import session, redirect, g
from core.db import get_db


def require_auth(f):
    """Décorateur pour requérir une authentification."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect('/login')
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
    Récupère les IDs des groupes accessibles par l'utilisateur :
    ceux où il est gestionnaire (group_users) ET ceux où il est joueur (group_members).
    """
    db = get_db()
    if is_admin(user):
        groups = db.execute('SELECT id FROM player_groups').fetchall()
    else:
        groups = db.execute('''
            SELECT id FROM player_groups WHERE id IN (
                SELECT group_id FROM group_users WHERE user_id = ?
                UNION
                SELECT group_id FROM group_members WHERE user_id = ?
            )
        ''', (user['id'], user['id'])).fetchall()
    return [g['id'] for g in groups]
