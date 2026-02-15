#!/usr/bin/env python3
"""
Predict outcomes of upcoming hockey games
"""

import csv
import math

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

def calculate_team_ratings(games):
    """
    Calculate team ratings based on goals scored and conceded
    Returns offensive and defensive ratings for each team
    """
    
    # Get all teams
    teams = set()
    for game in games:
        if game['status'] == 'Completed' and game['home_score'] and game['away_score']:
            teams.add(game['home_team'])
            teams.add(game['away_team'])
    
    teams = sorted(teams)
    
    # Initialize stats
    team_stats = {}
    for team in teams:
        team_stats[team] = {
            'goals_for': 0,
            'goals_against': 0,
            'games_played': 0,
            'wins': 0,
            'losses': 0,
            'ties': 0
        }
    
    # Calculate stats from completed games
    for game in games:
        if game['status'] == 'Completed' and game['home_score'] and game['away_score']:
            home = game['home_team']
            away = game['away_team']
            home_goals = int(game['home_score'])
            away_goals = int(game['away_score'])
            
            # Update goals
            team_stats[home]['goals_for'] += home_goals
            team_stats[home]['goals_against'] += away_goals
            team_stats[home]['games_played'] += 1
            
            team_stats[away]['goals_for'] += away_goals
            team_stats[away]['goals_against'] += home_goals
            team_stats[away]['games_played'] += 1
            
            # Update W/L/T
            if home_goals > away_goals:
                team_stats[home]['wins'] += 1
                team_stats[away]['losses'] += 1
            elif home_goals < away_goals:
                team_stats[home]['losses'] += 1
                team_stats[away]['wins'] += 1
            else:
                team_stats[home]['ties'] += 1
                team_stats[away]['ties'] += 1
    
    # Calculate ratings
    league_avg_goals = sum(t['goals_for'] for t in team_stats.values()) / sum(t['games_played'] for t in team_stats.values())
    
    team_ratings = {}
    for team in teams:
        stats = team_stats[team]
        games_played = stats['games_played']
        
        if games_played > 0:
            # Offensive rating: goals scored per game relative to league average
            offensive_rating = stats['goals_for'] / games_played / league_avg_goals
            
            # Defensive rating: goals conceded per game relative to league average (inverted)
            defensive_rating = league_avg_goals / (stats['goals_against'] / games_played)
            
            # Overall strength rating
            strength_rating = (offensive_rating + defensive_rating) / 2
            
            # Win percentage
            win_pct = (stats['wins'] + 0.5 * stats['ties']) / games_played
            
            team_ratings[team] = {
                'offensive': offensive_rating,
                'defensive': defensive_rating,
                'strength': strength_rating,
                'win_pct': win_pct,
                'goals_per_game': stats['goals_for'] / games_played,
                'goals_against_per_game': stats['goals_against'] / games_played,
                'games_played': games_played
            }
        else:
            # Team has no completed games - use league averages
            team_ratings[team] = {
                'offensive': 1.0,
                'defensive': 1.0,
                'strength': 1.0,
                'win_pct': 0.5,
                'goals_per_game': league_avg_goals,
                'goals_against_per_game': league_avg_goals,
                'games_played': 0
            }
    
    return team_ratings, league_avg_goals

