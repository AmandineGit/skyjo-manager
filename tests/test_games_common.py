"""
Routes communes aux jeux génériques (core/game_routes.py), vérifiées pour chaque jeu :
liste des parties, nouvelle partie, droits, suppression admin, règles, statistiques.
"""
import re
import sqlite3

import pytest

from games.registry import GENERIC_GAMES

# Une action qui fait marquer des points à Anna, propre à chaque jeu
FIRST_SCORE = {
    'flip7': lambda c, sid: c.post(f'/flip7/game/{sid}/round', data={
        'player': ['Anna', 'Ben'], 'numbers_0': '30', 'numbers_1': '10'}),
    'mantis': lambda c, sid: c.post(f'/mantis/game/{sid}/action', data={
        'player': 'Anna', 'action': 'score', 'count': '30'}),
}
SLUGS = [g['slug'] for g in GENERIC_GAMES]


def test_every_registered_game_has_a_scenario():
    assert set(SLUGS) == set(FIRST_SCORE)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    import core.db
    path = str(tmp_path / 'test.db')
    monkeypatch.setattr(core.db, 'DB_PATH', path)
    import app as fbg
    with fbg.app.app_context():
        core.db.init_db()
    con = sqlite3.connect(path)
    con.execute("INSERT INTO users (email, password_hash, player_name) VALUES ('anna@x.fr', 'x', 'Anna')")
    con.execute("INSERT INTO users (email, password_hash, player_name) VALUES ('admin@skyjo.local', 'x', 'Admin')")
    con.execute("INSERT INTO users (email, password_hash, player_name) VALUES ('zoe@x.fr', 'x', 'Zoé')")
    con.commit()
    con.close()
    return path


def _client(user_id):
    import app as fbg
    c = fbg.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = user_id
    return c


@pytest.mark.parametrize('slug', SLUGS)
def test_common_routes(db_path, slug):
    anna, admin, zoe = _client(1), _client(2), _client(3)

    assert anna.get(f'/{slug}/').status_code == 200
    assert anna.get(f'/{slug}/new').status_code == 200
    assert anna.get(f'/{slug}/rules').status_code == 200
    assert 'Aucune statistique' in anna.get(f'/{slug}/stats').get_data(as_text=True)

    # Au moins 2 joueurs
    rv = anna.post(f'/{slug}/new', data={'player_1': 'Anna', 'create_new_group': '1'})
    assert rv.headers['Location'].endswith(f'/familyboardgame/{slug}/new')

    rv = anna.post(f'/{slug}/new', data={'player_1': 'Anna', 'player_2': 'Ben', 'create_new_group': '1'})
    sid = int(re.search(r'/game/(\d+)', rv.headers['Location']).group(1))
    FIRST_SCORE[slug](anna, sid)

    listing = anna.get(f'/{slug}/').get_data(as_text=True)
    assert f'Partie #{sid}' in listing and '👑 Anna, 30' in listing

    # Un utilisateur hors du groupe ne voit pas la partie
    assert zoe.get(f'/{slug}/game/{sid}').status_code == 404
    assert f'Partie #{sid}' not in zoe.get(f'/{slug}/').get_data(as_text=True)

    # Stats et page joueur
    assert anna.get(f'/{slug}/stats/player/Anna').status_code == 200
    assert anna.get(f'/{slug}/stats?group=999').status_code == 302

    # Suppression : refusée à un joueur, acceptée pour l'admin
    anna.post(f'/{slug}/game/{sid}/delete')
    assert anna.get(f'/{slug}/game/{sid}').status_code == 200
    admin.post(f'/{slug}/game/{sid}/delete')
    assert anna.get(f'/{slug}/game/{sid}').status_code == 404


def test_admin_is_not_listed_as_linked_account(db_path):
    """L'admin voit tous les groupes : il n'apparaît pas dans « Comptes liés », même s'il y est rattaché."""
    anna, admin = _client(1), _client(2)
    admin.post('/mantis/new', data={'player_1': 'Anna', 'player_2': 'Ben', 'create_new_group': '1'})
    anna.post('/flip7/new', data={'player_1': 'Anna', 'player_2': 'Ben', 'create_new_group': '1'})

    con = sqlite3.connect(db_path)
    assert con.execute('SELECT COUNT(*) FROM group_users WHERE user_id = 2').fetchone()[0] == 0
    # Rattachement hérité (migration v1, anciens groupes) : masqué à l'affichage
    con.execute("INSERT INTO group_users (group_id, user_id, role) VALUES (2, 2, 'owner')")
    con.commit()
    con.close()

    detail = admin.get('/groups/2').get_data(as_text=True)
    linked = detail[detail.index('Comptes liés'):]
    assert 'Anna' in linked and 'Admin' not in linked
    assert 'Mantis' in admin.get('/groups/1').get_data(as_text=True)   # l'admin voit toujours son groupe
