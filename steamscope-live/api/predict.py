# api/predict.py
# Vercel turns this file into an API at /api/predict. It runs the real scikit-learn model
# saved from the notebook, so the website doesn't have to do the maths itself.
#
#   GET  /api/predict   -> health check: says the API is up and which model it serves
#   POST /api/predict   -> body: {"games": [ {...}, {...} ]}   reply: {"probabilities": [0.78, ...]}
#
# Each game in "games" looks like this (genres, tags and categories are names, not numbers):
#   {"genres": ["Action", "Indie"], "tags": ["Co-op", "Open World"], "categories": ["Online Co-op"],
#    "price": 15, "required_age": 0, "achievements": 30, "languages": 6,
#    "windows": 1, "mac": 1, "linux": 1}

from http.server import BaseHTTPRequestHandler
import json
import os

import joblib
import numpy as np

# ---- Load the model once, when Vercel starts this function (not on every request) ----
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, '..', 'model')
model = joblib.load(os.path.join(MODEL_DIR, 'model.joblib'))
with open(os.path.join(MODEL_DIR, 'model_info.json')) as f:
    info = json.load(f)

GENRES = info['genres']
TAGS = info['tags']
CATEGORIES = info['categories']
NUMERIC = info['numeric']          # the numeric column names, in training order
MAX_GAMES = 20                     # the market comparison sends the user's game plus a few what-ifs

genre_position = {name: i for i, name in enumerate(GENRES)}
tag_position = {name: i for i, name in enumerate(TAGS)}
category_position = {name: i for i, name in enumerate(CATEGORIES)}

# Column layout, exactly as in the notebook: genres | tags | numeric | categories
TAG_OFFSET = len(GENRES)
NUMERIC_OFFSET = TAG_OFFSET + len(TAGS)
CATEGORY_OFFSET = NUMERIC_OFFSET + len(NUMERIC)
TOTAL_COLUMNS = CATEGORY_OFFSET + len(CATEGORIES)


def read_number(game, key, minimum):
    value = float(game.get(key, minimum))
    if value < minimum:
        raise ValueError(f"'{key}' must be at least {minimum}")
    return value


def build_row(game):
    """Turn one game's details into the same row of numbers the model was trained on."""
    row = np.zeros(TOTAL_COLUMNS)

    for name in game.get('genres', []):
        if name in genre_position:
            row[genre_position[name]] = 1
    for name in game.get('tags', []):
        if name in tag_position:
            row[TAG_OFFSET + tag_position[name]] = 1
    for name in game.get('categories', []):
        if name in category_position:
            row[CATEGORY_OFFSET + category_position[name]] = 1

    numeric_values = {
        'log_price': np.log1p(read_number(game, 'price', 0)),
        'required_age': read_number(game, 'required_age', 0),
        'log_achievements': np.log1p(read_number(game, 'achievements', 0)),
        'num_languages': read_number(game, 'languages', 1),
        'windows': 1 if game.get('windows') else 0,
        'mac': 1 if game.get('mac') else 0,
        'linux': 1 if game.get('linux') else 0,
    }
    for i, name in enumerate(NUMERIC):
        row[NUMERIC_OFFSET + i] = numeric_values[name]
    return row


class handler(BaseHTTPRequestHandler):

    def send_json(self, status, body):
        data = json.dumps(body).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        # Health check: the page calls this once to see whether the API is available.
        self.send_json(200, {'status': 'ok', 'model': info.get('model_name', 'Gradient Boosting'),
                             'roc_auc': info.get('roc_auc'), 'features': TOTAL_COLUMNS})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length) or b'{}')
            games = body.get('games', [])
            if not isinstance(games, list) or not 1 <= len(games) <= MAX_GAMES:
                raise ValueError(f"send between 1 and {MAX_GAMES} games in a 'games' list")
            rows = np.array([build_row(game) for game in games])
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json(400, {'error': str(error)})
            return

        probabilities = model.predict_proba(rows)[:, 1]
        self.send_json(200, {'probabilities': [round(float(p), 6) for p in probabilities]})
