# Hockey Game Analysis System - Functional Requirements Recap

## Overview
A complete hockey game analysis system that scrapes game data, provides statistical analysis, and predicts future game outcomes using ELO ratings and Pythagorean expectation methods.

---

## 1. Data Collection

### 1.1 Web Scraping
- **Source**: scoresheets.ca API endpoint
- **Data Extracted**:
  - Game ID (format: #XXXX)
  - Date and time (without seconds)
  - Tournament name
  - Division name
  - Level name
  - Location name and full address
  - Home team
  - Away team
  - Scores (for completed games)
  - Game status (Completed, Initialized, Setup, Forfeit)

### 1.2 Data Storage
- **Format**: CSV file (`csv/hockey_games.csv`)
- **Columns**: game_id, tournament_name, division_name, level_name, date, location_name, location, home_team, away_team, home_score, away_score, status
- **Raw API Response**: Saved to `csv/response_payload.json` (32 fields per game)

---

## 2. Game Analysis & Statistics

### 2.1 Team Results Matrix
- **Purpose**: Visualize all games between teams
- **Format**: HTML table with banded rows
- **Features**:
  - Row headers: Home teams (bold)
  - Column headers: Away teams (bold, vertical text)
  - Cell content: Multiple scores when teams played multiple times at same venue
  - Diagonal cells: Grayed out (same team)
  - Upcoming games: Display "??-??" placeholder in gray italic
  - Empty cells: No game played

### 2.2 Combined Results Table
- **Purpose**: Show all games for each team (home + away)
- **Format**: HTML table
- **Features**:
  - Each row represents one team
  - Cell shows all games vs opponent (regardless of venue)
  - Score format: Row team's score first
  - Explanatory note above table
  - Row headers include team statistics:
    - **W**: Wins
    - **L**: Losses
    - **T**: Ties/Draws
    - **TBP**: To Be Played (upcoming games)

### 2.3 Output Files
- `html/recap_table.html` - Home vs Away specific results
- `html/recap_table_combined.html` - Triangular layout (combined view)
- `html/recap_table_all_games.html` - All games per team with statistics

---

## 3. Game Predictions (Statistical Method)

### 3.1 Rating-Based Prediction System
- **Method**: Custom rating system using offensive and defensive ratings
- **Calculation**:
  - Team ratings based on goals scored/conceded vs league average
  - Home ice advantage: ~5%
  - Expected goals calculation
  - Probabilities using logistic functions

### 3.2 Prediction Output
- **Format**: CSV and HTML
- **Content**:
  - Win/Tie/Loss probabilities (%)
  - Expected scores
  - Most likely outcome
  - Team ratings table (strength, offensive rating, defensive rating, win%, games played)

### 3.3 Output Files
- `csv/predictions.csv` - Prediction data
- `html/predictions.html` - Formatted predictions with color-coded probabilities:
  - 🟢 Green: ≥60% (high probability)
  - 🟠 Orange: 30-59% (medium)
  - 🔴 Red: <30% (low)

---

## 4. Game Predictions (ELO Method)

### 4.1 ELO Rating System
- **Initial ELO**: 1500 for all teams
- **Optimized Parameters** (after 750-combination testing):
  - K-factor: 35 (controls rating change magnitude)
  - Home advantage: +100 ELO points
  - Pythagorean exponent: 2.0
  - ELO weight: 0.8 (vs 0.2 for Pythagorean)

### 4.2 Pythagorean Expectation
- **Formula**: `pyth = (GF^2.0) / (GF^2.0 + GA^2.0)`
- **Purpose**: Calculate expected win percentage based on goals scored vs allowed
- **Source**: Adapted from baseball analytics (Nate Silver)

### 4.3 Combined Prediction
- **Method**: Weighted average of ELO (80%) and Pythagorean (20%) methods
- **Accuracy**: 71.4% (after optimization, improved from 60-64%)

### 4.4 Prediction Validation
- **Method**: Walk-forward validation on historical games
- **Features**:
  - Game-by-game validation results
  - Per-team accuracy tracking
  - Overall accuracy calculation

### 4.5 Output Files
- `csv/elo_predictions.csv` - ELO-based predictions with probabilities
- `html/elo_predictions.html` - Interactive HTML report with team rankings
- `csv/elo_validation.csv` - Game-by-game validation results
- `csv/elo_validation_accuracy.csv` - Per-team accuracy metrics
- `html/elo_validation.html` - Comprehensive validation report

---

## 5. Web Application

### 5.1 User Interface
- **Type**: Single-page web application
- **Framework**: Vanilla JavaScript, HTML5, CSS3
- **Features**:
  - "Scrape Data" button (rate-limited to once per hour)
  - 3 dropdown filters: Tournament, Division, Level
  - "Analyze & Predict" button
  - "Validate Predictions" button
  - CSV download functionality

### 5.2 Display Sections (in order)
1. **Team Results Matrix**: Visual grid of all game results
2. **Win/Loss/Tie Statistics**: Per-team record summary
3. **Upcoming Game Predictions**: ELO-based predictions with probabilities
4. **Team ELO Ratings**: Current ratings with accuracy column

### 5.3 Rate Limiting
- **Cooldown**: 1 hour between data scrapes
- **Storage**: `csv/last_fetch_time.json`
- **Display**: "Next fetch allowed on [date] at [time]"
- **Behavior**: Shared cooldown for all users, button auto-enables after cooldown

---

## 6. Backend API

### 6.1 Technology Stack
- **Server**: Node.js with Express (v4.18.2)
- **Dependencies**: Axios (v1.6.0), CORS (v2.8.5)

### 6.2 API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scrape/status` | GET | Check rate limit status |
| `/api/scrape` | POST | Scrape data (rate limited) |
| `/api/filters` | GET | Get filter options |
| `/api/analyze` | POST | Analyze games |
| `/api/predict` | POST | Generate ELO predictions |
| `/api/validate` | POST | Validate prediction accuracy |
| `/api/download/csv` | GET | Download CSV file |

---

## 7. Parameter Optimization

### 7.1 Optimization Process
- **Script**: `optimize_params.py`
- **Test Combinations**: 750
- **Parameters Tested**:
  - K-factors: 15, 20, 25, 30, 35, 40
  - Home advantages: 50, 75, 100, 125, 150
  - Pythagorean exponents: 1.8, 2.0, 2.2, 2.37, 2.5
  - ELO weights: 0.4, 0.5, 0.6, 0.7, 0.8

### 7.2 Results
- **Original Accuracy**: 60-64%
- **Optimized Accuracy**: 71.4%
- **Output**: `csv/optimization_results.csv`

### 7.3 Key Findings
- Higher K-factor (35) better suits hockey's game-to-game variance
- Lower Pythagorean exponent (2.0) fits hockey scoring patterns better than 2.37
- ELO ratings more predictive than Pythagorean expectation (80/20 split optimal)

---

## 8. File Organization

### 8.1 Directory Structure
```
/
├── csv/                    # All CSV and JSON data files
├── html/                   # All HTML output files
├── public/                 # Web application frontend
├── ai_sessions/            # Chat logs and documentation
└── [root]                  # Python scripts, server.js, configs
```

### 8.2 Python Scripts
- `scrape_games.py` - Data collection from scoresheets.ca
- `recap_games.py` - Generate statistics and result tables
- `predictor_games.py` - Statistical prediction method
- `elo_games.py` - ELO rating and prediction system
- `optimize_params.py` - Parameter optimization (750 combinations)

### 8.3 Configuration Files
- `package.json` - Node.js dependencies
- `server.js` - Express server and API
- `setup.sh` - Setup script
- `start.sh` - Launch script
- `README.md` - Main documentation
- `README_WEBAPP.md` - Web app documentation

---

## 9. Data Filtering

### 9.1 Current Implementation
- **Filter Target**: E.H.L., Moins de 15 ans, B
- **Results**: 96 games found (81 completed, 15 upcoming)
- **Teams**: 9 teams in division

### 9.2 Flexible Filtering
- Web application supports dynamic filtering by:
  - Tournament name
  - Division name
  - Level name

---

## 10. Visual Features

### 10.1 HTML Table Styling
- Banded rows (alternating colors)
- Bold headers (columns and rows)
- Color-coded probabilities
- Vertical text for column headers (space saving)
- Gray italic text for placeholders
- Responsive design

### 10.2 Data Visualization
- Team results matrix
- Statistical summaries
- Prediction confidence indicators
- Accuracy metrics display

---

## 11. Performance Metrics

| Metric | Value |
|--------|-------|
| Prediction Accuracy | 71.4% |
| Total Games Analyzed | 1393 |
| Filtered Division Games | 96 |
| Teams in Division | 9 |
| Upcoming Games | 14-15 |
| Optimization Tests | 750 |

---

## 12. References

### 12.1 Methodology
- ELO rating system (adapted from chess)
- Pythagorean expectation (inspired by Nate Silver's baseball analytics)
- Source: https://medium.com/@sameerkoppolu/predicting-the-results-of-nba-matches-using-elo-rating-system-and-pythagorean-expectation-4b8ee6ec577

### 12.2 Data Source
- scoresheets.ca API
- Tournament schedules and game results

---

## Summary

This system provides comprehensive hockey game analysis with:
- ✅ Automated data collection
- ✅ Historical game statistics and visualization
- ✅ Dual prediction methods (statistical + ELO)
- ✅ Optimized prediction parameters (71.4% accuracy)
- ✅ Validation and accuracy tracking
- ✅ User-friendly web interface
- ✅ Rate-limited API protection
- ✅ Flexible filtering
- ✅ CSV export functionality
- ✅ Professional HTML reports