def predict_game_outcome(home_team, away_team, team_ratings, league_avg_goals):
    """
    Predict the outcome of a game using team ratings
    Returns probabilities for home win, tie, away win
    """
    
    home_rating = team_ratings[home_team]
    away_rating = team_ratings[away_team]
    
    # Expected goals using offensive and defensive ratings
    # Home team typically has slight advantage (home ice advantage ~ 5%)
    home_advantage = 1.05
    
    expected_home_goals = league_avg_goals * home_rating['offensive'] * away_rating['defensive'] * home_advantage
    expected_away_goals = league_avg_goals * away_rating['offensive'] * home_rating['defensive']
    
    # Calculate goal difference
    goal_diff = expected_home_goals - expected_away_goals
    
    # Use a logistic function to convert goal difference to win probability
    # Standard deviation for hockey goals is approximately 1.5-2.0
    std_dev = 1.8
    
    # Probability of home win using normal distribution approximation
    # P(home wins) = P(goal_diff > 0)
    # P(tie) = P(goal_diff = 0) - we'll use a small window around 0
    # P(away wins) = P(goal_diff < 0)
    
    # For simplicity, we'll use a logistic-based approach
    # Probability home wins
    if goal_diff > 0:
        prob_home_win = 0.5 + 0.5 * math.tanh(goal_diff / std_dev)
    else:
        prob_home_win = 0.5 * (1 + math.tanh(goal_diff / std_dev))
    
    # Probability of tie (smaller in hockey, typically 5-15%)
    # Use a narrow window around 0 goal difference
    tie_window = 0.5
    prob_tie = 0.12 * math.exp(-(goal_diff ** 2) / (2 * tie_window ** 2))
    
    # Adjust and normalize
    prob_away_win = 1.0 - prob_home_win - prob_tie
    
    # Ensure non-negative
    if prob_away_win < 0:
        prob_away_win = 0
        total = prob_home_win + prob_tie
        prob_home_win = prob_home_win / total * (1.0 - 0.01)
        prob_tie = prob_tie / total * (1.0 - 0.01) + 0.01
    
    # Normalize to ensure sum = 1
    total = prob_home_win + prob_tie + prob_away_win
    prob_home_win /= total
    prob_tie /= total
    prob_away_win /= total
    
    return {
        'home_win': prob_home_win * 100,
        'tie': prob_tie * 100,
        'away_win': prob_away_win * 100,
        'expected_home_goals': expected_home_goals,
        'expected_away_goals': expected_away_goals
    }

def predict_upcoming_games(games, team_ratings, league_avg_goals):
    """Predict outcomes for all upcoming games"""
    
    predictions = []
    
    for game in games:
        if game['status'] in ['Initialized', 'Setup', 'In Progress']:
            home = game['home_team']
            away = game['away_team']
            
            if home and away and home in team_ratings and away in team_ratings:
                prediction = predict_game_outcome(home, away, team_ratings, league_avg_goals)
                
                predictions.append({
                    'game_id': game['game_id'],
                    'date': game['date'],
                    'home_team': home,
                    'away_team': away,
                    'location': game['location_name'],
                    'prediction': prediction
                })
    
    return predictions

def display_predictions(predictions):
    """Display predictions in a formatted way"""
    
    print("\n" + "="*80)
    print("GAME PREDICTIONS")
    print("="*80)
    
    if not predictions:
        print("No upcoming games to predict")
        return
    
    for pred in predictions:
        print(f"\n{pred['game_id']} - {pred['date']}")
        print(f"Location: {pred['location']}")
        print(f"{pred['home_team']} (Home) vs {pred['away_team']} (Away)")
        print("-" * 60)
        p = pred['prediction']
        print(f"  Home Win:  {p['home_win']:5.1f}%  |  Tie: {p['tie']:5.1f}%  |  Away Win: {p['away_win']:5.1f}%")
        print(f"  Expected Score: {p['expected_home_goals']:.2f} - {p['expected_away_goals']:.2f}")
        
        # Determine most likely outcome
        if p['home_win'] > p['away_win'] and p['home_win'] > p['tie']:
            print(f"  Most Likely: HOME WIN ({pred['home_team']})")
        elif p['away_win'] > p['home_win'] and p['away_win'] > p['tie']:
            print(f"  Most Likely: AWAY WIN ({pred['away_team']})")
        else:
            print(f"  Most Likely: TIE")

