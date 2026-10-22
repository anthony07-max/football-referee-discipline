-- Referee totals with a season-adjusted expectation: each match contributes the league-season average,
-- so referees who officiated in high-card eras are not penalised for the era.
WITH season_avg AS (
    SELECT league, season, AVG(yellows) AS exp_y, AVG(reds) AS exp_r, AVG(fouls) AS exp_f
    FROM matches GROUP BY league, season
)
SELECT m.league, m.referee,
       COUNT(*)                AS matches,
       MIN(m.season)           AS first_season,
       MAX(m.season)           AS last_season,
       SUM(m.yellows)          AS yellows,
       SUM(s.exp_y)            AS expected_yellows,
       SUM(m.reds)             AS reds,
       SUM(s.exp_r)            AS expected_reds,
       SUM(m.fouls)            AS fouls,
       SUM(s.exp_f)            AS expected_fouls,
       SUM(m.hy)               AS home_yellows,
       SUM(m.ay)               AS away_yellows
FROM matches m JOIN season_avg s USING (league, season)
WHERE m.referee IS NOT NULL AND m.season_start >= $since
GROUP BY m.league, m.referee
ORDER BY m.league, matches DESC;
