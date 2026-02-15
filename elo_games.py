#!/usr/bin/env python3
"""
Predict outcomes of upcoming hockey games using ELO rating system and Pythagorean Expectation
Based on methodology from: https://medium.com/@sameerkoppolu/predicting-the-results-of-nba-matches-using-elo-rating-system-and-pythagorean-expectation-4b8ee6ec577
"""

import csv
import math
from datetime import datetime

# Constants
INITIAL_ELO = 1500
K_FACTOR = 20  # How much ELO changes per game
HOME_ADVANTAGE = 100  # Home team gets bonus ELO points
PYTHAGOREAN_EXPONENT = 2.37  # Optimized for hockey (similar to basketball)


def load_and_filter_games(csv_file, tournament='E.H.L.', division='Moins de 15 ans', level='B'):
    """Load games from CSV and filter by tournament, division, and level"""
    
    games = []
    
    # Read the CSV file
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_games = list(reader)
    
    print(f"Total games loaded: {len(all_games)}")
    
    # Filter for the specified tournament, division, and level
    for game in all_games:
        if (game['tournament_name'] == tournament and 
            game['division_name'] == division and 
            game['level_name'] == level):
            games.append(game)
    
    print(f"Filtered games (E.H.L., Moins de 15 ans, B): {len(games)}")
    
    return games


def calculate_expected_score(elo_a, elo_b):
    """
    Calculate expected score for team A against team B using ELO formula
    Returns probability between 0 and 1
    """
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def update_elo(winner_elo, loser_elo, margin_of_victory=1):
    """
    Update ELO ratings after a game
    Includes margin of victory multiplier
    """
    # Expected scores
    expected_winner = calculate_expected_score(winner_elo, loser_elo)
    expected_loser = calculate_expected_score(loser_elo, winner_elo)
    
    # Margin of victory multiplier (bonus for decisive wins)
    mov_multiplier = math.log(max(margin_of_victory, 1) + 1)
    
    # Update ELO
    new_winner_elo = winner_elo + K_FACTOR * mov_multiplier * (1 - expected_winner)
    new_loser_elo = loser_elo + K_FACTOR * mov_multiplier * (0 - expected_loser)
    
    return new_winner_elo, new_loser_elo


def update_elo_tie(elo_a, elo_b):
    """Update ELO ratings after a tie"""
    expected_a = calculate_expected_score(elo_a, elo_b)
    expected_b = calculate_expected_score(elo_b, elo_a)
    
    # In a tie, both teams get 0.5 actual score
    new_elo_a = elo_a + K_FACTOR * (0.5 - expected_a)
    new_elo_b = elo_b + K_FACTOR * (0.5 - expected_b)
    
    return new_elo_a, new_elo_b


def build_elo_ratings(games):
    """
    Build ELO ratings for all teams based on completed games
    Returns dictionary of team ELO ratings and game-by-game history
    """
    # Initialize ELO ratings
    team_elos = {}
    teams = set()
    
    # Get all teams
    for game in games:
        teams.add(game['home_team'])
        teams.add(game['away_team'])
    
    # Initialize all teams with starting ELO
    for team in teams:
        team_elos[team] = {
            'current_elo': INITIAL_ELO,
            'games_played': 0,
            'total_points_for': 0,
            'total_points_against': 0
        }
    
    # Sort games by date
    completed_games = [g for g in games if g['status'] == 'Completed' and g['home_score'] and g['away_score']]
    completed_games.sort(key=lambda x: x['date'])
    
    print(f"\nProcessing {len(completed_games)} completed games to build ELO ratings...")
    
    # Process each completed game in chronological order
    for game in completed_games:
        home = game['home_team']
        away = game['away_team']
        home_score = int(game['home_score'])
        away_score = int(game['away_score'])
        
        # Get current ELO ratings (add home advantage for home team)
        home_elo = team_elos[home]['current_elo'] + HOME_ADVANTAGE
        away_elo = team_elos[away]['current_elo']
        
        # Update cumulative points
        team_elos[home]['total_points_for'] += home_score
        team_elos[home]['total_points_against'] += away_score
        team_elos[home]['games_played'] += 1
        
        team_elos[away]['total_points_for'] += away_score
        team_elos[away]['total_points_against'] += home_score
        team_elos[away]['games_played'] += 1
        
        # Update ELO based on result
        if home_score > away_score:
            # Home team wins
            margin = home_score - away_score
            new_home_elo, new_away_elo = update_elo(home_elo, away_elo, margin)
            # Remove home advantage from updated home ELO
            team_elos[home]['current_elo'] = new_home_elo - HOME_ADVANTAGE
            team_elos[away]['current_elo'] = new_away_elo
        elif away_score > home_score:
            # Away team wins
            margin = away_score - home_score
            new_away_elo, new_home_elo = update_elo(away_elo, home_elo, margin)
            team_elos[home]['current_elo'] = new_home_elo - HOME_ADVANTAGE
            team_elos[away]['current_elo'] = new_away_elo
        else:
            # Tie
            new_home_elo, new_away_elo = update_elo_tie(home_elo, away_elo)
            team_elos[home]['current_elo'] = new_home_elo - HOME_ADVANTAGE
            team_elos[away]['current_elo'] = new_away_elo
    
    return team_elos


