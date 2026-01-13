import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, flash, send_from_directory, session
from export_to_onedrive import export_all_to_onedrive

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'skyjo.db')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'change-me')

# Codes d'accès pour sécuriser l'application
ACCESS_CODE_INTERNAL = '1666'  # Accès complet
ACCESS_CODE_EXTERNAL = '1664'  # Accès limité (pas de stats)

# Décorateur pour protéger les routes
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect('/skyjo/login')
        return f(*args, **kwargs)
    return decorated_function

# Décorateur pour protéger les routes réservées aux utilisateurs internes
def require_internal_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect('/skyjo/login')
        if session.get('access_level') != 'int':
            flash('Accès interdit : cette fonctionnalité est réservée aux utilisateurs internes')
            return redirect('/skyjo/')
        return f(*args, **kwargs)
    return decorated_function

# Jinja filter: format ISO timestamp -> 'YYYY-MM-DD HH:MM UTC'
def format_ts(value):
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        # Format: 11/01/2026 à 18h05
        return dt.strftime('%d/%m/%Y à %Hh%M')
    except Exception:
        return value

# Format date as '11 janvier 2026' in French
def format_date_fr(value):
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
        day = dt.day
        month = months[dt.month - 1]
        year = dt.year
        return f"{day} {month} {year}"
    except Exception:
        return value

