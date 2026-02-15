const express = require('express');
const axios = require('axios');
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

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Get last fetch time
app.get('/api/scrape/status', async (req, res) => {
    try {
        const lastFetchData = await getLastFetchTime();
        res.json(lastFetchData);
    } catch (error) {
        res.json({ canFetch: true, nextAllowedTime: null });
    }
});

// Scrape games from scoresheets.ca API
app.post('/api/scrape', async (req, res) => {
    try {
        // Check if scraping is allowed
        const { canFetch, nextAllowedTime, timeRemaining } = await getLastFetchTime();
        
        if (!canFetch) {
            return res.status(429).json({ 
                success: false, 
                error: 'Rate limit exceeded',
                message: `Please wait ${Math.ceil(timeRemaining / 60000)} minutes before fetching again.`,
                nextAllowedTime 
            });
        }
        
        const { tournamentId, divisionId, levelId } = req.body;
        
        const payload = {
            getTournamentGameList: 'TournamentPublicData',
            filterBy: 'division',
            filterRange: 'all',
            tournamentId: tournamentId || 17,
            divisionId: divisionId || 45,
            levelId: levelId || 6,
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
        
        // Save raw response
        await fs.writeFile('csv/response_payload.json', JSON.stringify(data, null, 2));
        
        const games = [];
        
        if (data.resp && data.data) {
            for (const game of data.data) {
                const gameNumber = game.gameNumber || '';
                const gameDate = game.game_date || '';
                const startTime = game.startTime || '';
                
                let dateStr = '';
                if (gameDate && startTime) {
                    const timeWithoutSeconds = startTime.split(':').slice(0, 2).join(':');
                    dateStr = `${gameDate} ${timeWithoutSeconds}`;
                } else if (gameDate) {
                    dateStr = gameDate;
                }
                
                const locationName = game.locationName || '';
                const address1 = game.address1 || '';
                const completeAddress = game.complete_address || '';
                
                let location = '';
                if (locationName) {
                    location = address1 || completeAddress 
                        ? `${locationName}, ${address1 || completeAddress}`
                        : locationName;
                }
                
                const status = game.status || '';
                const homeScore = status.toLowerCase() === 'completed' ? (game.homeTotalGoals || '') : '';
                const awayScore = status.toLowerCase() === 'completed' ? (game.awayTotalGoals || '') : '';
                
                games.push({
                    game_id: gameNumber ? `#${gameNumber}` : '',
                    tournament_name: game.tournamentName || '',
                    division_name: game.divisionName || '',
                    level_name: game.levelName || '',
                    date: dateStr,
                    location_name: locationName,
                    location: location,
                    home_team: (game.homeTeamName || '').trim(),
                    away_team: (game.awayTeamName || '').trim(),
                    home_score: homeScore.toString(),
                    away_score: awayScore.toString(),
                    status: status
                });
            }
        }
        
        // Save to CSV
        const csv = convertToCSV(games);
        await fs.writeFile('csv/hockey_games.csv', csv);
        
        // Save last fetch timestamp
        const now = Date.now();
        await saveLastFetchTime(now);
        
        res.json({ 
            success: true, 
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
    try {
        const csvContent = await fs.readFile('csv/hockey_games.csv', 'utf-8');
        const games = parseCSV(csvContent);
        
        const tournaments = [...new Set(games.map(g => g.tournament_name))].filter(Boolean);
        const divisions = [...new Set(games.map(g => g.division_name))].filter(Boolean);
        const levels = [...new Set(games.map(g => g.level_name))].filter(Boolean);
        
        res.json({ tournaments, divisions, levels });
    } catch (error) {
        res.json({ tournaments: ['E.H.L.'], divisions: ['Moins de 15 ans'], levels: ['B'] });
    }
});

// Analyze games and generate tables
app.post('/api/analyze', async (req, res) => {
    try {
        const { tournament, division, level } = req.body;
        
        const csvContent = await fs.readFile('csv/hockey_games.csv', 'utf-8');
        const allGames = parseCSV(csvContent);
        
        // Filter games
        const games = allGames.filter(g => 
            g.tournament_name === tournament &&
            g.division_name === division &&
            g.level_name === level
        );
        
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

// Download CSV

// Get last fetch time and check if scraping is allowed
async function getLastFetchTime() {
    try {
        const data = await fs.readFile(LAST_FETCH_FILE, 'utf-8');
        const { lastFetchTime } = JSON.parse(data);
        const now = Date.now();
        const timeElapsed = now - lastFetchTime;
        const timeRemaining = SCRAPE_COOLDOWN_MS - timeElapsed;
        
        const canFetch = timeElapsed >= SCRAPE_COOLDOWN_MS;
        const nextAllowedTime = canFetch ? null : lastFetchTime + SCRAPE_COOLDOWN_MS;
        
        return { canFetch, nextAllowedTime, timeRemaining, lastFetchTime };
    } catch (error) {
        // File doesn't exist or is invalid - allow fetch
        return { canFetch: true, nextAllowedTime: null, timeRemaining: 0, lastFetchTime: null };
    }
}

// Save last fetch time
async function saveLastFetchTime(timestamp) {
    await fs.writeFile(LAST_FETCH_FILE, JSON.stringify({ lastFetchTime: timestamp }, null, 2));
}

app.get('/api/download/csv', async (req, res) => {
    try {
        const csvPath = path.join(__dirname, 'csv', 'hockey_games.csv');
        res.download(csvPath, 'hockey_games.csv');
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
        
        if (game.status === 'Completed' && game.home_score && game.away_score) {
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
        } else if (['Initialized', 'Setup', 'In Progress'].includes(game.status)) {
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
        .filter(g => g.status === 'Completed' && g.home_score && g.away_score)
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
        g.status !== 'Completed' && g.home_team && g.away_team
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
        .filter(g => g.status === 'Completed' && g.home_score && g.away_score)
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
        const { tournament, division, level } = req.body;
        
        const csvContent = await fs.readFile('csv/hockey_games.csv', 'utf-8');
        const allGames = parseCSV(csvContent);
        
        const games = allGames.filter(g => 
            g.tournament_name === tournament &&
            g.division_name === division &&
            g.level_name === level
        );
        
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
        const { tournament, division, level } = req.body;
        
        const csvContent = await fs.readFile('csv/hockey_games.csv', 'utf-8');
        const allGames = parseCSV(csvContent);
        
        const games = allGames.filter(g => 
            g.tournament_name === tournament &&
            g.division_name === division &&
            g.level_name === level
        );
        
        const teamElos = buildEloRatings(games);
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
