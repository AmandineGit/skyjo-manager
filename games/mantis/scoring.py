"""
Règles Mantis telles que jouées dans l'app (sans Flask, testables seules).

Règle maison : on ne s'arrête pas à 10 cartes, on joue jusqu'à épuisement de la pioche.
Le plus grand nombre de cartes dans la pile de score gagne ; en cas d'égalité,
le plus de cartes dans le tank (règle officielle « pioche vide ») ; sinon ex aequo.
Le seuil officiel (10 cartes, 15 à 2 joueurs) reste un repère : le premier à le franchir
est « le sprinteur ».

Une partie est un journal d'actions (une ligne session_scores par action, dans l'ordre) :
- EVENT_SCORE : un « Marquer » réussi, score = cartes ajoutées à la pile
- EVENT_STEAL : un vol réussi, score = 0 (les cartes vont dans le tank, pas dans la pile)
- EVENT_FIX   : correction via ✏️, score = écart de cartes, détail 'steals' = écart de vols
- EVENT_TANK  : départage en fin de partie, score = 0, détail 'tank' = cartes dans le tank
"""
import json

EVENT_SCORE = 'score'
EVENT_STEAL = 'steal'
EVENT_FIX = 'fix'
EVENT_TANK = 'tank'


def sprint_threshold(nb_players):
    """Seuil officiel de victoire : 10 cartes, 15 à deux joueurs."""
    return 15 if nb_players == 2 else 10


def replay(players, events):
    """
    Rejoue le journal d'une partie.
    events : lignes ordonnées avec 'player_name', 'score', 'details' (JSON).
    Retourne {'totals', 'steals', 'tanks', 'sprinter', 'best_move'}.
    """
    totals = {p: 0 for p in players}
    steals = {p: 0 for p in players}
    tanks = {}
    sprinter = None
    best_move = None
    threshold = sprint_threshold(len(players))

    for e in events:
        p = e['player_name']
        details = json.loads(e['details']) if e['details'] else {}
        kind = details.get('type', EVENT_SCORE)
        totals[p] = totals.get(p, 0) + e['score']
        if kind == EVENT_STEAL:
            steals[p] = steals.get(p, 0) + 1
        elif kind == EVENT_FIX:
            steals[p] = steals.get(p, 0) + details.get('steals', 0)
        elif kind == EVENT_TANK:
            tanks[p] = details.get('tank', 0)
        elif kind == EVENT_SCORE and (best_move is None or e['score'] > best_move['score']):
            best_move = {'player': p, 'score': e['score']}
        if sprinter is None and totals[p] >= threshold:
            sprinter = p

    return {'totals': totals, 'steals': steals, 'tanks': tanks,
            'sprinter': sprinter, 'best_move': best_move}


def leaders(totals):
    """Joueurs en tête (plusieurs en cas d'égalité)."""
    if not totals:
        return []
    best = max(totals.values())
    return sorted(p for p, t in totals.items() if t == best)


def winners(totals, tanks):
    """
    Gagnant(s) d'une partie terminée : meilleur total, puis départage au tank
    si les tanks des ex aequo sont connus. Plusieurs noms = ex aequo.
    """
    top = leaders(totals)
    if len(top) <= 1 or not all(p in tanks for p in top):
        return top
    best_tank = max(tanks[p] for p in top)
    return [p for p in top if tanks[p] == best_tank]
