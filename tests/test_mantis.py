import json
import re
import sqlite3

import pytest

from games.mantis.scoring import replay, winners, sprint_threshold


def _ev(player, score, kind, **extra):
    return {'player_name': player, 'score': score, 'details': json.dumps({'type': kind, **extra})}


# ---------- Règles ----------

def test_sprint_threshold():
    assert sprint_threshold(2) == 15
    assert sprint_threshold(4) == 10


def test_replay_totals_steals_fix_and_sprinter():
    state = replay(['A', 'B', 'C'], [
        _ev('A', 4, 'score'),
        _ev('B', 0, 'steal'),
        _ev('B', 7, 'score'),
        _ev('A', 6, 'score'),          # A passe 10 en premier
        _ev('B', 5, 'score'),
        _ev('B', -2, 'fix', steals=1),  # correction : -2 cartes, +1 vol
    ])
    assert state['totals'] == {'A': 10, 'B': 10, 'C': 0}
    assert state['steals'] == {'A': 0, 'B': 2, 'C': 0}
    assert state['sprinter'] == 'A'
    assert state['best_move'] == {'player': 'B', 'score': 7}


def test_winners_tiebreak_on_tank():
    assert winners({'A': 12, 'B': 9}, {}) == ['A']
    assert winners({'A': 12, 'B': 12}, {}) == ['A', 'B']
    assert winners({'A': 12, 'B': 12}, {'A': 3, 'B': 5}) == ['B']
    assert winners({'A': 12, 'B': 12}, {'A': 4, 'B': 4}) == ['A', 'B']


# ---------- Parcours via les routes ----------

@pytest.fixture
def client(tmp_path, monkeypatch):
    import core.db
    monkeypatch.setattr(core.db, 'DB_PATH', str(tmp_path / 'test.db'))
    import app as fbg
    with fbg.app.app_context():
        core.db.init_db()
    con = sqlite3.connect(str(tmp_path / 'test.db'))
    con.execute("INSERT INTO users (email, password_hash, player_name) VALUES ('anna@x.fr', 'x', 'Anna')")
    con.commit()
    con.close()
    c = fbg.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = 1
    return c


def _new_game(client, *players):
    data = {f'player_{i + 1}': p for i, p in enumerate(players)}
    data['create_new_group'] = '1'
    rv = client.post('/mantis/new', data=data)
    return int(re.search(r'/game/(\d+)', rv.headers['Location']).group(1))


def _act(client, sid, player, action, **fields):
    return client.post(f'/mantis/game/{sid}/action', data={'player': player, 'action': action, **fields})


def test_live_counter_and_finish(client):
    sid = _new_game(client, 'Anna', 'Ben', 'Chloé')
    _act(client, sid, 'Anna', 'score', count='4')
    _act(client, sid, 'Ben', 'steal')
    _act(client, sid, 'Ben', 'score', count='abc')      # refusé
    _act(client, sid, 'Inconnu', 'score', count='3')    # refusé
    _act(client, sid, 'Chloé', 'score', count='12')
    _act(client, sid, 'Anna', 'fix', cards='5', steals='1')

    page = client.get(f'/mantis/game/{sid}').get_data(as_text=True)
    assert 'Premier à 10 cartes' in page            # Chloé sprinteuse
    assert 'Anna</strong> corrigé' in page

    client.post(f'/mantis/game/{sid}/undo')         # annule la correction d'Anna
    page = client.get(f'/mantis/game/{sid}').get_data(as_text=True)
    assert 'Anna</strong> corrigé' not in page

    client.post(f'/mantis/game/{sid}/finish')
    page = client.get(f'/mantis/game/{sid}').get_data(as_text=True)
    assert 'Gagnant : Chloé' in page
    assert client.post(f'/mantis/game/{sid}/action', data={'player': 'Anna', 'action': 'score', 'count': '3'}).status_code == 302
    assert 'Anna</strong> marque 3' not in client.get(f'/mantis/game/{sid}').get_data(as_text=True)


def test_tie_asks_tank_then_decides(client):
    sid = _new_game(client, 'Anna', 'Ben')
    _act(client, sid, 'Anna', 'score', count='8')
    _act(client, sid, 'Ben', 'score', count='8')

    form = client.post(f'/mantis/game/{sid}/finish').get_data(as_text=True)
    assert 'Égalité à 8 cartes' in form and 'tank_1' in form

    client.post(f'/mantis/game/{sid}/finish', data={'tied': ['Anna', 'Ben'], 'tank_0': '2', 'tank_1': '5'})
    page = client.get(f'/mantis/game/{sid}').get_data(as_text=True)
    assert 'Gagnant : Ben' in page and 'Départage au tank' in page


def test_empty_game_is_deleted_on_finish(client):
    sid = _new_game(client, 'Anna', 'Ben')
    client.post(f'/mantis/game/{sid}/finish')
    assert client.get(f'/mantis/game/{sid}').status_code == 404


def test_stats_and_shared_pages_include_mantis(client):
    sid = _new_game(client, 'Anna', 'Ben')
    _act(client, sid, 'Anna', 'score', count='11')
    _act(client, sid, 'Ben', 'steal')
    _act(client, sid, 'Ben', 'score', count='3')
    client.post(f'/mantis/game/{sid}/finish')

    stats = client.get('/mantis/stats').get_data(as_text=True)
    assert 'Le Gros Coup' in stats and 'Le Pickpocket' in stats
    assert client.get('/mantis/stats/player/Anna').status_code == 200
    assert client.get('/mantis/stats/player/Inconnu').status_code == 302

    assert 'Mantis' in client.get('/').get_data(as_text=True)
    assert 'images/Mantis.jpg' in client.get('/stats').get_data(as_text=True)
    assert 'Mantis · 1 partie' in client.get('/groups').get_data(as_text=True)
    detail = client.get('/groups/1').get_data(as_text=True)
    assert f'/familyboardgame/mantis/game/{sid}' in detail and '/familyboardgame/mantis/new?group=1' in detail
    assert client.get('/mantis/rules').status_code == 200
