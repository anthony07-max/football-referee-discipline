"""Referee discipline analysis: DuckDB SQL layer, shrinkage estimates, statistical tests and charts."""
import json
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PROC, CHARTS, SQL = ROOT / "data" / "processed", ROOT / "charts", ROOT / "sql"
CHARTS.mkdir(exist_ok=True)
RECENT = 2019          # "recent era" for referee rankings: 2019/20 to 2025/26
MIN_MATCHES = 40
COLORS = {"Premier League": "#3d195b", "League One": "#e03a3e"}
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.3, "font.size": 10})
F = {}  # key findings


def q(con, name, **params):
    return con.execute((SQL / f"{name}.sql").read_text(), params or None).df()


def poisson_ci(k, alpha=0.05):
    lo = np.where(k > 0, stats.gamma.ppf(alpha / 2, k), 0.0)
    hi = stats.gamma.ppf(1 - alpha / 2, k + 1)
    return lo, hi


def shrink(df, obs, exp):
    """Gamma-Poisson empirical Bayes: obs ~ Poisson(theta * exp), theta ~ Gamma(a, a) (prior mean 1)."""
    ratio = df[obs] / df[exp]
    w = df[exp] / df[exp].sum()
    mean = np.sum(w * ratio)
    var_total = np.sum(w * (ratio - mean) ** 2)
    var_poisson = np.sum(w / df[exp])           # expected sampling variance of the ratio
    tau2 = max(var_total - var_poisson, 1e-6)  # between-referee variance
    a = 1 / tau2
    post_a, post_b = df[obs] + a, df[exp] + a
    df[f"{obs}_index_raw"] = ratio
    lo, hi = poisson_ci(df[obs].to_numpy())
    df[f"{obs}_raw_lo"], df[f"{obs}_raw_hi"] = lo / df[exp], hi / df[exp]
    df[f"{obs}_index"] = post_a / post_b
    df[f"{obs}_lo"] = stats.gamma.ppf(0.025, post_a, scale=1 / post_b)
    df[f"{obs}_hi"] = stats.gamma.ppf(0.975, post_a, scale=1 / post_b)
    return df, float(np.sqrt(tau2))


