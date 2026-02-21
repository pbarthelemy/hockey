#!/usr/bin/env python3
"""
Scrape hockey game schedules from multiple sources.

Supported sources:
- scoresheets.ca (API)
- capitalhlc.com (schedule page linked from standings URL)
"""

import requests
import csv
import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime


DEFAULT_CAPITAL_STANDINGS_URL = (
    'https://www.capitalhlc.com/en/stats/standing.html?season=2750&subSeason=4834&category=6557'
)


def _normalize_whitespace(value):
    return ' '.join(str(value or '').split())


def _pick_first(obj, keys):
    for key in keys:
        value = obj.get(key)
        if value not in (None, ''):
            return str(value)
    return ''


def _is_numeric(value):
    if value in (None, ''):
        return False
    try:
        float(str(value))
        return True
    except ValueError:
        return False


def _normalize_status(raw_status, has_numeric_score=False):
    status = _normalize_whitespace(raw_status).lower()
    if not status and has_numeric_score:
        return 'Completed'

    if any(token in status for token in ['final', 'completed', 'termin']):
        return 'Completed'
    if any(token in status for token in ['live', 'progress', 'period']):
        return 'In Progress'
    if any(token in status for token in ['pre-game', 'scheduled', 'setup', 'init']):
        return 'Setup'

    return 'Completed' if has_numeric_score else 'Setup'


def _split_division_level(league):
    league = _normalize_whitespace(league)
    if not league:
        return '', ''

    parts = league.split()
    if len(parts) >= 2:
        return ' '.join(parts[:-1]), parts[-1]
    return league, ''


def _normalize_scoresheets_game(game):
    game_number = _pick_first(game, ['gameNumber', 'game_number', 'gameId', 'id'])
    game_date = _pick_first(game, ['game_date', 'gameDate', 'date'])
    start_time = _pick_first(game, ['startTime', 'start_time', 'time'])
    location_name = _pick_first(game, ['locationName', 'location_name', 'arenaName'])
    address1 = _pick_first(game, ['address1', 'address', 'addressLine1'])
    complete_address = _pick_first(game, ['complete_address', 'completeAddress'])

    raw_status = _pick_first(game, ['status', 'gameStatus', 'state'])
    home_score_raw = _pick_first(game, ['homeTotalGoals', 'home_score', 'homeGoals'])
    away_score_raw = _pick_first(game, ['awayTotalGoals', 'away_score', 'awayGoals'])
    has_numeric_score = _is_numeric(home_score_raw) and _is_numeric(away_score_raw)
    status = _normalize_status(raw_status, has_numeric_score)

    if game_date and start_time:
        time_without_seconds = ':'.join(start_time.split(':')[:2])
        date_value = f"{game_date} {time_without_seconds}"
    else:
        date_value = game_date

    if location_name:
        location = f"{location_name}, {address1 or complete_address}" if (address1 or complete_address) else location_name
    else:
        location = ''

    return {
        'source': 'scoresheets',
        'game_id': f"#{game_number}" if game_number else '',
        'tournament_name': _pick_first(game, ['tournamentName', 'tournament_name', 'tournament']),
        'division_name': _pick_first(game, ['divisionName', 'division_name', 'division']),
        'level_name': _pick_first(game, ['levelName', 'level_name', 'level']),
        'date': date_value,
        'location_name': location_name,
        'location': location,
        'home_team': _pick_first(game, ['homeTeamName', 'home_team', 'homeTeam']).strip(),
        'away_team': _pick_first(game, ['awayTeamName', 'away_team', 'awayTeam']).strip(),
        'home_score': str(home_score_raw) if status == 'Completed' and has_numeric_score else '',
        'away_score': str(away_score_raw) if status == 'Completed' and has_numeric_score else '',
        'status': status,
    }


def _build_capital_schedule_url(standings_url):
    if not standings_url:
        standings_url = DEFAULT_CAPITAL_STANDINGS_URL
    return standings_url.replace('/standing.html', '/schedule.html')


def _extract_capital_game_id(href):
    if not href:
        return ''
    parsed = urlparse(href)
    return parse_qs(parsed.query).get('game', [''])[0]


