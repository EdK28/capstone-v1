# SteamScope: prediction API and live player counts

This folder is a complete website you can deploy to Vercel:

```
steamscope-live/
├── index.html            the SteamScope explorer and "Will it sell?" predictor
├── api/
│   ├── predict.py        prediction API: runs the scikit-learn model saved from the notebook
│   └── players.js        live player counts from Steam
├── model/
│   ├── model.joblib      the trained model (written by the notebook's export cell)
│   └── model_info.json   its column lists, base rate and scikit-learn version
├── requirements.txt      Python packages the prediction API needs
└── vercel.json           tells Vercel to include the model/ folder with the API
```

## The prediction API

When the user clicks **Estimate chance of selling**, the page sends the game's details to `/api/predict`.
That API is `api/predict.py`, a Python function on Vercel that loads the real scikit-learn model from
`model/model.joblib` and returns the probability.

```
Browser (index.html)                         Vercel                                   
┌──────────────────────────┐  POST {"games": [...]}  ┌────────────────────────────────┐
│ predictBatch()           │ ──────────────────────▶ │ api/predict.py                 │
│ the user's game plus     │                         │ build_row(): same columns as   │
│ every what-if version,   │ ◀────────────────────── │ the notebook, then             │
│ in one request           │  {"probabilities":[...]}│ model.predict_proba()          │
└──────────────────────────┘                         └────────────────────────────────┘
```

**Request** (genres, tags and store features are names):

```json
{ "games": [ { "genres": ["Action", "Indie"], "tags": ["Co-op", "Open World"], "categories": ["Online Co-op"],
               "price": 15, "required_age": 0, "achievements": 30, "languages": 6,
               "windows": 1, "mac": 1, "linux": 1 } ] }
```

**Reply:** `{ "probabilities": [0.782255] }`. Up to 20 games per request. A negative price or fewer than one
language returns a 400 error with a message.

**How it works, step by step**

1. When the page opens, `probePredictApi()` sends `GET /api/predict`. If the reply says `"status": "ok"`, the
   page uses the API from then on.
2. On each click, `leverScenarios()` builds the what-if versions of the game, and `predictBatch()` sends the user's
   game plus all of them in **one** request.
3. `api/predict.py` turns each game into the same 215 columns the model was trained on (`build_row()`), runs
   `model.predict_proba()`, and returns the probabilities.
4. Under the result, the page says which one did the calculation: the API, or the browser.

**If the API isn't available** (on claude.ai, when the file is opened from disk, or if the API errors), the page
uses a copy of the same model built into `index.html`. Both give the same answer, to within rounding.

**Updating the model:** re-run the notebook, including section 12 "Export the Model for the Website". It rewrites
`model/model.joblib`, `model/model_info.json` and the model copy inside `index.html`. Then run `vercel --prod`.

**Keep the scikit-learn version the same.** A model saved with one version of scikit-learn may not load in
another. The export cell prints the version it used (`scikit-learn==1.8.0` here); `requirements.txt` must match.

## Live player counts: where the numbers come from

SteamDB does not offer a public API, so the site does not use SteamDB. SteamDB's own player counts come
from Valve's official Steam Web API, and this site uses the same source:

```
https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=730
```

It is free and needs no API key. Steam replies with:

```json
{ "response": { "player_count": 812345, "result": 1 } }
```

`result: 1` means success. Any other value means Steam has no count for that app (for example a DLC,
a soundtrack, or a delisted game). Steam refreshes these numbers roughly every 5 minutes.

## How live player counts are linked

The obvious approach would be for the page's JavaScript to call Steam directly. That does not work:

1. **Browsers block it (CORS).** A page on `your-site.vercel.app` may only read a response from another
   website if that website says it's allowed, using a header called `Access-Control-Allow-Origin`.
   Steam's API doesn't send that header, so the browser throws the response away before your code sees it.
2. **Server code has no such rule.** CORS is a browser safety feature. Code running on a server can call
   any API it likes.

So the site uses a small middleman (a "proxy") that runs on Vercel's servers:

