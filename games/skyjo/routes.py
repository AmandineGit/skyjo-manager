"""
Routes de gestion de parties Skyjo.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timezone
from core.auth import require_auth, get_current_user, is_admin, get_user_group_ids
from core.db import get_db, get_totals, normalize_name, format_date_fr

skyjo_bp = Blueprint('skyjo', __name__, url_prefix='/skyjo', template_folder='../../templates')


@skyjo_bp.route('/')
@require_auth
def index():
    db = get_db()
    user = get_current_user()

    # Get optional date filter from query params
    search_date = request.args.get('date')

    group_ids = get_user_group_ids(user)

    if search_date:
        # When searching by date, show all games for that date
        if group_ids:
            placeholders = ','.join('?' * len(group_ids))
            games = db.execute(
                f'SELECT id, created_at, type, finished, group_id FROM skyjo_games WHERE DATE(created_at) = ? AND (group_id IN ({placeholders}) OR created_by = ?) ORDER BY id DESC',
                (search_date, *group_ids, user['id'])
            ).fetchall()
        else:
            games = db.execute(
                'SELECT id, created_at, type, finished, group_id FROM skyjo_games WHERE DATE(created_at) = ? AND created_by = ? ORDER BY id DESC',
                (search_date, user['id'])
            ).fetchall()
    else:
        # Default: show only ongoing games
        if group_ids:
            placeholders = ','.join('?' * len(group_ids))
            games = db.execute(
                f'SELECT id, created_at, type, finished, group_id FROM skyjo_games WHERE finished = 0 AND (group_id IN ({placeholders}) OR created_by = ?) ORDER BY id DESC',
                (*group_ids, user['id'])
            ).fetchall()
        else:
            games = db.execute(
                'SELECT id, created_at, type, finished, group_id FROM skyjo_games WHERE finished = 0 AND created_by = ? ORDER BY id DESC',
                (user['id'],)
            ).fetchall()

    # Ensure created_at is formatted server-side
    games_list = []
    for g in games:
        gd = dict(g)
        gd['created_display'] = format_date_fr(gd.get('created_at'))
        games_list.append(gd)

    return render_template('index.html', games=games_list, search_date=search_date, user=user)


@skyjo_bp.route('/new', methods=['GET', 'POST'])
@require_auth
def new_game():
    user = get_current_user()
    db = get_db()
    cur = db.cursor()
    now = datetime.now(timezone.utc).isoformat()

    group_ids = get_user_group_ids(user)
    if group_ids:
        placeholders = ','.join('?' * len(group_ids))
        user_groups = db.execute(
            f'SELECT id, name FROM player_groups WHERE id IN ({placeholders}) ORDER BY name',
            group_ids
        ).fetchall()
    else:
        user_groups = []

    if request.method == 'POST':
        game_type = request.form.get('type') or 'Skyjo'
        comments = request.form.get('comments') or ''
        group_id = request.form.get('group_id')
        create_new_group = request.form.get('create_new_group') or (not user_groups and not group_id)
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
            'INSERT INTO skyjo_games (created_at, type, comments, group_id, created_by) VALUES (?, ?, ?, ?, ?)',
            (now, game_type, comments, group_id, user['id'])
        )
        game_id = cur.lastrowid

        for p in players:
            cur.execute('INSERT INTO skyjo_players (game_id, name) VALUES (?, ?)', (game_id, p))

        db.commit()
        return redirect(f"/skyjo/game/{game_id}")

    # GET: récupérer le type de jeu et le groupe depuis les paramètres URL
    default_type = request.args.get('type', None)
    default_group_id = request.args.get('group', None)

    return render_template('new_game.html',
                           default_type=default_type,
                           user_groups=user_groups,
                           default_group_id=default_group_id,
                           user=user)


@skyjo_bp.route('/game/<int:game_id>', methods=['GET'])
@require_auth
def game_view(game_id):
    db = get_db()
    game = db.execute('SELECT * FROM skyjo_games WHERE id=?', (game_id,)).fetchone()
    players = db.execute('SELECT name FROM skyjo_players WHERE game_id=?', (game_id,)).fetchall()
    player_names = [p['name'] for p in players]
    totals = get_totals(game_id, table_name='skyjo_rounds')

    # Récupère les rounds et regroupe par numéro de round en matrice
    rows = db.execute('SELECT round_number, player_name, score, created_at, is_finisher FROM skyjo_rounds WHERE game_id=? ORDER BY round_number, id', (game_id,)).fetchall()
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
            min_score = min(scores.values())
            if finisher_score > min_score and finisher_score > 0:
                round_data['was_doubled'] = True
            else:
                round_data['was_doubled'] = False
        else:
            round_data['was_doubled'] = False

    rounds_matrix = [rounds_by_num[n] for n in sorted(rounds_by_num.keys())]

    user = get_current_user()
    if game['finished']:
        can_edit = is_admin(user)
    else:
        can_edit = True

    return render_template('game.html', game=game, players=player_names, totals=totals,
                           rounds_matrix=rounds_matrix, can_edit=can_edit,
                           is_admin=is_admin(user))


@skyjo_bp.route('/submit_round/<int:game_id>', methods=['POST'])
@require_auth
def submit_round(game_id):
    db = get_db()
    game = db.execute('SELECT * FROM skyjo_games WHERE id=?', (game_id,)).fetchone()
    if not game:
        flash('Partie introuvable')
        return redirect('/skyjo/')
    if game['finished']:
        flash('La partie est terminée, les scores ne sont plus modifiables')
        return redirect(f"/skyjo/game/{game_id}")

    cur = db.execute('SELECT MAX(round_number) as m FROM skyjo_rounds WHERE game_id=?', (game_id,)).fetchone()
    next_round = (cur['m'] or 0) + 1
    players = db.execute('SELECT name FROM skyjo_players WHERE game_id=?', (game_id,)).fetchall()

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
        min_score = min(round_scores.values())
        finisher_score = round_scores[finisher]
        has_strictly_smallest = finisher_score == min_score and list(round_scores.values()).count(min_score) == 1

        if not has_strictly_smallest and finisher_score > 0:
            round_scores[finisher] = finisher_score * 2
            doubled_player = finisher

    # Insérer les rounds avec les scores (possiblement doublés)
    for p in players:
        name = p['name']
        score = round_scores[name]
        is_finisher = 1 if name == finisher else 0

        db.execute('INSERT INTO skyjo_rounds (game_id, round_number, player_name, score, created_at, is_finisher) VALUES (?, ?, ?, ?, ?, ?)',
                   (game_id, next_round, name, score, datetime.now(timezone.utc).isoformat(), is_finisher))

    db.commit()

    if doubled_player:
        flash(f'⚠️ {doubled_player} a terminé mais n\'a pas le meilleur score : points doublés ! ({round_scores[doubled_player]//2} × 2 = {round_scores[doubled_player]})', 'warning')

    # Vérifier si quelqu'un atteint 100 points
    totals = get_totals(game_id, table_name='skyjo_rounds')
    for total in totals.values():
        if total >= 100:
            db.execute('UPDATE skyjo_games SET finished=1 WHERE id=?', (game_id,))
            db.commit()
            flash('Un joueur a atteint 100 points — la partie est terminée.')
            break

    return redirect(f"/skyjo/game/{game_id}")


@skyjo_bp.route('/terminate/<int:game_id>', methods=['POST'])
@require_auth
def terminate(game_id):
    db = get_db()
    has_rounds = db.execute('SELECT 1 FROM skyjo_rounds WHERE game_id=? LIMIT 1', (game_id,)).fetchone()
    if not has_rounds:
        db.execute('DELETE FROM skyjo_players WHERE game_id=?', (game_id,))
        db.execute('DELETE FROM skyjo_games WHERE id=?', (game_id,))
        db.commit()
        flash('Partie vide supprimée.')
        return redirect('/skyjo/')
    db.execute('UPDATE skyjo_games SET finished=1 WHERE id=?', (game_id,))
    db.commit()
    flash('Partie terminée manuellement.')
    return redirect(f"/skyjo/game/{game_id}")


@skyjo_bp.route('/delete_game/<int:game_id>', methods=['POST'])
@require_auth
def delete_game(game_id):
    user = get_current_user()
    if not is_admin(user):
        flash('Action réservée à l\'admin')
        return redirect(f"/skyjo/game/{game_id}")
    db = get_db()
    db.execute('DELETE FROM skyjo_rounds WHERE game_id=?', (game_id,))
    db.execute('DELETE FROM skyjo_players WHERE game_id=?', (game_id,))
    db.execute('DELETE FROM skyjo_games WHERE id=?', (game_id,))
    db.commit()
    flash('Partie supprimée.')
    return redirect('/skyjo/')


@skyjo_bp.route('/edit_round/<int:game_id>/<int:round_number>', methods=['POST'])
@require_auth
def edit_round(game_id, round_number):
    try:
        data = request.get_json()
        if not data or 'scores' not in data:
            return {'success': False, 'error': 'Données manquantes'}, 400

        scores = data['scores']
        finisher = data.get('finisher', None)
        db = get_db()

        game = db.execute('SELECT * FROM skyjo_games WHERE id=?', (game_id,)).fetchone()
        if not game:
            return {'success': False, 'error': 'Partie introuvable'}, 404

        user = get_current_user()
        if game['finished'] and not is_admin(user):
            return {'success': False, 'error': 'Partie terminée, modification réservée à l\'admin'}, 403

        # Vérifier que le round existe
        existing = db.execute(
            'SELECT COUNT(*) as cnt FROM skyjo_rounds WHERE game_id=? AND round_number=?',
            (game_id, round_number)
        ).fetchone()

        if existing['cnt'] == 0:
            return {'success': False, 'error': 'Round introuvable'}, 404

        # Appliquer la règle de doublement si nécessaire
        round_scores = scores.copy()
        if finisher and finisher in round_scores:
            min_score = min(round_scores.values())
            finisher_score = round_scores[finisher]
            has_strictly_smallest = finisher_score == min_score and list(round_scores.values()).count(min_score) == 1

            if not has_strictly_smallest and finisher_score > 0:
                round_scores[finisher] = finisher_score * 2

        # Mettre à jour les scores et le is_finisher
        for player, original_score in scores.items():
            final_score = round_scores[player]
            is_finisher = 1 if player == finisher else 0

            db.execute(
                'UPDATE skyjo_rounds SET score=?, is_finisher=? WHERE game_id=? AND round_number=? AND player_name=?',
                (final_score, is_finisher, game_id, round_number, player)
            )

        db.commit()

        # Vérifier si un joueur a maintenant atteint 100 points
        totals = get_totals(game_id, table_name='skyjo_rounds')
        should_finish = any(total >= 100 for total in totals.values())

        if should_finish:
            db.execute('UPDATE skyjo_games SET finished=1 WHERE id=?', (game_id,))
            db.commit()

        return {'success': True, 'finished': should_finish}

    except Exception as e:
        return {'success': False, 'error': str(e)}, 500


# ========== API endpoints ==========

@skyjo_bp.route('/api/players/search')
@require_auth
def search_players():
    """API pour rechercher des joueurs existants."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    db = get_db()
    # Récupère tous les noms de joueurs uniques
    all_players = db.execute(
        'SELECT DISTINCT name FROM skyjo_players ORDER BY name'
    ).fetchall()

    # Normalise la requête pour la comparaison
    query_normalized = normalize_name(query)

    # Trouve les correspondances
    matches = []
    for row in all_players:
        name = row['name']
        if query_normalized in normalize_name(name):
            matches.append(name)

    return jsonify(matches[:10])


