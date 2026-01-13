import re
import sqlite3
import pytest
import app as skyjo_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_players.db"
    monkeypatch.setattr(skyjo_app, 'DB_PATH', str(db_file))
    with skyjo_app.app.app_context():
        skyjo_app.init_db()
    return skyjo_app.app.test_client()


def test_new_game_form_has_player_inputs(client):
    rv = client.get('/new')
    html = rv.data.decode('utf-8')
    # Ensure inputs player_1..player_10 are present
    for i in range(1, 11):
        assert f'name="player_{i}"' in html
    # Ensure add-player button exists
    assert 'id="add-player"' in html


def test_post_multiple_players_creates_players(client):
    data = {'type': 'Skyjo'}
    # Provide 6 players
    for i, name in enumerate(['Alice', 'Bob', 'Claire', 'David', 'Eve', 'Frank'], start=1):
        data[f'player_{i}'] = name
    rv = client.post('/new', data=data, follow_redirects=False)
    assert rv.status_code == 302
    m = re.search(r'/game/(\d+)', rv.headers['Location'])
    game_id = int(m.group(1))

    con = sqlite3.connect(skyjo_app.DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT name FROM players WHERE game_id=? ORDER BY id', (game_id,))
    rows = [r[0] for r in cur.fetchall()]
    con.close()
    assert rows == ['Alice', 'Bob', 'Claire', 'David', 'Eve', 'Frank']