app.jinja_env.filters['format_ts'] = format_ts
app.jinja_env.filters['format_date_fr'] = format_date_fr

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY,
        created_at TEXT,
        type TEXT,
        comments TEXT,
        finished INTEGER DEFAULT 0,
        access_type TEXT DEFAULT 'int'
    );
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY,
        game_id INTEGER,
        name TEXT
    );
    CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY,
        game_id INTEGER,
        round_number INTEGER,
        player_name TEXT,
        score INTEGER,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS game_rules (
        id INTEGER PRIMARY KEY,
        game_type TEXT UNIQUE,
        rules_pdf TEXT
    );
    ''')
    db.commit()

    # Ensure schema for older DBs: add created_at to rounds if missing
    cur = db.execute("PRAGMA table_info(rounds)")
    cols = [r['name'] for r in cur.fetchall()]
    if 'created_at' not in cols:
        db.execute("ALTER TABLE rounds ADD COLUMN created_at TEXT")
        db.commit()

    # Ensure schema for older DBs: add access_type to games if missing
    cur = db.execute("PRAGMA table_info(games)")
    cols = [r['name'] for r in cur.fetchall()]
    if 'access_type' not in cols:
        db.execute("ALTER TABLE games ADD COLUMN access_type TEXT DEFAULT 'int'")
        db.commit()

    # Initialize default game rules
    cur = db.execute("SELECT COUNT(*) as cnt FROM game_rules")
    if cur.fetchone()['cnt'] == 0:
        db.execute("INSERT INTO game_rules (game_type, rules_pdf) VALUES (?, ?)",
                   ('Skyjo', '88-skyjo-regle.pdf'))
        db.execute("INSERT INTO game_rules (game_type, rules_pdf) VALUES (?, ?)",
                   ('Skyjo Action', '88-skyjo-regle.pdf'))
        db.commit()

# Ensure DB schema exists at import time (works with Flask 3 and Gunicorn boots)
with app.app_context():
    init_db()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def get_totals(game_id):
    db = get_db()
    cur = db.execute(
        'SELECT player_name, SUM(score) as total FROM rounds WHERE game_id=? GROUP BY player_name',
        (game_id,)
    )
    return {row['player_name']: row['total'] for row in cur.fetchall()}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if code == ACCESS_CODE_INTERNAL:
            session['authenticated'] = True
            session['access_level'] = 'int'
            return redirect('/skyjo/')
        elif code == ACCESS_CODE_EXTERNAL:
            session['authenticated'] = True
            session['access_level'] = 'ext'
            return redirect('/skyjo/')
        else:
            flash('Code d\'accès incorrect')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    session.pop('access_level', None)
    flash('Vous avez été déconnecté')
    return redirect('/skyjo/login')

@app.route('/')
@require_auth
def index():
    init_db()
    db = get_db()

    # Get optional date filter from query params
    search_date = request.args.get('date')

    # Get user access level
    access_level = session.get('access_level', 'int')

    if search_date:
        # When searching by date, show all games (finished or not) for that date
        if access_level == 'ext':
            # External users only see games with access_type='ext'
            games = db.execute(
                'SELECT id, created_at, type, finished FROM games WHERE DATE(created_at) = ? AND access_type = ? ORDER BY id DESC',
                (search_date, 'ext')
            ).fetchall()
        else:
            # Internal users see all games
            games = db.execute(
                'SELECT id, created_at, type, finished FROM games WHERE DATE(created_at) = ? ORDER BY id DESC',
                (search_date,)
            ).fetchall()
    else:
        # Default: show only ongoing games
        if access_level == 'ext':
            # External users only see ongoing games with access_type='ext'
            games = db.execute('SELECT id, created_at, type, finished FROM games WHERE finished = 0 AND access_type = ? ORDER BY id DESC', ('ext',)).fetchall()
        else:
            # Internal users see all ongoing games
            games = db.execute('SELECT id, created_at, type, finished FROM games WHERE finished = 0 ORDER BY id DESC').fetchall()

    # Ensure created_at is formatted server-side to avoid template/env inconsistencies
    games_list = []
    for g in games:
        gd = dict(g)
        gd['created_display'] = format_date_fr(gd.get('created_at'))
        games_list.append(gd)

    return render_template('index.html', games=games_list, search_date=search_date, access_level=access_level)

@app.route('/new', methods=['GET', 'POST'])
@require_auth
def new_game():
    if request.method == 'POST':
        game_type = request.form.get('type') or 'Skyjo'
        comments = request.form.get('comments') or ''
        # Get user access level to tag the game
        access_level = session.get('access_level', 'int')
        # Collect players from player_1..player_10 fields if present
        players = []
        for i in range(1, 11):
            p = request.form.get(f'player_{i}')
            if p and p.strip():
                players.append(p.strip())
        # Fallback to legacy comma-separated field
        if not players:
            players_raw = request.form.get('players') or ''
            players = [p.strip() for p in players_raw.split(',') if p.strip()]
        if not players:
            flash('Ajoutez au moins un joueur (au moins 1).')
            return redirect('/skyjo/new')
        db = get_db()
        cur = db.cursor()
        cur.execute('INSERT INTO games (created_at, type, comments, access_type) VALUES (?, ?, ?, ?)',
                    (datetime.now(timezone.utc).isoformat(), game_type, comments, access_level))
        game_id = cur.lastrowid
        for p in players:
            cur.execute('INSERT INTO players (game_id, name) VALUES (?, ?)', (game_id, p))
        db.commit()
        return redirect(f"/skyjo/game/{game_id}")
    return render_template('new_game.html')

@app.route('/game/<int:game_id>', methods=['GET'])
@require_auth
def game_view(game_id):
    db = get_db()
    game = db.execute('SELECT * FROM games WHERE id=?', (game_id,)).fetchone()
    players = db.execute('SELECT name FROM players WHERE game_id=?', (game_id,)).fetchall()
    player_names = [p['name'] for p in players]
    totals = get_totals(game_id)

    # Récupère les rounds et regroupe par numéro de round en matrice
    rows = db.execute('SELECT round_number, player_name, score, created_at FROM rounds WHERE game_id=? ORDER BY round_number, id', (game_id,)).fetchall()
    rounds_by_num = {}
    for r in rows:
        n = r['round_number']
        if n not in rounds_by_num:
            rounds_by_num[n] = {'round': n, 'scores': {}, 'timestamp': None}
        rounds_by_num[n]['scores'][r['player_name']] = r['score']
        if r['created_at']:
            ts = r['created_at']
            if rounds_by_num[n]['timestamp'] is None or ts > rounds_by_num[n]['timestamp']:
                rounds_by_num[n]['timestamp'] = ts

    rounds_matrix = [rounds_by_num[n] for n in sorted(rounds_by_num.keys())]

    return render_template('game.html', game=game, players=player_names, totals=totals, rounds_matrix=rounds_matrix)

@app.route('/submit_round/<int:game_id>', methods=['POST'])
@require_auth
def submit_round(game_id):
    db = get_db()
    game = db.execute('SELECT * FROM games WHERE id=?', (game_id,)).fetchone()
    if not game:
        flash('Partie introuvable')
        return redirect('/skyjo/')
    if game['finished']:
        flash('La partie est déjà terminée')
        return redirect(f"/skyjo/game/{game_id}")
    cur = db.execute('SELECT MAX(round_number) as m FROM rounds WHERE game_id=?', (game_id,)).fetchone()
    next_round = (cur['m'] or 0) + 1
    players = db.execute('SELECT name FROM players WHERE game_id=?', (game_id,)).fetchall()
    for p in players:
        name = p['name']
        s = request.form.get('score_' + name)
        try:
            val = int(s)
        except Exception:
            val = 0
        db.execute('INSERT INTO rounds (game_id, round_number, player_name, score, created_at) VALUES (?, ?, ?, ?, ?)',
                   (game_id, next_round, name, val, datetime.now(timezone.utc).isoformat()))
    db.commit()
    totals = get_totals(game_id)
    for total in totals.values():
        if total >= 100:
            db.execute('UPDATE games SET finished=1 WHERE id=?', (game_id,))
            db.commit()
            flash('Un joueur a atteint 100 points — la partie est terminée.')
            break
    return redirect(f"/skyjo/game/{game_id}")

@app.route('/terminate/<int:game_id>', methods=['POST'])
@require_auth
def terminate(game_id):
    db = get_db()
    db.execute('UPDATE games SET finished=1 WHERE id=?', (game_id,))
    db.commit()
    flash('Partie terminée manuellement.')
    return redirect(f"/skyjo/game/{game_id}")

@app.route('/export')
@require_auth
def export_route():
    try:
        path = export_all_to_onedrive()
        flash('Export effectué: ' + path)
    except Exception as e:
        flash('Erreur export: ' + str(e))
    return redirect('/skyjo/')

@app.route('/stats')
@require_internal_access
def stats_menu():
    """Menu de sélection des statistiques par type de jeu"""
    db = get_db()

    # Récupérer tous les types de jeux qui ont été joués
    game_types = db.execute('''
        SELECT DISTINCT type FROM games WHERE type IS NOT NULL ORDER BY type
    ''').fetchall()
    game_types = [row['type'] for row in game_types]

    # Compter le nombre de parties et rounds par type
    games_count = {}
    rounds_count = {}
    for game_type in game_types:
        count_games = db.execute('SELECT COUNT(*) as cnt FROM games WHERE type = ?', (game_type,)).fetchone()
        games_count[game_type] = count_games['cnt']

        count_rounds = db.execute('''
            SELECT COUNT(*) as cnt FROM rounds
            WHERE game_id IN (SELECT id FROM games WHERE type = ?)
        ''', (game_type,)).fetchone()
        rounds_count[game_type] = count_rounds['cnt']

    return render_template('stats_menu.html',
                          game_types=game_types,
                          games_count=games_count,
                          rounds_count=rounds_count)

@app.route('/stats/<game_type>')
@require_internal_access
def stats_detail(game_type):
    """Statistiques détaillées pour un type de jeu spécifique"""
    db = get_db()
    stats = []
    import pandas as pd

    # Récupérer uniquement les rounds des parties du type spécifié
    query = '''
        SELECT r.* FROM rounds r
        INNER JOIN games g ON r.game_id = g.id
        WHERE g.type = ?
    '''
    df = pd.read_sql_query(query, db, params=(game_type,))

    if not df.empty:
        for name in df['player_name'].unique():
            sub = df[df['player_name'] == name]['score']
            stats.append({
                'player': name,
                'mean': float(sub.mean()),
                'median': float(sub.median()),
                'best': int(sub.min()),
                'worst': int(sub.max()),
                'rounds': int(sub.count())
            })

        # Trier par moyenne croissante pour le podium
        stats.sort(key=lambda x: x['mean'])

    # Podium (top 3)
    podium = stats[:3] if stats else []

    # Trouver le pire score sur un round (Looser du pire)
    worst_single = None
    if not df.empty:
        worst_idx = df['score'].idxmax()
        worst_row = df.loc[worst_idx]
        worst_single = {
            'player': worst_row['player_name'],
            'score': int(worst_row['score']),
            'round_number': int(worst_row['round_number']),
            'game_id': int(worst_row['game_id'])
        }

    # Trouver le meilleur score sur un round (Boss des coups de bol)
    best_single = None
    if not df.empty:
        best_idx = df['score'].idxmin()
        best_row = df.loc[best_idx]
        best_single = {
            'player': best_row['player_name'],
            'score': int(best_row['score']),
            'round_number': int(best_row['round_number']),
            'game_id': int(best_row['game_id'])
        }

    # Compter les parties et rounds totaux
    total_games = db.execute('SELECT COUNT(*) as cnt FROM games WHERE type = ?', (game_type,)).fetchone()['cnt']
    total_rounds = len(df)

    return render_template('stats_detail.html',
                          game_type=game_type,
                          stats=stats,
                          podium=podium,
                          worst_single=worst_single,
                          best_single=best_single,
                          total_games=total_games,
                          total_rounds=total_rounds)


@app.route('/images/<path:filename>')
def image_file(filename):
    # Serve project-level images placed in /var/www/skyjo/images
    return send_from_directory(os.path.join(BASE_DIR, 'images'), filename)

@app.route('/rules/<game_type>')
@require_auth
def get_rules(game_type):
    """Return the PDF rules file path for a given game type"""
    db = get_db()
    rule = db.execute('SELECT rules_pdf FROM game_rules WHERE game_type=?', (game_type,)).fetchone()
    if rule and rule['rules_pdf']:
        return send_from_directory(os.path.join(BASE_DIR, 'images'), rule['rules_pdf'])
    flash('Règles non disponibles pour ce type de jeu')
    return redirect('/skyjo/')

# Application WSGI entrypoint (no dispatcher): keep app at root; Apache proxies /skyjo/ -> http://127.0.0.1:8000/
application = app

if __name__ == '__main__':
    # Initialize the database inside the application context
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
