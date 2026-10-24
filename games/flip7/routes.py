"""
Routes du jeu Flip 7.

Blueprint monté sur /flip7 côté Flask, exposé publiquement sous /familyboardgame/flip7/
(préfixe déjà proxifié par Apache : aucune règle supplémentaire nécessaire).
Données dans les tables génériques game_sessions / session_players / session_scores.
"""
import json

from flask import Blueprint, render_template, request, redirect, flash, abort

from core.auth import require_auth, get_current_user, is_admin
from core.db import get_db
from core.game_routes import add_common_routes
from core.sessions import (
    get_accessible_session, get_session_players, get_totals, can_edit,
    delete_session, next_round_number, insert_score,
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
    return {'target_score': TARGET_SCORE, 'flip7_bonus': FLIP7_BONUS}


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

def _summarize(session_id, players):
    """Meilleur total et joueur(s) en tête, pour la liste des parties."""
    totals = get_totals(session_id, players)
    best = max(totals.values()) if totals else 0
    return best, [p for p in players if totals[p] == best]


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

    round_number = next_round_number(session_id)
    for name, details in entries.items():
        insert_score(session_id, round_number, name, score_from_details(details), details)
    get_db().commit()

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


# Routes communes (liste, nouvelle partie, suppression, règles, statistiques) : core/game_routes.py
add_common_routes(flip7_bp, slug=GAME_SLUG, name=GAME_NAME, base_url=BASE_URL,
                  summarize=_summarize,
                  score_unit='points',
                  compute_stats=compute_stats, compute_player_stats=compute_player_stats)
