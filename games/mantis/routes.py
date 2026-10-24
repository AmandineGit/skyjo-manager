"""
Routes du jeu Mantis.

Blueprint monté sur /mantis côté Flask, exposé publiquement sous /familyboardgame/mantis/.
Une partie est un journal d'actions dans session_scores (voir games/mantis/scoring.py) :
compteur en direct pendant le jeu, fin de partie quand la pioche est vide.
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, flash

from core.auth import require_auth, get_current_user, is_admin
from core.db import get_db
from core.groups import get_user_groups, parse_players, resolve_game_group
from core.sessions import (
    get_accessible_session, get_session_players, can_edit,
    list_user_sessions, create_session, delete_session, load_stats_rows,
)
from games.mantis.scoring import (
    EVENT_SCORE, EVENT_STEAL, EVENT_FIX, EVENT_TANK,
    sprint_threshold, replay, leaders, winners,
)
from games.mantis.stats import compute_stats, compute_player_stats

GAME_SLUG = 'mantis'
GAME_NAME = 'Mantis'
BASE_URL = '/familyboardgame/mantis'

mantis_bp = Blueprint('mantis', __name__, url_prefix='/mantis', template_folder='../../templates')


@mantis_bp.context_processor
def inject_constants():
    return {'base_url': BASE_URL}


# ========== Helpers ==========

def _events(session_id):
    return get_db().execute(
        'SELECT round_number, player_name, score, details, created_at FROM session_scores '
        'WHERE session_id=? ORDER BY round_number, id', (session_id,)
    ).fetchall()


def _add_event(session_id, player, score, details):
    db = get_db()
    last = db.execute('SELECT MAX(round_number) AS m FROM session_scores WHERE session_id=?',
                      (session_id,)).fetchone()['m']
    db.execute(
        'INSERT INTO session_scores (session_id, round_number, player_name, score, details, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        (session_id, (last or 0) + 1, player, score, json.dumps(details),
         datetime.now(timezone.utc).isoformat())
    )


def _game_url(session_id):
    return f'{BASE_URL}/game/{session_id}'


def _finish(session_id):
    db = get_db()
    db.execute('UPDATE game_sessions SET finished=1 WHERE id=?', (session_id,))
    db.commit()


# ========== Parties ==========

@mantis_bp.route('/')
@require_auth
def index():
    user = get_current_user()
    ongoing, finished = [], []
    for s in list_user_sessions(user, GAME_SLUG):
        players = get_session_players(s['id'])
        state = replay(players, _events(s['id']))
        top = winners(state['totals'], state['tanks'])
        entry = {'id': s['id'], 'created_at': s['created_at'], 'players': players,
                 'leaders': top, 'best': max(state['totals'].values()) if players else 0}
        (finished if s['finished'] else ongoing).append(entry)
    return render_template('mantis/index.html', ongoing=ongoing, finished=finished[:10], user=user)


@mantis_bp.route('/new', methods=['GET', 'POST'])
@require_auth
def new_game():
    user = get_current_user()
    user_groups = get_user_groups(user)

    if request.method == 'POST':
        players, error = parse_players(request.form)
        if not error and len(players) < 2:
            error = 'Il faut au moins 2 joueurs pour une partie de Mantis.'
        if error:
            flash(error)
            return redirect(f'{BASE_URL}/new')

        db = get_db()
        cur = db.cursor()
        now = datetime.now(timezone.utc).isoformat()
        group_id = resolve_game_group(cur, user, user_groups, request.form, players, now)
        session_id = create_session(cur, GAME_SLUG, group_id, user, now,
                                    request.form.get('comments') or '', players)
        db.commit()
        return redirect(_game_url(session_id))

    return render_template('new_game.html',
                           default_type=GAME_NAME,
                           single_type=True,
                           page_title=GAME_NAME,
                           body_class='mantis',
                           form_action=f'{BASE_URL}/new',
                           home_url=f'{BASE_URL}/',
                           rules_url=f'{BASE_URL}/rules',
                           user_groups=user_groups,
                           default_group_id=request.args.get('group'),
                           user=user)


@mantis_bp.route('/game/<int:session_id>')
@require_auth
def game_view(session_id):
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    players = get_session_players(session_id)
    events = _events(session_id)
    state = replay(players, events)
    totals = state['totals']

    # Déroulé lisible, du plus récent au plus ancien
    log = []
    for e in events:
        details = json.loads(e['details']) if e['details'] else {}
        log.append({'player': e['player_name'], 'score': e['score'], 'created_at': e['created_at'], **details})
    log.reverse()

    best = max(totals.values()) if totals else 0
    return render_template('mantis/game.html',
                           game=game, players=players, state=state,
                           threshold=sprint_threshold(len(players)),
                           scale=max(best, sprint_threshold(len(players))) * 1.15,
                           top=leaders(totals) if best > 0 else [],
                           game_winners=winners(totals, state['tanks']) if game['finished'] else [],
                           log=log, has_actions=bool(events),
                           can_edit=can_edit(game, user), is_admin=is_admin(user))


@mantis_bp.route('/game/<int:session_id>/action', methods=['POST'])
@require_auth
def action(session_id):
    """Marquer (+n cartes), vol réussi, ou correction ✏️ (nouvelles valeurs absolues)."""
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    if game['finished']:
        flash('La partie est terminée.')
        return redirect(_game_url(session_id))

    players = get_session_players(session_id)
    player = request.form.get('player')
    kind = request.form.get('action')
    if player not in players:
        flash('Joueur inconnu dans cette partie, rechargez la page.')
        return redirect(_game_url(session_id))

    if kind == EVENT_SCORE:
        raw = (request.form.get('count') or '').strip()
        if not raw.isdigit() or not 1 <= int(raw) <= 99:
            flash(f'{player} — indiquez le nombre de cartes marquées (entre 1 et 99).')
            return redirect(_game_url(session_id))
        _add_event(session_id, player, int(raw), {'type': EVENT_SCORE})
    elif kind == EVENT_STEAL:
        _add_event(session_id, player, 0, {'type': EVENT_STEAL})
    elif kind == EVENT_FIX:
        state = replay(players, _events(session_id))
        values = {}
        for field in ('cards', 'steals'):
            raw = (request.form.get(field) or '').strip()
            if not raw.isdigit() or int(raw) > 999:
                flash(f'{player} — correction : nombres entiers positifs attendus.')
                return redirect(_game_url(session_id))
            values[field] = int(raw)
        delta_cards = values['cards'] - state['totals'][player]
        delta_steals = values['steals'] - state['steals'][player]
        if delta_cards or delta_steals:
            _add_event(session_id, player, delta_cards, {'type': EVENT_FIX, 'steals': delta_steals})
            flash(f'{player} corrigé : {values["cards"]} cartes, {values["steals"]} vols.')
    else:
        flash('Action inconnue.')
        return redirect(_game_url(session_id))

    get_db().commit()
    return redirect(_game_url(session_id))


@mantis_bp.route('/game/<int:session_id>/undo', methods=['POST'])
@require_auth
def undo(session_id):
    """Annule la dernière action de la partie en cours."""
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    if game['finished']:
        flash('La partie est terminée.')
        return redirect(_game_url(session_id))
    db = get_db()
    last = db.execute('SELECT MAX(round_number) AS m FROM session_scores WHERE session_id=?',
                      (session_id,)).fetchone()['m']
    if last:
        db.execute('DELETE FROM session_scores WHERE session_id=? AND round_number=?', (session_id, last))
        db.commit()
        flash('Dernière action annulée.')
    return redirect(_game_url(session_id))


@mantis_bp.route('/game/<int:session_id>/finish', methods=['POST'])
@require_auth
def finish(session_id):
    """Pioche vide : fin de partie. En cas d'égalité en tête, départage au nombre de cartes du tank."""
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    if game['finished']:
        return redirect(_game_url(session_id))

    players = get_session_players(session_id)
    events = _events(session_id)
    if not events:
        delete_session(session_id)
        flash('Partie vide supprimée.')
        return redirect(f'{BASE_URL}/')

    top = leaders(replay(players, events)['totals'])
    if len(top) > 1:
        tanks = {}
        for i, p in enumerate(top):
            raw = (request.form.get(f'tank_{i}') or '').strip()
            if request.form.getlist('tied') != top or not raw.isdigit():
                # Pas encore (ou mal) renseigné : on affiche le formulaire de départage
                return render_template('mantis/tiebreak.html', game=game, tied=top,
                                       score=replay(players, events)['totals'][top[0]])
            tanks[p] = int(raw)
        for p, tank in tanks.items():
            _add_event(session_id, p, 0, {'type': EVENT_TANK, 'tank': tank})

    _finish(session_id)
    state = replay(players, _events(session_id))
    result = winners(state['totals'], state['tanks'])
    if len(result) == 1:
        flash(f'🏆 {result[0]} gagne avec {state["totals"][result[0]]} cartes !')
    else:
        flash(f'🏆 Ex æquo : {", ".join(result)}')
    return redirect(_game_url(session_id))


