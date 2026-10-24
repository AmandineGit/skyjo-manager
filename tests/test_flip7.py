import re
import sqlite3

import pytest
from werkzeug.datastructures import MultiDict

from games.flip7.scoring import (
    round_score, game_outcome, parse_entry,
    STATUS_ONGOING, STATUS_FINISHED, STATUS_TIEBREAK,
)
from games.flip7.stats import compute_stats


# ---------- Règles de score ----------

def test_x2_doubles_only_numbers():
    assert round_score(numbers=30, bonus=6, x2=True) == 66


def test_flip7_bonus_not_doubled():
    assert round_score(numbers=40, x2=True, flip7=True) == 95


def test_bust_scores_zero():
    assert round_score(numbers=40, bonus=10, x2=True, flip7=True, bust=True) == 0


@pytest.mark.parametrize('totals, expected', [
    ({}, (STATUS_ONGOING, [])),
    ({'A': 199, 'B': 150}, (STATUS_ONGOING, [])),
    ({'A': 205, 'B': 230}, (STATUS_FINISHED, ['B'])),
    ({'A': 210, 'B': 210, 'C': 120}, (STATUS_TIEBREAK, ['A', 'B'])),
])
def test_game_outcome(totals, expected):
    assert game_outcome(totals) == expected


def test_parse_entry_bust_clears_everything():
    details, error = parse_entry(MultiDict({'numbers_0': '25', 'x2_0': 'on', 'stop_0': 'on', 'bust_0': 'on'}), 0)
    assert error is None
    assert details == {'numbers': 0, 'bonus': 0, 'x2': False, 'flip7': False, 'bust': True, 'stop': False}


def test_parse_entry_flip7_is_not_a_stop():
    details, _ = parse_entry(MultiDict({'numbers_0': '40', 'flip7_0': 'on', 'stop_0': 'on'}), 0)
    assert details['flip7'] and not details['stop']


@pytest.mark.parametrize('raw', ['abc', '-3', '1000'])
def test_parse_entry_rejects_invalid_numbers(raw):
    details, error = parse_entry(MultiDict({'numbers_0': raw}), 0)
    assert details is None and error


def test_stats_wins_and_rates():
    sessions = [{'id': 1, 'finished': 1}]
    players = [{'session_id': 1, 'player_name': n} for n in ('A', 'B')]
    rows = [
        {'session_id': 1, 'round_number': 1, 'player_name': 'A', 'score': 120, 'details': '{"stop": true}'},
        {'session_id': 1, 'round_number': 1, 'player_name': 'B', 'score': 0, 'details': '{"bust": true}'},
        {'session_id': 1, 'round_number': 2, 'player_name': 'A', 'score': 95, 'details': '{"flip7": true}'},
        {'session_id': 1, 'round_number': 2, 'player_name': 'B', 'score': 30, 'details': '{"stop": true}'},
    ]
    stats = compute_stats(sessions, players, rows)
    a = next(p for p in stats['players'] if p['name'] == 'A')
    assert (a['wins'], a['stops'], a['flip7s'], a['best_round']) == (1, 1, 1, 120)
    assert stats['podium'][0]['name'] == 'A'
    assert stats['total_rounds'] == 2


# ---------- Parcours complet via les routes ----------

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


def _play(client, session_id, entries):
    data = MultiDict([('player', name) for name, _ in entries])
    for i, (_, fields) in enumerate(entries):
        for k, v in fields.items():
            data.add(f'{k}_{i}', v)
    return client.post(f'/flip7/game/{session_id}/round', data=data)


def test_tie_above_target_triggers_tiebreak_round(client):
    rv = client.post('/flip7/new', data={'player_1': 'Anna', 'player_2': 'Ben', 'player_3': 'Chloé',
                                         'create_new_group': '1'})
    session_id = int(re.search(r'/game/(\d+)', rv.headers['Location']).group(1))

    _play(client, session_id, [('Anna', {'numbers': '210'}), ('Ben', {'numbers': '210'}), ('Chloé', {'numbers': '50'})])
    page = client.get(f'/flip7/game/{session_id}').get_data(as_text=True)
    assert 'Manche de départage' in page
    assert 'name="numbers_2"' not in page  # Chloé ne joue pas le départage

    _play(client, session_id, [('Anna', {'numbers': '8'}), ('Ben', {'numbers': '3'})])
    page = client.get(f'/flip7/game/{session_id}').get_data(as_text=True)
    assert 'Gagnant : Anna' in page


def test_player_stats_page(client):
    rv = client.post('/flip7/new', data={'player_1': 'Anna', 'player_2': 'Chloé', 'create_new_group': '1'})
    session_id = int(re.search(r'/game/(\d+)', rv.headers['Location']).group(1))
    _play(client, session_id, [('Anna', {'numbers': '40', 'stop': 'on'}), ('Chloé', {'bust': 'on'})])
    _play(client, session_id, [('Anna', {'numbers': '12'}), ('Chloé', {'numbers': '30', 'flip7': 'on'})])

    stats_page = client.get('/flip7/stats').get_data(as_text=True)
    assert '/flip7/stats/player/Chlo%C3%A9' in stats_page

    page = client.get('/flip7/stats/player/Chlo%C3%A9')
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'Chloé' in html and '45' in html  # meilleure manche : 30 + 15 (Flip 7)
    assert client.get('/flip7/stats/player/Inconnu').status_code == 302


def test_stats_menu_shows_game_images(client):
    client.post('/flip7/new', data={'player_1': 'Anna', 'player_2': 'Ben', 'create_new_group': '1'})
    html = client.get('/stats').get_data(as_text=True)
    assert 'images/Flip7.webp' in html


def test_group_pages_list_every_game(client):
    rv = client.post('/flip7/new', data={'player_1': 'Anna', 'player_2': 'Ben', 'create_new_group': '1'})
    flip7_id = int(re.search(r'/game/(\d+)', rv.headers['Location']).group(1))
    client.post('/play/new', data={'type': 'Skyjo', 'player_1': 'Anna', 'player_2': 'Ben', 'group_id': '1'})

    groups = client.get('/groups').get_data(as_text=True)
    assert 'Skyjo · 1 partie' in groups and 'Flip 7 · 1 partie' in groups

    detail = client.get('/groups/1').get_data(as_text=True)
    assert f'/familyboardgame/flip7/game/{flip7_id}' in detail and '/skyjo/game/' in detail
    assert '/familyboardgame/flip7/new?group=1' in detail
