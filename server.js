const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const path = require('path');
const fs = require('fs').promises;
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// ELO constants (optimized via cross-validation)
const INITIAL_ELO = 1500;
const K_FACTOR = 35;  // Optimized: was 20
const HOME_ADVANTAGE = 100;
const PYTHAGOREAN_EXPONENT = 2.0;  // Optimized: was 2.37
const ELO_WEIGHT = 0.8;  // Optimized: was 0.6
const PYTH_WEIGHT = 0.2;

// Rate limiting - 1 hour cooldown for scraping
const SCRAPE_COOLDOWN_MS = 60 * 60 * 1000; // 1 hour in milliseconds
const LAST_FETCH_FILE = 'csv/last_fetch_time.json';
const DEFAULT_SOURCE = 'scoresheets';
const SCORESHEETS_ARCHIVE_FILE = path.join('csv', 'hockey_games_scoresheets_archive.csv');

function getSourceCsvPath(source = DEFAULT_SOURCE) {
    return path.join('csv', `hockey_games_${source}.csv`);
}

async function readGamesForSource(source = DEFAULT_SOURCE) {
    const sourceCsvPath = getSourceCsvPath(source);
    try {
        const csvContent = await fs.readFile(sourceCsvPath, 'utf-8');
        return parseCSV(csvContent);
    } catch (error) {
        const csvContent = await fs.readFile('csv/hockey_games.csv', 'utf-8');
        const allGames = parseCSV(csvContent);
        const matchingSourceGames = allGames.filter((g) => (g.source || DEFAULT_SOURCE) === source);

        if (matchingSourceGames.length > 0) {
            return matchingSourceGames;
        }

        throw new Error(`No scraped data found for source '${source}'. Please scrape this source first.`);
    }
}

async function readScoresheetsArchiveGames() {
    const csvContent = await fs.readFile(SCORESHEETS_ARCHIVE_FILE, 'utf-8');
    return parseCSV(csvContent);
}

async function ensureScoresheetsArchiveGames() {
    try {
        const games = await readScoresheetsArchiveGames();
        if (games.length > 0) {
            return games;
        }
    } catch (error) {
        // Archive does not exist yet, create it from source 1.
    }

    const { games } = await scrapeScoresheetsSource({
        tournamentId: 17,
        divisionId: 45,
        levelId: 6
    });

    const csv = convertToCSV(games);
    await fs.writeFile(SCORESHEETS_ARCHIVE_FILE, csv);
    return games;
}

function mergeSeriesWithArchive(seriesGames, archiveGames, division, level, knownGamesOnly) {
    const seriesKnownTeams = new Set();
    seriesGames.forEach((g) => {
        if (isKnownTeamName(g.home_team)) seriesKnownTeams.add(g.home_team);
        if (isKnownTeamName(g.away_team)) seriesKnownTeams.add(g.away_team);
    });

    const archiveFiltered = archiveGames.filter((g) => {
        const sameCategory = g.division_name === division && g.level_name === level;
        if (!sameCategory) return false;

        if (knownGamesOnly) {
            return seriesKnownTeams.has(g.home_team) && seriesKnownTeams.has(g.away_team);
        }

        return true;
    });

    const dedup = new Map();
    [...archiveFiltered, ...seriesGames].forEach((g) => {
        const key = `${g.game_id}|${g.date}|${g.home_team}|${g.away_team}`;
        if (!dedup.has(key)) {
            dedup.set(key, g);
        }
    });

    return Array.from(dedup.values());
}

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Get last fetch time
app.get('/api/scrape/status', async (req, res) => {
    try {
        const source = (req.query.source || DEFAULT_SOURCE).toString();
        const lastFetchData = await getLastFetchTime(source);
        res.json(lastFetchData);
    } catch (error) {
        res.json({ canFetch: true, nextAllowedTime: null, source: req.query.source || DEFAULT_SOURCE });
    }
});

