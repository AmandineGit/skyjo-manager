"""
Routes du jeu Qwirkle.

Blueprint monté sur /qwirkle côté Flask, exposé publiquement sous /familyboardgame/qwirkle/.
Saisie tour par tour (une ligne session_scores par tour, voir games/qwirkle/scoring.py) :
la main passe automatiquement au joueur suivant ; fin de partie avec bonus de 6 points.
"""
import json

from flask import Blueprint, render_template, request, redirect, flash, abort

from core.auth import require_auth, get_current_user, is_admin
from core.db import get_db
from core.game_routes import add_common_routes
from core.sessions import (
    get_accessible_session, get_session_players, can_edit,
    delete_session, next_round_number, insert_score, delete_last_score,
)
from games.qwirkle.scoring import (
    END_BONUS, QWIRKLE_BONUS, TYPE_TURN, TYPE_BONUS,
    details_of, qwirkles_of, turn_score, replay, next_player, winners,
)
from games.qwirkle.stats import compute_stats, compute_player_stats

GAME_SLUG = 'qwirkle'
GAME_NAME = 'Qwirkle'
BASE_URL = '/familyboardgame/qwirkle'

# Une pose peut compléter plusieurs lignes ; borne haute pour éviter les fautes de frappe
MAX_QWIRKLES_PER_TURN = 6

qwirkle_bp = Blueprint('qwirkle', __name__, url_prefix='/qwirkle', template_folder='../../templates')


@qwirkle_bp.context_processor
def inject_constants():
    return {'end_bonus': END_BONUS, 'qwirkle_bonus': QWIRKLE_BONUS}


# ========== Helpers ==========

def _rows(session_id):
    return get_db().execute(
        'SELECT round_number, player_name, score, details, created_at FROM session_scores '
        'WHERE session_id=? ORDER BY round_number, id', (session_id,)
    ).fetchall()


def _game_url(session_id):
    return f'{BASE_URL}/game/{session_id}'


def _parse_turn(form):
    """Points, nombre de Qwirkles et échange d'un tour. Retourne (score, details, erreur)."""
    if form.get('swap'):
        return 0, {'type': TYPE_TURN, 'qwirkles': 0, 'swap': True}, None
    raw = (form.get('points') or '').strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 999:
        return None, None, 'Indiquez les points du tour (entier positif), ou choisissez « Échange ».'
    qwirkles = (form.get('qwirkles') or '0').strip()
    if not qwirkles.isdigit() or int(qwirkles) > MAX_QWIRKLES_PER_TURN:
        return None, None, f'Nombre de Qwirkles invalide (0 à {MAX_QWIRKLES_PER_TURN}).'
    points, qwirkles = int(raw), int(qwirkles)
    return turn_score(points, qwirkles), {'type': TYPE_TURN, 'points': points, 'qwirkles': qwirkles, 'swap': False}, None


# ========== Parties ==========

def _summarize(session_id, players):
    """Meilleur total et joueur(s) en tête, pour la liste des parties."""
    totals = replay(players, _rows(session_id))['totals']
    return (max(totals.values()) if players else 0), winners(totals)


@qwirkle_bp.route('/game/<int:session_id>')
@require_auth
def game_view(session_id):
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    players = get_session_players(session_id)
    rows = _rows(session_id)
    state = replay(players, rows)

    # Joueur en cours : suivant dans l'ordre, ou celui choisi en touchant sa carte
    current = request.args.get('player')
    if current not in players:
        current = next_player(players, rows)

    played_turns = sum(state['turns'].values())
    best = max(state['totals'].values()) if players else 0
    return render_template('qwirkle/game.html',
                           game=game, players=players, state=state, current=current,
                           table_turn=played_turns // len(players) + 1 if players else 1,
                           top=winners(state['totals']) if best > 0 else [],
                           game_winners=winners(state['totals']) if game['finished'] else [],
                           has_turns=bool(rows),
                           can_edit=can_edit(game, user), is_admin=is_admin(user))


@qwirkle_bp.route('/game/<int:session_id>/turn', methods=['POST'])
@require_auth
def play_turn(session_id):
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    if game['finished']:
        flash('La partie est terminée.')
        return redirect(_game_url(session_id))

    player = request.form.get('player')
    if player not in get_session_players(session_id):
        flash('Joueur inconnu dans cette partie, rechargez la page.')
        return redirect(_game_url(session_id))
    score, details, error = _parse_turn(request.form)
    if error:
        flash(f'{player} — {error}')
        return redirect(_game_url(session_id) + f'?player={player}')

    insert_score(session_id, next_round_number(session_id), player, score, details)
    get_db().commit()
    if details['qwirkles']:
        flash(f"{'⭐' * details['qwirkles']} {details['qwirkles']} Qwirkle{'s' if details['qwirkles'] > 1 else ''} pour {player} !")
    return redirect(_game_url(session_id))


