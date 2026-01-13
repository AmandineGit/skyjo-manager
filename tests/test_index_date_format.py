import re
import pytest
import app as skyjo_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_index.db"
    monkeypatch.setattr(skyjo_app, 'DB_PATH', str(db_file))
    with skyjo_app.app.app_context():
        skyjo_app.init_db()
    return skyjo_app.app.test_client()


def test_index_shows_created_date_in_french(client):
    rv = client.post('/new', data={'type': 'Test', 'players': 'Anna,Ben'}, follow_redirects=False)
    assert rv.status_code == 302

    rv = client.get('/')
    html = rv.data.decode('utf-8')

    # Expect 'DD month YYYY' style in French, e.g. '11 janvier 2026'
    assert re.search(r"\d{1,2}\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}", html)