@mantis_bp.route('/game/<int:session_id>/reopen', methods=['POST'])
@require_auth
def reopen(session_id):
    """Admin : reprend une partie terminée par erreur (efface le départage éventuel)."""
    user = get_current_user()
    get_accessible_session(session_id, user, GAME_SLUG)
    if not is_admin(user):
        flash('Action réservée à l\'admin')
        return redirect(_game_url(session_id))
    db = get_db()
    tank_rows = [r['round_number'] for r in _events(session_id)
                 if r['details'] and json.loads(r['details']).get('type') == EVENT_TANK]
    for n in tank_rows:
        db.execute('DELETE FROM session_scores WHERE session_id=? AND round_number=?', (session_id, n))
    db.execute('UPDATE game_sessions SET finished=0 WHERE id=?', (session_id,))
    db.commit()
    flash('Partie reprise.')
    return redirect(_game_url(session_id))


@mantis_bp.route('/game/<int:session_id>/delete', methods=['POST'])
@require_auth
def delete_game(session_id):
    user = get_current_user()
    get_accessible_session(session_id, user, GAME_SLUG)
    if not is_admin(user):
        flash('Action réservée à l\'admin')
        return redirect(_game_url(session_id))
    delete_session(session_id)
    flash('Partie supprimée.')
    return redirect(f'{BASE_URL}/')