```
 Visitor's browser                 Your Vercel site                      Steam
┌──────────────────┐  1. request  ┌────────────────────┐  2. request  ┌─────────────────┐
│ index.html       │ ───────────▶ │ api/players.js     │ ───────────▶ │ Steam Web API   │
│ fetch(           │              │ (serverless        │              │ GetNumberOf     │
│  '/api/players   │ ◀─────────── │  function)         │ ◀─────────── │ CurrentPlayers  │
│   ?appids=730')  │  4. counts   └────────────────────┘  3. counts   └─────────────────┘
└──────────────────┘
```

1. The page asks its **own** site: `GET /api/players?appids=730,570`. Same website, so no CORS problem.
2. `api/players.js` calls Steam once per game, all at the same time.
3. Steam answers with each game's player count.
4. The function sends back one tidy answer: `{ "counts": { "730": 812345, "570": 401234 }, "fetchedAt": "…" }`.

### What `api/players.js` does, step by step

- **Checks the input.** Keeps only numeric app IDs, removes duplicates, and allows at most 20 games per
  request, so nobody can use your site to flood Steam with requests.
- **Calls Steam in parallel** with `Promise.all`, so 20 games take about as long as 1.
- **Never crashes on a bad reply.** If Steam is slow (over 4 seconds), down, or has no count for a game,
  that game comes back as `null` and the rest still work.
- **Caches for 60 seconds** (`Cache-Control: s-maxage=60`). Vercel's network reuses the same answer for a
  minute, so a hundred visitors cause one call to Steam, not a hundred. Since Steam only updates about
  every 5 minutes, visitors lose nothing.

### What the page does with it (in `index.html`)

Search for `LIVE_API` in `index.html` to find this code.

- **On load**, it makes one test request (`/api/players?appids=730`). If that works, live features turn on.
  If it fails (for example when the page is opened from your computer, or on claude.ai), everything live
  stays hidden and the rest of the site works as normal.
- **Home page:** a "Playing on Steam right now" table. It asks for the 20 biggest games in the dataset and
  shows the 12 with the most players at this moment, next to their peak from the dataset for comparison.
- **Each game page:** a "Playing right now" count in the sidebar.
- **Refreshes every 60 seconds** while you stay on the page.

## Deploy it (about 5 minutes)

You need Node.js installed and a free Vercel account (the same one as your portfolio works).

**Option A: Vercel CLI**

```bash
npm install -g vercel
cd steamscope-live
vercel          # first run: log in, accept the defaults
vercel --prod   # publish to your production URL
```

**Option B: GitHub**

1. Put this folder in a new GitHub repository.
2. On vercel.com choose **Add New → Project**, import the repository, and click **Deploy**.

No build step, framework, or `package.json` is needed. Vercel serves `index.html` as the website,
turns each file inside `api/` into a server function, and installs the Python packages listed in
`requirements.txt` for `api/predict.py`.

## Check that it works

1. Open `https://YOUR-PROJECT.vercel.app/api/predict`. You should see `"status": "ok"` and the model's ROC AUC.
2. Open `https://YOUR-PROJECT.vercel.app/api/players?appids=730,570`. You should see JSON with two numbers.
3. Open `https://YOUR-PROJECT.vercel.app/`. A green **Playing on Steam right now** table should appear on
   the home page, and after a prediction the result should say **Calculated by the prediction API**.

If the table doesn't appear, open the browser's developer tools (F12), go to the **Network** tab, reload,
and look for the `players?appids=730` request to see what went wrong.

## Things to know

- **The first prediction after a quiet period can be slow.** Vercel starts the Python function on demand, and
  loading scikit-learn takes a few seconds. Later requests are fast.
- **Function size.** scikit-learn, NumPy and SciPy are large, close to Vercel's size limit for a function. If the
  deploy fails with a size error, the site still works: predictions fall back to the built-in model.

- **Live counts appear only when deployed.** The claude.ai version and the file opened from your
  computer can't reach the function, so they show the dataset only. This is expected.
- **The rest of the site is still a snapshot** (data up to 25 Dec 2025). Only the player counts are live.
- **Counts only include people connected to Steam.** Players in offline mode aren't counted. This is a
  Steam limitation, and SteamDB has the same one.
