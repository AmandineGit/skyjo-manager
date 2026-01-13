import os
import tempfile
import sqlite3
import re
from flask import url_for
import pytest

import app as skyjo_app

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_skyjo.db"
    # Point the app DB_PATH to this temp file
    monkeypatch.setattr(skyjo_app, 'DB_PATH', str(db_file))
    # Ensure DB initialized
    with skyjo_app.app.app_context():
        skyjo_app.init_db()
    return str(db_file)


def create_game(client, players):
    rv = client.post('/new', data={'type': 'Test', 'players': players}, follow_redirects=False)
    assert rv.status_code == 302
    loc = rv.headers['Location']
    m = re.search(r'/game/(\d+)', loc)
    assert m, f"Unexpected redirect location: {loc}"
    return int(m.group(1))


def get_totals(db_path, game_id):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT player_name, SUM(score) FROM rounds WHERE game_id=? GROUP BY player_name', (game_id,))
    rows = {r[0]: r[1] or 0 for r in cur.fetchall()}
    con.close()
    return rows


def test_negative_score_recorded(tmp_db):
    client = skyjo_app.app.test_client()
    game_id = create_game(client, 'Anna,Ben')

    # Submit a negative round for Anna
    rv = client.post(f'/submit_round/{game_id}', data={'score_Anna': '-4', 'score_Ben': '1'}, follow_redirects=False)
    assert rv.status_code == 302

    # Verify rounds table contains the negative score
    con = sqlite3.connect(tmp_db)
    cur = con.cursor()
    cur.execute('SELECT score, created_at FROM rounds WHERE game_id=? ORDER BY id DESC LIMIT 2', (game_id,))
    rows = cur.fetchall()
    con.close()

    scores = [r[0] for r in rows]
    created_ats = [r[1] for r in rows]
    assert -4 in scores
    # created_at should be present and timezone-aware ISO
    import datetime
    for ts in created_ats:
        assert ts is not None
        dt = datetime.datetime.fromisoformat(ts)
        assert dt.tzinfo is not None


def test_negative_affects_totals(tmp_db):
    client = skyjo_app.app.test_client()
    game_id = create_game(client, 'Anna,Ben')

    # Submit positive round
    client.post(f'/submit_round/{game_id}', data={'score_Anna': '10', 'score_Ben': '5'})
    # Submit negative round
    client.post(f'/submit_round/{game_id}', data={'score_Anna': '-3', 'score_Ben': '2'})

    totals = get_totals(tmp_db, game_id)
    assert totals['Anna'] == 7  # 10 + (-3)
    assert totals['Ben'] == 7   # 5 + 2

    # Check that created_at exists on rounds
    con = sqlite3.connect(tmp_db)
    cur = con.cursor()
    cur.execute('SELECT created_at FROM rounds WHERE game_id=?', (game_id,))
    rows = [r[0] for r in cur.fetchall()]
    con.close()
    import datetime
    for ts in rows:
        assert ts is not None
        dt = datetime.datetime.fromisoformat(ts)
        assert dt.tzinfo is not None
