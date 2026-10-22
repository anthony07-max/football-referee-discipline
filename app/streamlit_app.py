"""Interactive referee discipline dashboard. Run: streamlit run app/streamlit_app.py"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"
st.set_page_config(page_title="Referee discipline: Premier League & League One", layout="wide")


@st.cache_data
def load():
    m = pd.read_csv(PROC / "matches.csv", parse_dates=["date"])
    refs = pd.read_csv(PROC / "referee_stats.csv")
    trends = pd.read_csv(PROC / "season_trends.csv")
    kf = json.loads((PROC / "key_findings.json").read_text())
    return m, refs, trends, kf


m, refs, trends, kf = load()
st.title("Referee discipline in English football, 2000/01 to 2025/26")
st.caption("Premier League and League One match data from football-data.co.uk. Built by Anthony Adusei-Poku (@anthony07-max).")

league = st.sidebar.radio("League", ["Premier League", "League One"])
lo, hi = int(m.season_start.min()), int(m.season_start.max())
yrs = st.sidebar.slider("Seasons (start year)", lo, hi, (lo, hi))
sub = m[(m.league == league) & m.season_start.between(*yrs)]

c = st.columns(4)
c[0].metric("Matches", f"{len(sub):,}")
c[1].metric("Yellows per match", f"{sub.yellows.mean():.2f}")
c[2].metric("Reds per match", f"{sub.reds.mean():.3f}")
c[3].metric("Away vs home yellows", f"{100 * (sub.ay.mean() / sub.hy.mean() - 1):+.1f}%")

tab1, tab2, tab3 = st.tabs(["Trends", "Referees (2019/20 to 2025/26)", "Referee lookup"])
with tab1:
    t = trends[trends.season_start.between(*yrs)]
    metric = st.selectbox("Metric", ["yellows_pm", "reds_pm", "fouls_pm", "yellows_per_foul", "home_yellows_pm", "away_yellows_pm"])
    st.plotly_chart(px.line(t, x="season", y=metric, color="league", markers=True), width="stretch")
with tab2:
    r = refs[refs.league == league].sort_values("yellows_index", ascending=False)
    fig = px.scatter(r, x="yellows_index", y="referee", error_x=r.yellows_hi - r.yellows_index,
                     error_x_minus=r.yellows_index - r.yellows_lo, hover_data=["matches", "yellows_pm", "fouls_pm"],
                     height=28 * len(r) + 120, labels={"yellows_index": "Shrunk yellow-card index (1 = average)"})
    fig.add_vline(x=1, line_dash="dash")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(r[["referee", "matches", "yellows_pm", "yellows_index", "yellows_lo", "yellows_hi", "reds", "fouls_pm"]].round(3),
                 hide_index=True, width="stretch")
with tab3:
    names = sub.referee.value_counts()
    ref = st.selectbox("Referee", names[names >= 10].index)
    rm = sub[sub.referee == ref]
    by = rm.groupby("season").agg(matches=("yellows", "size"), yellows_pm=("yellows", "mean"), reds=("reds", "sum"),
                                  home_y=("hy", "mean"), away_y=("ay", "mean")).reset_index()
    st.plotly_chart(px.bar(by, x="season", y="yellows_pm", hover_data=["matches", "reds"], title=f"{ref}: yellows per match"),
                    width="stretch")
    st.dataframe(rm[["date", "home", "away", "hg", "ag", "hy", "ay", "hr", "ar", "hf", "af"]].sort_values("date", ascending=False),
                 hide_index=True, width="stretch")
st.caption("Card counts follow football-data.co.uk conventions: a second yellow that becomes a red is counted as a red only.")
