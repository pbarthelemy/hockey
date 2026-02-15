#!/usr/bin/env python3
"""
Analyze hockey games from CSV file
"""

import csv

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

def build_match_matrix(games):
    """Build a match matrix showing results between teams"""
    
    # Get all unique teams
    teams = set()
    for game in games:
        if game['home_team']:
            teams.add(game['home_team'])
        if game['away_team']:
            teams.add(game['away_team'])
    
    teams = sorted(teams)
    
    # Build the matrix - dict of dict of lists
    # matrix[home_team][away_team] = [result1, result2, ...]
    matrix = {team: {other_team: [] for other_team in teams} for team in teams}
    
    for game in games:
        home = game['home_team']
        away = game['away_team']
        
        if not home or not away:
            continue
        
        # Include completed games with scores
        if game['status'] == 'Completed' and game['home_score'] and game['away_score']:
            score = f"{game['home_score']}-{game['away_score']}"
            matrix[home][away].append(score)
        # Include planned/upcoming games with placeholder
        elif game['status'] in ['Initialized', 'Setup', 'In Progress']:
            matrix[home][away].append('??-??')
    
    return teams, matrix

def build_combined_matrix(games):
    """Build a combined matrix showing all results between teams (home/away combined)"""
    
    # Get all unique teams
    teams = set()
    for game in games:
        if game['home_team']:
            teams.add(game['home_team'])
        if game['away_team']:
            teams.add(game['away_team'])
    
    teams = sorted(teams)
    
    # Build the matrix - dict of dict of lists
    # matrix[team1][team2] = [(team1_score-team2_score, location), ...]
    # We'll store results from the perspective of team1
    matrix = {}
    for i, team1 in enumerate(teams):
        matrix[team1] = {}
        for j, team2 in enumerate(teams):
            if i < j:  # Only fill upper triangle
                matrix[team1][team2] = []
    
    for game in games:
        home = game['home_team']
        away = game['away_team']
        
        if not home or not away or home == away:
            continue
        
        # Determine which team comes first in sorted order
        team1, team2 = (home, away) if home < away else (away, home)
        
        # Include completed games with scores
        if game['status'] == 'Completed' and game['home_score'] and game['away_score']:
            # Store score from team1's perspective
            if home == team1:
                score = f"{game['home_score']}-{game['away_score']}"
            else:
                score = f"{game['away_score']}-{game['home_score']}"
            matrix[team1][team2].append(score)
        # Include planned/upcoming games with placeholder
        elif game['status'] in ['Initialized', 'Setup', 'In Progress']:
            matrix[team1][team2].append('??-??')
    
    return teams, matrix

def build_team_results_matrix(games):
    """Build a matrix where each team's row shows all their games against opponents"""
    
    # Get all unique teams
    teams = set()
    for game in games:
        if game['home_team']:
            teams.add(game['home_team'])
        if game['away_team']:
            teams.add(game['away_team'])
    
    teams = sorted(teams)
    
    # Build the matrix - dict of dict of lists
    # matrix[team][opponent] = [(team_score-opponent_score), ...]
    # Store results from each team's perspective
    matrix = {team: {other_team: [] for other_team in teams} for team in teams}
    
    # Track statistics for each team
    team_stats = {team: {'wins': 0, 'losses': 0, 'ties': 0, 'to_play': 0} for team in teams}
    
    for game in games:
        home = game['home_team']
        away = game['away_team']
        
        if not home or not away:
            continue
        
        # Include completed games with scores
        if game['status'] == 'Completed' and game['home_score'] and game['away_score']:
            # Store from home team's perspective
            home_score_str = f"{game['home_score']}-{game['away_score']}"
            matrix[home][away].append(home_score_str)
            
            # Store from away team's perspective (reverse score)
            away_score_str = f"{game['away_score']}-{game['home_score']}"
            matrix[away][home].append(away_score_str)
            
            # Update statistics
            home_score_int = int(game['home_score'])
            away_score_int = int(game['away_score'])
            
            if home_score_int > away_score_int:
                team_stats[home]['wins'] += 1
                team_stats[away]['losses'] += 1
            elif home_score_int < away_score_int:
                team_stats[home]['losses'] += 1
                team_stats[away]['wins'] += 1
            else:
                team_stats[home]['ties'] += 1
                team_stats[away]['ties'] += 1
            
        # Include planned/upcoming games with placeholder
        elif game['status'] in ['Initialized', 'Setup', 'In Progress']:
            matrix[home][away].append('??-??')
            matrix[away][home].append('??-??')
            
            # Update to_play count
            team_stats[home]['to_play'] += 1
            team_stats[away]['to_play'] += 1
    
    return teams, matrix, team_stats