@qwirkle_bp.route('/game/<int:session_id>/turn/<int:number>', methods=['GET', 'POST'])
@require_auth
def edit_turn(session_id, number):
    """✏️ Modifie un tour déjà joué (points, Qwirkle, échange)."""
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    if not can_edit(game, user):
        flash('Partie terminée : modification réservée à l\'admin')
        return redirect(_game_url(session_id))

    db = get_db()
    row = db.execute('SELECT * FROM session_scores WHERE session_id=? AND round_number=?',
                     (session_id, number)).fetchone()
    if not row or details_of(row).get('type') != TYPE_TURN:
        abort(404)

    if request.method == 'POST':
        score, details, error = _parse_turn(request.form)
        if error:
            flash(error)
            return redirect(f'{_game_url(session_id)}/turn/{number}')
        db.execute('UPDATE session_scores SET score=?, details=? WHERE session_id=? AND round_number=?',
                   (score, json.dumps(details), session_id, number))
        db.commit()
        flash(f'Tour de {row["player_name"]} modifié.')
        return redirect(_game_url(session_id))

    details = details_of(row)
    qwirkles = qwirkles_of(details)
    # Tours saisis avant l'ajout automatique du bonus : pas de 'points', le score saisi était celui des lignes
    return render_template('qwirkle/edit_turn.html', game=game, row=row, details=details, qwirkles=qwirkles,
                           points=details.get('points', row['score']))


@qwirkle_bp.route('/game/<int:session_id>/undo', methods=['POST'])
@require_auth
def undo(session_id):
    """Annule le dernier tour joué de la partie en cours."""
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    if game['finished']:
        flash('La partie est terminée.')
        return redirect(_game_url(session_id))
    player = delete_last_score(session_id)
    if player:
        get_db().commit()
        flash(f'Dernier tour annulé : à {player} de rejouer.')
    return redirect(_game_url(session_id))


@qwirkle_bp.route('/game/<int:session_id>/finish', methods=['POST'])
@require_auth
def finish(session_id):
    """Fin de partie : bonus au joueur qui a vidé sa main en premier (ou à personne si blocage)."""
    user = get_current_user()
    game = get_accessible_session(session_id, user, GAME_SLUG)
    if game['finished']:
        return redirect(_game_url(session_id))

    players = get_session_players(session_id)
    rows = _rows(session_id)
    if not rows:
        delete_session(session_id)
        flash('Partie vide supprimée.')
        return redirect(f'{BASE_URL}/')

    finisher = request.form.get('finisher')
    db = get_db()
    if finisher in players:
        insert_score(session_id, next_round_number(session_id), finisher, END_BONUS, {'type': TYPE_BONUS})
    db.execute('UPDATE game_sessions SET finished=1 WHERE id=?', (session_id,))
    db.commit()

    totals = replay(players, _rows(session_id))['totals']
    result = winners(totals)
    if len(result) == 1:
        flash(f'🏆 {result[0]} gagne avec {totals[result[0]]} points !')
    else:
        flash(f'🏆 Ex æquo : {", ".join(result)}')
    return redirect(_game_url(session_id))


@qwirkle_bp.route('/game/<int:session_id>/reopen', methods=['POST'])
@require_auth
def reopen(session_id):
    """Admin : reprend une partie terminée par erreur (retire le bonus de fin)."""
    user = get_current_user()
    get_accessible_session(session_id, user, GAME_SLUG)
    if not is_admin(user):
        flash('Action réservée à l\'admin')
        return redirect(_game_url(session_id))
    db = get_db()
    for row in _rows(session_id):
        if details_of(row).get('type') == TYPE_BONUS:
            db.execute('DELETE FROM session_scores WHERE session_id=? AND round_number=?',
                       (session_id, row['round_number']))
    db.execute('UPDATE game_sessions SET finished=0 WHERE id=?', (session_id,))
    db.commit()
    flash('Partie reprise.')
    return redirect(_game_url(session_id))


# Routes communes (liste, nouvelle partie, suppression, règles, statistiques) : core/game_routes.py
add_common_routes(qwirkle_bp, slug=GAME_SLUG, name=GAME_NAME, base_url=BASE_URL,
                  summarize=_summarize,
                  score_unit='points',
                  compute_stats=compute_stats, compute_player_stats=compute_player_stats)
