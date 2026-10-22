-- Home vs away discipline by league
SELECT league,
       COUNT(*)                    AS matches,
       AVG(hy)                     AS home_yellows_pm,
       AVG(ay)                     AS away_yellows_pm,
       AVG(hr)                     AS home_reds_pm,
       AVG(ar)                     AS away_reds_pm,
       AVG(hf)                     AS home_fouls_pm,
       AVG(af)                     AS away_fouls_pm,
       SUM(hy) / SUM(hf)           AS home_yellows_per_foul,
       SUM(ay) / SUM(af)           AS away_yellows_per_foul
FROM matches
GROUP BY league ORDER BY league DESC;
