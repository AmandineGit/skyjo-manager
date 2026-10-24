"""
Routes identiques pour tous les jeux génériques (Flip 7, Mantis…) :
liste des parties, nouvelle partie, suppression (admin), règles, statistiques et stats par joueur.
Chaque jeu les ajoute à son blueprint avec add_common_routes, puis définit ses routes propres
(page de partie, saisie, fin de partie…). Templates attendus : <slug>/rules.html,
<slug>/stats.html et <slug>/player_stats.html.
"""
from datetime import datetime, timezone

from flask import render_template, request, redirect, flash

from core.auth import require_auth, get_current_user, is_admin
from core.db import get_db
from core.groups import get_user_groups, parse_players, resolve_game_group
from core.sessions import (
    get_accessible_session, get_session_players, list_user_sessions,
    create_session, delete_session, load_stats_rows,
)


def add_common_routes(bp, *, slug, name, base_url, summarize, score_unit,
                      compute_stats, compute_player_stats, min_players=2):
    """
    Calculs propres au jeu :
    - summarize(session_id, players) -> (meilleur score, [joueur(s) en tête]) pour la liste des parties ;
    - compute_stats(sessions, session_players, score_rows) ;
    - compute_player_stats(player, sessions, session_players, score_rows).
    score_unit : unité affichée dans la liste (« points », « cartes »).
    """

    @bp.context_processor
    def inject_game():
        return {'base_url': base_url, 'game_name': name, 'game_slug': slug}

    @bp.route('/')
    @require_auth
    def index():
        user = get_current_user()
        ongoing, finished = [], []
        for s in list_user_sessions(user, slug):
            players = get_session_players(s['id'])
            best, leaders = summarize(s['id'], players)
            entry = {'id': s['id'], 'created_at': s['created_at'], 'players': players,
                     'leaders': leaders, 'best': best}
            (finished if s['finished'] else ongoing).append(entry)
        return render_template('_game_index.html', ongoing=ongoing, finished=finished[:10],
                               score_unit=score_unit, user=user)

    @bp.route('/new', methods=['GET', 'POST'])
    @require_auth
    def new_game():
        user = get_current_user()
        user_groups = get_user_groups(user)

        if request.method == 'POST':
            players, error = parse_players(request.form)
            if not error and len(players) < min_players:
                error = f'Il faut au moins {min_players} joueurs pour une partie de {name}.'
            if error:
                flash(error)
                return redirect(f'{base_url}/new')

            db = get_db()
            cur = db.cursor()
            now = datetime.now(timezone.utc).isoformat()
            group_id = resolve_game_group(cur, user, user_groups, request.form, players, now)
            session_id = create_session(cur, slug, group_id, user, now,
                                        request.form.get('comments') or '', players)
            db.commit()
            return redirect(f'{base_url}/game/{session_id}')

        return render_template('new_game.html',
                               default_type=name,
                               single_type=True,
                               page_title=name,
                               body_class=slug,
                               form_action=f'{base_url}/new',
                               home_url=f'{base_url}/',
                               rules_url=f'{base_url}/rules',
                               user_groups=user_groups,
                               default_group_id=request.args.get('group'),
                               user=user)

    @bp.route('/game/<int:session_id>/delete', methods=['POST'])
    @require_auth
    def delete_game(session_id):
        user = get_current_user()
        get_accessible_session(session_id, user, slug)
        if not is_admin(user):
            flash('Action réservée à l\'admin')
            return redirect(f'{base_url}/game/{session_id}')
        delete_session(session_id)
        flash('Partie supprimée.')
        return redirect(f'{base_url}/')

    @bp.route('/rules')
    @require_auth
    def rules():
        return render_template(f'{slug}/rules.html')

    @bp.route('/stats')
    @require_auth
    def stats():
        user = get_current_user()
        group_id = request.args.get('group')
        data = load_stats_rows(user, slug, group_id)
        if data is None:
            flash('Vous n\'avez pas accès à ce groupe')
            return redirect(f'{base_url}/stats')

        selected_group = None
        if group_id:
            selected_group = get_db().execute('SELECT * FROM player_groups WHERE id = ?', (group_id,)).fetchone()

        return render_template(f'{slug}/stats.html',
                               stats=compute_stats(*data),
                               user_groups=get_user_groups(user),
                               selected_group=selected_group, group_id=group_id)

    @bp.route('/stats/player/<player_name>')
    @require_auth
    def player_stats(player_name):
        user = get_current_user()
        group_id = request.args.get('group')
        stats_url = f'{base_url}/stats' + (f'?group={group_id}' if group_id else '')
        data = load_stats_rows(user, slug, group_id)
        if data is None:
            flash('Vous n\'avez pas accès à ce groupe')
            return redirect(f'{base_url}/stats')

        player = compute_player_stats(player_name, *data)
        if player is None:
            flash(f'Aucune statistique {name} pour {player_name}')
            return redirect(stats_url)

        return render_template(f'{slug}/player_stats.html', player=player, group_id=group_id, stats_url=stats_url)
