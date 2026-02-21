#!/usr/bin/env node

/**
 * Standalone Capital HLC scraper (Node.js)
 *
 * Normalized output file: csv/hockey_games.csv
 * Raw metadata file: csv/response_payload.json
 */

const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs').promises;

const DEFAULT_STANDINGS_URL =
    'https://www.capitalhlc.com/en/stats/standing.html?season=2750&subSeason=4834&category=6557';

function normalizeWhitespace(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
}

function isNumeric(value) {
    if (value === null || value === undefined || value === '') return false;
    return !Number.isNaN(Number(value));
}

function normalizeStatus(rawStatus, hasNumericScore = false) {
    const status = normalizeWhitespace(rawStatus).toLowerCase();
    if (!status && hasNumericScore) return 'Completed';

    if (status.includes('final') || status.includes('completed') || status.includes('termin')) return 'Completed';
    if (status.includes('live') || status.includes('progress') || status.includes('period')) return 'In Progress';
    if (status.includes('pre-game') || status.includes('scheduled') || status.includes('setup') || status.includes('init')) return 'Setup';

    return hasNumericScore ? 'Completed' : 'Setup';
}

function splitDivisionAndLevel(league) {
    const normalized = normalizeWhitespace(league);
    const match = normalized.match(/^(.*)\s+([A-Za-z0-9]+)$/);
    if (!match) return { divisionName: normalized || 'Unknown', levelName: '' };
    return { divisionName: match[1].trim(), levelName: match[2].trim() };
}

function extractGameId(urlValue) {
    if (!urlValue) return '';
    try {
        const url = new URL(urlValue);
        return url.searchParams.get('game') || '';
    } catch {
        return '';
    }
}

function convertToCSV(games) {
    if (!games.length) return '';

    const headers = Object.keys(games[0]);
    const rows = games.map((game) =>
        headers
            .map((header) => {
                const value = game[header] || '';
                return value.toString().includes(',') ? `"${value}"` : value;
            })
            .join(','),
    );

    return [headers.join(','), ...rows].join('\n');
}

function buildScheduleUrl(standingsUrl) {
    return (standingsUrl || DEFAULT_STANDINGS_URL).replace('/standing.html', '/schedule.html');
}

