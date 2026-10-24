"""
Calcul des statistiques Mantis à partir des lignes brutes de la base (sans Flask).
Chaque partie est rejouée à partir de son journal d'actions (voir scoring.replay).
"""
import json
from collections import defaultdict

from core.stats import award, player_profile
from games.mantis.scoring import EVENT_SCORE, replay, winners


def _replay_sessions(sessions, session_players, score_rows):
    """{session_id: (joueurs, état rejoué)} pour chaque partie."""
    players_by_session = defaultdict(list)
    for sp in session_players:
        players_by_session[sp['session_id']].append(sp['player_name'])
    events_by_session = defaultdict(list)
    for row in score_rows:
        events_by_session[row['session_id']].append(row)
    return {s['id']: (players_by_session[s['id']], replay(players_by_session[s['id']], events_by_session[s['id']]))
            for s in sessions}


def compute_stats(sessions, session_players, score_rows):
    """
    Retourne {'players': [...], 'podium': [...], 'awards': [...], 'total_games', 'finished_games'}.
    Seules les parties terminées comptent pour les victoires et les scores finaux.
    """
    finished = {s['id'] for s in sessions if s['finished']}
    replays = _replay_sessions(sessions, session_players, score_rows)

    players = defaultdict(lambda: {
        'games': 0, 'finished_games': 0, 'wins': 0, 'cards': 0, 'best_game': None,
        'steals': 0, 'sprints': 0, 'best_move': 0, 'best_move_session': None, 'finals': [],
    })
    for session_id, (names, state) in replays.items():
        game_winners = winners(state['totals'], state['tanks'])
        for name in names:
            p = players[name]
            p['games'] += 1
            p['steals'] += state['steals'].get(name, 0)
            if state['sprinter'] == name:
                p['sprints'] += 1
            if session_id in finished:
                final = state['totals'][name]
                p['finished_games'] += 1
                p['cards'] += final
                p['finals'].append(final)
                if p['best_game'] is None or final > p['best_game']:
                    p['best_game'] = final
                # Victoire : gagnant unique (un ex aequo ne compte pas)
                if game_winners == [name]:
                    p['wins'] += 1

    # Plus gros « Marquer » de chaque joueur
    for row in score_rows:
        kind = json.loads(row['details']).get('type') if row['details'] else EVENT_SCORE
        if kind == EVENT_SCORE and row['score'] > players[row['player_name']]['best_move']:
            players[row['player_name']]['best_move'] = row['score']
            players[row['player_name']]['best_move_session'] = row['session_id']

    rows = []
    for name, p in players.items():
        if not p['games']:
            continue
        done = p['finished_games']
        rows.append({
            'name': name,
            **p,
            'avg': round(p['cards'] / done, 1) if done else 0,
            'win_rate': round(100 * p['wins'] / done) if done else 0,
            'steals_per_game': round(p['steals'] / p['games'], 1),
        })
    rows.sort(key=lambda r: (-r['wins'], -r['win_rate'], -r['avg'], r['name']))

    return {
        'players': rows,
        'podium': [r for r in rows if r['wins'] > 0][:3],
        'awards': _awards(rows),
        'total_games': len(sessions),
        'finished_games': len(finished),
    }


def _awards(rows):
    awards = []
    move = max(rows, key=lambda r: r['best_move'], default=None)
    if move and move['best_move']:
        awards.append(award('tile-best', '💎', 'Le Gros Coup', move['best_move'], 'cartes marquées d\'un coup',
                             move['name'], f"Partie #{move['best_move_session']}"))

    thief = max(rows, key=lambda r: (r['steals_per_game'], r['steals']), default=None)
    if thief and thief['steals']:
        awards.append(award('tile-mantis-steal', '🦐', 'Le Pickpocket', thief['steals_per_game'], 'vols par partie',
                             thief['name'], f"{thief['steals']} vols au total"))

    sprinter = max(rows, key=lambda r: r['sprints'], default=None)
    if sprinter and sprinter['sprints']:
        awards.append(award('tile-precoce', '🏃', 'Le Sprinteur', sprinter['sprints'], 'fois premier au seuil',
                             sprinter['name'], 'Premier à 10 cartes (15 à deux)'))

    collector = max((r for r in rows if r['best_game'] is not None), key=lambda r: r['best_game'], default=None)
    if collector:
        awards.append(award('tile-mantis-collect', '🌈', 'Le Collectionneur', collector['best_game'],
                             'cartes en une partie', collector['name'], 'Meilleur score final'))
    return awards


def compute_player_stats(player, sessions, session_players, score_rows):
    """Statistiques individuelles d'un joueur ; None s'il n'a joué aucune partie."""
    return player_profile(compute_stats, player, sessions, session_players, score_rows)
