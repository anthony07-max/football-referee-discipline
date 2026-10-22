"""Combine the raw season files into one tidy match-level table: data/processed/matches.csv."""
import re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
DIV_NAME = {"E0": "Premier League", "E2": "League One"}
KEEP = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "HTHG", "HTAG", "Referee",
        "HS", "AS", "HF", "AF", "HY", "AY", "HR", "AR", "AvgH", "AvgD", "AvgA", "BbAvH", "BbAvD", "BbAvA", "B365H", "B365D", "B365A"]


def norm_referee(name) -> str | None:
    """Normalise referee names to 'Initial Surname' (e.g. 'Rob Harris' -> 'R Harris')."""
    if not isinstance(name, str) or not name.strip():
        return None
    name = re.sub(r"\s+", " ", name.replace(".", " ").replace("\xa0", " ")).strip()
    parts = name.split(" ")
    if len(parts) == 1:
        return parts[0].title()
    first, surname = parts[0], " ".join(parts[1:])
    return f"{first[0].upper()} {surname.title()}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for f in sorted(RAW.glob("E*_*.csv")):
        div, code = f.stem.split("_")
        d = pd.read_csv(f, encoding="latin1", on_bad_lines="skip")
        d = d.dropna(subset=["HomeTeam", "AwayTeam"])
        d = d[[c for c in KEEP if c in d.columns]].copy()
        start = 2000 + int(code[:2])
        d["season"] = f"{start}/{str(start + 1)[-2:]}"
        d["season_start"] = start
        d["div"] = div
        d["league"] = DIV_NAME[div]
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce", format="mixed")
    df["referee"] = df["Referee"].map(norm_referee)
    # pre-match market 1X2 odds (market average where available, else Bet365)
    for side in ("H", "D", "A"):
        cols = [c for c in (f"Avg{side}", f"BbAv{side}", f"B365{side}") if c in df]
        df[f"odds_{side.lower()}"] = df[cols].bfill(axis=1).iloc[:, 0]
    num = ["FTHG", "FTAG", "HS", "AS", "HF", "AF", "HY", "AY", "HR", "AR"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    df = df.rename(columns={"HomeTeam": "home", "AwayTeam": "away", "FTHG": "hg", "FTAG": "ag", "FTR": "result",
                            "HS": "hs", "AS": "as_", "HF": "hf", "AF": "af", "HY": "hy", "AY": "ay", "HR": "hr", "AR": "ar"})
    df = df.dropna(subset=["hy", "ay", "hr", "ar"])
    df["yellows"] = df.hy + df.ay
    df["reds"] = df.hr + df.ar
    df["fouls"] = df.hf + df.af
    # booking points as defined by football-data.co.uk: 10 per yellow, 25 per red
    df["booking_pts"] = 10 * df.yellows + 25 * df.reds
    cols = ["league", "div", "season", "season_start", "date", "home", "away", "hg", "ag", "result", "referee",
            "hs", "as_", "hf", "af", "hy", "ay", "hr", "ar", "yellows", "reds", "fouls", "booking_pts", "odds_h", "odds_d", "odds_a"]
    df = df[cols].sort_values(["date", "div"]).reset_index(drop=True)
    df.to_csv(OUT / "matches.csv", index=False, date_format="%Y-%m-%d")
    print(df.groupby("league").agg(matches=("home", "size"), seasons=("season", "nunique"),
                                   referees=("referee", "nunique"), missing_ref=("referee", lambda s: s.isna().sum())))
    print("file size MB:", round((OUT / "matches.csv").stat().st_size / 1e6, 2))


if __name__ == "__main__":
    main()