function formatTimestampToDateTime(timestampSeconds) {
    const timestampMs = Number(timestampSeconds) * 1000;
    if (Number.isNaN(timestampMs)) return '';

    const date = new Date(timestampMs);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function splitTopLevelArgs(text) {
    const args = [];
    let current = '';
    let quote = null;
    let depthBraces = 0;
    let depthBrackets = 0;
    let depthParens = 0;

    for (let i = 0; i < text.length; i += 1) {
        const ch = text[i];

        if (quote) {
            current += ch;
            if (ch === '\\') {
                if (i + 1 < text.length) {
                    current += text[i + 1];
                    i += 1;
                }
                continue;
            }
            if (ch === quote) quote = null;
            continue;
        }

        if (ch === '"' || ch === "'") {
            quote = ch;
            current += ch;
            continue;
        }

        if (ch === '{') depthBraces += 1;
        else if (ch === '}') depthBraces -= 1;
        else if (ch === '[') depthBrackets += 1;
        else if (ch === ']') depthBrackets -= 1;
        else if (ch === '(') depthParens += 1;
        else if (ch === ')') depthParens -= 1;

        if (ch === ',' && depthBraces === 0 && depthBrackets === 0 && depthParens === 0) {
            args.push(current);
            current = '';
            continue;
        }

        current += ch;
    }

    if (current.trim()) args.push(current);
    return args;
}

function extractCapitalEmbeddedData(html) {
    const marker = 'PS.component.statistic_schedule_sd(';
    const start = html.indexOf(marker);
    if (start === -1) return null;

    const callStart = start + marker.length;
    let depth = 1;
    let i = callStart;
    let quote = null;

    while (i < html.length && depth > 0) {
        const ch = html[i];

        if (quote) {
            if (ch === '\\') {
                i += 2;
                continue;
            }
            if (ch === quote) quote = null;
            i += 1;
            continue;
        }

        if (ch === '"' || ch === "'") {
            quote = ch;
        } else if (ch === '(') {
            depth += 1;
        } else if (ch === ')') {
            depth -= 1;
        }
        i += 1;
    }

    if (depth !== 0) return null;

    const argsText = html.slice(callStart, i - 1);
    const args = splitTopLevelArgs(argsText);
    if (args.length < 5) return null;

    try {
        return {
            data: JSON.parse(args[3].trim()),
            liveBarns: JSON.parse(args[4].trim()),
        };
    } catch {
        return null;
    }
}

function mapEmbeddedGames(embeddedData) {
    const data = embeddedData?.data || {};
    const eventsInfo = data.eventsInfo || {};
    const gamesInfo = data.gamesInfo || {};
    const locationsInfo = data.locationsInfo || {};

    const games = [];

    Object.entries(eventsInfo).forEach(([timestamp, events]) => {
        if (!Array.isArray(events)) return;

        events.forEach((event) => {
            if (String(event?.eventTypeId || '') !== '3') return;

            const gameId = String(event.gameId || '');
            const gameInfo = gamesInfo[gameId] || {};
            const locationInfo = locationsInfo[String(event.locationId || '')] || {};

            const homeTeam = normalizeWhitespace(gameInfo.localTeamName || '');
            const awayTeam = normalizeWhitespace(gameInfo.awayTeamName || '');
            if (!homeTeam || !awayTeam) return;

            const homeScoreRaw = gameInfo.gameLocalScore;
            const awayScoreRaw = gameInfo.gameVisitorScore;
            const hasNumericScore = isNumeric(homeScoreRaw) && isNumeric(awayScoreRaw);

            const gameIsPlayed = String(gameInfo.gameIsPlayed || '') === '1';
            const gameIsLive = String(gameInfo.gameIsLive || '') === '1';
            const status = normalizeStatus(gameIsPlayed ? 'final' : (gameIsLive ? 'live' : 'scheduled'), hasNumericScore);

            const { divisionName, levelName } = splitDivisionAndLevel(gameInfo.gameCategoryName || '');

            games.push({
                source: 'capitalhlc',
                game_id: gameInfo.gameNum ? `#${gameInfo.gameNum}` : (gameId ? `#${gameId}` : ''),
                tournament_name: normalizeWhitespace(gameInfo.OrganisationNameLoc || gameInfo.OrganisationNameVis || 'Capital HLC'),
                division_name: divisionName,
                level_name: levelName,
                date: formatTimestampToDateTime(timestamp),
                location_name: normalizeWhitespace(locationInfo.locationName || ''),
                location: normalizeWhitespace(locationInfo.locationName || ''),
                home_team: homeTeam,
                away_team: awayTeam,
                home_score: status === 'Completed' && hasNumericScore ? String(homeScoreRaw) : '',
                away_score: status === 'Completed' && hasNumericScore ? String(awayScoreRaw) : '',
                status,
            });
        });
    });

    return games.sort((a, b) => a.date.localeCompare(b.date));
}

function mapDomGames(html) {
    const $ = cheerio.load(html);
    const games = [];

    $('li.match_wrapper .match').each((_, match) => {
        const $match = $(match);
        const $teams = $match.find('.team_wrapper');
        if ($teams.length < 2) return;

        const homeTeam = normalizeWhitespace($($teams[0]).find('.team_name').first().text());
        const awayTeam = normalizeWhitespace($($teams[1]).find('.team_name').first().text());
        if (!homeTeam || !awayTeam) return;

        const homeScoreRaw = normalizeWhitespace($($teams[0]).find('.score').first().text());
        const awayScoreRaw = normalizeWhitespace($($teams[1]).find('.score').first().text());
        const hasNumericScore = isNumeric(homeScoreRaw) && isNumeric(awayScoreRaw);

        const info = $match.find('.info').first();
        const league = normalizeWhitespace($match.find('.league').first().text());
        const timeText = normalizeWhitespace($match.find('.match_number').first().text());
        const locationName = normalizeWhitespace($match.find('a.location').first().text());
        const gameLink = $match.find('a.game_link').first();
        const statusText = normalizeWhitespace(gameLink.text());
        const href = gameLink.attr('href') || '';

        const { divisionName, levelName } = splitDivisionAndLevel(league);
        const status = normalizeStatus(statusText, hasNumericScore);
        const gameId = extractGameId(href);

        const dateIso = info.attr('data-date') || '';
        const dateTime = info.attr('data-date-time') || '';

        games.push({
            source: 'capitalhlc',
            game_id: gameId ? `#${gameId}` : '',
            tournament_name: 'Capital HLC',
            division_name: divisionName,
            level_name: levelName,
            date: dateIso && timeText ? `${dateIso} ${timeText}` : (dateTime || dateIso),
            location_name: locationName,
            location: locationName,
            home_team: homeTeam,
            away_team: awayTeam,
            home_score: status === 'Completed' && hasNumericScore ? homeScoreRaw : '',
            away_score: status === 'Completed' && hasNumericScore ? awayScoreRaw : '',
            status,
        });
    });

    return games;
}

async function scrapeCapital(standingsUrl = DEFAULT_STANDINGS_URL) {
    const scheduleUrl = buildScheduleUrl(standingsUrl);

    const response = await axios.get(scheduleUrl, {
        timeout: 30000,
        headers: {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        },
    });

    const html = response.data;
    const embeddedData = extractCapitalEmbeddedData(html);
    const games = embeddedData ? mapEmbeddedGames(embeddedData) : mapDomGames(html);

    await fs.writeFile(
        'csv/response_payload.json',
        JSON.stringify({ source: 'capitalhlc', scheduleUrl, htmlLength: html.length, mode: embeddedData ? 'embedded-json' : 'dom-fallback', extractedGames: games.length }, null, 2),
    );

    await fs.writeFile('csv/hockey_games.csv', convertToCSV(games));

    console.log(`Saved ${games.length} games to csv/hockey_games.csv`);
}

const standingsUrl = process.argv[2] || DEFAULT_STANDINGS_URL;
scrapeCapital(standingsUrl).catch((error) => {
    console.error('Capital scrape failed:', error.message);
    process.exit(1);
});
