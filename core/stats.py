"""
Briques communes aux statistiques des jeux génériques (sans Flask).
"""
from statistics import median

from core.sessions import frequent_coplayers, first_game_date


def award(tile, icon, title, value, label, name, details):
    """Une dalle de palmarès, au format des tuiles Metro des stats Skyjo."""
    return {'tile': tile, 'icon': icon, 'title': title, 'value': value,
            'label': label, 'name': name, 'details': details}


def player_profile(compute_stats, player, sessions, session_players, score_rows):
    """
    Stats individuelles pour les jeux dont compute_stats fournit, par joueur, 'finals'
    (scores finaux des parties terminées) : ligne du joueur + médiane, ancienneté, co-joueurs.
    None si le joueur n'a joué aucune partie.
    """
    base = next((p for p in compute_stats(sessions, session_players, score_rows)['players']
                 if p['name'] == player), None)
    if base is None:
        return None
    return {
        **base,
        'median': median(base['finals']) if base['finals'] else 0,
        'first_game_date': first_game_date(player, sessions, session_players),
        'frequent_players': frequent_coplayers(player, session_players),
    }