def calculate_pythagorean_expectation(team_elos):
    """
    Calculate Pythagorean expectation (expected win %) for each team
    Based on points scored and points allowed
    """
    for team, stats in team_elos.items():
        if stats['games_played'] > 0:
            points_for = stats['total_points_for']
            points_against = stats['total_points_against']
            
            # Pythagorean expectation formula
            if points_for + points_against > 0:
                pyth_exp = (points_for ** PYTHAGOREAN_EXPONENT) / (
                    points_for ** PYTHAGOREAN_EXPONENT + points_against ** PYTHAGOREAN_EXPONENT
                )
            else:
                pyth_exp = 0.5
            
            stats['pythagorean_expectation'] = pyth_exp
        else:
            stats['pythagorean_expectation'] = 0.5
    
    return team_elos


def predict_game_elo(home_team, away_team, team_elos):
    """
    Predict game outcome using ELO ratings
    Returns home win probability
    """
    home_elo = team_elos[home_team]['current_elo'] + HOME_ADVANTAGE
    away_elo = team_elos[away_team]['current_elo']
    
    # Calculate expected score (win probability) for home team
    home_win_prob = calculate_expected_score(home_elo, away_elo)
    
    return home_win_prob


def predict_game_pythagorean(home_team, away_team, team_elos):
    """
    Predict game outcome using Pythagorean expectation
    Uses logit model: ln(odds) = β0 + β1*pyth + β2*home
    
    For hockey, we'll use simplified coefficients based on the methodology
    """
    home_pyth = team_elos[home_team]['pythagorean_expectation']
    away_pyth = team_elos[away_team]['pythagorean_expectation']
    
    # Logit model coefficients (approximated for hockey)
    beta_0 = 0.0  # Intercept
    beta_pyth = 3.5  # Coefficient for Pythagorean expectation difference
    beta_home = 0.4  # Coefficient for home advantage
    
    # Calculate log odds for home team
    # We use the difference in Pythagorean expectations
    pyth_diff = home_pyth - away_pyth
    log_odds = beta_0 + beta_pyth * pyth_diff + beta_home
    
    # Convert log odds to probability
    odds = math.exp(log_odds)
    home_win_prob = odds / (1 + odds)
    
    return home_win_prob