def main():
    m = pd.read_csv(PROC / "matches.csv", parse_dates=["date"])
    con = duckdb.connect()
    con.register("matches", m)

    # ---------------- 1. trends ----------------
    tr = q(con, "season_trends")
    tr.to_csv(PROC / "season_trends.csv", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
    for lg, g in tr.groupby("league"):
        axes[0].plot(g.season_start, g.yellows_pm, marker="o", ms=3, label=lg, color=COLORS[lg])
        axes[1].plot(g.season_start, g.fouls_pm, marker="o", ms=3, label=lg, color=COLORS[lg])
        axes[2].plot(g.season_start, 100 * g.yellows_per_foul, marker="o", ms=3, label=lg, color=COLORS[lg])
    for ax, t in zip(axes, ["Yellow cards per match", "Fouls per match", "Yellow cards per 100 fouls"]):
        ax.set_title(t); ax.set_xlabel("Season (start year)")
    axes[0].legend()
    fig.suptitle("Discipline trends, 2000/01 to 2025/26 (football-data.co.uk)", weight="bold")
    fig.tight_layout(); fig.savefig(CHARTS / "01_season_trends.png"); plt.close(fig)
    for lg in COLORS:
        g = tr[tr.league == lg].set_index("season_start")
        slope = np.polyfit(g.index, g.yellows_pm, 1)[0]
        F[f"{lg}_trend"] = {
            "yellows_2000": round(g.loc[2000, "yellows_pm"], 2), "yellows_2025": round(g.loc[2025, "yellows_pm"], 2),
            "fouls_2000": round(g.loc[2000, "fouls_pm"], 1), "fouls_2025": round(g.loc[2025, "fouls_pm"], 1),
            "yellows_per_100_fouls_2000": round(100 * g.loc[2000, "yellows_per_foul"], 1),
            "yellows_per_100_fouls_2025": round(100 * g.loc[2025, "yellows_per_foul"], 1),
            "reds_2000": round(g.loc[2000, "reds_pm"], 3), "reds_2025": round(g.loc[2025, "reds_pm"], 3),
            "yellow_slope_per_season": round(slope, 3),
            "peak_yellow_season": g.yellows_pm.idxmax(), "peak_yellows": round(g.yellows_pm.max(), 2),
        }

    # ---------------- 2. referees with shrinkage ----------------
    refs = q(con, "referee_summary", since=RECENT)
    out = []
    for lg, g in refs.groupby("league"):
        g = g[g.matches >= MIN_MATCHES].copy()
        g, sd_y = shrink(g, "yellows", "expected_yellows")
        g, sd_r = shrink(g, "reds", "expected_reds")
        # dispersion test: are referee differences bigger than chance?
        chi2 = float(((g.yellows - g.expected_yellows * g.yellows.sum() / g.expected_yellows.sum()) ** 2
                      / (g.expected_yellows * g.yellows.sum() / g.expected_yellows.sum())).sum())
        dof = len(g) - 1
        g["yellows_pm"] = g.yellows / g.matches
        g["fouls_pm"] = g.fouls / g.matches
        g["fouls_index"] = g.fouls / g.expected_fouls
        F[f"{lg}_referees"] = {
            "referees": len(g), "matches": int(g.matches.sum()), "between_ref_sd_pct": round(100 * sd_y, 1),
            "red_between_ref_sd_pct": round(100 * sd_r, 1),
            "dispersion_chi2": round(chi2, 1), "dof": dof, "p_value": float(stats.chi2.sf(chi2, dof)),
            "strictest": g.nlargest(3, "yellows_index")[["referee", "matches", "yellows_pm", "yellows_index", "yellows_lo", "yellows_hi"]].round(3).to_dict("records"),
            "most_lenient": g.nsmallest(3, "yellows_index")[["referee", "matches", "yellows_pm", "yellows_index", "yellows_lo", "yellows_hi"]].round(3).to_dict("records"),
            "corr_foul_index_vs_card_index": round(float(np.corrcoef(g.fouls_index, g.yellows_index_raw)[0, 1]), 2),
        }
        out.append(g)
    refs = pd.concat(out)
    refs.round(4).to_csv(PROC / "referee_stats.csv", index=False)

    pl = refs[refs.league == "Premier League"].sort_values("yellows_index")
    fig, ax = plt.subplots(figsize=(9, 0.32 * len(pl) + 1.5))
    y = np.arange(len(pl))
    ax.errorbar(pl.yellows_index_raw, y + 0.18, xerr=[pl.yellows_index_raw - pl.yellows_raw_lo, pl.yellows_raw_hi - pl.yellows_index_raw],
                fmt="o", color="#bbbbbb", ms=4, label="Raw rate (exact Poisson 95% CI)")
    ax.errorbar(pl.yellows_index, y - 0.18, xerr=[pl.yellows_index - pl.yellows_lo, pl.yellows_hi - pl.yellows_index],
                fmt="o", color=COLORS["Premier League"], ms=5, label="Shrunk estimate (empirical Bayes 95% interval)")
    ax.axvline(1, color="k", lw=1, ls="--")
    ax.set_yticks(y, [f"{r} ({n})" for r, n in zip(pl.referee, pl.matches)])
    ax.set_xlabel("Yellow cards relative to league-season average (1.0 = average)")
    ax.set_title(f"Premier League referees, 2019/20 to 2025/26 (min {MIN_MATCHES} matches)", weight="bold")
    ax.legend(loc="lower right", fontsize=8); fig.tight_layout(); fig.savefig(CHARTS / "02_pl_referee_card_index.png"); plt.close(fig)

    # funnel plot (both leagues)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    for ax, (lg, g) in zip(axes, refs.groupby("league", sort=False)):
        ax.scatter(g.expected_yellows, g.yellows_index_raw, s=18, color=COLORS[lg], alpha=0.75)
        e = np.linspace(g.expected_yellows.min() * 0.9, g.expected_yellows.max() * 1.05, 200)
        for z, ls in ((1.96, "--"), (3.09, ":")):
            ax.plot(e, 1 + z / np.sqrt(e), "k", ls=ls, lw=0.8); ax.plot(e, 1 - z / np.sqrt(e), "k", ls=ls, lw=0.8)
        ax.axhline(1, color="k", lw=0.8)
        for _, r in pd.concat([g.nlargest(3, "yellows_index_raw"), g.nsmallest(3, "yellows_index_raw")]).iterrows():
            ax.annotate(r.referee, (r.expected_yellows, r.yellows_index_raw), fontsize=7, xytext=(3, 3), textcoords="offset points")
        ax.set_title(f"{lg}: funnel plot ({len(g)} referees)"); ax.set_xlabel("Expected yellow cards (exposure)")
    axes[0].set_ylabel("Observed / expected yellows")
    fig.suptitle("Is a referee's card rate more extreme than chance? (dashed 95%, dotted 99.8% Poisson limits), 2019/20 to 2025/26", weight="bold", fontsize=10)
    fig.tight_layout(); fig.savefig(CHARTS / "03_referee_funnel.png"); plt.close(fig)

    # ---------------- 3. home vs away ----------------
    ha = q(con, "home_away")
    ha.to_csv(PROC / "home_away.csv", index=False)
    for _, r in ha.iterrows():
        lg = r.league
        g = m[m.league == lg]
        t = stats.ttest_rel(g.ay, g.hy)
        # does the away-card excess survive controlling for fouls? Poisson GLM on team-match rows
        tm = pd.concat([pd.DataFrame({"y": g.hy, "fouls": g.hf, "away": 0, "season": g.season}),
                        pd.DataFrame({"y": g.ay, "fouls": g.af, "away": 1, "season": g.season})]).dropna()
        glm = smf.glm("y ~ away + np.log1p(fouls) + C(season)", tm, family=sm.families.Poisson()).fit()
        F[f"{lg}_home_away"] = {
            "home_yellows_pm": round(r.home_yellows_pm, 2), "away_yellows_pm": round(r.away_yellows_pm, 2),
            "away_excess_pct": round(100 * (r.away_yellows_pm / r.home_yellows_pm - 1), 1),
            "home_fouls_pm": round(r.home_fouls_pm, 2), "away_fouls_pm": round(r.away_fouls_pm, 2),
            "home_yellows_per_100_fouls": round(100 * r.home_yellows_per_foul, 1), "away_yellows_per_100_fouls": round(100 * r.away_yellows_per_foul, 1),
            "away_reds_pm": round(r.away_reds_pm, 3), "home_reds_pm": round(r.home_reds_pm, 3),
            "paired_t_p": float(t.pvalue),
            "away_rate_ratio_controlling_fouls": round(float(np.exp(glm.params["away"])), 3),
            "rr_ci": [round(float(np.exp(x)), 3) for x in glm.conf_int().loc["away"]],
        }
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.3), sharey=True)
    for ax, lg in zip(axes, COLORS):
        g = tr[tr.league == lg]
        ax.plot(g.season_start, g.home_yellows_pm, marker="o", ms=3, label="Home team", color="#2a9d8f")
        ax.plot(g.season_start, g.away_yellows_pm, marker="o", ms=3, label="Away team", color="#e76f51")
        ax.axvspan(2019.6, 2020.9, color="grey", alpha=0.15, label="Mostly behind closed doors")
        ax.set_title(f"{lg}: yellow cards per team per match"); ax.set_xlabel("Season (start year)")
    axes[0].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(CHARTS / "04_home_vs_away_cards.png"); plt.close(fig)
    # behind-closed-doors natural experiment (2020/21 PL; L1 2020/21 also played without fans)
    bcd = {}
    for lg in COLORS:
        g = tr[tr.league == lg].set_index("season_start")
        gap = (g.away_yellows_pm - g.home_yellows_pm)
        bcd[lg] = {"gap_2020_21": round(gap.loc[2020], 3),
                   "gap_mean_other_seasons_2015_2025": round(gap.loc[[s for s in range(2015, 2026) if s not in (2019, 2020)]].mean(), 3)}
    F["behind_closed_doors"] = bcd

    # ---------------- 4. cards vs fouls and outcomes ----------------
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for lg in COLORS:
        g = m[m.league == lg].dropna(subset=["fouls"])
        b = g.groupby(pd.cut(g.fouls, bins=range(0, 46, 3)), observed=True).agg(y=("yellows", "mean"), n=("yellows", "size"))
        b = b[b.n >= 30]
        axes[0].plot([iv.mid for iv in b.index], b.y, marker="o", color=COLORS[lg], label=lg)
        F[f"{lg}_fouls_corr"] = round(float(g[["fouls", "yellows"]].corr().iloc[0, 1]), 3)
    axes[0].set_xlabel("Total fouls in match"); axes[0].set_ylabel("Mean yellow cards"); axes[0].legend()
    axes[0].set_title("More fouls, more cards (match level)")
    cr = q(con, "cards_by_result")
    cr.to_csv(PROC / "cards_by_result.csv", index=False)
    order = ["Win", "Draw", "Loss"]
    w = 0.38
    for i, lg in enumerate(COLORS):
        g = cr[cr.league == lg].set_index("team_result").loc[order]
        axes[1].bar(np.arange(3) + (i - 0.5) * w, g.yellows_pm, w, color=COLORS[lg], label=lg)
        F[f"{lg}_cards_by_result"] = g[["yellows_pm", "reds_pm", "fouls_pm"]].round(3).to_dict("index")
    axes[1].set_xticks(range(3), order); axes[1].set_ylabel("Yellow cards per team per match")
    axes[1].set_title("Losing teams collect more cards"); axes[1].legend()
    fig.tight_layout(); fig.savefig(CHARTS / "05_cards_fouls_outcome.png"); plt.close(fig)

    # red card impact versus pre-match expectation (bookmaker implied probabilities)
    o = m.dropna(subset=["odds_h", "odds_d", "odds_a"]).copy()
    inv = 1 / o[["odds_h", "odds_d", "odds_a"]]
    p = inv.div(inv.sum(axis=1), axis=0)
    o["p_h"], o["p_d"], o["p_a"] = p.odds_h, p.odds_d, p.odds_a
    rows = []
    for side, opp, red, res_w in (("h", "a", "hr", "H"), ("a", "h", "ar", "A")):
        t = pd.DataFrame({"league": o.league, "red": (o[red] > 0) & (o["hr" if side == "a" else "ar"] == 0),
                          "exp_pts": 3 * o[f"p_{side}"] + o.p_d,
                          "pts": np.select([o.result == res_w, o.result == "D"], [3, 1], 0)})
        rows.append(t)
    rc = pd.concat(rows)
    rc_s = rc.groupby(["league", "red"]).agg(n=("pts", "size"), pts=("pts", "mean"), exp_pts=("exp_pts", "mean")).reset_index()
    rc_s["pts_vs_expected"] = rc_s.pts - rc_s.exp_pts
    rc_s.to_csv(PROC / "red_card_impact.csv", index=False)
    F["red_card_impact"] = rc_s.round(3).to_dict("records")
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    sub = rc_s[rc_s.red]
    x = np.arange(len(sub))
    ax.bar(x - 0.2, sub.exp_pts, 0.4, color="#999999", label="Expected (pre-match odds)")
    ax.bar(x + 0.2, sub.pts, 0.4, color=[COLORS[l] for l in sub.league], label="Actual")
    for xi, (e, a) in enumerate(zip(sub.exp_pts, sub.pts)):
        ax.text(xi + 0.2, a + 0.03, f"{a - e:+.2f}", ha="center", fontsize=9, weight="bold")
    ax.set_xticks(x, sub.league); ax.set_ylabel("Points per match")
    ax.set_title("Teams shown a red card (opponent not): points vs expectation", weight="bold", fontsize=10)
    ax.legend(); fig.tight_layout(); fig.savefig(CHARTS / "06_red_card_impact.png"); plt.close(fig)

    # match-level Poisson model of yellow cards
    mm = m.dropna(subset=["fouls"]).copy()
    mm["goal_diff_abs"] = (mm.hg - mm.ag).abs()
    mm["draw"] = (mm.result == "D").astype(int)
    glm = smf.glm("yellows ~ np.log1p(fouls) + C(league) + season_start + goal_diff_abs", mm, family=sm.families.Poisson()).fit()
    F["match_glm"] = {k: round(float(v), 4) for k, v in np.exp(glm.params).items()}
    F["match_glm_pvalues"] = {k: float(v) for k, v in glm.pvalues.items()}

    # ---------------- 5. League One vs Premier League ----------------
    rec = m[m.season_start >= RECENT]
    comp = rec.groupby("league").agg(yellows_pm=("yellows", "mean"), reds_pm=("reds", "mean"), fouls_pm=("fouls", "mean"),
                                     matches=("yellows", "size"), red_share=("reds", lambda s: (s > 0).mean()))
    comp["yellows_per_100_fouls"] = 100 * rec.groupby("league").yellows.sum() / rec.groupby("league").fouls.sum()
    comp.round(3).to_csv(PROC / "league_comparison_recent.csv")
    F["league_comparison_2019_2025"] = comp.round(3).to_dict("index")
    tt = stats.mannwhitneyu(rec[rec.league == "League One"].yellows, rec[rec.league == "Premier League"].yellows)
    F["league_comparison_mwu_p"] = float(tt.pvalue)
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.8))
    metrics = [("yellows_pm", "Yellows per match"), ("reds_pm", "Reds per match"), ("fouls_pm", "Fouls per match"),
               ("yellows_per_100_fouls", "Yellows per 100 fouls")]
    for ax, (c, t) in zip(axes, metrics):
        vals = comp.loc[list(COLORS), c]
        ax.bar(vals.index, vals.values, color=[COLORS[l] for l in vals.index])
        for i, v in enumerate(vals.values):
            ax.text(i, v, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
        ax.set_title(t); ax.tick_params(axis="x", labelsize=8)
    fig.suptitle("League One vs Premier League, 2019/20 to 2025/26", weight="bold")
    fig.tight_layout(); fig.savefig(CHARTS / "07_league_one_vs_premier_league.png"); plt.close(fig)

    # distribution of referee strictness, both leagues
    fig, ax = plt.subplots(figsize=(8, 4))
    for lg in COLORS:
        g = refs[refs.league == lg]
        ax.hist(g.yellows_index, bins=np.arange(0.7, 1.35, 0.025), alpha=0.6, color=COLORS[lg], label=f"{lg} ({len(g)} refs)")
    ax.axvline(1, color="k", ls="--", lw=1)
    ax.set_xlabel("Shrunk yellow-card index (1.0 = league-season average)"); ax.set_ylabel("Referees")
    ax.set_title("How much do referees differ? (2019/20 to 2025/26)", weight="bold"); ax.legend()
    fig.tight_layout(); fig.savefig(CHARTS / "08_referee_spread.png"); plt.close(fig)

    (PROC / "key_findings.json").write_text(json.dumps(F, indent=2, default=lambda x: x.item() if hasattr(x, "item") else str(x)))
    print(json.dumps(F, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


if __name__ == "__main__":
    main()