# ========== Règles et statistiques ==========

@mantis_bp.route('/rules')
@require_auth
def rules():
    return render_template('mantis/rules.html')


@mantis_bp.route('/stats')
@require_auth
def stats():
    user = get_current_user()
    group_id = request.args.get('group')
    data = load_stats_rows(user, GAME_SLUG, group_id)
    if data is None:
        flash('Vous n\'avez pas accès à ce groupe')
        return redirect(f'{BASE_URL}/stats')

    selected_group = None
    if group_id:
        selected_group = get_db().execute('SELECT * FROM player_groups WHERE id = ?', (group_id,)).fetchone()

    return render_template('mantis/stats.html',
                           stats=compute_stats(*data),
                           user_groups=get_user_groups(user),
                           selected_group=selected_group, group_id=group_id)


@mantis_bp.route('/stats/player/<player_name>')
@require_auth
def player_stats(player_name):
    user = get_current_user()
    group_id = request.args.get('group')
    stats_url = f'{BASE_URL}/stats' + (f'?group={group_id}' if group_id else '')
    data = load_stats_rows(user, GAME_SLUG, group_id)
    if data is None:
        flash('Vous n\'avez pas accès à ce groupe')
        return redirect(f'{BASE_URL}/stats')

    player = compute_player_stats(player_name, *data)
    if player is None:
        flash(f'Aucune statistique Mantis pour {player_name}')
        return redirect(stats_url)

    return render_template('mantis/player_stats.html', player=player, group_id=group_id, stats_url=stats_url)