def _split_top_level_args(text):
    args = []
    current = []
    quote = None
    depth_braces = depth_brackets = depth_parens = 0
    i = 0

    while i < len(text):
        ch = text[i]

        if quote:
            current.append(ch)
            if ch == '\\' and i + 1 < len(text):
                i += 1
                current.append(text[i])
            elif ch == quote:
                quote = None
            i += 1
            continue

        if ch in ('"', "'"):
            quote = ch
            current.append(ch)
            i += 1
            continue

        if ch == '{':
            depth_braces += 1
        elif ch == '}':
            depth_braces -= 1
        elif ch == '[':
            depth_brackets += 1
        elif ch == ']':
            depth_brackets -= 1
        elif ch == '(':
            depth_parens += 1
        elif ch == ')':
            depth_parens -= 1

        if ch == ',' and depth_braces == depth_brackets == depth_parens == 0:
            args.append(''.join(current))
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = ''.join(current).strip()
    if tail:
        args.append(''.join(current))
    return args


def _extract_capital_embedded_data(html):
    marker = 'PS.component.statistic_schedule_sd('
    start = html.find(marker)
    if start == -1:
        return None

    i = start + len(marker)
    depth = 1
    quote = None

    while i < len(html) and depth > 0:
        ch = html[i]

        if quote:
            if ch == '\\':
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue

        if ch in ('"', "'"):
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1

        i += 1

    if depth != 0:
        return None

    args_text = html[start + len(marker): i - 1]
    args = _split_top_level_args(args_text)
    if len(args) < 5:
        return None

    try:
        return {
            'data': json.loads(args[3].strip()),
            'liveBarns': json.loads(args[4].strip())
        }
    except json.JSONDecodeError:
        return None


def _format_timestamp(ts_seconds):
    try:
        dt = datetime.fromtimestamp(int(str(ts_seconds)))
        return dt.strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return ''


def _map_capital_embedded_games(embedded):
    data = embedded.get('data', {})
    events_info = data.get('eventsInfo', {}) or {}
    games_info = data.get('gamesInfo', {}) or {}
    locations_info = data.get('locationsInfo', {}) or {}

    games = []

    for timestamp, events in events_info.items():
        if not isinstance(events, list):
            continue

        for event in events:
            if str(event.get('eventTypeId', '')) != '3':
                continue

            game_id = str(event.get('gameId', ''))
            game_info = games_info.get(game_id, {})
            location_info = locations_info.get(str(event.get('locationId', '')), {})

            home_team = _normalize_whitespace(game_info.get('localTeamName', ''))
            away_team = _normalize_whitespace(game_info.get('awayTeamName', ''))
            if not home_team or not away_team:
                continue

            home_score_raw = game_info.get('gameLocalScore')
            away_score_raw = game_info.get('gameVisitorScore')
            has_numeric_score = _is_numeric(home_score_raw) and _is_numeric(away_score_raw)

            game_is_played = str(game_info.get('gameIsPlayed', '')) == '1'
            game_is_live = str(game_info.get('gameIsLive', '')) == '1'
            status = _normalize_status('final' if game_is_played else ('live' if game_is_live else 'scheduled'), has_numeric_score)

            division_name, level_name = _split_division_level(game_info.get('gameCategoryName', ''))

            game_number = game_info.get('gameNum') or game_id
            location_name = _normalize_whitespace(location_info.get('locationName', ''))

            games.append({
                'source': 'capitalhlc',
                'game_id': f"#{game_number}" if game_number else '',
                'tournament_name': _normalize_whitespace(game_info.get('OrganisationNameLoc') or game_info.get('OrganisationNameVis') or 'Capital HLC'),
                'division_name': division_name,
                'level_name': level_name,
                'date': _format_timestamp(timestamp),
                'location_name': location_name,
                'location': location_name,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': str(home_score_raw) if status == 'Completed' and has_numeric_score else '',
                'away_score': str(away_score_raw) if status == 'Completed' and has_numeric_score else '',
                'status': status,
            })

    return sorted(games, key=lambda g: g.get('date', ''))


