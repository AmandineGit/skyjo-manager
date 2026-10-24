"""
Skyjo (blueprint /play, tables skyjo_*). Reprend les anciens tests v1
(création de partie, scores négatifs, mise en page des manches, dates en français)
et ajoute les règles du finisher et de la fin à 100 points.
"""
import datetime
import re
import sqlite3

import pytest

MONTHS = r'(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)'


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
    con.commit()
    con.close()
    return path


@pytest.fixture
def client(db_path):
    import app as fbg
    c = fbg.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = 1
    return c


def _new_game(client, players, game_type='Skyjo'):
    data = {'type': game_type, 'create_new_group': '1'}
    data.update({f'player_{i}': p for i, p in enumerate(players, start=1)})
    rv = client.post('/play/new', data=data)
    assert rv.status_code == 302
    return int(re.search(r'/game/(\d+)', rv.headers['Location']).group(1))


def _rows(db_path, sql, params):
    con = sqlite3.connect(db_path)
    rows = con.execute(sql, params).fetchall()
    con.close()
    return rows


def _totals(db_path, game_id):
    return dict(_rows(db_path, 'SELECT player_name, SUM(score) FROM skyjo_rounds WHERE game_id=? GROUP BY player_name',
                      (game_id,)))


def test_new_game_form_offers_both_types_and_ten_players(client):
    html = client.get('/play/new').get_data(as_text=True)
    assert 'data-type="Skyjo"' in html and 'data-type="Skyjo Action"' in html
    for i in range(1, 11):
        assert f'name="player_{i}"' in html
    assert 'id="add-player"' in html


def test_new_game_stores_type_and_players(client, db_path):
    names = ['Alice', 'Bob', 'Claire', 'David', 'Eve', 'Frank']
    game_id = _new_game(client, names, 'Skyjo Action')
    assert _rows(db_path, 'SELECT type FROM skyjo_games WHERE id=?', (game_id,))[0][0] == 'Skyjo Action'
    assert [r[0] for r in _rows(db_path, 'SELECT name FROM skyjo_players WHERE game_id=? ORDER BY id', (game_id,))] == names


def test_negative_scores_count_in_totals(client, db_path):
    game_id = _new_game(client, ['Anna', 'Ben'])
    client.post(f'/play/submit_round/{game_id}', data={'score_Anna': '10', 'score_Ben': '5'})
    client.post(f'/play/submit_round/{game_id}', data={'score_Anna': '-3', 'score_Ben': '2'})
    assert _totals(db_path, game_id) == {'Anna': 7, 'Ben': 7}
    for (ts,) in _rows(db_path, 'SELECT created_at FROM skyjo_rounds WHERE game_id=?', (game_id,)):
        assert datetime.datetime.fromisoformat(ts).tzinfo is not None


def test_finisher_without_lowest_score_is_doubled(client, db_path):
    game_id = _new_game(client, ['Anna', 'Ben'])
    client.post(f'/play/submit_round/{game_id}', data={'score_Anna': '8', 'score_Ben': '3', 'finisher': 'Anna'})
    assert _totals(db_path, game_id) == {'Anna': 16, 'Ben': 3}
    client.post(f'/play/submit_round/{game_id}', data={'score_Anna': '1', 'score_Ben': '9', 'finisher': 'Anna'})
    assert _totals(db_path, game_id) == {'Anna': 17, 'Ben': 12}   # plus petit score : pas de doublement


def test_game_ends_at_100_points(client, db_path):
    game_id = _new_game(client, ['Anna', 'Ben'])
    client.post(f'/play/submit_round/{game_id}', data={'score_Anna': '100', 'score_Ben': '5'})
    assert _rows(db_path, 'SELECT finished FROM skyjo_games WHERE id=?', (game_id,))[0][0] == 1


def test_game_page_layout_and_french_dates(client):
    game_id = _new_game(client, ['Anna', 'Ben'])
    client.post(f'/play/submit_round/{game_id}', data={'score_Anna': '10', 'score_Ben': '5'})
    client.post(f'/play/submit_round/{game_id}', data={'score_Anna': '-3', 'score_Ben': '2'})
    html = client.get(f'/play/game/{game_id}').get_data(as_text=True)
    assert re.search(r'<th[^>]*>\s*Anna\s*</th>', html) and re.search(r'<th[^>]*>\s*Ben\s*</th>', html)
    assert re.search(r'data-label="Round">\s*2\s*<', html)
    assert re.search(r'\d{2}/\d{2}/\d{4}\s+à\s+\d{2}h\d{2}', html)
    assert re.search(rf'\d{{1,2}}\s+{MONTHS}\s+\d{{4}}', html)


def test_index_lists_ongoing_game_with_french_date(client):
    _new_game(client, ['Anna', 'Ben'])
    html = client.get('/play/').get_data(as_text=True)
    assert re.search(rf'Partie #\d+</a> — \d{{1,2}}\s+{MONTHS}\s+\d{{4}}', html)
