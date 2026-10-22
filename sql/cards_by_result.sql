-- Team-match view: cards received by result for that team
WITH team_matches AS (
    SELECT league, season_start, hy AS yellows, hr AS reds, hf AS fouls, 'home' AS venue,
           CASE result WHEN 'H' THEN 'Win' WHEN 'D' THEN 'Draw' ELSE 'Loss' END AS team_result
    FROM matches
    UNION ALL
    SELECT league, season_start, ay, ar, af, 'away',
           CASE result WHEN 'A' THEN 'Win' WHEN 'D' THEN 'Draw' ELSE 'Loss' END
    FROM matches
)
SELECT league, team_result, COUNT(*) AS team_matches,
       AVG(yellows) AS yellows_pm, AVG(reds) AS reds_pm, AVG(fouls) AS fouls_pm
FROM team_matches
GROUP BY league, team_result
ORDER BY league DESC, team_result;