def scrape_games_scoresheets(tournament_id, division_id, level_id):
    """Scrape all games from scoresheets.ca API."""

    api_url = "https://scoresheets.ca/classes/TournamentPublicData.php"
    payload = {
        'getTournamentGameList': 'TournamentPublicData',
        'filterBy': 'division',
        'filterRange': 'all',
        'tournamentId': tournament_id,
        'divisionId': division_id,
        'levelId': level_id,
        'sortingOrder': 'ascending'
    }

    response = requests.post(api_url, data=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    with open('csv/response_payload.json', 'w', encoding='utf-8') as f:
        json.dump({'source': 'scoresheets', 'rawData': data}, f, indent=2, ensure_ascii=False)

    games = []
    if data.get('resp') and data.get('data'):
        games = [_normalize_scoresheets_game(game) for game in data['data']]

    return games


def scrape_games_capital(standings_url=DEFAULT_CAPITAL_STANDINGS_URL):
    """Scrape all games from capitalhlc.com schedule page."""

    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Please install beautifulsoup4: pip install beautifulsoup4") from exc

    schedule_url = _build_capital_schedule_url(standings_url)
    response = requests.get(
        schedule_url,
        timeout=30,
        headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
    )
    response.raise_for_status()
    html = response.text

    with open('csv/response_payload.json', 'w', encoding='utf-8') as f:
        json.dump({'source': 'capitalhlc', 'scheduleUrl': schedule_url, 'htmlLength': len(html)}, f, indent=2, ensure_ascii=False)

    embedded = _extract_capital_embedded_data(html)
    if embedded:
        return _map_capital_embedded_games(embedded)

    soup = BeautifulSoup(html, 'html.parser')
    games = []

    for match in soup.select('li.match_wrapper .match'):
        teams = match.select('.team_wrapper')
        if len(teams) < 2:
            continue

        game_link = match.select_one('a.game_link')
        status_text = _normalize_whitespace(game_link.get_text(' ', strip=True) if game_link else '')
        href = game_link.get('href', '') if game_link else ''

        home_team = _normalize_whitespace(teams[0].select_one('.team_name').get_text(' ', strip=True) if teams[0].select_one('.team_name') else '')
        away_team = _normalize_whitespace(teams[1].select_one('.team_name').get_text(' ', strip=True) if teams[1].select_one('.team_name') else '')
        home_score_raw = _normalize_whitespace(teams[0].select_one('.score').get_text(' ', strip=True) if teams[0].select_one('.score') else '')
        away_score_raw = _normalize_whitespace(teams[1].select_one('.score').get_text(' ', strip=True) if teams[1].select_one('.score') else '')

        if not home_team or not away_team:
            continue

        info = match.select_one('.info')
        date_iso = info.get('data-date', '') if info else ''
        date_time_attr = info.get('data-date-time', '') if info else ''

        time_text = _normalize_whitespace(match.select_one('.match_number').get_text(' ', strip=True) if match.select_one('.match_number') else '')
        date_value = f"{date_iso} {time_text}".strip() if date_iso else date_time_attr

        league = _normalize_whitespace(match.select_one('.league').get_text(' ', strip=True) if match.select_one('.league') else '')
        division_name, level_name = _split_division_level(league)

        location_name = _normalize_whitespace(match.select_one('a.location').get_text(' ', strip=True) if match.select_one('a.location') else '')
        game_id = _extract_capital_game_id(href)
        has_numeric_score = _is_numeric(home_score_raw) and _is_numeric(away_score_raw)
        status = _normalize_status(status_text, has_numeric_score)

        games.append({
            'source': 'capitalhlc',
            'game_id': f"#{game_id}" if game_id else '',
            'tournament_name': 'Capital HLC',
            'division_name': division_name,
            'level_name': level_name,
            'date': date_value,
            'location_name': location_name,
            'location': location_name,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score_raw if status == 'Completed' and has_numeric_score else '',
            'away_score': away_score_raw if status == 'Completed' and has_numeric_score else '',
            'status': status,
        })

    return games


def scrape_games(source='scoresheets', tournament_id=17, division_id=45, level_id=6, standings_url=DEFAULT_CAPITAL_STANDINGS_URL):
    """Scrape games from selected source."""
    if source == 'capitalhlc':
        return scrape_games_capital(standings_url=standings_url)
    return scrape_games_scoresheets(tournament_id, division_id, level_id)

def save_to_csv(games, filename='csv/hockey_games.csv'):
    """Save games to CSV file"""
    
    if not games:
        print("No games found")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['source', 'game_id', 'tournament_name', 'division_name', 'level_name', 'date', 'location_name', 'location', 'home_team', 'away_team', 'home_score', 'away_score', 'status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for game in games:
            writer.writerow({
                'source': game.get('source', ''),
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
    # Scoresheets defaults
    source = 'scoresheets'
    tournament_id = 17
    division_id = 45
    level_id = 6
    standings_url = DEFAULT_CAPITAL_STANDINGS_URL
    
    print(f"Scraping games from source: {source}...")
    games = scrape_games(
        source=source,
        tournament_id=tournament_id,
        division_id=division_id,
        level_id=level_id,
        standings_url=standings_url,
    )
    
    print(f"Found {len(games)} games")
    
    if games:
        save_to_csv(games, 'csv/hockey_games.csv')
        print("Done!")
    else:
        print("No games to save")