def generate_team_results_table(teams, matrix, team_stats, output_file='recap_table_all_games.html'):
    """Generate HTML table with all games for each team"""
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hockey Games Recap - E.H.L. Moins de 15 ans B (All Games)</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        table {
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: center;
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
        tbody th {
            background-color: #34495e;
            color: white;
            font-weight: bold;
            text-align: left;
        }
        td {
            min-width: 60px;
        }
        td:empty {
            background-color: #ecf0f1;
        }
        .header-cell {
            writing-mode: vertical-rl;
            transform: rotate(180deg);
            white-space: nowrap;
            min-width: 40px;
        }
        .score-list {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .score-item {
            font-size: 0.9em;
        }
        .placeholder {
            color: #7f8c8d;
            font-style: italic;
        }
        .team-stats {
            font-size: 0.75em;
            font-weight: normal;
            color: #bdc3c7;
            margin-top: 3px;
        }
    </style>
</head>
<body>
    <h1>E.H.L. - Moins de 15 ans - B - All Games Results</h1>
    <p>Results showing all games for each team (home and away combined)</p>
    <p><strong>Score format:</strong> The score always shows the row team's score first, then the opponent's score.</p>
    <p>Example: If row "BULLDOGS VERDUN" vs column "DEVILS M.R.O." shows "3-2", it means BULLDOGS VERDUN scored 3 and DEVILS M.R.O. scored 2.</p>
    <table>
        <thead>
            <tr>
                <th>Team \\ Opponent</th>
"""
    
    # Column headers (opponents)
    for team in teams:
        html += f'                <th><div class="header-cell">{team}</div></th>\n'
    
    html += """            </tr>
        </thead>
        <tbody>
"""
    
    # Rows (teams)
    for team in teams:
        html += f'            <tr>\n'
        stats = team_stats[team]
        html += f'                <th>{team}<div class="team-stats">W:{stats["wins"]} L:{stats["losses"]} T:{stats["ties"]} TBP:{stats["to_play"]}</div></th>\n'
        
        # Cells (results against opponents)
        for opponent in teams:
            if team == opponent:
                html += '                <td style="background-color: #95a5a6;"></td>\n'
            else:
                results = matrix[team].get(opponent, [])
                if results:
                    if len(results) == 1:
                        result_class = ' class="placeholder"' if results[0] == '??-??' else ''
                        html += f'                <td{result_class}>{results[0]}</td>\n'
                    else:
                        html += '                <td><div class="score-list">\n'
                        for result in results:
                            result_class = ' class="score-item placeholder"' if result == '??-??' else ' class="score-item"'
                            html += f'                    <div{result_class}>{result}</div>\n'
                        html += '                </div></td>\n'
                else:
                    html += '                <td></td>\n'
        
        html += '            </tr>\n'
    
    html += """        </tbody>
    </table>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML all games table generated: {output_file}")

def generate_html_table(teams, matrix, output_file='recap_table.html'):
    """Generate HTML table with match results"""
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hockey Games Recap - E.H.L. Moins de 15 ans B</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        table {
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: center;
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
        tbody th {
            background-color: #34495e;
            color: white;
            font-weight: bold;
            text-align: left;
        }
        td {
            min-width: 60px;
        }
        td:empty {
            background-color: #ecf0f1;
        }
        .header-cell {
            writing-mode: vertical-rl;
            transform: rotate(180deg);
            white-space: nowrap;
            min-width: 40px;
        }
        .score-list {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .score-item {
            font-size: 0.9em;
        }
        .placeholder {
            color: #7f8c8d;
            font-style: italic;
        }
    </style>
</head>
<body>
    <h1>E.H.L. - Moins de 15 ans - B - Match Results</h1>
    <p>Results matrix showing Home Team (rows) vs Away Team (columns)</p>
    <table>
        <thead>
            <tr>
                <th>Home \\ Away</th>
"""
    
    # Column headers (away teams)
    for team in teams:
        html += f'                <th><div class="header-cell">{team}</div></th>\n'
    
    html += """            </tr>
        </thead>
        <tbody>
"""
    
    # Rows (home teams)
    for home_team in teams:
        html += f'            <tr>\n'
        html += f'                <th>{home_team}</th>\n'
        
        # Cells (results)
        for away_team in teams:
            if home_team == away_team:
                html += '                <td style="background-color: #95a5a6;"></td>\n'
            else:
                results = matrix[home_team].get(away_team, [])
                if results:
                    if len(results) == 1:
                        result_class = ' class="placeholder"' if results[0] == '??-??' else ''
                        html += f'                <td{result_class}>{results[0]}</td>\n'
                    else:
                        html += '                <td><div class="score-list">\n'
                        for result in results:
                            result_class = ' class="score-item placeholder"' if result == '??-??' else ' class="score-item"'
                            html += f'                    <div{result_class}>{result}</div>\n'
                        html += '                </div></td>\n'
                else:
                    html += '                <td></td>\n'
        
        html += '            </tr>\n'
    
    html += """        </tbody>
    </table>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\nHTML table generated: {output_file}")

def main():
    csv_file = 'hockey_games.csv'
    
    # Filter games for E.H.L., Moins de 15 ans, B
    games = load_and_filter_games(csv_file)
    
    # Display basic statistics
    print("\n" + "="*60)
    print("GAME STATISTICS")
    print("="*60)
    
    # Count games by status
    status_counts = {}
    for game in games:
        status = game['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("\nGames by status:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    
    # Count completed games
    completed_games = [g for g in games if g['status'] == 'Completed']
    print(f"\nTotal completed games: {len(completed_games)}")
    
    # Count upcoming games
    upcoming_games = [g for g in games if g['status'] != 'Completed']
    print(f"Total upcoming/scheduled games: {len(upcoming_games)}")
    
    # Build match matrix
    teams, matrix = build_match_matrix(games)
    print(f"\nTotal teams: {len(teams)}")
    
    # Generate HTML table (home vs away)
    generate_html_table(teams, matrix)
    
    # Build team results matrix (all games)
    teams_all, matrix_all, team_stats = build_team_results_matrix(games)
    
    # Generate HTML table for all games
    generate_team_results_table(teams_all, matrix_all, team_stats)

if __name__ == '__main__':
    main()
