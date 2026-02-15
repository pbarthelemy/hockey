# Hockey Scoresheet Analyzer - Node.js App

A single-page web application for scraping and analyzing hockey game data from scoresheets.ca.

## Features

- 🔄 Scrape game data from scoresheets.ca API with 1-hour rate limiting
- 📊 Analyze games with interactive filters (tournament, division, level)
- 📈 Display team results matrix showing all games
- 📉 Statistics summary (wins, losses, ties, upcoming games)
- 🎯 ELO-based predictions for upcoming games (71.4% accuracy)
- ✓ Validate prediction accuracy on historical data
- 🎲 Optimized parameters via cross-validation (K=35, Home=100, Pyth=2.0, ELO weight=0.8)
- 📊 Accuracy column showing past game prediction performance per team
- ⬇️ Download scraped data as CSV
- 🎯 Single-page application with no page reloads

## Installation

1. Install dependencies:
```bash
npm install
```

## Usage

1. Start the server:
```bash
npm start
```

Or for development with auto-reload:
```bash
npm run dev
```

2. Open your browser to:
```
http://localhost:3000
```

## How to Use

1. **Scrape Data**: Click "Scrape Data" button to fetch the latest games from scoresheets.ca
   - Note: Rate limited to once per hour for all users
   - Next allowed fetch time displayed below the button
2. **Select Filters**: Choose Tournament, Division, and Level from the dropdowns
3. **Analyze & Predict**: Click "Analyze & Predict" to generate:
   - Team results matrix with all game scores
   - Win/Loss/Tie statistics
   - ELO-based predictions for upcoming games
   - Team ELO ratings with historical prediction accuracy
4. **Validate Predictions**: Click "Validate Predictions" to test accuracy on historical data
5. **Download**: Click "Download CSV" to get the raw data file

## Rate Limiting

To avoid overloading the scoresheets.ca API:
- Scraping is limited to once per hour (server-wide)
- Last fetch time persists across server restarts
- UI shows when next fetch is allowed
Current system achieves **71.4% accuracy** on E.H.L. Moins de 15 ans B division.

## Parameter Optimization

TheGET /api/scrape/status` - Check if scraping is allowed (rate limit status)
- `POST /api/scrape` - Scrape games from scoresheets.ca (rate limited)
- `GET /api/filters` - Get available filter options
- `POST /api/analyze` - Analyze games with filters
- `POST /api/predict` - Generate ELO predictions
- `POST /api/validate` - Validate prediction accuracy
K_FACTOR = 35              // (was 20) - Faster ELO adjustments
HOME_ADVANTAGE = 100       // Home team bonus
PYTHAGOREAN_EXPONENT = 2.0 // (was 2.37) - Hockey-specific
ELO_WEIGHT = 0.8           // (was 0.6) - ELO vs Pythagorean
PYTH_WEIGHT = 0.2
```

To re-optimize parameters for your data:
```bash
python3 optimize_params.py
```

This tests 750 parameter   # Express server and API endpoints
├── package.json           # Node.js dependencies
├── optimize_params.py     # Parameter optimization script
├── elo_games.py           # Python ELO prediction script
├── public/
│   └── index.html        # Single-page application UI
├── csv/                  # CSV and JSON data files
│   ├── hockey_games.csv
│   ├── last_fetch_time.json
│   ├── optimization_results.csv
│   └── ...
└── html/                 # Generated HTML reports

The validation feature tests the accuracy of the ELO prediction system by:
- Processing each completed game chronologically
- Using only data available before each game to make a prediction
- Comparing predictions to actual outcomes
- Calculating accuracy per team and overall

This provides insight into how reliable the predictions are for future games.

## API Endpoints

- `POST /api/scrape` - Scrape games from scoresheets.ca
- `GET /api/filters` - Get available filter options
- `POST /api/analyze` - Analyze games with filters
- `GET /api/download/csv` - Download CSV file

## Default Values

- Tournament: E.H.L.
- Division: Moins de 15 ans
- Level: B
- Tournament ID: 17
- Division ID: 45
- Level ID: 6

## File Structure

```
.
├── server.js           # Express server and API endpoints
├── package.json        # Node.js dependencies
├── public/
│   └── index.html     # Single-page application UI
├── csv/               # CSV and JSON data files
└── html/              # Generated HTML reports (from Python scripts)
```

## Technologies Used

- **Backend**: Node.js, Express
- **HTTP Client**: Axios
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
