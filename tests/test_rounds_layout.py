import re
import sqlite3
import datetime
import pytest
import app as skyjo_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_layout.db"
    monkeypatch.setattr(skyjo_app, 'DB_PATH', str(db_file))
    with skyjo_app.app.app_context():
        skyjo_app.init_db()
    return skyjo_app.app.test_client()


def test_rounds_table_layout(client):
    # Create game with two players
    rv = client.post('/new', data={'type': 'Test', 'players': 'Anna,Ben'}, follow_redirects=False)
    assert rv.status_code == 302
    m = re.search(r'/game/(\d+)', rv.headers['Location'])
    game_id = int(m.group(1))

    # Submit two rounds
    client.post(f'/submit_round/{game_id}', data={'score_Anna': '10', 'score_Ben': '5'})
    client.post(f'/submit_round/{game_id}', data={'score_Anna': '-3', 'score_Ben': '2'})

    # Fetch game page
    rv = client.get(f'/game/{game_id}')
    html = rv.data.decode('utf-8')

    # Check headers include player names (allows attributes on <th>)
    assert re.search(r'<th[^>]*>\s*Anna\s*</th>', html)
    assert re.search(r'<th[^>]*>\s*Ben\s*</th>', html)

    # Check two rounds rendered (presence of round numbers, allow attributes)
    assert re.search(r'<td[^>]*>\s*1\s*</td>', html)
    assert re.search(r'<td[^>]*>\s*2\s*</td>', html)

    # Check timestamp formatted like 'DD/MM/YYYY à HHhMM'
    assert re.search(r"\d{2}/\d{2}/\d{4}\s+à\s+\d{2}h\d{2}", html)

    # Check the created_at displayed in French like '11 janvier 2025'
    assert 'Créée:' in html
    assert re.search(r"Créée:\s*\d{1,2}\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}", html)
