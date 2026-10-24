"""
Calcul des statistiques Flip 7 à partir des lignes brutes de la base (sans Flask).
"""
import json
from statistics import median
from collections import defaultdict

from core.sessions import frequent_coplayers, first_game_date
from core.stats import award
from games.flip7.scoring import FLIP7_BONUS

# Nombre minimum de manches pour figurer dans les palmarès en pourcentage
MIN_ROUNDS_FOR_RATES = 5


def compute_stats(sessions, session_players, score_rows):
    """
    sessions        : [{'id', 'finished'}]
    session_players : [{'session_id', 'player_name'}]
    score_rows      : [{'session_id', 'player_name', 'score', 'details'}]
    Retourne {'players': [...], 'podium': [...], 'awards': [...], 'total_games', 'total_rounds'}.
    """
    finished = {s['id'] for s in sessions if s['finished']}

    players = defaultdict(lambda: {
        'games': 0, 'wins': 0, 'rounds': 0, 'points': 0, 'best_round': None,
        'busts': 0, 'flip7s': 0, 'x2s': 0, 'stops': 0,
        'best_round_number': None, 'best_round_session': None,
    })
    for sp in session_players:
        players[sp['player_name']]['games'] += 1

    totals_by_session = defaultdict(lambda: defaultdict(int))
    round_keys = set()
    for row in score_rows:
        p = players[row['player_name']]
        details = json.loads(row['details']) if row['details'] else {}
        p['rounds'] += 1
        p['points'] += row['score']
        if p['best_round'] is None or row['score'] > p['best_round']:
            p['best_round'] = row['score']
            p['best_round_number'] = row.get('round_number')
            p['best_round_session'] = row['session_id']
        p['busts'] += 1 if details.get('bust') else 0
        p['flip7s'] += 1 if details.get('flip7') else 0
        p['x2s'] += 1 if details.get('x2') else 0
        p['stops'] += 1 if details.get('stop') else 0
        totals_by_session[row['session_id']][row['player_name']] += row['score']
        round_keys.add((row['session_id'], row.get('round_number')))

    # Victoire : meilleur total d'une partie terminée, sans égalité
    for session_id in finished:
        totals = totals_by_session.get(session_id)
        if not totals:
            continue
        best = max(totals.values())
        leaders = [name for name, t in totals.items() if t == best]
        if len(leaders) == 1:
            players[leaders[0]]['wins'] += 1

    rows = []
    for name, p in players.items():
        if not p['games']:
            continue
        rows.append({
            'name': name,
            **p,
            'avg': round(p['points'] / p['rounds'], 1) if p['rounds'] else 0,
            'win_rate': round(100 * p['wins'] / p['games']),
            'bust_rate': round(100 * p['busts'] / p['rounds']) if p['rounds'] else 0,
            'stop_rate': round(100 * p['stops'] / p['rounds']) if p['rounds'] else 0,
        })
    rows.sort(key=lambda r: (-r['wins'], -r['win_rate'], -r['avg'], r['name']))

    return {
        'players': rows,
        'podium': [r for r in rows if r['wins'] > 0][:3],
        'awards': _awards(rows),
        'total_games': len(sessions),
        'total_rounds': len(round_keys),
    }


def _plural(n, word):
    return word + ('s' if n > 1 else '')


def _awards(rows):
    """Dalles de palmarès, dans l'ordre d'affichage (même esprit que Skyjo : pire, meilleur, puis les spécialités)."""
    awards = []
    with_rounds = [r for r in rows if r['rounds'] >= MIN_ROUNDS_FOR_RATES]

    if with_rounds:
        kamikaze = max(with_rounds, key=lambda r: r['bust_rate'])
        if kamikaze['busts']:
            awards.append(award('tile-worst', '💥', 'Le Kamikaze', f"{kamikaze['bust_rate']} %", 'de doublons',
                                 kamikaze['name'], f"{kamikaze['busts']} {_plural(kamikaze['busts'], 'doublon')} en {kamikaze['rounds']} manches"))

    best = max(rows, key=lambda r: r['best_round'] or 0, default=None)
    if best and best['best_round']:
        awards.append(award('tile-best', '🚀', 'La manche de rêve', best['best_round'], 'points',
                             best['name'], f"Manche #{best['best_round_number']} · Partie #{best['best_round_session']}"))

    flip7 = max(rows, key=lambda r: r['flip7s'], default=None)
    if flip7 and flip7['flip7s']:
        awards.append(award('tile-f7-flip7', '🎯', 'Le Roi du Flip 7', flip7['flip7s'], 'Flip 7 ' + _plural(flip7['flip7s'], 'réussi'),
                             flip7['name'], f"+{FLIP7_BONUS * flip7['flip7s']} pts de bonus"))

    if with_rounds:
        banker = max(with_rounds, key=lambda r: r['stop_rate'])
        if banker['stops']:
            awards.append(award('tile-f7-stop', '✋', 'Le Banquier', f"{banker['stop_rate']} %", 'de manches finies par un stop',
                                 banker['name'], 'Sait dire stop à temps'))
        prudent = min(with_rounds, key=lambda r: r['bust_rate'])
        awards.append(award('tile-f7-prudent', '🛡️', 'Le Prudent', f"{prudent['bust_rate']} %", 'de doublons',
                             prudent['name'], f"{prudent['rounds']} manches jouées"))

    x2 = max(rows, key=lambda r: r['x2s'], default=None)
    if x2 and x2['x2s']:
        awards.append(award('tile-precoce', '✖️', 'Le Multiplicateur', x2['x2s'], _plural(x2['x2s'], 'carte') + ' ×2',
                             x2['name'], 'Double la mise'))
    return awards


def compute_player_stats(player, sessions, session_players, score_rows):
    """
    Statistiques individuelles d'un joueur, mêmes entrées que compute_stats
    (sessions avec 'created_at'). Retourne None si le joueur n'a joué aucune manche.
    """
    rows = [r for r in score_rows if r['player_name'] == player]
    if not rows:
        return None
    base = next(p for p in compute_stats(sessions, session_players, score_rows)['players'] if p['name'] == player)

    top = max(rows, key=lambda r: r['score'])

    return {
        **base,
        'median': median(r['score'] for r in rows),
        'top': {'score': top['score'], 'round_number': top.get('round_number'), 'session_id': top['session_id']},
        'first_game_date': first_game_date(player, sessions, session_players),
        'frequent_players': frequent_coplayers(player, session_players),
    }
