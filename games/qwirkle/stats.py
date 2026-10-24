"""
Calcul des statistiques Qwirkle à partir des lignes brutes de la base (sans Flask).
Chaque partie est rejouée à partir de ses tours (voir scoring.replay).
"""
from collections import defaultdict

from core.stats import award, player_profile
from games.qwirkle.scoring import END_BONUS, QWIRKLE_BONUS, replay, winners

# Nombre minimum de tours pour figurer dans les palmarès en moyenne
MIN_TURNS_FOR_AVERAGES = 5


def compute_stats(sessions, session_players, score_rows):
    """
    Retourne {'players': [...], 'podium': [...], 'awards': [...], 'total_games', 'finished_games'}.
    Seules les parties terminées comptent pour les victoires et les scores finaux.
    """
    finished = {s['id'] for s in sessions if s['finished']}
    players_by_session = defaultdict(list)
    for sp in session_players:
        players_by_session[sp['session_id']].append(sp['player_name'])
    rows_by_session = defaultdict(list)
    for row in score_rows:
        rows_by_session[row['session_id']].append(row)

    players = defaultdict(lambda: {
        'games': 0, 'finished_games': 0, 'wins': 0, 'points': 0, 'turn_points': 0, 'turns': 0,
        'best_game': None, 'best_turn': 0, 'best_turn_session': None,
        'qwirkles': 0, 'swaps': 0, 'finishes': 0, 'finals': [],
    })
    for s in sessions:
        names = players_by_session[s['id']]
        state = replay(names, rows_by_session[s['id']])
        game_winners = winners(state['totals'])
        for name in names:
            p = players[name]
            p['games'] += 1
            p['turns'] += state['turns'][name]
            p['qwirkles'] += state['qwirkles'][name]
            p['swaps'] += state['swaps'][name]
            p['turn_points'] += state['totals'][name] - (END_BONUS if state['finisher'] == name else 0)
            if state['best_turn'][name] > p['best_turn']:
                p['best_turn'] = state['best_turn'][name]
                p['best_turn_session'] = s['id']
            if state['finisher'] == name:
                p['finishes'] += 1
            if s['id'] in finished:
                final = state['totals'][name]
                p['finished_games'] += 1
                p['points'] += final
                p['finals'].append(final)
                if p['best_game'] is None or final > p['best_game']:
                    p['best_game'] = final
                # Victoire : gagnant unique (un ex aequo ne compte pas)
                if game_winners == [name]:
                    p['wins'] += 1

    rows = []
    for name, p in players.items():
        if not p['games']:
            continue
        done = p['finished_games']
        rows.append({
            'name': name,
            **p,
            'avg': round(p['points'] / done, 1) if done else 0,
            'avg_turn': round(p['turn_points'] / p['turns'], 1) if p['turns'] else 0,
            'win_rate': round(100 * p['wins'] / done) if done else 0,
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
    king = max(rows, key=lambda r: r['qwirkles'], default=None)
    if king and king['qwirkles']:
        awards.append(award('tile-qwirkle-king', '⭐', 'Le Roi du Qwirkle', king['qwirkles'],
                             'Qwirkle' + ('s' if king['qwirkles'] > 1 else ''), king['name'],
                             f"+{king['qwirkles'] * QWIRKLE_BONUS} points de bonus"))

    big = max(rows, key=lambda r: r['best_turn'], default=None)
    if big and big['best_turn']:
        awards.append(award('tile-best', '💥', 'Le Gros Tour', big['best_turn'], 'points en un tour',
                             big['name'], f"Partie #{big['best_turn_session']}"))

    with_turns = [r for r in rows if r['turns'] >= MIN_TURNS_FOR_AVERAGES]
    if with_turns:
        steady = max(with_turns, key=lambda r: r['avg_turn'])
        awards.append(award('tile-qwirkle-steady', '📈', 'Le Régulier', steady['avg_turn'], 'points par tour',
                             steady['name'], f"{steady['turns']} tours joués"))

    finisher = max(rows, key=lambda r: r['finishes'], default=None)
    if finisher and finisher['finishes']:
        awards.append(award('tile-precoce', '🏁', 'Le Finisseur', finisher['finishes'],
                             'fois premier à vider sa main', finisher['name'], f'+{END_BONUS} points à chaque fois'))

    mixer = max(rows, key=lambda r: r['swaps'], default=None)
    if mixer and mixer['swaps']:
        awards.append(award('tile-worst', '🔄', 'Le Brasseur', mixer['swaps'],
                             'échange' + ('s' if mixer['swaps'] > 1 else '') + ' de tuiles', mixer['name'],
                             'Préfère piocher que jouer'))
    return awards


def compute_player_stats(player, sessions, session_players, score_rows):
    """Statistiques individuelles d'un joueur ; None s'il n'a joué aucune partie."""
    return player_profile(compute_stats, player, sessions, session_players, score_rows)