def predict_upcoming_games(games, team_elos):
    """
    Predict outcomes for all upcoming (non-completed) games
    Returns list of predictions
    """
    predictions = []
    
    # Get upcoming games
    upcoming_games = [g for g in games if g['status'] != 'Completed']
    
    print(f"\nPredicting {len(upcoming_games)} upcoming games...")
    
    for game in upcoming_games:
        home = game['home_team']
        away = game['away_team']
        
        # Skip if teams don't have ELO ratings (shouldn't happen)
        if home not in team_elos or away not in team_elos:
            continue
        
        # Get predictions using both methods
        elo_home_win_prob = predict_game_elo(home, away, team_elos)
        pyth_home_win_prob = predict_game_pythagorean(home, away, team_elos)
        
        # Combined prediction (average of both methods)
        combined_home_win_prob = (elo_home_win_prob + pyth_home_win_prob) / 2
        
        prediction = {
            'game_id': game['game_id'],
            'date': game['date'],
            'location': game['location_name'],
            'home_team': home,
            'away_team': away,
            'home_elo': team_elos[home]['current_elo'],
            'away_elo': team_elos[away]['current_elo'],
            'home_pyth': team_elos[home]['pythagorean_expectation'],
            'away_pyth': team_elos[away]['pythagorean_expectation'],
            'elo_home_win_prob': elo_home_win_prob * 100,
            'pyth_home_win_prob': pyth_home_win_prob * 100,
            'combined_home_win_prob': combined_home_win_prob * 100,
            'combined_away_win_prob': (1 - combined_home_win_prob) * 100,
            'predicted_winner': home if combined_home_win_prob > 0.5 else away
        }
        
        predictions.append(prediction)
    
    return predictions


def save_predictions_to_csv(predictions, output_file='elo_predictions.csv'):
    """Save predictions to CSV file"""
    if not predictions:
        print("No predictions to save.")
        return
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'game_id', 'date', 'location', 'home_team', 'away_team',
            'home_elo', 'away_elo', 'home_pyth', 'away_pyth',
            'elo_home_win_prob', 'pyth_home_win_prob',
            'combined_home_win_prob', 'combined_away_win_prob',
            'predicted_winner'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(predictions)
    
    print(f"\nPredictions saved to {output_file}")


