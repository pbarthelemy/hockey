#!/usr/bin/env python3
"""
Parameter Optimization Script
Tests different combinations of ELO parameters to maximize prediction accuracy
"""

import csv
import math
from datetime import datetime
from itertools import product

# Parameter ranges to test
K_FACTORS = [15, 20, 25, 30, 35, 40]
HOME_ADVANTAGES = [50, 75, 100, 125, 150]
PYTHAGOREAN_EXPONENTS = [1.8, 2.0, 2.2, 2.37, 2.5]
ELO_WEIGHTS = [0.4, 0.5, 0.6, 0.7, 0.8]

INITIAL_ELO = 1500

def read_games():
    """Read games from CSV file"""
    games = []
    with open('csv/hockey_games.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            games.append(row)
    return games

def filter_games(games, tournament='E.H.L.', division='Moins de 15 ans', level='B'):
    """Filter games by tournament, division, and level"""
    return [g for g in games 
            if g['tournament_name'] == tournament 
            and g['division_name'] == division 
            and g['level_name'] == level
            and g['status'] == 'Completed'
            and g['home_score'] and g['away_score']]

def calculate_expected_score(elo_a, elo_b):
    """Calculate expected score for player A"""
    return 1 / (1 + math.pow(10, (elo_b - elo_a) / 400))

def update_elo(winner_elo, loser_elo, margin, k_factor):
    """Update ELO ratings after a game"""
    expected_winner = calculate_expected_score(winner_elo, loser_elo)
    expected_loser = 1 - expected_winner
    
    margin_multiplier = math.log(max(margin, 1) + 1)
    
    new_winner_elo = winner_elo + k_factor * margin_multiplier * (1 - expected_winner)
    new_loser_elo = loser_elo + k_factor * margin_multiplier * (0 - expected_loser)
    
    return new_winner_elo, new_loser_elo

def update_elo_tie(elo_a, elo_b, k_factor):
    """Update ELO ratings for a tie"""
    expected_a = calculate_expected_score(elo_a, elo_b)
    expected_b = 1 - expected_a
    
    new_elo_a = elo_a + k_factor * (0.5 - expected_a)
    new_elo_b = elo_b + k_factor * (0.5 - expected_b)
    
    return new_elo_a, new_elo_b

def validate_with_params(games, k_factor, home_advantage, pyth_exp, elo_weight):
    """Validate predictions with specific parameters"""
    completed_games = sorted(games, key=lambda g: g['date'])
    
    correct = 0
    total = 0
    
    for i in range(len(completed_games)):
        test_game = completed_games[i]
        training_games = completed_games[:i]
        
        if len(training_games) < 2:
            continue
        
        # Build ELO ratings from training data
        team_elos = {}
        teams = set()
        
        for game in training_games:
            teams.add(game['home_team'])
            teams.add(game['away_team'])
        
        for team in teams:
            team_elos[team] = {
                'elo': INITIAL_ELO,
                'games': 0,
                'points_for': 0,
                'points_against': 0
            }
        
        # Process training games
        for game in training_games:
            home = game['home_team']
            away = game['away_team']
            home_score = int(game['home_score'])
            away_score = int(game['away_score'])
            
            home_elo = team_elos[home]['elo'] + home_advantage
            away_elo = team_elos[away]['elo']
            
            team_elos[home]['points_for'] += home_score
            team_elos[home]['points_against'] += away_score
            team_elos[home]['games'] += 1
            
            team_elos[away]['points_for'] += away_score
            team_elos[away]['points_against'] += home_score
            team_elos[away]['games'] += 1
            
            if home_score > away_score:
                margin = home_score - away_score
                new_home, new_away = update_elo(home_elo, away_elo, margin, k_factor)
                team_elos[home]['elo'] = new_home - home_advantage
                team_elos[away]['elo'] = new_away
            elif away_score > home_score:
                margin = away_score - home_score
                new_away, new_home = update_elo(away_elo, home_elo, margin, k_factor)
                team_elos[away]['elo'] = new_away
                team_elos[home]['elo'] = new_home - home_advantage
            else:
                new_home, new_away = update_elo_tie(home_elo, away_elo, k_factor)
                team_elos[home]['elo'] = new_home - home_advantage
                team_elos[away]['elo'] = new_away
        
        # Calculate Pythagorean expectations
        for team in team_elos:
            stats = team_elos[team]
            if stats['games'] > 0:
                pf_squared = math.pow(stats['points_for'], pyth_exp)
                pa_squared = math.pow(stats['points_against'], pyth_exp)
                stats['pyth'] = pf_squared / (pf_squared + pa_squared) if (pf_squared + pa_squared) > 0 else 0.5
            else:
                stats['pyth'] = 0.5
        
        # Make prediction
        home = test_game['home_team']
        away = test_game['away_team']
        
        if home not in team_elos or away not in team_elos:
            continue
        
        home_elo = team_elos[home]['elo'] + home_advantage
        away_elo = team_elos[away]['elo']
        
        elo_home_win_prob = calculate_expected_score(home_elo, away_elo)
        
        home_pyth = team_elos[home]['pyth']
        away_pyth = team_elos[away]['pyth']
        pyth_home_win_prob = home_pyth / (home_pyth + away_pyth) if (home_pyth + away_pyth) > 0 else 0.5
        
        combined_home_win_prob = elo_home_win_prob * elo_weight + pyth_home_win_prob * (1 - elo_weight)
        
        predicted_winner = home if combined_home_win_prob > 0.5 else away
        
        # Check actual result
        home_score = int(test_game['home_score'])
        away_score = int(test_game['away_score'])
        
        if home_score > away_score:
            actual_winner = home
        elif away_score > home_score:
            actual_winner = away
        else:
            actual_winner = 'Tie'
        
        if predicted_winner == actual_winner and actual_winner != 'Tie':
            correct += 1
        total += 1
    
    accuracy = (correct / total * 100) if total > 0 else 0
    return accuracy, correct, total

def optimize_parameters():
    """Find optimal parameter combinations"""
    print("Loading games...")
    all_games = read_games()
    games = filter_games(all_games)
    
    print(f"Found {len(games)} completed games for E.H.L. / Moins de 15 ans / B")
    print(f"\nTesting {len(K_FACTORS)} × {len(HOME_ADVANTAGES)} × {len(PYTHAGOREAN_EXPONENTS)} × {len(ELO_WEIGHTS)} = {len(K_FACTORS) * len(HOME_ADVANTAGES) * len(PYTHAGOREAN_EXPONENTS) * len(ELO_WEIGHTS)} combinations...\n")
    
    best_accuracy = 0
    best_params = None
    results = []
    
    total_combinations = len(K_FACTORS) * len(HOME_ADVANTAGES) * len(PYTHAGOREAN_EXPONENTS) * len(ELO_WEIGHTS)
    current = 0
    
    for k, home_adv, pyth_exp, elo_weight in product(K_FACTORS, HOME_ADVANTAGES, PYTHAGOREAN_EXPONENTS, ELO_WEIGHTS):
        current += 1
        accuracy, correct, total = validate_with_params(games, k, home_adv, pyth_exp, elo_weight)
        
        results.append({
            'k_factor': k,
            'home_advantage': home_adv,
            'pyth_exponent': pyth_exp,
            'elo_weight': elo_weight,
            'accuracy': accuracy,
            'correct': correct,
            'total': total
        })
        
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_params = (k, home_adv, pyth_exp, elo_weight)
            print(f"[{current}/{total_combinations}] NEW BEST: K={k}, Home={home_adv}, Pyth={pyth_exp}, EloWeight={elo_weight:.1f} → {accuracy:.1f}% ({correct}/{total})")
        elif current % 50 == 0:
            print(f"[{current}/{total_combinations}] Progress... Current best: {best_accuracy:.1f}%")
    
    # Sort results by accuracy
    results.sort(key=lambda x: x['accuracy'], reverse=True)
    
    # Save results to CSV
    with open('csv/optimization_results.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['k_factor', 'home_advantage', 'pyth_exponent', 'elo_weight', 'accuracy', 'correct', 'total'])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n{'='*80}")
    print("OPTIMIZATION COMPLETE")
    print(f"{'='*80}")
    print(f"\nBest Parameters:")
    print(f"  K_FACTOR = {best_params[0]}")
    print(f"  HOME_ADVANTAGE = {best_params[1]}")
    print(f"  PYTHAGOREAN_EXPONENT = {best_params[2]}")
    print(f"  ELO_WEIGHT = {best_params[3]:.1f} (Pythagorean weight = {1-best_params[3]:.1f})")
    print(f"\nAccuracy: {best_accuracy:.1f}%")
    print(f"\nTop 10 parameter combinations:")
    for i, result in enumerate(results[:10], 1):
        print(f"  {i}. K={result['k_factor']:2d}, Home={result['home_advantage']:3d}, Pyth={result['pyth_exponent']:.2f}, EloW={result['elo_weight']:.1f} → {result['accuracy']:.1f}%")
    
    print(f"\nFull results saved to: csv/optimization_results.csv")
    
    return best_params, best_accuracy

if __name__ == '__main__':
    optimize_parameters()
