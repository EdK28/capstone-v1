# Will It Sell? and SteamBank

Predict whether an upcoming paid Steam game will find an audience, then compare it with the real market before deciding.

**Will It Sell?** is a machine learning model that estimates the chance a paid Steam game reaches **20,000 owners**, using only details a developer controls before launch: genres, tags, store features, price, platforms, languages and achievements.

**SteamBank** is the website around it: a SteamDB-style explorer of 117,715 Steam games, with the predictor and a market comparison built in. Predictions come from a Python API that runs the trained scikit-learn model, with a built-in copy of the model as a fallback.

## Features

- **Predictor:** enter a game's details and get its estimated chance of reaching 20,000 owners, compared with the 26.7% average.
- **Market comparison** after every prediction:
  - where the estimate ranks among all paid games;
  - how often the 250 most similar games actually reached 20,000 owners;
  - whether the price is typical for that niche;
  - how many games in the same genres launch each year;
  - the 10 closest existing games, with thumbnails and their real results;
  - which single change (price, platforms, languages, store features) would move the estimate most.
- **Catalog explorer:** search, filter and sort 117,715 games; rankings; charts of market trends; tag statistics; developer and publisher pages; a page for every game.
- **Live player counts** from Steam's official API when deployed on Vercel.

## Results

| Model | ROC AUC |
| --- | --- |
| Baseline (always predicts "did not sell") | 0.500 |
| Logistic Regression | 0.789 |
| Random Forest | 0.806 |
| Gradient Boosting (untuned) | 0.829 |
| **Gradient Boosting (tuned, final model)** | **0.8296** |

The final model has 0.72 precision and 0.42 recall on games that sold, and 80% accuracy against the baseline's 73%. Gradient Boosting was chosen because it led at every stage, before and after tuning. It also captures combinations of features that a linear model can't, and is small enough (242 trees, about 394 KB) to run in full in the browser.

## Repository structure

```
steambank/
├── steambank_v.ipynb      data cleaning, features, model comparison and evaluation
├── README.md
├── .gitignore
└── steamscope-live/           the website (deploy this folder to Vercel)
    ├── index.html             SteamScope, the predictor and the market comparison
    ├── api/predict.py         prediction API: runs the saved scikit-learn model
    ├── api/players.js         server function that fetches live player counts from Steam
    ├── model/                 model.joblib and model_info.json, written by the notebook's export cell
    ├── requirements.txt       Python packages for the prediction API
    ├── vercel.json            includes the model/ folder with the API
    └── README.md              deployment guide for the API and live player counts
```

## How to run

**Notebook**

1. Download `games.csv` from the [Steam Games Dataset on Kaggle](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset) and put it next to the notebook.
2. Install the libraries:
   ```
   pip install pandas numpy scikit-learn matplotlib jupyter
   ```
3. Open `steambank_v.ipynb` and run all cells. The hyperparameter search takes a few minutes. The last section exports the model into `steamscope-live/`.

**Website**

- Open `steamscope-live/index.html` in a browser to use it locally (no install needed).
- To deploy with live player counts, run these commands inside `steamscope-live`:
  ```
  npm install -g vercel
  vercel
  vercel --prod
  ```
  Accept the default settings. See `steamscope-live/README.md` for details.

## How it works

1. **Data:** 125,855 Steam games, cleaned to 77,764 paid games released before 2025. A game is labelled `sold` if its estimated owners start at 20,000 or more.
2. **Features:** one-hot genres and store features, the top 120 community tags, log-scaled price and achievements, required age, language count and platforms.
3. **Model:** scikit-learn's `HistGradientBoostingClassifier`, tuned with `RandomizedSearchCV`, compared against a baseline, Logistic Regression and Random Forest.
4. **Prediction API:** the notebook saves the model with `joblib`. On Vercel, `api/predict.py` loads it and returns probabilities for the page. The page sends the user's game and all its what-if versions in one request.
5. **Fallback:** the same trees are also embedded in `index.html` as JSON, so predictions still work when the API isn't reachable (offline). Both give the same answer, to within rounding.
6. **Live data:** browsers can't call Steam's API directly (no CORS header), so `api/players.js` runs on Vercel, fetches the counts, and caches them for 60 seconds.

## Changelog

### Model

| Version | Change | Tuned ROC AUC |
| --- | --- | --- |
| v7 | Trains and tests only on games released before 2025. Recent games hadn't had time to sell (5.1% of 2025 games reached 20,000 owners, against 25.9% of 2021 games), and most had no community tags yet, an easy shortcut that doesn't exist for a real upcoming game. | 0.830 |
| v6 | Duplicates removed by app ID instead of name. Removing by name had dropped 1,190 different games that shared a name, including the real Portal 2. | 0.866 |
| v5 | Removed two leaking features: the Steam Trading Cards store feature (only allowed after a game passes a sales threshold) and DLC count (usually released after a game sells). | 0.866 |
| v4 | Added a side-by-side comparison of Logistic Regression, Random Forest and Gradient Boosting. | 0.884 |
| v3 | Added a majority-class baseline, and ran the hyperparameter search live in the notebook. | 0.884 |
| v2 | Added store features (co-op, controller support, achievements and so on) and widened tags from 80 to 120. | 0.889 |
| v1 | First classifier: paid games, one-hot genres, top tags with opinion tags removed, and numeric listing features. | 0.866 |

The score falls from v5 onwards on purpose. Each of those versions removed something that made the model look better than it really was. 0.830 is the honest score for a genuine pre-launch prediction.

### Website

- **Prediction API:** predictions now come from the scikit-learn model through `api/predict.py` on Vercel, with the built-in model as a fallback. The notebook's new export section writes the model files.
- **Thumbnails** in the market comparison, from each game's Steam header image.
- **Market comparison** after every prediction: niche track record, price check, competition trend, closest games and what-if changes.
- **Live player counts** through a Vercel server function and Steam's official API.
- **SteamScope explorer:** catalog of 117,715 games, search, filters, rankings, charts, tags, developers and game pages, with the predictor built in.
- **Will It Sell? predictor page:** form with searchable genres, tags and store features, input validation, and a result panel beside the form.

## Limitations

- Owner counts are Steam estimates given in ranges, so 20,000 owners is a proxy for commercial success, not confirmed sales.
- Marketing, timing, word of mouth and gameplay quality aren't in the data, which limits how accurate any listing-based model can be.
- The what-if changes show what the model associates with success, not guaranteed cause and effect.
- The catalog is a snapshot with releases up to 25 December 2025. Only player counts are live.
- Free-to-play games are excluded, since they are never sold.

## Credits

- Data: [Steam Games Dataset](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset) on Kaggle.
- Live player counts: Steam Web API, `ISteamUserStats/GetNumberOfCurrentPlayers`.
- Built as a data science capstone project, with AI assistance during development.

This is an independent student project and is not affiliated with Valve or Steam.
