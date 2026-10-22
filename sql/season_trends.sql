-- Discipline per match by league and season
SELECT league, season, season_start,
       COUNT(*)                         AS matches,
       AVG(yellows)                     AS yellows_pm,
       AVG(reds)                        AS reds_pm,
       AVG(fouls)                       AS fouls_pm,
       AVG(hy)                          AS home_yellows_pm,
       AVG(ay)                          AS away_yellows_pm,
       SUM(yellows) / SUM(fouls)        AS yellows_per_foul,
       AVG(CASE WHEN reds > 0 THEN 1.0 ELSE 0 END) AS share_matches_with_red
FROM matches
GROUP BY league, season, season_start
ORDER BY league, season_start;
