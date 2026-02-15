# Hockey Scoresheet Analyzer

A comprehensive web application and Python scripts for analyzing hockey game data from scoresheets.ca with ELO-based predictions.

## 🚀 Quick Start

**Web Application (Recommended):**
```bash
npm install
npm start
```
Then open http://localhost:3000

**Python Scripts:**
```bash
python3 elo_games.py
```

## ✨ Features

- 🔄 Scrape live game data from scoresheets.ca API
- 📊 Interactive web dashboard with real-time analysis
- 🎯 **71.4% prediction accuracy** using optimized ELO ratings
- 📈 Team performance matrix and statistics
- ✓ Historical validation of prediction accuracy
- 🎲 Parameter optimization via cross-validation
- 📊 Per-team accuracy tracking
- ⬇️ Export data to CSV/HTML

## 📊 Prediction System

The system uses a hybrid approach combining:
- **ELO Ratings** (80% weight) - adapted from chess
- **Pythagorean Expectation** (20% weight) - based on goal differential

### Optimized Parameters
```
K_FACTOR = 35              # ELO adjustment rate (was 20)
HOME_ADVANTAGE = 100       # Home team bonus
PYTHAGOREAN_EXPONENT = 2.0 # Goal differential weight (was 2.37)
ELO_WEIGHT = 0.8           # ELO vs Pythagorean (was 0.6)
```

These were optimized via systematic testing of 750 parameter combinations.

## 🛡️ Rate Limiting

Scraping is limited to once per hour (server-wide) to avoid API overload:
- Status persists across server restarts
- UI displays next allowed fetch time
- Shared cooldown for all users

## 🔧 Scripts

- **`server.js`** - Node.js web server with Express API
- **`elo_games.py`** - Python ELO prediction engine
- **`optimize_params.py`** - Parameter optimization via cross-validation
- **`scrape_games.py`** - Data scraping utility
- **`predictor_games.py`** - Game prediction generator
- **`recap_games.py`** - Statistics and recap tables

## 📂 Project Structure

```
├── server.js                    # Express web server
├── package.json                 # Node.js dependencies
├── optimize_params.py           # Parameter tuning
├── elo_games.py                 # ELO prediction engine
├── public/
│   └── index.html              # Web UI
├── csv/                        # Data files
│   ├── hockey_games.csv
│   ├── last_fetch_time.json
│   └── optimization_results.csv
└── html/                       # Generated reports
```

## 🎯 Improving Predictions

To re-optimize parameters for your dataset:
```bash
python3 optimize_params.py
```

Tests combinations of:
- K-factors: 15-40
- Home advantages: 50-150
- Pythagorean exponents: 1.8-2.5
- ELO/Pythagorean weights: 0.4-0.8

Results saved to `csv/optimization_results.csv`.

## 📖 Documentation

See [README_WEBAPP.md](README_WEBAPP.md) for detailed web application documentation.

## 🧪 Technologies

- **Backend**: Node.js, Express, Python 3
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Data**: CSV processing, JSON APIs
- **Math**: ELO ratings, Pythagorean expectation, cross-validation
