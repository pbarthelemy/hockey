#!/usr/bin/env python3
"""
Scrape hockey game schedules from scoresheets.ca
"""

import requests
import csv
import json
from datetime import datetime

def scrape_games(tournament_id, division_id, level_id):
    """Scrape all games from the schedule using the API"""
    
    # API endpoint
    api_url = "https://scoresheets.ca/classes/TournamentPublicData.php"
    
    # Parameters for the API request
    payload = {
        'getTournamentGameList': 'TournamentPublicData',
        'filterBy': 'division',
        'filterRange': 'all',
        'tournamentId': tournament_id,
        'divisionId': division_id,
        'levelId': level_id,
        'sortingOrder': 'ascending'
    }
    
    # Make the POST request
    response = requests.post(api_url, data=payload)
    response.raise_for_status()
    
    data = response.json()
    
    # Save the raw response to a JSON file
    with open('response_payload.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Response payload saved to response_payload.json")
    
    games = []
    
    if not data.get('resp') or not data.get('data'):
        print("No games found in response")
        return games
    
    for game in data['data']:
        game_data = {}
        
        # Game ID
        game_number = game.get('gameNumber', '')
        game_data['game_id'] = f"#{game_number}" if game_number else ''
        
        # Tournament, Division, Level
        game_data['tournament_name'] = game.get('tournamentName', '')
        game_data['division_name'] = game.get('divisionName', '')
        game_data['level_name'] = game.get('levelName', '')
        
        # Date and time (without seconds)
        game_date = game.get('game_date', '')
        start_time = game.get('startTime', '')
        if game_date and start_time:
            # Remove seconds from time (HH:MM:SS -> HH:MM)
            time_without_seconds = ':'.join(start_time.split(':')[:2])
            game_data['date'] = f"{game_date} {time_without_seconds}"
        elif game_date:
            game_data['date'] = game_date
        else:
            game_data['date'] = ''
        
        # Location
        location_name = game.get('locationName', '')
        address1 = game.get('address1', '')
        complete_address = game.get('complete_address', '')
        
        game_data['location_name'] = location_name
        
        if location_name:
            if address1 or complete_address:
                game_data['location'] = f"{location_name}, {address1 if address1 else complete_address}"
            else:
                game_data['location'] = location_name
        else:
            game_data['location'] = ''
        
        # Teams
        game_data['home_team'] = game.get('homeTeamName', '').strip()
        game_data['away_team'] = game.get('awayTeamName', '').strip()
        
        # Scores - only for completed games
        status = game.get('status', '')
        game_data['status'] = status
        
        if status.lower() in ['completed', 'final']:
            # Game is finished, extract scores
            home_score = game.get('homeTotalGoals', '')
            away_score = game.get('awayTotalGoals', '')
            
            game_data['home_score'] = str(home_score) if home_score else ''
            game_data['away_score'] = str(away_score) if away_score else ''
        else:
            # Game is upcoming or in progress, leave scores blank
            game_data['home_score'] = ''
            game_data['away_score'] = ''
        
        games.append(game_data)
    
    return games

def save_to_csv(games, filename='hockey_games.csv'):
    """Save games to CSV file"""
    
    if not games:
        print("No games found")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['game_id', 'tournament_name', 'division_name', 'level_name', 'date', 'location_name', 'location', 'home_team', 'away_team', 'home_score', 'away_score', 'status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for game in games:
            writer.writerow({
                'game_id': game.get('game_id', ''),
                'tournament_name': game.get('tournament_name', ''),
                'division_name': game.get('division_name', ''),
                'level_name': game.get('level_name', ''),
                'date': game.get('date', ''),
                'location_name': game.get('location_name', ''),
                'location': game.get('location', ''),
                'home_team': game.get('home_team', ''),
                'away_team': game.get('away_team', ''),
                'home_score': game.get('home_score', ''),
                'away_score': game.get('away_score', ''),
                'status': game.get('status', '')
            })
    
    print(f"Saved {len(games)} games to {filename}")

if __name__ == '__main__':
    # Parameters from the URL
    tournament_id = 17
    division_id = 45
    level_id = 6
    
    print("Scraping games from schedule...")
    games = scrape_games(tournament_id, division_id, level_id)
    
    print(f"Found {len(games)} games")
    
    if games:
        save_to_csv(games, 'hockey_games.csv')
        print("Done!")
    else:
        print("No games to save")