// Scrape games from scoresheets.ca API
app.post('/api/scrape', async (req, res) => {
    try {
        const source = (req.body.source || DEFAULT_SOURCE).toString();

        // Check if scraping is allowed
        const { canFetch, nextAllowedTime, timeRemaining } = await getLastFetchTime(source);
        
        if (!canFetch) {
            return res.status(429).json({ 
                success: false, 
                error: 'Rate limit exceeded',
                message: `Please wait ${Math.ceil(timeRemaining / 60000)} minutes before fetching again.`,
                nextAllowedTime,
                source
            });
        }

        const scrapeRequest = {
            tournamentId: req.body.tournamentId,
            divisionId: req.body.divisionId,
            levelId: req.body.levelId,
            season: req.body.season,
            subSeason: req.body.subSeason,
            category: req.body.category,
            standingsUrl: req.body.standingsUrl,
            scheduleUrl: req.body.scheduleUrl
        };

        let result;
        if (source === 'capitalhlc') {
            result = await scrapeCapitalSource(scrapeRequest);
        } else {
            result = await scrapeScoresheetsSource(scrapeRequest);
        }

        const { rawData, games } = result;

        // Save raw response
        await fs.writeFile('csv/response_payload.json', JSON.stringify({ source, rawData }, null, 2));
        
        // Save to CSV
        const csv = convertToCSV(games);
        await fs.writeFile(getSourceCsvPath(source), csv);
        await fs.writeFile('csv/hockey_games.csv', csv);

        // Keep an archive snapshot of source 1 results for series predictions.
        if (source === 'scoresheets') {
            try {
                await fs.access(SCORESHEETS_ARCHIVE_FILE);
            } catch (error) {
                await fs.writeFile(SCORESHEETS_ARCHIVE_FILE, csv);
            }
        }
        
        // Save last fetch timestamp
        const now = Date.now();
        await saveLastFetchTime(source, now);
        
        res.json({ 
            success: true, 
            source,
            games, 
            count: games.length,
            fetchTime: now,
            nextAllowedTime: now + SCRAPE_COOLDOWN_MS
        });
    } catch (error) {
        console.error('Scrape error:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Get available filter options
app.get('/api/filters', async (req, res) => {
    const source = (req.query.source || DEFAULT_SOURCE).toString();
    try {
        const games = await readGamesForSource(source);
        
        const tournaments = [...new Set(games.map(g => g.tournament_name))].filter(Boolean);
        const divisions = [...new Set(games.map(g => g.division_name))].filter(Boolean);
        const levels = [...new Set(games.map(g => g.level_name))].filter(Boolean);
        
        res.json({ tournaments, divisions, levels });
    } catch (error) {
        if (source === 'capitalhlc') {
            res.json({ tournaments: ['Capital HLC'], divisions: ['U15 House'], levels: ['B'] });
        } else if (source === 'scoresheets_series') {
            res.json({ tournaments: ['E.H.L. - SÉRIES'], divisions: ['Moins de 15 ans'], levels: ['B'] });
        } else {
            res.json({ tournaments: ['E.H.L.'], divisions: ['Moins de 15 ans'], levels: ['B'] });
        }
    }
});

// Analyze games and generate tables
app.post('/api/analyze', async (req, res) => {
    try {
        const { source = DEFAULT_SOURCE, tournament, division, level, knownGamesOnly = false } = req.body;
        const allGames = await readGamesForSource(source);
        
        // Filter games
        const filteredGames = allGames.filter(g => 
            g.tournament_name === tournament &&
            g.division_name === division &&
            g.level_name === level
        );
        const games = applyKnownGamesOnly(filteredGames, source, knownGamesOnly);
        
        // Build team results matrix
        const { teams, matrix, teamStats } = buildTeamResultsMatrix(games);
        
        res.json({ 
            success: true, 
            teams, 
            matrix, 
            teamStats,
            gameCount: games.length 
        });
    } catch (error) {
        console.error('Analysis error:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Get raw games (used by tournament bracket page)
app.get('/api/games', async (req, res) => {
    try {
        const source = (req.query.source || DEFAULT_SOURCE).toString();
        const tournament = (req.query.tournament || '').toString();
        const division = (req.query.division || '').toString();
        const level = (req.query.level || '').toString();
        const knownGamesOnly = String(req.query.knownGamesOnly || 'false').toLowerCase() === 'true';

        const allGames = await readGamesForSource(source);
        const filteredGames = allGames.filter((g) =>
            (!tournament || g.tournament_name === tournament) &&
            (!division || g.division_name === division) &&
            (!level || g.level_name === level)
        );

        const games = applyKnownGamesOnly(filteredGames, source, knownGamesOnly)
            .sort((a, b) => (a.date || '').localeCompare(b.date || ''));

        res.json({ success: true, source, count: games.length, games });
    } catch (error) {
        console.error('Games endpoint error:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Download CSV

// Get last fetch time and check if scraping is allowed
async function getLastFetchTime(source = DEFAULT_SOURCE) {
    try {
        const data = await fs.readFile(LAST_FETCH_FILE, 'utf-8');
        const parsed = JSON.parse(data);
        const bySource = parsed.bySource || {};

        // Legacy compatibility: old format had a single lastFetchTime.
        // Apply it only to default source, never globally across all sources.
        const legacy = parsed.lastFetchTime;
        const lastFetchTime = bySource[source] || (source === DEFAULT_SOURCE ? legacy : null) || null;

        if (!lastFetchTime) {
            return { canFetch: true, nextAllowedTime: null, timeRemaining: 0, lastFetchTime: null, source };
        }

        const now = Date.now();
        const timeElapsed = now - lastFetchTime;
        const timeRemaining = SCRAPE_COOLDOWN_MS - timeElapsed;
        
        const canFetch = timeElapsed >= SCRAPE_COOLDOWN_MS;
        const nextAllowedTime = canFetch ? null : lastFetchTime + SCRAPE_COOLDOWN_MS;
        
        return { canFetch, nextAllowedTime, timeRemaining, lastFetchTime, source };
    } catch (error) {
        // File doesn't exist or is invalid - allow fetch
        return { canFetch: true, nextAllowedTime: null, timeRemaining: 0, lastFetchTime: null, source };
    }
}

// Save last fetch time
async function saveLastFetchTime(source, timestamp) {
    let bySource = {};
    try {
        const data = await fs.readFile(LAST_FETCH_FILE, 'utf-8');
        const parsed = JSON.parse(data);
        bySource = parsed.bySource || {};
    } catch (error) {
        bySource = {};
    }

    bySource[source] = timestamp;
    await fs.writeFile(LAST_FETCH_FILE, JSON.stringify({ bySource }, null, 2));
}

async function scrapeScoresheetsSource(options = {}) {
    const payload = {
        getTournamentGameList: 'TournamentPublicData',
        filterBy: 'division',
        filterRange: 'all',
        tournamentId: options.tournamentId || 17,
        divisionId: options.divisionId || 45,
        levelId: options.levelId || 6,
        sortingOrder: 'ascending'
    };

    const response = await axios.post(
        'https://scoresheets.ca/classes/TournamentPublicData.php',
        new URLSearchParams(payload),
        {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        }
    );

    const data = response.data;
    const games = [];

    if (data?.resp && Array.isArray(data?.data)) {
        for (const game of data.data) {
            games.push(normalizeScoresheetsGame(game));
        }
    }

    return { rawData: data, games };
}

async function scrapeCapitalSource(options = {}) {
    const scheduleUrl = buildCapitalScheduleUrl(options);
    const response = await axios.get(scheduleUrl, {
        timeout: 30000,
        headers: {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
    });

    const html = response.data;
    const embeddedData = extractCapitalEmbeddedData(html);
    const games = embeddedData ? mapCapitalEmbeddedGames(embeddedData) : extractCapitalGamesFromDom(html);

    return {
        rawData: {
            scheduleUrl,
            htmlLength: html.length,
            mode: embeddedData ? 'embedded-json' : 'dom-fallback',
            extractedGames: games.length
        },
        games
    };
}

function extractCapitalGamesFromDom(html) {
    const $ = cheerio.load(html);
    const games = [];

    $('li.match_wrapper .match').each((_, match) => {
        const $match = $(match);
        const $info = $match.find('.info').first();
        const $gameLink = $match.find('a.game_link').first();
        const $teams = $match.find('.team_wrapper');

        if ($teams.length < 2) return;

        const homeTeam = normalizeWhitespace($($teams[0]).find('.team_name').first().text());
        const awayTeam = normalizeWhitespace($($teams[1]).find('.team_name').first().text());
        if (!homeTeam || !awayTeam) return;

        const homeScoreRaw = normalizeWhitespace($($teams[0]).find('.score').first().text());
        const awayScoreRaw = normalizeWhitespace($($teams[1]).find('.score').first().text());
        const league = normalizeWhitespace($match.find('.league').first().text()) || 'Unknown';
        const timeText = normalizeWhitespace($match.find('.match_number').first().text());
        const locationName = normalizeWhitespace($match.find('a.location').first().text());
        const statusText = normalizeWhitespace($gameLink.text());
        const href = $gameLink.attr('href') || '';

        const dateIso = $info.attr('data-date') || '';
        const dateTime = $info.attr('data-date-time') || '';
        const { divisionName, levelName } = splitDivisionAndLevel(league);

        const gameId = extractQueryParam(href, 'game');
        const hasNumericScore = isNumeric(homeScoreRaw) && isNumeric(awayScoreRaw);
        const status = normalizeStatus(statusText, hasNumericScore);

        games.push({
            source: 'capitalhlc',
            game_id: gameId ? `#${gameId}` : '',
            tournament_name: 'Capital HLC',
            division_name: divisionName,
            level_name: levelName,
            date: normalizeCapitalDate(dateIso, timeText, dateTime),
            location_name: locationName,
            location: locationName,
            home_team: homeTeam,
            away_team: awayTeam,
            home_score: isCompletedStatus(status) && hasNumericScore ? homeScoreRaw : '',
            away_score: isCompletedStatus(status) && hasNumericScore ? awayScoreRaw : '',
            status
        });
    });

    return games;
}

function mapCapitalEmbeddedGames(embedded) {
    const data = embedded?.data || {};
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

            const league = normalizeWhitespace(gameInfo.gameCategoryName || '');
            const { divisionName, levelName } = splitDivisionAndLevel(league);

            const homeTeam = normalizeWhitespace(gameInfo.localTeamName || event.eventLocalTeamName || '');
            const awayTeam = normalizeWhitespace(gameInfo.awayTeamName || event.eventVisitorTeamName || '');
            if (!homeTeam || !awayTeam) return;

            const homeScoreRaw = gameInfo.gameLocalScore;
            const awayScoreRaw = gameInfo.gameVisitorScore;
            const hasNumericScore = isNumeric(homeScoreRaw) && isNumeric(awayScoreRaw);

            const gameIsPlayed = String(gameInfo.gameIsPlayed || '') === '1';
            const gameIsLive = String(gameInfo.gameIsLive || '') === '1';
            const rawStatus = gameIsPlayed ? 'final' : (gameIsLive ? 'live' : 'scheduled');
            const status = normalizeStatus(rawStatus, hasNumericScore);

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
                home_score: isCompletedStatus(status) && hasNumericScore ? String(homeScoreRaw) : '',
                away_score: isCompletedStatus(status) && hasNumericScore ? String(awayScoreRaw) : '',
                status
            });
        });
    });

    return games.sort((a, b) => a.date.localeCompare(b.date));
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
            liveBarns: JSON.parse(args[4].trim())
        };
    } catch (error) {
        return null;
    }
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

function buildCapitalScheduleUrl(options = {}) {
    const providedSchedule = options.scheduleUrl;
    if (providedSchedule) return providedSchedule;

    if (options.standingsUrl) {
        try {
            const url = new URL(options.standingsUrl);
            url.pathname = url.pathname.replace('standing.html', 'schedule.html');
            return url.toString();
        } catch (error) {
            // fall through to defaults
        }
    }

    const season = options.season || 2750;
    const subSeason = options.subSeason || 4834;
    const category = options.category || 6557;
    return `https://www.capitalhlc.com/en/stats/schedule.html?season=${season}&subSeason=${subSeason}&category=${category}`;
}

function normalizeScoresheetsGame(game) {
    const gameNumber = pickFirst(game, ['gameNumber', 'game_number', 'gameId', 'id']);
    const gameDate = pickFirst(game, ['game_date', 'gameDate', 'date']);
    const startTime = pickFirst(game, ['startTime', 'start_time', 'time']);

    const locationName = pickFirst(game, ['locationName', 'location_name', 'arenaName']);
    const address1 = pickFirst(game, ['address1', 'address', 'addressLine1']);
    const completeAddress = pickFirst(game, ['complete_address', 'completeAddress']);

    const rawStatus = pickFirst(game, ['status', 'gameStatus', 'state']);
    const homeScoreRaw = pickFirst(game, ['homeTotalGoals', 'home_score', 'homeGoals', 'home']);
    const awayScoreRaw = pickFirst(game, ['awayTotalGoals', 'away_score', 'awayGoals', 'away']);
    const hasNumericScore = isNumeric(homeScoreRaw) && isNumeric(awayScoreRaw);
    const status = normalizeStatus(rawStatus, hasNumericScore);

    let location = '';
    if (locationName) {
        location = address1 || completeAddress
            ? `${locationName}, ${address1 || completeAddress}`
            : locationName;
    }

    return {
        source: 'scoresheets',
        game_id: gameNumber ? `#${gameNumber}` : '',
        tournament_name: pickFirst(game, ['tournamentName', 'tournament_name', 'tournament']) || '',
        division_name: pickFirst(game, ['divisionName', 'division_name', 'division']) || '',
        level_name: pickFirst(game, ['levelName', 'level_name', 'level']) || '',
        date: normalizeScoresheetsDate(gameDate, startTime),
        location_name: locationName || '',
        location: location,
        home_team: (pickFirst(game, ['homeTeamName', 'home_team', 'homeTeam']) || '').trim(),
        away_team: (pickFirst(game, ['awayTeamName', 'away_team', 'awayTeam']) || '').trim(),
        home_score: isCompletedStatus(status) && hasNumericScore ? String(homeScoreRaw) : '',
        away_score: isCompletedStatus(status) && hasNumericScore ? String(awayScoreRaw) : '',
        status
    };
}

function normalizeScoresheetsDate(gameDate, startTime) {
    if (gameDate && startTime) {
        const timeWithoutSeconds = String(startTime).split(':').slice(0, 2).join(':');
        return `${gameDate} ${timeWithoutSeconds}`;
    }
    return gameDate || '';
}

function normalizeCapitalDate(dateIso, timeText, dateTime) {
    if (dateIso && timeText) return `${dateIso} ${timeText}`;
    if (dateTime) return dateTime;
    return dateIso || '';
}

function splitDivisionAndLevel(league) {
    const normalized = normalizeWhitespace(league);
    const match = normalized.match(/^(.*)\s+([A-Za-z0-9]+)$/);
    if (!match) {
        return { divisionName: normalized || 'Unknown', levelName: '' };
    }

    return {
        divisionName: match[1].trim(),
        levelName: match[2].trim()
    };
}

function pickFirst(obj, keys) {
    for (const key of keys) {
        const value = obj?.[key];
        if (value !== undefined && value !== null && value !== '') {
            return String(value);
        }
    }
    return '';
}

function extractQueryParam(urlValue, param) {
    if (!urlValue) return '';
    try {
        const url = new URL(urlValue);
        return url.searchParams.get(param) || '';
    } catch (error) {
        return '';
    }
}

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

    if (status.includes('final') || status.includes('completed') || status.includes('termin')) {
        return 'Completed';
    }

    if (status.includes('live') || status.includes('progress') || status.includes('period')) {
        return 'In Progress';
    }

    if (status.includes('pre-game') || status.includes('scheduled') || status.includes('setup') || status.includes('init')) {
        return 'Setup';
    }

    return hasNumericScore ? 'Completed' : 'Setup';
}

function isCompletedStatus(status) {
    return normalizeStatus(status, false) === 'Completed';
}

function isUpcomingStatus(status) {
    return !isCompletedStatus(status);
}

function isKnownTeamName(teamName) {
    const normalized = normalizeWhitespace(teamName || '').toLowerCase();
    return Boolean(normalized)
        && !normalized.includes('gagnant')
        && !normalized.includes('perdant')
        && !normalized.includes('position');
}

function applyKnownGamesOnly(games, source, knownGamesOnly) {
    if (source !== 'scoresheets_series' || !knownGamesOnly) {
        return games;
    }

    return games.filter((g) => isKnownTeamName(g.home_team) && isKnownTeamName(g.away_team));
}

app.get('/api/download/csv', async (req, res) => {
    try {
        const source = (req.query.source || DEFAULT_SOURCE).toString();
        const sourceCsvPath = path.join(__dirname, getSourceCsvPath(source));

        try {
            await fs.access(sourceCsvPath);
            return res.download(sourceCsvPath, `hockey_games_${source}.csv`);
        } catch (error) {
            const csvPath = path.join(__dirname, 'csv', 'hockey_games.csv');
            return res.download(csvPath, 'hockey_games.csv');
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Helper functions
function convertToCSV(games) {
    if (games.length === 0) return '';
    
    const headers = Object.keys(games[0]);
    const rows = games.map(game => 
        headers.map(header => {
            const value = game[header] || '';
            return value.toString().includes(',') ? `"${value}"` : value;
        }).join(',')
    );
    
    return [headers.join(','), ...rows].join('\n');
}

function parseCSV(csvContent) {
    const lines = csvContent.split('\n');
    if (lines.length < 2) return [];
    
    const headers = parseCSVLine(lines[0]);
    const games = [];
    
    for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        
        const values = parseCSVLine(lines[i]);
        const game = {};
        headers.forEach((header, index) => {
            game[header] = values[index] || '';
        });
        games.push(game);
    }
    
    return games;
}

function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        
        if (char === '"') {
            inQuotes = !inQuotes;
        } else if (char === ',' && !inQuotes) {
            result.push(current.trim());
            current = '';
        } else {
            current += char;
        }
    }
    
    result.push(current.trim());
    return result;
}

function buildTeamResultsMatrix(games) {
    // Get all unique teams
    const teamsSet = new Set();
    games.forEach(game => {
        if (game.home_team) teamsSet.add(game.home_team);
        if (game.away_team) teamsSet.add(game.away_team);
    });
    
    const teams = Array.from(teamsSet).sort();
    
    // Initialize matrix and stats
    const matrix = {};
    const teamStats = {};
    
    teams.forEach(team => {
        matrix[team] = {};
        teams.forEach(otherTeam => {
            matrix[team][otherTeam] = [];
        });
        teamStats[team] = { wins: 0, losses: 0, ties: 0, to_play: 0 };
    });
    
    // Process games
    games.forEach(game => {
        const home = game.home_team;
        const away = game.away_team;
        
        if (!home || !away) return;
        
        if (isCompletedStatus(game.status) && game.home_score && game.away_score) {
            const homeScore = parseInt(game.home_score);
            const awayScore = parseInt(game.away_score);
            
            // Store from each team's perspective
            matrix[home][away].push(`${homeScore}-${awayScore}`);
            matrix[away][home].push(`${awayScore}-${homeScore}`);
            
            // Update stats
            if (homeScore > awayScore) {
                teamStats[home].wins++;
                teamStats[away].losses++;
            } else if (awayScore > homeScore) {
                teamStats[home].losses++;
                teamStats[away].wins++;
            } else {
                teamStats[home].ties++;
                teamStats[away].ties++;
            }
        } else if (isUpcomingStatus(game.status)) {
            matrix[home][away].push('??-??');
            matrix[away][home].push('??-??');
            teamStats[home].to_play++;
            teamStats[away].to_play++;
        }
    });
    
    return { teams, matrix, teamStats };
}

function calculateExpectedScore(eloA, eloB) {
    return 1 / (1 + Math.pow(10, (eloB - eloA) / 400));
}

function updateElo(winnerElo, loserElo, marginOfVictory = 1) {
    const expectedWinner = calculateExpectedScore(winnerElo, loserElo);
    const expectedLoser = calculateExpectedScore(loserElo, winnerElo);
    const movMultiplier = Math.log(Math.max(marginOfVictory, 1) + 1);
    
    const newWinnerElo = winnerElo + K_FACTOR * movMultiplier * (1 - expectedWinner);
    const newLoserElo = loserElo + K_FACTOR * movMultiplier * (0 - expectedLoser);
    
    return { newWinnerElo, newLoserElo };
}

function updateEloTie(eloA, eloB) {
    const expectedA = calculateExpectedScore(eloA, eloB);
    const expectedB = calculateExpectedScore(eloB, eloA);
    
    const newEloA = eloA + K_FACTOR * (0.5 - expectedA);
    const newEloB = eloB + K_FACTOR * (0.5 - expectedB);
    
    return { newEloA, newEloB };
}

function buildEloRatings(games) {
    const teamElos = {};
    const teams = new Set();
    
    games.forEach(game => {
        teams.add(game.home_team);
        teams.add(game.away_team);
    });
    
    teams.forEach(team => {
        teamElos[team] = {
            currentElo: INITIAL_ELO,
            gamesPlayed: 0,
            totalPointsFor: 0,
            totalPointsAgainst: 0
        };
    });
    
    const completedGames = games
        .filter(g => isCompletedStatus(g.status) && g.home_score && g.away_score)
        .sort((a, b) => a.date.localeCompare(b.date));
    
    completedGames.forEach(game => {
        const home = game.home_team;
        const away = game.away_team;
        const homeScore = parseInt(game.home_score);
        const awayScore = parseInt(game.away_score);
        
        const homeElo = teamElos[home].currentElo + HOME_ADVANTAGE;
        const awayElo = teamElos[away].currentElo;
        
        teamElos[home].totalPointsFor += homeScore;
        teamElos[home].totalPointsAgainst += awayScore;
        teamElos[home].gamesPlayed++;
        
        teamElos[away].totalPointsFor += awayScore;
        teamElos[away].totalPointsAgainst += homeScore;
        teamElos[away].gamesPlayed++;
        
        if (homeScore > awayScore) {
            const margin = homeScore - awayScore;
            const { newWinnerElo, newLoserElo } = updateElo(homeElo, awayElo, margin);
            teamElos[home].currentElo = newWinnerElo - HOME_ADVANTAGE;
            teamElos[away].currentElo = newLoserElo;
        } else if (awayScore > homeScore) {
            const margin = awayScore - homeScore;
            const { newWinnerElo, newLoserElo } = updateElo(awayElo, homeElo, margin);
            teamElos[away].currentElo = newWinnerElo;
            teamElos[home].currentElo = newLoserElo - HOME_ADVANTAGE;
        } else {
            const { newEloA, newEloB } = updateEloTie(homeElo, awayElo);
            teamElos[home].currentElo = newEloA - HOME_ADVANTAGE;
            teamElos[away].currentElo = newEloB;
        }
    });
    
    // Calculate Pythagorean expectation
    Object.keys(teamElos).forEach(team => {
        const stats = teamElos[team];
        if (stats.gamesPlayed > 0) {
            const pfSquared = Math.pow(stats.totalPointsFor, PYTHAGOREAN_EXPONENT);
            const paSquared = Math.pow(stats.totalPointsAgainst, PYTHAGOREAN_EXPONENT);
            stats.pythagoreanExpectation = pfSquared / (pfSquared + paSquared);
        } else {
            stats.pythagoreanExpectation = 0.5;
        }
    });
    
    return teamElos;
}

function predictUpcomingGames(games, teamElos) {
    const predictions = [];
    
    const upcomingGames = games.filter(g => 
        !isCompletedStatus(g.status) && g.home_team && g.away_team
    );
    
    upcomingGames.forEach(game => {
        const home = game.home_team;
        const away = game.away_team;
        
        const homeElo = teamElos[home].currentElo + HOME_ADVANTAGE;
        const awayElo = teamElos[away].currentElo;
        
        const eloHomeWinProb = calculateExpectedScore(homeElo, awayElo) * 100;
        
        const homePyth = teamElos[home].pythagoreanExpectation;
        const awayPyth = teamElos[away].pythagoreanExpectation;
        const pythHomeWinProb = (homePyth / (homePyth + awayPyth)) * 100;
        
        const combinedHomeWinProb = (eloHomeWinProb * ELO_WEIGHT + pythHomeWinProb * PYTH_WEIGHT);
        const combinedAwayWinProb = 100 - combinedHomeWinProb;
        
        predictions.push({
            game_id: game.game_id,
            date: game.date,
            location: game.location,
            home_team: home,
            away_team: away,
            home_elo: teamElos[home].currentElo,
            away_elo: teamElos[away].currentElo,
            home_pyth: homePyth,
            away_pyth: awayPyth,
            elo_home_win_prob: eloHomeWinProb,
            pyth_home_win_prob: pythHomeWinProb,
            combined_home_win_prob: combinedHomeWinProb,
            combined_away_win_prob: combinedAwayWinProb,
            predicted_winner: combinedHomeWinProb > 50 ? home : away
        });
    });
    
    return predictions;
}

function validatePredictions(games) {
    const completedGames = games
        .filter(g => isCompletedStatus(g.status) && g.home_score && g.away_score)
        .sort((a, b) => a.date.localeCompare(b.date));
    
    console.log(`\nValidating predictions on ${completedGames.length} completed games...`);
    
    const validationResults = [];
    const teamAccuracy = {};
    
    for (let i = 0; i < completedGames.length; i++) {
        const testGame = completedGames[i];
        const trainingGames = completedGames.slice(0, i);
        
        if (trainingGames.length < 2) continue;
        
        // Build ELO ratings from training data
        const teamElos = {};
        const teams = new Set();
        
        trainingGames.forEach(game => {
            teams.add(game.home_team);
            teams.add(game.away_team);
        });
        
        teams.forEach(team => {
            teamElos[team] = {
                currentElo: INITIAL_ELO,
                gamesPlayed: 0,
                totalPointsFor: 0,
                totalPointsAgainst: 0
            };
        });
        
        // Process training games
        trainingGames.forEach(game => {
            const home = game.home_team;
            const away = game.away_team;
            const homeScore = parseInt(game.home_score);
            const awayScore = parseInt(game.away_score);
            
            const homeElo = teamElos[home].currentElo + HOME_ADVANTAGE;
            const awayElo = teamElos[away].currentElo;
            
            teamElos[home].totalPointsFor += homeScore;
            teamElos[home].totalPointsAgainst += awayScore;
            teamElos[home].gamesPlayed++;
            
            teamElos[away].totalPointsFor += awayScore;
            teamElos[away].totalPointsAgainst += homeScore;
            teamElos[away].gamesPlayed++;
            
            if (homeScore > awayScore) {
                const margin = homeScore - awayScore;
                const { newWinnerElo, newLoserElo } = updateElo(homeElo, awayElo, margin);
                teamElos[home].currentElo = newWinnerElo - HOME_ADVANTAGE;
                teamElos[away].currentElo = newLoserElo;
            } else if (awayScore > homeScore) {
                const margin = awayScore - homeScore;
                const { newWinnerElo, newLoserElo } = updateElo(awayElo, homeElo, margin);
                teamElos[away].currentElo = newWinnerElo;
                teamElos[home].currentElo = newLoserElo - HOME_ADVANTAGE;
            } else {
                const { newEloA, newEloB } = updateEloTie(homeElo, awayElo);
                teamElos[home].currentElo = newEloA - HOME_ADVANTAGE;
                teamElos[away].currentElo = newEloB;
            }
        });
        
        // Calculate Pythagorean expectations
        Object.keys(teamElos).forEach(team => {
            const stats = teamElos[team];
            if (stats.gamesPlayed > 0) {
                const pfSquared = Math.pow(stats.totalPointsFor, PYTHAGOREAN_EXPONENT);
                const paSquared = Math.pow(stats.totalPointsAgainst, PYTHAGOREAN_EXPONENT);
                stats.pythagoreanExpectation = pfSquared / (pfSquared + paSquared);
            } else {
                stats.pythagoreanExpectation = 0.5;
            }
        });
        
        // Make prediction
        const home = testGame.home_team;
        const away = testGame.away_team;
        
        if (!teamElos[home] || !teamElos[away]) continue;
        
        const homeElo = teamElos[home].currentElo + HOME_ADVANTAGE;
        const awayElo = teamElos[away].currentElo;
        
        const eloHomeWinProb = calculateExpectedScore(homeElo, awayElo) * 100;
        
        const homePyth = teamElos[home].pythagoreanExpectation;
        const awayPyth = teamElos[away].pythagoreanExpectation;
        const pythHomeWinProb = (homePyth / (homePyth + awayPyth)) * 100;
        
        const combinedHomeWinProb = eloHomeWinProb * ELO_WEIGHT + pythHomeWinProb * PYTH_WEIGHT;
        
        const predictedWinner = combinedHomeWinProb > 50 ? home : away;
        
        // Determine actual winner
        const homeScore = parseInt(testGame.home_score);
        const awayScore = parseInt(testGame.away_score);
        
        let actualWinner;
        if (homeScore > awayScore) {
            actualWinner = home;
        } else if (awayScore > homeScore) {
            actualWinner = away;
        } else {
            actualWinner = 'Tie';
        }
        
        const correct = (predictedWinner === actualWinner) && actualWinner !== 'Tie';
        
        // Track accuracy per team
        [home, away].forEach(team => {
            if (!teamAccuracy[team]) {
                teamAccuracy[team] = { correct: 0, total: 0 };
            }
            teamAccuracy[team].total++;
            if (correct) {
                teamAccuracy[team].correct++;
            }
        });
        
        validationResults.push({
            game_id: testGame.game_id,
            date: testGame.date,
            home_team: home,
            away_team: away,
            home_score: homeScore,
            away_score: awayScore,
            predicted_winner: predictedWinner,
            actual_winner: actualWinner,
            correct: correct,
            combined_prob: combinedHomeWinProb,
            home_elo: teamElos[home].currentElo,
            away_elo: teamElos[away].currentElo
        });
    }
    
    return { validationResults, teamAccuracy };
}

// Validate predictions endpoint
app.post('/api/validate', async (req, res) => {
    try {
        const { source = DEFAULT_SOURCE, tournament, division, level, knownGamesOnly = false } = req.body;
        const allGames = await readGamesForSource(source);
        
        const filteredGames = allGames.filter(g => 
            g.tournament_name === tournament &&
            g.division_name === division &&
            g.level_name === level
        );
        const games = applyKnownGamesOnly(filteredGames, source, knownGamesOnly);
        
        const { validationResults, teamAccuracy } = validatePredictions(games);
        
        const overallCorrect = validationResults.filter(r => r.correct).length;
        const overallTotal = validationResults.length;
        const overallAccuracy = overallTotal > 0 ? (overallCorrect / overallTotal * 100) : 0;
        
        res.json({ 
            success: true, 
            validationResults,
            teamAccuracy,
            overallCorrect,
            overallTotal,
            overallAccuracy
        });
    } catch (error) {
        console.error('Validation error:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Predict with ELO
app.post('/api/predict', async (req, res) => {
    try {
        const { source = DEFAULT_SOURCE, tournament, division, level, knownGamesOnly = false } = req.body;
        const allGames = await readGamesForSource(source);
        
        const filteredGames = allGames.filter(g => 
            g.tournament_name === tournament &&
            g.division_name === division &&
            g.level_name === level
        );
        const games = applyKnownGamesOnly(filteredGames, source, knownGamesOnly);

        let gamesForRatings = games;
        if (source === 'scoresheets_series') {
            const archiveGames = await ensureScoresheetsArchiveGames();
            gamesForRatings = mergeSeriesWithArchive(games, archiveGames, division, level, knownGamesOnly);
        }
        
        const teamElos = buildEloRatings(gamesForRatings);
        const predictions = predictUpcomingGames(games, teamElos);
        
        // Add validation accuracy to teamElos
        const { teamAccuracy } = validatePredictions(games);
        Object.keys(teamElos).forEach(team => {
            if (teamAccuracy[team]) {
                const stats = teamAccuracy[team];
                teamElos[team].validationAccuracy = stats.total > 0 ? (stats.correct / stats.total * 100) : 0;
                teamElos[team].validationGames = stats.total;
            } else {
                teamElos[team].validationAccuracy = 0;
                teamElos[team].validationGames = 0;
            }
        });
        
        res.json({ 
            success: true, 
            teamElos,
            predictions,
            predictionCount: predictions.length 
        });
    } catch (error) {
        console.error('Prediction error:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});
