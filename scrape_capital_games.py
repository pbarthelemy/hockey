#!/usr/bin/env python3
"""Standalone Capital HLC scraper wrapper."""

from scrape_games import scrape_games, save_to_csv, DEFAULT_CAPITAL_STANDINGS_URL


if __name__ == '__main__':
    games = scrape_games(source='capitalhlc', standings_url=DEFAULT_CAPITAL_STANDINGS_URL)
    print(f"Found {len(games)} games")
    if games:
        save_to_csv(games, 'csv/hockey_games.csv')
        print('Done!')
    else:
        print('No games to save')
