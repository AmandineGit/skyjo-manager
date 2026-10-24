"""
Règles de score Flip 7 (indépendantes de Flask, testables seules).

- Score de manche = chiffres (doublés si carte x2) + cartes bonus + 15 si Flip 7
- Doublon : 0 point pour la manche
- Stop (le joueur s'arrête et garde ses points) : sans effet sur le score, sert aux statistiques
- Fin de partie : à la fin d'une manche, dès qu'un joueur a 200 points ou plus ;
  le meilleur total gagne. En cas d'égalité en tête, les joueurs à égalité
  jouent une manche de départage.
"""

TARGET_SCORE = 200
FLIP7_BONUS = 15

STATUS_ONGOING = 'ongoing'
STATUS_TIEBREAK = 'tiebreak'
STATUS_FINISHED = 'finished'


def round_score(numbers=0, bonus=0, x2=False, flip7=False, bust=False):
    """Score d'un joueur pour une manche. La carte x2 ne double que les chiffres."""
    if bust:
        return 0
    return numbers * (2 if x2 else 1) + bonus + (FLIP7_BONUS if flip7 else 0)


def game_outcome(totals):
    """
    État de la partie à partir des totaux {joueur: points}.
    Retourne (statut, leaders) :
    - STATUS_ONGOING, []            : personne n'a atteint 200
    - STATUS_FINISHED, [gagnant]    : 200 atteint, un seul meilleur total
    - STATUS_TIEBREAK, [ex aequo]   : 200 atteint, égalité en tête -> manche de départage
    """
    if not totals or max(totals.values()) < TARGET_SCORE:
        return STATUS_ONGOING, []
    best = max(totals.values())
    leaders = sorted(p for p, t in totals.items() if t == best)
    if len(leaders) == 1:
        return STATUS_FINISHED, leaders
    return STATUS_TIEBREAK, leaders


def parse_entry(form, index):
    """
    Lit la saisie d'un joueur (champs suffixés par son index dans le formulaire).
    Retourne (details, erreur) ; details est le dict stocké en JSON dans session_scores.
    """
    values = {}
    for field, label, maximum in (('numbers', 'Chiffres', 999), ('bonus', 'Bonus', 99)):
        raw = (form.get(f'{field}_{index}') or '').strip()
        if raw == '':
            values[field] = 0
            continue
        if not raw.isdigit() or int(raw) > maximum:
            return None, f'{label} : entier entre 0 et {maximum} attendu (reçu « {raw} »)'
        values[field] = int(raw)

    details = {
        'numbers': values['numbers'],
        'bonus': values['bonus'],
        'x2': bool(form.get(f'x2_{index}')),
        'flip7': bool(form.get(f'flip7_{index}')),
        'bust': bool(form.get(f'bust_{index}')),
        'stop': bool(form.get(f'stop_{index}')),
    }
    # Une manche se termine d'une seule façon pour un joueur : doublon, Flip 7 ou stop
    if details['bust']:
        # Un doublon annule tout le reste de la manche
        details.update(numbers=0, bonus=0, x2=False, flip7=False, stop=False)
    elif details['flip7']:
        details['stop'] = False
    return details, None


def score_from_details(details):
    return round_score(details['numbers'], details['bonus'],
                       details['x2'], details['flip7'], details['bust'])
