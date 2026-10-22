"""Download English league results CSVs (Premier League E0 and League One E2) from football-data.co.uk.

Data: https://www.football-data.co.uk/englandm.php  (free historical data, credit Football-Data.co.uk).
Files are cached in data/raw/ and only fetched once; a polite pause is used between requests.
"""
import time
from pathlib import Path
import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
DIVISIONS = {"E0": "Premier League", "E2": "League One"}
FIRST_SEASON, LAST_SEASON = 2000, 2025   # season start years: 2000/01 ... 2025/26
BASE = "https://www.football-data.co.uk/mmz4281/{code}/{div}.csv"


def season_code(start: int) -> str:
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "football-referee-discipline (portfolio project; github.com/anthony07-max)"
    for div in DIVISIONS:
        for start in range(FIRST_SEASON, LAST_SEASON + 1):
            code = season_code(start)
            out = RAW / f"{div}_{code}.csv"
            if out.exists() and out.stat().st_size > 1000:
                continue
            url = BASE.format(code=code, div=div)
            r = session.get(url, timeout=60)
            r.raise_for_status()
            out.write_bytes(r.content)
            print(f"downloaded {url} ({len(r.content)/1024:.0f} KB)")
            time.sleep(1)
    print("raw files:", len(list(RAW.glob("*.csv"))))


if __name__ == "__main__":
    main()