@skyjo_bp.route('/api/players/check-duplicate')
@require_auth
def check_player_duplicate():
    """API pour vérifier si un nom de joueur existe déjà."""
    name = request.args.get('name', '').strip()
    group_id = request.args.get('group_id')

    if not name:
        return jsonify({'exists': False, 'similar_names': [], 'message': ''})

    db = get_db()
    name_normalized = normalize_name(name)

    # Chercher les noms similaires
    if group_id:
        all_players = db.execute('''
            SELECT DISTINCT player_name as name FROM group_members WHERE group_id = ?
            UNION
            SELECT DISTINCT name FROM skyjo_players p
            JOIN skyjo_games g ON p.game_id = g.id
            WHERE g.group_id = ?
        ''', (group_id, group_id)).fetchall()
    else:
        all_players = db.execute(
            'SELECT DISTINCT name FROM skyjo_players ORDER BY name'
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


@skyjo_bp.route('/api/groups/<int:group_id>/members')
@require_auth
def api_group_members(group_id):
    """API pour récupérer les membres d'un groupe."""
    user = get_current_user()
    db = get_db()

    # Vérifier que l'utilisateur a accès au groupe
    access = db.execute('''
        SELECT 1 FROM group_users WHERE group_id = ? AND user_id = ?
        UNION
        SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?
    ''', (group_id, user['id'], group_id, user['id'])).fetchone()

    if not access:
        return jsonify([])

    members = db.execute(
        'SELECT player_name FROM group_members WHERE group_id = ? ORDER BY player_name',
        (group_id,)
    ).fetchall()

    return jsonify([m['player_name'] for m in members])


@skyjo_bp.route('/api/groups/suggest')
@require_auth
def api_groups_suggest():
    """API pour suggérer des groupes basés sur les joueurs sélectionnés."""
    user = get_current_user()
    db = get_db()

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
        WHERE pg.id IN (
            SELECT group_id FROM group_users WHERE user_id = ?
            UNION
            SELECT group_id FROM group_members WHERE user_id = ?
        )
        HAVING matching_members > 0
        ORDER BY matching_members DESC, total_members ASC
        LIMIT 5
    '''.format(placeholders=','.join('?' * len(player_names))),
        (*player_names, user['id'], user['id'])
    ).fetchall()

    return jsonify([{
        'id': g['id'],
        'name': g['name'],
        'matching': g['matching_members'],
        'total': g['total_members']
    } for g in user_groups])