def save_predictions_csv(predictions, output_file='predictions.csv'):
    """Save predictions to CSV file"""
    
    if not predictions:
        print("No predictions to save")
        return
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['game_id', 'date', 'location', 'home_team', 'away_team', 
                     'home_win_pct', 'tie_pct', 'away_win_pct', 
                     'expected_home_goals', 'expected_away_goals', 'most_likely_outcome']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for pred in predictions:
            p = pred['prediction']
            
            # Determine most likely outcome
            if p['home_win'] > p['away_win'] and p['home_win'] > p['tie']:
                outcome = 'HOME WIN'
            elif p['away_win'] > p['home_win'] and p['away_win'] > p['tie']:
                outcome = 'AWAY WIN'
            else:
                outcome = 'TIE'
            
            writer.writerow({
                'game_id': pred['game_id'],
                'date': pred['date'],
                'location': pred['location'],
                'home_team': pred['home_team'],
                'away_team': pred['away_team'],
                'home_win_pct': f"{p['home_win']:.1f}",
                'tie_pct': f"{p['tie']:.1f}",
                'away_win_pct': f"{p['away_win']:.1f}",
                'expected_home_goals': f"{p['expected_home_goals']:.2f}",
                'expected_away_goals': f"{p['expected_away_goals']:.2f}",
                'most_likely_outcome': outcome
            })
    
    print(f"\nPredictions saved to {output_file}")