def generate_html_report(predictions, team_elos, output_file='elo_predictions.html'):
    """Generate HTML report with predictions and team ratings"""
    
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ELO Predictions - E.H.L. Moins de 15 ans B</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1, h2 {
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        th {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        tr:hover {
            background-color: #ddd;
        }
        .high-prob {
            background-color: #90EE90;
            font-weight: bold;
        }
        .medium-prob {
            background-color: #FFFACD;
        }
        .low-prob {
            background-color: #FFB6C1;
        }
        .timestamp {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 20px;
        }
        .stats-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }
        .stat-label {
            font-size: 0.9em;
            color: #666;
        }
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏒 ELO Rating System - Game Predictions</h1>
        <h2>E.H.L. - Moins de 15 ans - Level B</h2>
        <div class="timestamp">Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</div>
        
        <h2>📊 Team ELO Ratings</h2>
        <table>
            <tr>
                <th>Team</th>
                <th>Current ELO</th>
                <th>Games Played</th>
                <th>Pythagorean Exp.</th>
                <th>Avg Goals For</th>
                <th>Avg Goals Against</th>
            </tr>
"""
    
    # Sort teams by ELO rating
    sorted_teams = sorted(team_elos.items(), key=lambda x: x[1]['current_elo'], reverse=True)
    
    for team, stats in sorted_teams:
        if stats['games_played'] > 0:
            avg_for = stats['total_points_for'] / stats['games_played']
            avg_against = stats['total_points_against'] / stats['games_played']
            html += f"""            <tr>
                <td><strong>{team}</strong></td>
                <td>{stats['current_elo']:.1f}</td>
                <td>{stats['games_played']}</td>
                <td>{stats['pythagorean_expectation']:.3f}</td>
                <td>{avg_for:.2f}</td>
                <td>{avg_against:.2f}</td>
            </tr>
"""
    
    html += """        </table>
        
        <h2>🎯 Upcoming Game Predictions</h2>
        <table>
            <tr>
                <th>Game ID</th>
                <th>Date</th>
                <th>Location</th>
                <th>Home Team</th>
                <th>Away Team</th>
                <th>Home ELO</th>
                <th>Away ELO</th>
                <th>ELO Win %</th>
                <th>Pyth Win %</th>
                <th>Combined Win %</th>
                <th>Predicted Winner</th>
            </tr>
"""
    
    for pred in predictions:
        # Determine cell class based on confidence
        combined_prob = max(pred['combined_home_win_prob'], pred['combined_away_win_prob'])
        prob_class = 'high-prob' if combined_prob > 70 else ('medium-prob' if combined_prob > 55 else 'low-prob')
        
        html += f"""            <tr>
                <td>{pred['game_id']}</td>
                <td>{pred['date']}</td>
                <td>{pred['location']}</td>
                <td>{pred['home_team']}</td>
                <td>{pred['away_team']}</td>
                <td>{pred['home_elo']:.1f}</td>
                <td>{pred['away_elo']:.1f}</td>
                <td>{pred['elo_home_win_prob']:.1f}%</td>
                <td>{pred['pyth_home_win_prob']:.1f}%</td>
                <td class="{prob_class}">{pred['combined_home_win_prob']:.1f}% / {pred['combined_away_win_prob']:.1f}%</td>
                <td class="{prob_class}"><strong>{pred['predicted_winner']}</strong></td>
            </tr>
"""
    
    html += """        </table>
        
        <div class="stats-summary">
            <div class="stat-card">
                <div class="stat-label">Total Predictions</div>
                <div class="stat-value">""" + str(len(predictions)) + """</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Teams Tracked</div>
                <div class="stat-value">""" + str(len(team_elos)) + """</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Methodology</div>
                <div class="stat-value">ELO + Pythagorean</div>
            </div>
        </div>
        
        <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
            <strong>Methodology:</strong> Predictions use a combination of ELO rating system and Pythagorean expectation.
            ELO ratings are updated after each game based on results and margin of victory.
            Pythagorean expectation estimates win probability based on goals scored vs. goals allowed.
            Home advantage of +100 ELO points is included.
        </p>
    </div>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML report saved to {output_file}")


def main():
    """Main function"""
    print("=" * 80)
    print("ELO Rating System - Hockey Game Predictions")
    print("E.H.L. - Moins de 15 ans - Level B")
    print("=" * 80)
    
    # Load and filter games
    games = load_and_filter_games('hockey_games.csv')
    
    if not games:
        print("No games found matching the criteria.")
        return
    
    # Build ELO ratings from completed games
    team_elos = build_elo_ratings(games)
    
    # Calculate Pythagorean expectations
    team_elos = calculate_pythagorean_expectation(team_elos)
    
    # Display team ratings
    print("\n" + "=" * 80)
    print("TEAM ELO RATINGS")
    print("=" * 80)
    sorted_teams = sorted(team_elos.items(), key=lambda x: x[1]['current_elo'], reverse=True)
    
    print(f"{'Team':<30} {'ELO':>8} {'Games':>6} {'Pyth Exp':>10} {'GF/G':>8} {'GA/G':>8}")
    print("-" * 80)
    
    for team, stats in sorted_teams:
        if stats['games_played'] > 0:
            avg_for = stats['total_points_for'] / stats['games_played']
            avg_against = stats['total_points_against'] / stats['games_played']
            print(f"{team:<30} {stats['current_elo']:>8.1f} {stats['games_played']:>6} "
                  f"{stats['pythagorean_expectation']:>10.3f} {avg_for:>8.2f} {avg_against:>8.2f}")
    
    # Predict upcoming games
    predictions = predict_upcoming_games(games, team_elos)
    
    # Display predictions
    print("\n" + "=" * 80)
    print("UPCOMING GAME PREDICTIONS")
    print("=" * 80)
    
    if predictions:
        for pred in predictions:
            print(f"\nGame: {pred['game_id']} - {pred['date']}")
            print(f"  {pred['home_team']} (Home) vs {pred['away_team']} (Away)")
            print(f"  Home ELO: {pred['home_elo']:.1f} | Away ELO: {pred['away_elo']:.1f}")
            print(f"  ELO Method: {pred['elo_home_win_prob']:.1f}% - {100-pred['elo_home_win_prob']:.1f}%")
            print(f"  Pythagorean Method: {pred['pyth_home_win_prob']:.1f}% - {100-pred['pyth_home_win_prob']:.1f}%")
            print(f"  Combined Prediction: {pred['combined_home_win_prob']:.1f}% - {pred['combined_away_win_prob']:.1f}%")
            print(f"  → Predicted Winner: {pred['predicted_winner']}")
    else:
        print("No upcoming games to predict.")
    
    # Save results
    save_predictions_to_csv(predictions)
    generate_html_report(predictions, team_elos)
    
    print("\n" + "=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == '__main__':
    main()
