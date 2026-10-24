import json
import re
import sqlite3

import pytest

from games.qwirkle.scoring import replay, next_player, winners, turn_score


def _turn(n, player, score, qwirkles=0, swap=False):
    return {'round_number': n, 'player_name': player, 'score': score,
            'details': json.dumps({'type': 'turn', 'qwirkles': qwirkles, 'swap': swap})}


# ---------- Règles ----------

def test_replay_builds_score_sheet():
    rows = [_turn(1, 'A', 5), _turn(2, 'B', 24, qwirkles=2), _turn(3, 'C', 0, swap=True),
            _turn(4, 'A', 7), _turn(5, 'B', 3),
            {'round_number': 6, 'player_name': 'A', 'score': 6, 'details': json.dumps({'type': 'bonus'})}]
    state = replay(['A', 'B', 'C'], rows)
    assert state['totals'] == {'A': 18, 'B': 27, 'C': 0}
    assert state['qwirkles']['B'] == 2 and state['swaps']['C'] == 1
    assert state['finisher'] == 'A'
    assert [sorted(line) for line in state['sheet']] == [['A', 'B', 'C'], ['A', 'B']]


def test_turn_score_adds_six_per_qwirkle():
    # Exemple K des règles : Elvire marque 6 + 3 + 3 avec un Qwirkle = 18
    assert turn_score(12, 1) == 18
    assert turn_score(18, 2) == 30
    assert turn_score(7, 0) == 7


def test_edit_turn_prefills_line_points(client):
    rv = client.post('/qwirkle/new', data={'player_1': 'Anna', 'player_2': 'Ben', 'create_new_group': '1'})
    sid = int(re.search(r'/game/(\d+)', rv.headers['Location']).group(1))
    client.post(f'/qwirkle/game/{sid}/turn', data={'player': 'Anna', 'points': '12', 'qwirkles': '1'})
    edit = client.get(f'/qwirkle/game/{sid}/turn/1').get_data(as_text=True)
    assert 'value="12"' in edit                       # points des lignes, sans le bonus


def test_next_player_rotates_and_ignores_bonus():
    players = ['A', 'B', 'C']
    assert next_player(players, []) == 'A'
    assert next_player(players, [_turn(1, 'A', 5)]) == 'B'
    assert next_player(players, [_turn(1, 'C', 5)]) == 'A'


def test_winners_can_be_ex_aequo():
    assert winners({'A': 40, 'B': 31}) == ['A']
    assert winners({'A': 40, 'B': 40}) == ['A', 'B']


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
    rv = client.post('/qwirkle/new', data=data)
    return int(re.search(r'/game/(\d+)', rv.headers['Location']).group(1))


def _play(client, sid, player, **fields):
    return client.post(f'/qwirkle/game/{sid}/turn', data={'player': player, **fields})


def test_turns_rotation_edit_undo_and_finish(client):
    sid = _new_game(client, 'Anna', 'Ben', 'Chloé')
    assert 'à <strong>Anna</strong> de jouer' in client.get(f'/qwirkle/game/{sid}').get_data(as_text=True)

    _play(client, sid, 'Anna', points='6')
    _play(client, sid, 'Ben', points='18', qwirkles='2')
    _play(client, sid, 'Chloé', swap='1')
    _play(client, sid, 'Anna', points='abc')   # refusé
    _play(client, sid, 'Anna', points='5', qwirkles='9')   # refusé : trop de Qwirkles
    page = client.get(f'/qwirkle/game/{sid}').get_data(as_text=True)
    assert 'à <strong>Anna</strong> de jouer' in page and 'Tour 2' in page
    assert '30 ⭐⭐' in page                    # 18 points de lignes + 2 Qwirkles × 6

    # Changer de joueur en touchant sa carte
    assert 'à <strong>Chloé</strong> de jouer' in client.get(f'/qwirkle/game/{sid}?player=Chlo%C3%A9').get_data(as_text=True)

    # Modifier le tour 1 d'Anna
    assert client.get(f'/qwirkle/game/{sid}/turn/1').status_code == 200
    client.post(f'/qwirkle/game/{sid}/turn/1', data={'points': '9'})
    _play(client, sid, 'Anna', points='4')
    client.post(f'/qwirkle/game/{sid}/undo')    # annule les 4 points d'Anna

    client.post(f'/qwirkle/game/{sid}/finish', data={'finisher': 'Anna'})
    page = client.get(f'/qwirkle/game/{sid}').get_data(as_text=True)
    assert 'Gagnant : Ben' in page                    # Ben 30 > Anna 9 + 6
    assert 'Anna a vidé sa main en premier' in page
    assert _play(client, sid, 'Ben', points='5').status_code == 302
    assert 'Gagnant : Ben — 30 points' in client.get(f'/qwirkle/game/{sid}').get_data(as_text=True)


def test_empty_game_is_deleted_on_finish(client):
    sid = _new_game(client, 'Anna', 'Ben')
    client.post(f'/qwirkle/game/{sid}/finish', data={'finisher': ''})
    assert client.get(f'/qwirkle/game/{sid}').status_code == 404


def test_stats_and_shared_pages_include_qwirkle(client):
    sid = _new_game(client, 'Anna', 'Ben')
    for player, pts in (('Anna', '12'), ('Ben', '5'), ('Anna', '7'), ('Ben', '3')):
        _play(client, sid, player, points=pts, **({'qwirkles': '1'} if pts == '12' else {}))
    client.post(f'/qwirkle/game/{sid}/finish', data={'finisher': 'Ben'})

    stats = client.get('/qwirkle/stats').get_data(as_text=True)
    assert 'Le Roi du Qwirkle' in stats and 'Le Gros Tour' in stats and 'Le Finisseur' in stats
    assert client.get('/qwirkle/stats/player/Anna').status_code == 200
    assert client.get('/qwirkle/rules').status_code == 200

    assert 'images/qwirkle.png' in client.get('/').get_data(as_text=True)
    assert 'images/qwirkle.png' in client.get('/stats').get_data(as_text=True)
    assert 'Qwirkle · 1 partie' in client.get('/groups').get_data(as_text=True)
    assert '/familyboardgame/qwirkle/new?group=1' in client.get('/groups/1').get_data(as_text=True)
