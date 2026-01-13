import re
import sqlite3
import pytest
import app as skyjo_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_newgame.db"
    monkeypatch.setattr(skyjo_app, 'DB_PATH', str(db_file))
    with skyjo_app.app.app_context():
        skyjo_app.init_db()
    return skyjo_app.app.test_client()


def test_new_game_type_select_present(client):
    rv = client.get('/new')
    html = rv.data.decode('utf-8')
    assert re.search(r'<select[^>]*name="type"', html)
    assert '<option value="Skyjo">Skyjo</option>' in html
    assert '<option value="Skyjo Action">Skyjo Action</option>' in html


def test_new_game_submits_type(client):
    rv = client.post('/new', data={'type': 'Skyjo Action', 'players': 'A,B'}, follow_redirects=False)
    assert rv.status_code == 302
    m = re.search(r'/game/(\d+)', rv.headers['Location'])
    game_id = int(m.group(1))

    con = sqlite3.connect(skyjo_app.DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT type FROM games WHERE id=?', (game_id,))
    row = cur.fetchone()
    con.close()
    assert row[0] == 'Skyjo Action'