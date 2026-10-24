"""
Règles Qwirkle telles que suivies dans l'app (sans Flask, testables seules).

Partie tour par tour : à chaque tour, un seul joueur marque des points
(1 point par tuile de chaque ligne créée ou complétée), plus 6 points supplémentaires
par « Qwirkle » (ligne de 6 tuiles terminée ; une pose peut en terminer plusieurs).
Le joueur qui pose toutes ses tuiles en premier, sac vide, termine la partie
et gagne 6 points de bonus. Le plus haut score gagne ; égalité = ex aequo.

Une ligne session_scores par tour, dans l'ordre (round_number = n° de tour joué) :
- TYPE_TURN  : un tour, score = total du tour (bonus Qwirkle compris), détails 'points' (points des
               lignes saisis), 'qwirkles' (nombre de Qwirkles du tour) et 'swap' (échange, 0 point)
- TYPE_BONUS : bonus de fin (+6) du joueur qui a vidé sa main
"""
import json

END_BONUS = 6
QWIRKLE_BONUS = 6

TYPE_TURN = 'turn'
TYPE_BONUS = 'bonus'


def details_of(row):
    return json.loads(row['details']) if row['details'] else {'type': TYPE_TURN}


def qwirkles_of(details):
    """Nombre de Qwirkles d'un tour."""
    return details.get('qwirkles', 0)


def turn_score(points, qwirkles):
    """Total d'un tour : points des lignes + 6 par Qwirkle."""
    return points + QWIRKLE_BONUS * qwirkles


def replay(players, rows):
    """
    Rejoue les tours d'une partie.
    Retourne {'totals', 'qwirkles', 'swaps', 'turns', 'best_turn', 'finisher', 'sheet'} où
    sheet est la feuille de score : une ligne par tour de table, {joueur: ligne de tour}.
    """
    totals = {p: 0 for p in players}
    qwirkles = {p: 0 for p in players}
    swaps = {p: 0 for p in players}
    turns = {p: 0 for p in players}
    best_turn = {p: 0 for p in players}
    finisher = None
    sheet, line = [], {}

    for row in rows:
        p = row['player_name']
        d = details_of(row)
        totals[p] = totals.get(p, 0) + row['score']
        if d.get('type') == TYPE_BONUS:
            finisher = p
            continue
        turns[p] = turns.get(p, 0) + 1
        qwirkles[p] = qwirkles.get(p, 0) + qwirkles_of(d)
        swaps[p] = swaps.get(p, 0) + (1 if d.get('swap') else 0)
        best_turn[p] = max(best_turn.get(p, 0), row['score'])
        # Nouvelle ligne de feuille dès qu'un joueur rejoue dans le même tour de table
        if p in line:
            sheet.append(line)
            line = {}
        line[p] = {'number': row['round_number'], 'score': row['score'],
                   'qwirkles': qwirkles_of(d), 'swap': bool(d.get('swap'))}
    if line:
        sheet.append(line)

    return {'totals': totals, 'qwirkles': qwirkles, 'swaps': swaps, 'turns': turns,
            'best_turn': best_turn, 'finisher': finisher, 'sheet': sheet}


def next_player(players, rows):
    """Joueur dont c'est le tour : celui qui suit l'auteur du dernier tour joué."""
    played = [r['player_name'] for r in rows if details_of(r).get('type') != TYPE_BONUS]
    if not played or played[-1] not in players:
        return players[0] if players else None
    return players[(players.index(played[-1]) + 1) % len(players)]


def winners(totals):
    """Meilleur(s) total(aux) ; plusieurs noms = ex aequo."""
    if not totals:
        return []
    best = max(totals.values())
    return sorted(p for p, t in totals.items() if t == best)
