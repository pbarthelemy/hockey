User: In a fourth python file named elo_games.py, we will predict upcoming games.
1- filter for E.H.L.,Moins de 15 ans,B only.
2-build the ELO rating of the teams
2- predict for the upcoming games using the method below.

both the elo method and the predictor are descrided here https://medium.com/@sameerkoppolu/predicting-the-results-of-nba-matches-using-elo-rating-system-and-pythagorean-expectation-4b8ee6ec577



GitHub Copilot: Searched codebase for "In a fourth python file named elo_games.py, we will predict upcoming games.
1- filter for E.H.L.,Moins de 15 ans,B only.
2-build the ELO rating of the teams
2- predict for the upcoming games using the method below.

both the elo method and the predictor are descrided here https://medium.com/@sameerkoppolu/predicting-the-results-of-nba-matches-using-elo-rating-system-and-pythagorean-expectation-4b8ee6ec577

", 14 results

I'll help you create an `elo_games.py` file that implements ELO ratings and predictions for upcoming games. Let me first fetch the Medium article to understand the methodology, then examine your existing files. 

Using "Fetch Web Page"

Fetched https://medium.com/@sameerkoppolu/predicting-the-results-of-nba-matches-using-elo-rating-system-and-pythagorean-expectation-4b8ee6ec577

Read [](file:///home/philippe/Documents/framagit/scoresheet/predictor_games.py#1-1), lines 1 to 50

Read [](file:///home/philippe/Documents/framagit/scoresheet/scrape_games.py#1-1), lines 1 to 50

Let me also check the data files to understand the structure better: 

Ran terminal command:  head -20 /home/philippe/Documents/framagit/scoresheet/hockey_games.csv

Now let me check the predictions.csv structure and read more of the existing predictor file: 

Ran terminal command:  head -10 /home/philippe/Documents/framagit/scoresheet/predictions.csv

Read [](file:///home/philippe/Documents/framagit/scoresheet/predictor_games.py#50-50), lines 50 to 150

Perfect! Now I have enough context. Let me create the `elo_games.py` file that implements the ELO rating system and Pythagorean expectation as described in the Medium article: 

Created [](file:///home/philippe/Documents/framagit/scoresheet/elo_games.py)

Great! Now let's test the script to make sure it works: 

Ran terminal command:  python3 elo_games.py

Perfect! The script is working well. Let me verify that the output files were created: 

Ran terminal command:  ls -lh /home/philippe/Documents/framagit/scoresheet/elo_predictions.*

Excellent! Let me also check a sample of the CSV output to make sure it's formatted correctly: 

Ran terminal command:  head -5 /home/philippe/Documents/framagit/scoresheet/elo_predictions.csv

Perfect! Everything is working as expected. Let me create a summary of what was implemented:

## Summary

I've successfully created elo_games.py that implements **ELO rating system** and **Pythagorean expectation** to predict upcoming hockey games for the **E.H.L., Moins de 15 ans, B** division.

### Key Features:

**1. Data Filtering**
   - Filters games for "E.H.L., Moins de 15 ans, B" only
   - Found 96 games (81 completed, 15 upcoming)

**2. ELO Rating System**
   - Initial ELO: 1500 for all teams
   - K-factor: 20 (controls rating change magnitude)
   - Home advantage: +100 ELO points
   - Margin of victory multiplier included
   - Updates ratings chronologically through completed games

**3. Pythagorean Expectation**
   - Calculates expected win percentage based on goals scored vs. allowed
   - Formula: `pyth = (GF^2.37) / (GF^2.37 + GA^2.37)`
   - Uses logit model for prediction

**4. Combined Prediction**
   - Averages both ELO and Pythagorean methods
   - Provides win probabilities for home and away teams

**5. Output Files**
   - **elo_predictions.csv**: Detailed predictions with probabilities
   - **elo_predictions.html**: Interactive HTML report with team rankings and predictions

### Current Top Teams (by ELO):
1. WARRIORS ST-LAURENT (1669.5)
2. DIABLES M.R.O. (1605.9)
3. DEVILS M.R.O. (1601.1)
4. PANTHERES LASALLE (1565.0)

The script successfully predicted 15 upcoming games with confidence levels ranging from 51.7% to 90.1%.

Made changes.