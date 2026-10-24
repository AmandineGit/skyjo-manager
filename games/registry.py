"""
Jeux stockés dans les tables génériques (game_sessions / session_players / session_scores).
Lu par le hub, le menu des statistiques et les pages de groupes : ajouter un jeu ici
le fait apparaître partout. Skyjo, historique, a ses propres tables et n'y figure pas.
"""

GENERIC_GAMES = [
    {
        'slug': 'flip7',
        'name': 'Flip 7',
        'url': '/familyboardgame/flip7',
        'image': '/familyboardgame/images/Flip7.webp',
        'description': 'Stop ou encore ? Le premier à 200 points',
    },
    {
        'slug': 'mantis',
        'name': 'Mantis',
        'url': '/familyboardgame/mantis',
        'image': '/familyboardgame/images/Mantis.jpg',
        'description': 'Marquer ou voler ? Le plus de cartes gagne',
    },
    {
        'slug': 'qwirkle',
        'name': 'Qwirkle',
        'url': '/familyboardgame/qwirkle',
        'image': '/familyboardgame/images/qwirkle.png',
        'description': 'Formes et couleurs : visez le Qwirkle !',
    },
]

GAMES_BY_SLUG = {g['slug']: g for g in GENERIC_GAMES}
