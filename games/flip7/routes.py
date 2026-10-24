"""
Routes du jeu Flip 7.

Blueprint monté sur /flip7 côté Flask, exposé publiquement sous /familyboardgame/flip7/
(préfixe déjà proxifié par Apache : aucune règle supplémentaire nécessaire).
Données dans les tables génériques game_sessions / session_players / session_scores.
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, flash, abort

from core.auth import require_auth, get_current_user, is_admin
from core.db import get_db
from core.groups import get_user_groups, parse_players, resolve_game_group
from core.sessions import (
    get_accessible_session, get_session_players, get_totals, can_edit,
    list_user_sessions, create_session, delete_session, load_stats_rows,
)
from games.flip7.scoring import (
    TARGET_SCORE, FLIP7_BONUS, STATUS_FINISHED, STATUS_TIEBREAK,
    game_outcome, parse_entry, score_from_details,
)
from games.flip7.stats import compute_stats, compute_player_stats

GAME_SLUG = 'flip7'
GAME_NAME = 'Flip 7'
BASE_URL = '/familyboardgame/flip7'

flip7_bp = Blueprint('flip7', __name__, url_prefix='/flip7', template_folder='../../templates')


@flip7_bp.context_processor
def inject_constants():
    return {'base_url': BASE_URL, 'target_score': TARGET_SCORE, 'flip7_bonus': FLIP7_BONUS}


# ========== Helpers ==========

def _parse_round(form, expected):
    """Lit la saisie d'une manche pour les joueurs attendus. Retourne ({joueur: details}, erreur)."""
    submitted = form.getlist('player')
    if sorted(submitted) != sorted(expected):
        return None, 'Les joueurs de la manche ne correspondent pas à la partie, rechargez la page.'
    entries = {}
    for i, name in enumerate(submitted):
        details, error = parse_entry(form, i)
        if error:
            return None, f'{name} — {error}'
        entries[name] = details
    return entries, None


def _update_finished(session_id, players, was_finished):
    """
    Recalcule l'état de la partie après une manche saisie ou modifiée.
    Une partie terminée manuellement (sous 200) le reste.
    """
    status, leaders = game_outcome(get_totals(session_id, players))
    if status == STATUS_FINISHED:
        finished = 1
    elif status == STATUS_TIEBREAK:
        finished = 0
    else:
        finished = 1 if was_finished else 0
    db = get_db()
    db.execute('UPDATE game_sessions SET finished=? WHERE id=?', (finished, session_id))
    db.commit()
    return status, leaders


def _flash_outcome(status, leaders, totals):
    if status == STATUS_FINISHED:
        flash(f'🏆 {leaders[0]} remporte la partie avec {totals[leaders[0]]} points !')
    elif status == STATUS_TIEBREAK:
        flash(f'⚖️ Égalité en tête entre {", ".join(leaders)} : manche de départage !')


# ========== Parties ==========

@flip7_bp.route('/')
@require_auth
def index():
    user = get_current_user()
    ongoing, finished = [], []
    for s in list_user_sessions(user, GAME_SLUG):
        players = get_session_players(s['id'])
        totals = get_totals(s['id'], players)
        entry = {'id': s['id'], 'created_at': s['created_at'], 'players': players,
                 'leader': max(totals, key=totals.get) if totals else None,
                 'best': max(totals.values()) if totals else 0}
        (finished if s['finished'] else ongoing).append(entry)

    return render_template('flip7/index.html', ongoing=ongoing, finished=finished[:10], user=user)


@flip7_bp.route('/new', methods=['GET', 'POST'])
@require_auth
def new_game():
    user = get_current_user()
    user_groups = get_user_groups(user)

    if request.method == 'POST':
        players, error = parse_players(request.form)
        if not error and len(players) < 2:
            error = 'Il faut au moins 2 joueurs pour une partie de Flip 7.'
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
        return redirect(f'{BASE_URL}/game/{session_id}')

    return render_template('new_game.html',
                           default_type=GAME_NAME,
                           single_type=True,
                           page_title=GAME_NAME,
                           body_class='flip7',
                           form_action=f'{BASE_URL}/new',
                           home_url=f'{BASE_URL}/',
                           rules_url=f'{BASE_URL}/rules',
                           user_groups=user_groups,
                           default_group_id=request.args.get('group'),
                           user=user)


@flip7_bp.route('/game/<int:session_id>')
@require_auth
def game_view(session_id):
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    players = get_session_players(session_id)
    totals = get_totals(session_id, players)
    status, leaders = game_outcome(totals)

    rows = get_db().execute(
        'SELECT round_number, player_name, score, details, created_at FROM session_scores '
        'WHERE session_id=? ORDER BY round_number, id', (session_id,)
    ).fetchall()
    rounds = {}
    for r in rows:
        rnd = rounds.setdefault(r['round_number'], {'number': r['round_number'], 'cells': {}, 'timestamp': r['created_at']})
        rnd['cells'][r['player_name']] = {'score': r['score'], **(json.loads(r['details']) if r['details'] else {})}
    rounds = [rounds[n] for n in sorted(rounds)]
    for rnd in rounds:
        rnd['tiebreak'] = len(rnd['cells']) < len(players)

    winners = []
    if game['finished'] and rounds:
        best = max(totals.values())
        winners = [p for p in players if totals[p] == best]

    return render_template('flip7/game.html',
                           game=game, players=players, totals=totals,
                           ranking=sorted(players, key=lambda p: -totals[p]),
                           rounds=rounds, status=status, leaders=leaders,
                           round_players=leaders if status == STATUS_TIEBREAK else players,
                           winners=winners,
                           can_edit=can_edit(game, user), is_admin=is_admin(user))


