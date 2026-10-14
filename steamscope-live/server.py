# server.py
# Runs SteamBank in one container: serves the website AND the two APIs.
# On Vercel, each file in api/ became its own endpoint. Here, this one small
# Python server does the same job, so the page works unchanged.
#
#   /                -> index.html and assets/ (the website)
#   /api/predict     -> the scikit-learn model (reuses api/predict.py)
#   /api/players     -> live player counts from Steam (Python version of api/players.js)

import importlib.util
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get('PORT', 8000))

# ---- Load api/predict.py once: it loads model.joblib and defines build_row ----
spec = importlib.util.spec_from_file_location('predict', os.path.join(HERE, 'api', 'predict.py'))
predict = importlib.util.module_from_spec(spec)
spec.loader.exec_module(predict)

# ---- Live player counts (same rules as api/players.js) ----
STEAM_URL = 'https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid='
MAX_APPS = 20
CACHE_SECONDS = 60
cache = {}   # appid -> (time fetched, player count)


def fetch_players(appid):
    saved = cache.get(appid)
    if saved and time.time() - saved[0] < CACHE_SECONDS:
        return saved[1]
    try:
        with urllib.request.urlopen(STEAM_URL + appid, timeout=4) as reply:
            body = json.load(reply).get('response', {})
        count = body.get('player_count') if body.get('result') == 1 else None
    except Exception:
        count = None          # Steam slow or unreachable: report "unknown", never crash
    cache[appid] = (time.time(), count)
    return count


class Handler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def send_json(self, status, body):
        data = json.dumps(body).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/api/predict':
            info = predict.info
            self.send_json(200, {'status': 'ok', 'model': info.get('model_name'),
                                 'roc_auc': info.get('roc_auc'), 'features': predict.TOTAL_COLUMNS})
        elif url.path == '/api/players':
            raw = parse_qs(url.query).get('appids', [''])[0]
            appids = list(dict.fromkeys(a.strip() for a in raw.split(',') if a.strip().isdigit()))[:MAX_APPS]
            if not appids:
                self.send_json(400, {'error': 'Pass numeric app IDs, e.g. /api/players?appids=730,570'})
                return
            with ThreadPoolExecutor(max_workers=8) as pool:
                counts = dict(zip(appids, pool.map(fetch_players, appids)))
            self.send_json(200, {'counts': counts, 'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        elif (url.path.startswith(('/api/', '/model/')) or '/.' in url.path
              or url.path.endswith(('.py', 'Dockerfile', 'dockerignore', '.json', '.md', '.txt'))):
            self.send_error(404)   # never serve code, the model, settings or hidden files as downloads
        else:
            super().do_GET()       # index.html, assets/styles.css, ...

    def do_POST(self):
        if urlparse(self.path).path != '/api/predict':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length) or b'{}')
            games = body.get('games', [])
            if not isinstance(games, list) or not 1 <= len(games) <= predict.MAX_GAMES:
                raise ValueError(f"send between 1 and {predict.MAX_GAMES} games in a 'games' list")
            rows = predict.np.array([predict.build_row(game) for game in games])
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json(400, {'error': str(error)})
            return
        probabilities = predict.model.predict_proba(rows)[:, 1]
        self.send_json(200, {'probabilities': [round(float(p), 6) for p in probabilities]})


if __name__ == '__main__':
    print(f'SteamBank running on http://localhost:{PORT}')
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
