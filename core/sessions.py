"""
Accès communs aux parties des jeux génériques
(tables game_sessions / session_players / session_scores, distinguées par game_slug).
"""
import json
from collections import defaultdict
from datetime import datetime, timezone

from flask import abort

from core.auth import is_admin, get_user_group_ids
from core.db import get_db, get_session_totals


def get_accessible_session(session_id, user, game_slug):
    """Partie visible par l'utilisateur (son groupe, sa création, ou admin), sinon 404."""
    game = get_db().execute(
        'SELECT * FROM game_sessions WHERE id=? AND game_slug=?', (session_id, game_slug)
    ).fetchone()
    if not game:
        abort(404)
    if not is_admin(user) and game['created_by'] != user['id'] \
            and game['group_id'] not in get_user_group_ids(user):
        abort(404)
    return game


def get_session_players(session_id):
    rows = get_db().execute(
        'SELECT player_name FROM session_players WHERE session_id=? ORDER BY position, id', (session_id,)
    ).fetchall()
    return [r['player_name'] for r in rows]


def get_totals(session_id, players):
    """Totaux par joueur, à 0 pour ceux qui n'ont encore rien marqué."""
    totals = {p: 0 for p in players}
    totals.update(get_session_totals(session_id))
    return totals


def can_edit(game, user):
    """Partie en cours : tout utilisateur connecté ; partie terminée : admin uniquement."""
    return is_admin(user) if game['finished'] else True


def list_user_sessions(user, game_slug):
    """Parties du jeu visibles par l'utilisateur, les plus récentes d'abord."""
    group_ids = get_user_group_ids(user)
    placeholders = ','.join('?' * len(group_ids)) or 'NULL'
    return get_db().execute(
        f'''SELECT * FROM game_sessions
            WHERE game_slug = ? AND (group_id IN ({placeholders}) OR created_by = ?)
            ORDER BY id DESC''',
        (game_slug, *group_ids, user['id'])
    ).fetchall()


def create_session(cur, game_slug, group_id, user, now, comments, players):
    """Crée la partie et ses joueurs (sans commit). Retourne l'id de la partie."""
    cur.execute(
        'INSERT INTO game_sessions (game_slug, group_id, created_by, created_at, comments) VALUES (?, ?, ?, ?, ?)',
        (game_slug, group_id, user['id'], now, comments)
    )
    session_id = cur.lastrowid
    for position, p in enumerate(players):
        cur.execute('INSERT INTO session_players (session_id, player_name, position) VALUES (?, ?, ?)',
                    (session_id, p, position))
    return session_id


def next_round_number(session_id):
    """Numéro de la prochaine ligne de score (manche, action ou tour selon le jeu)."""
    last = get_db().execute('SELECT MAX(round_number) AS m FROM session_scores WHERE session_id=?',
                            (session_id,)).fetchone()['m']
    return (last or 0) + 1


def insert_score(session_id, round_number, player, score, details):
    """Ajoute une ligne de score (sans commit) ; details est sérialisé en JSON."""
    get_db().execute(
        'INSERT INTO session_scores (session_id, round_number, player_name, score, details, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        (session_id, round_number, player, score, json.dumps(details), datetime.now(timezone.utc).isoformat())
    )


def delete_last_score(session_id):
    """Supprime la dernière ligne de score (sans commit). Retourne le joueur concerné, ou None si aucune."""
    db = get_db()
    last = db.execute(
        'SELECT round_number, player_name FROM session_scores WHERE session_id=? ORDER BY round_number DESC LIMIT 1',
        (session_id,)
    ).fetchone()
    if not last:
        return None
    db.execute('DELETE FROM session_scores WHERE session_id=? AND round_number=?', (session_id, last['round_number']))
    return last['player_name']


def delete_session(session_id):
    db = get_db()
    db.execute('DELETE FROM session_scores WHERE session_id=?', (session_id,))
    db.execute('DELETE FROM session_players WHERE session_id=?', (session_id,))
    db.execute('DELETE FROM game_sessions WHERE id=?', (session_id,))
    db.commit()


def load_stats_rows(user, game_slug, group_id):
    """
    Lignes brutes des parties visibles d'un jeu (tous les groupes accessibles, ou un seul).
    Retourne (sessions, session_players, score_rows) sous forme de dicts,
    ou None si le groupe demandé n'est pas accessible.
    """
    db = get_db()
    accessible = get_user_group_ids(user)
    if group_id:
        if not group_id.isdigit() or int(group_id) not in accessible:
            return None
        group_ids = [int(group_id)]
    else:
        group_ids = accessible

    sessions, session_players, score_rows = [], [], []
    if group_ids:
        placeholders = ','.join('?' * len(group_ids))
        sessions = [dict(r) for r in db.execute(
            f'SELECT id, finished, created_at FROM game_sessions WHERE game_slug=? AND group_id IN ({placeholders})',
            (game_slug, *group_ids)
        ).fetchall()]
    if sessions:
        ids = [s['id'] for s in sessions]
        placeholders = ','.join('?' * len(ids))
        session_players = [dict(r) for r in db.execute(
            f'SELECT session_id, player_name FROM session_players WHERE session_id IN ({placeholders})', ids
        ).fetchall()]
        score_rows = [dict(r) for r in db.execute(
            f'SELECT session_id, round_number, player_name, score, details, created_at FROM session_scores '
            f'WHERE session_id IN ({placeholders}) ORDER BY session_id, round_number, id', ids
        ).fetchall()]
    return sessions, session_players, score_rows


def frequent_coplayers(player, session_players, limit=3):
    """Joueurs ayant le plus souvent partagé une partie avec `player`."""
    my_sessions = {sp['session_id'] for sp in session_players if sp['player_name'] == player}
    counts = defaultdict(int)
    for sp in session_players:
        if sp['session_id'] in my_sessions and sp['player_name'] != player:
            counts[sp['player_name']] += 1
    return [{'player': name, 'games': n}
            for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def first_game_date(player, sessions, session_players):
    my_sessions = {sp['session_id'] for sp in session_players if sp['player_name'] == player}
    dates = [s['created_at'] for s in sessions if s['id'] in my_sessions and s.get('created_at')]
    return min(dates) if dates else None