def generate_predictions_html(predictions, team_ratings, output_file='predictions.html'):
    """Generate HTML table with predictions"""
    
    if not predictions:
        print("No predictions to generate HTML")
        return
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Game Predictions - E.H.L. Moins de 15 ans B</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        h2 {
            color: #555;
            margin-top: 30px;
        }
        table {
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            width: 100%;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        th {
            background-color: #2c3e50;
            color: white;
            font-weight: bold;
        }
        tbody tr:nth-child(odd) {
            background-color: #f9f9f9;
        }
        tbody tr:nth-child(even) {
            background-color: #ffffff;
        }
        .center {
            text-align: center;
        }
        .right {
            text-align: right;
        }
        .prob-high {
            background-color: #2ecc71;
            color: white;
            font-weight: bold;
            padding: 5px;
            border-radius: 3px;
        }
        .prob-medium {
            background-color: #f39c12;
            color: white;
            padding: 5px;
            border-radius: 3px;
        }
        .prob-low {
            background-color: #e74c3c;
            color: white;
            padding: 5px;
            border-radius: 3px;
        }
        .outcome {
            font-weight: bold;
            color: #2c3e50;
        }
        .team-name {
            font-weight: bold;
        }
        .rating-table {
            margin-top: 20px;
        }
        .rating-table td {
            text-align: center;
        }
    </style>
</head>
<body>
    <h1>E.H.L. - Moins de 15 ans - B - Game Predictions</h1>
    <p>Statistical predictions based on historical performance of all teams</p>
    
    <h2>Team Ratings</h2>
    <table class="rating-table">
        <thead>
            <tr>
                <th>Team</th>
                <th class="center">Strength</th>
                <th class="center">Offensive</th>
                <th class="center">Defensive</th>
                <th class="center">Win %</th>
                <th class="center">Games Played</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Add team ratings
    for team in sorted(team_ratings.keys()):
        r = team_ratings[team]
        html += f"""            <tr>
                <td class="team-name">{team}</td>
                <td class="center">{r['strength']:.3f}</td>
                <td class="center">{r['offensive']:.3f}</td>
                <td class="center">{r['defensive']:.3f}</td>
                <td class="center">{r['win_pct']*100:.1f}%</td>
                <td class="center">{r['games_played']}</td>
            </tr>
"""
    
    html += """        </tbody>
    </table>
    
    <h2>Upcoming Games Predictions</h2>
    <table>
        <thead>
            <tr>
                <th>Game ID</th>
                <th>Date</th>
                <th>Location</th>
                <th>Home Team</th>
                <th>Away Team</th>
                <th class="center">Home Win %</th>
                <th class="center">Tie %</th>
                <th class="center">Away Win %</th>
                <th class="center">Expected Score</th>
                <th class="center">Most Likely</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Add predictions
    for pred in predictions:
        p = pred['prediction']
        
        # Determine most likely outcome
        if p['home_win'] > p['away_win'] and p['home_win'] > p['tie']:
            outcome = f"HOME WIN"
            outcome_team = pred['home_team']
        elif p['away_win'] > p['home_win'] and p['away_win'] > p['tie']:
            outcome = f"AWAY WIN"
            outcome_team = pred['away_team']
        else:
            outcome = "TIE"
            outcome_team = ""
        
        # Apply styling based on probability ranges
        def get_prob_class(prob):
            if prob >= 60:
                return "prob-high"
            elif prob >= 30:
                return "prob-medium"
            else:
                return "prob-low"
        
        home_class = get_prob_class(p['home_win'])
        tie_class = get_prob_class(p['tie'])
        away_class = get_prob_class(p['away_win'])
        
        html += f"""            <tr>
                <td>{pred['game_id']}</td>
                <td>{pred['date']}</td>
                <td>{pred['location']}</td>
                <td class="team-name">{pred['home_team']}</td>
                <td class="team-name">{pred['away_team']}</td>
                <td class="center"><span class="{home_class}">{p['home_win']:.1f}%</span></td>
                <td class="center"><span class="{tie_class}">{p['tie']:.1f}%</span></td>
                <td class="center"><span class="{away_class}">{p['away_win']:.1f}%</span></td>
                <td class="center">{p['expected_home_goals']:.2f} - {p['expected_away_goals']:.2f}</td>
                <td class="center outcome">{outcome}{"<br>" + outcome_team if outcome_team else ""}</td>
            </tr>
"""
    
    html += """        </tbody>
    </table>
    
    <div style="margin-top: 20px; padding: 15px; background-color: #ecf0f1; border-radius: 5px;">
        <h3>Methodology</h3>
        <p><strong>Team Ratings:</strong> Calculated from all completed games using offensive (goals scored) and defensive (goals conceded) performance relative to league average.</p>
        <p><strong>Predictions:</strong> Based on team ratings with home ice advantage factor (~5%). Probabilities calculated using expected goal difference and statistical distributions.</p>
        <p><strong>Color Coding:</strong> 
            <span class="prob-high">Green ≥60%</span>, 
            <span class="prob-medium">Orange 30-59%</span>, 
            <span class="prob-low">Red <30%</span>
        </p>
    </div>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML predictions table generated: {output_file}")

def main():
    csv_file = 'hockey_games.csv'
    
    # Filter games for E.H.L., Moins de 15 ans, B
    games = load_and_filter_games(csv_file)
    
    # Calculate team ratings based on historical performance
    print("\nCalculating team ratings from historical games...")
    team_ratings, league_avg_goals = calculate_team_ratings(games)
    
    print(f"\nLeague average goals per game: {league_avg_goals:.2f}")
    print("\nTeam Ratings:")
    print(f"{'Team':<25} {'Strength':<10} {'Off':<8} {'Def':<8} {'Win%':<8} {'GP':<5}")
    print("-" * 75)
    for team in sorted(team_ratings.keys()):
        r = team_ratings[team]
        print(f"{team:<25} {r['strength']:>8.3f}  {r['offensive']:>6.3f}  {r['defensive']:>6.3f}  {r['win_pct']*100:>6.1f}%  {r['games_played']:>4}")
    
    # Predict upcoming games
    predictions = predict_upcoming_games(games, team_ratings, league_avg_goals)
    
    # Display predictions
    display_predictions(predictions)
    
    # Save to CSV
    save_predictions_csv(predictions)
    
    # Generate HTML table
    generate_predictions_html(predictions, team_ratings)

if __name__ == '__main__':
    main()
