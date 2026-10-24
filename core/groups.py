"""
Logique commune à la création de partie : joueurs saisis et groupe associé.
Partagée entre tous les jeux (Skyjo, Flip 7, ...).
"""
from core.db import get_db, normalize_name
from core.auth import get_user_group_ids, is_admin


def get_user_groups(user):
    """Groupes accessibles par l'utilisateur, pour le sélecteur de groupe."""
    group_ids = get_user_group_ids(user)
    if not group_ids:
        return []
    placeholders = ','.join('?' * len(group_ids))
    return get_db().execute(
        f'SELECT id, name FROM player_groups WHERE id IN ({placeholders}) ORDER BY name',
        group_ids
    ).fetchall()


def parse_players(form):
    """
    Récupère les joueurs du formulaire de nouvelle partie (player_1..player_10,
    ou champ legacy 'players' séparé par des virgules).
    Retourne (players, erreur) ; erreur vaut None si la liste est valide.
    """
    players = []
    for i in range(1, 11):
        p = form.get(f'player_{i}')
        if p and p.strip():
            players.append(p.strip())
    if not players:
        players_raw = form.get('players') or ''
        players = [p.strip() for p in players_raw.split(',') if p.strip()]
    if not players:
        return [], 'Ajoutez au moins un joueur (au moins 1).'

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
        return [], (f'Noms de joueurs identiques détectés : {dup_msg}. '
                    f'Si ce sont des personnes différentes, ajoutez une distinction (ex: initiale du nom).')

    return players, None


def _add_missing_members(cur, group_id, players):
    existing_members = cur.execute(
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


def resolve_game_group(cur, user, user_groups, form, players, now):
    """
    Détermine le groupe de la nouvelle partie et y ajoute les joueurs manquants :
    - création d'un groupe si demandé (ou si l'utilisateur n'en a aucun),
    - sinon groupe sélectionné, à défaut le premier groupe de l'utilisateur.
    N'effectue pas de commit. Retourne l'id du groupe.
    """
    group_id = form.get('group_id')
    create_new_group = form.get('create_new_group') or (not user_groups and not group_id)
    new_group_name = form.get('new_group_name', '').strip()

    if create_new_group:
        # Générer un nom automatique si non fourni
        if not new_group_name:
            count = cur.execute(
                'SELECT COUNT(*) as c FROM player_groups WHERE created_by = ?',
                (user['id'],)
            ).fetchone()['c']
            new_group_name = f"Groupe {count + 1}"
        cur.execute(
            'INSERT INTO player_groups (name, created_by, created_at) VALUES (?, ?, ?)',
            (new_group_name, user['id'], now)
        )
        group_id = cur.lastrowid
        # Ajouter l'utilisateur comme owner (sauf l'admin, qui voit déjà tous les groupes)
        if not is_admin(user):
            cur.execute(
                'INSERT INTO group_users (group_id, user_id, role) VALUES (?, ?, ?)',
                (group_id, user['id'], 'owner')
            )
        for p in players:
            cur.execute(
                'INSERT INTO group_members (group_id, player_name) VALUES (?, ?)',
                (group_id, p)
            )
        return group_id

    # Si pas de groupe sélectionné, utiliser le premier groupe de l'utilisateur
    if not group_id:
        group_id = user_groups[0]['id']
    _add_missing_members(cur, group_id, players)
    return group_id