@flip7_bp.route('/game/<int:session_id>/round', methods=['POST'])
@require_auth
def submit_round(session_id):
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    game_url = f'{BASE_URL}/game/{session_id}'
    if game['finished']:
        flash('La partie est terminée, les scores ne sont plus modifiables')
        return redirect(game_url)

    players = get_session_players(session_id)
    status, leaders = game_outcome(get_totals(session_id, players))
    expected = leaders if status == STATUS_TIEBREAK else players

    entries, error = _parse_round(request.form, expected)
    if error:
        flash(error)
        return redirect(game_url)

    db = get_db()
    last = db.execute('SELECT MAX(round_number) AS m FROM session_scores WHERE session_id=?',
                      (session_id,)).fetchone()['m']
    now = datetime.now(timezone.utc).isoformat()
    for name, details in entries.items():
        db.execute(
            'INSERT INTO session_scores (session_id, round_number, player_name, score, details, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (session_id, (last or 0) + 1, name, score_from_details(details), json.dumps(details), now)
        )
    db.commit()

    status, leaders = _update_finished(session_id, players, was_finished=False)
    _flash_outcome(status, leaders, get_totals(session_id, players))
    return redirect(game_url)


@flip7_bp.route('/game/<int:session_id>/round/<int:round_number>', methods=['GET', 'POST'])
@require_auth
def edit_round(session_id, round_number):
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    game_url = f'{BASE_URL}/game/{session_id}'
    if not can_edit(game, user):
        flash('Partie terminée : modification réservée à l\'admin')
        return redirect(game_url)

    db = get_db()
    rows = db.execute(
        'SELECT player_name, score, details FROM session_scores WHERE session_id=? AND round_number=? ORDER BY id',
        (session_id, round_number)
    ).fetchall()
    if not rows:
        abort(404)
    round_players = [r['player_name'] for r in rows]

    if request.method == 'POST':
        entries, error = _parse_round(request.form, round_players)
        if error:
            flash(error)
            return redirect(f'{game_url}/round/{round_number}')
        for name, details in entries.items():
            db.execute(
                'UPDATE session_scores SET score=?, details=? WHERE session_id=? AND round_number=? AND player_name=?',
                (score_from_details(details), json.dumps(details), session_id, round_number, name)
            )
        db.commit()
        players = get_session_players(session_id)
        flash(f'Manche {round_number} modifiée.')
        status, leaders = _update_finished(session_id, players, was_finished=bool(game['finished']))
        _flash_outcome(status, leaders, get_totals(session_id, players))
        return redirect(game_url)

    # Pré-remplissage : détail enregistré, ou score brut à défaut
    prefill = {r['player_name']: json.loads(r['details']) if r['details'] else {'numbers': r['score']}
               for r in rows}
    return render_template('flip7/edit_round.html', game=game, round_number=round_number,
                           round_players=round_players, prefill=prefill)


@flip7_bp.route('/game/<int:session_id>/terminate', methods=['POST'])
@require_auth
def terminate(session_id):
    user = get_current_user()
    get_accessible_session(session_id, user, GAME_SLUG)
    db = get_db()
    has_rounds = db.execute('SELECT 1 FROM session_scores WHERE session_id=? LIMIT 1', (session_id,)).fetchone()
    if not has_rounds:
        delete_session(session_id)
        flash('Partie vide supprimée.')
        return redirect(f'{BASE_URL}/')
    db.execute('UPDATE game_sessions SET finished=1 WHERE id=?', (session_id,))
    db.commit()
    flash('Partie terminée manuellement.')
    return redirect(f'{BASE_URL}/game/{session_id}')


@flip7_bp.route('/game/<int:session_id>/delete', methods=['POST'])
@require_auth
def delete_game(session_id):
    user = get_current_user()
    get_accessible_session(session_id, user, GAME_SLUG)
    if not is_admin(user):
        flash('Action réservée à l\'admin')
        return redirect(f'{BASE_URL}/game/{session_id}')
    delete_session(session_id)
    flash('Partie supprimée.')
    return redirect(f'{BASE_URL}/')


# ========== Règles et statistiques ==========

@flip7_bp.route('/rules')
@require_auth
def rules():
    return render_template('flip7/rules.html')


@flip7_bp.route('/stats')
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

    return render_template('flip7/stats.html',
                           stats=compute_stats(*data),
                           user_groups=get_user_groups(user),
                           selected_group=selected_group, group_id=group_id)


@flip7_bp.route('/stats/player/<player_name>')
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
        flash(f'Aucune statistique Flip 7 pour {player_name}')
        return redirect(stats_url)

    return render_template('flip7/player_stats.html', player=player, group_id=group_id, stats_url=stats_url)
