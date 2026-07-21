

import duckdb
import pandas as pd
import pydeck as pdk
import streamlit as st

# ------------------------------ CONFIG ------------------------------
PARQUET_PATH = "data/fct_stop_performance.parquet"
STOPS_PATH = "data/stops.parquet"

COL_ROUTE = "route_id"
COL_STOP = "stop_name"
COL_STOP_ID = "stop_id"
COL_DIRECTION = "direction_id"
COL_ARRIVAL_TS = "actual_arrival"
COL_DELAY = "delay_minutes"
COL_ON_TIME = "is_on_time"

EARLY_MIN = 1   # TTC surface standard: <=1 min early
LATE_MIN = 5    # and <=5 min late counts as on time

BUNCH_FACTOR = 0.5   # headway < 50% of that stop's median = bunched
GAP_FACTOR = 1.5     # headway > 150% of median = gap

GITHUB_URL = "https://github.com/shoaib1289/ttc-transit-reliability-pipeline"

st.set_page_config(
    page_title="TTC Transit Reliability Pipeline",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------ STYLE ------------------------------
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

      :root {
        --ink:      #14161A;
        --slate:    #2A2F3A;
        --fog:      #8A93A3;
        --paper:    #F5F6F8;
        --ttc-red:  #DA291C;
        --signal:   #1F9E8C;
      }

      .stApp { background: var(--paper); }
      html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--ink); }
      h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: -0.02em; }

      .masthead {
        border-top: 6px solid var(--ttc-red);
        background: var(--ink);
        color: var(--paper);
        padding: 2.2rem 2.4rem 1.8rem 2.4rem;
      }
      .masthead .eyebrow {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem; letter-spacing: 0.18em; text-transform: uppercase;
        color: var(--ttc-red); margin-bottom: 0.6rem;
      }
      .masthead h1 { font-size: 2.6rem; line-height: 1.05; margin: 0 0 0.6rem 0; color: var(--paper) !important; }
      .masthead p { color: var(--fog); max-width: 62ch; margin: 0; font-size: 0.98rem; }

      .stagestrip { display: flex; flex-wrap: wrap; background: var(--slate); margin-bottom: 2rem; }
      .stage { flex: 1 1 130px; padding: 0.9rem 1rem; border-right: 1px solid rgba(245,246,248,0.12); }
      .stage:last-child { border-right: none; }
      .stage .n { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: var(--ttc-red); letter-spacing: 0.1em; }
      .stage .label { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 0.92rem; color: var(--paper); margin-top: 0.15rem; }
      .stage .sub { font-size: 0.74rem; color: var(--fog); margin-top: 0.15rem; font-family: 'JetBrains Mono', monospace; }

      .statrow { display: flex; flex-wrap: wrap; gap: 1px; background: #DFE3E8; margin-bottom: 2rem; }
      .stat { flex: 1 1 150px; background: var(--paper); padding: 1.1rem 1.2rem; }
      .stat .v { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 1.9rem; line-height: 1; color: var(--ink); }
      .stat .k { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; letter-spacing: 0.09em; text-transform: uppercase; color: var(--fog); margin-top: 0.4rem; }

      .sectionlabel {
        font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.16em;
        text-transform: uppercase; color: var(--ttc-red);
        border-bottom: 1px solid #DFE3E8; padding-bottom: 0.5rem; margin: 2.4rem 0 1.1rem 0;
      }
      .note { color: var(--fog); font-size: 0.87rem; max-width: 70ch; }

      [data-testid="stSidebar"] { background: var(--ink); }
      [data-testid="stSidebar"] * { color: var(--paper) !important; }
      /* Select control: dark surface so forced-white text stays readable */
      [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: var(--slate) !important;
        border-color: rgba(245,246,248,0.25) !important;
      }
      [data-testid="stSidebar"] [data-baseweb="select"] svg { fill: var(--paper); }
      /* Dropdown menu opens in a portal outside the sidebar: give it its own colors */
      [data-baseweb="popover"] li { color: var(--ink) !important; }
      #MainMenu, footer { visibility: hidden; }
      header[data-testid="stHeader"] { display: none; }
      .block-container { padding-top: 1.2rem !important; max-width: 1180px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------ DATA ------------------------------
@st.cache_data
def load_data():
    df = duckdb.sql("SELECT * FROM '{}'".format(PARQUET_PATH)).df()
    df[COL_ARRIVAL_TS] = pd.to_datetime(df[COL_ARRIVAL_TS])
    df["hour"] = df[COL_ARRIVAL_TS].dt.hour
    return df


@st.cache_data
def load_stops():
    try:
        return duckdb.sql("SELECT * FROM '{}'".format(STOPS_PATH)).df()
    except Exception:
        return None


@st.cache_data
def compute_headways(_key):
    """Actual headway = gap between consecutive arrivals at the same
    stop + direction on the same route. Classic LAG-over-partition pattern."""
    hw = df.sort_values(COL_ARRIVAL_TS).copy()
    grp = [COL_ROUTE, COL_STOP_ID, COL_DIRECTION]
    hw["headway_min"] = (
        hw.groupby(grp)[COL_ARRIVAL_TS].diff().dt.total_seconds() / 60
    )
    hw = hw.dropna(subset=["headway_min"])
    # 90-min cap: bigger gaps are collection boundaries, not service gaps
    hw = hw[hw["headway_min"].between(1, 90)]
    med = hw.groupby(grp)["headway_min"].transform("median")
    hw["hw_median"] = med
    hw["bunched"] = hw["headway_min"] < BUNCH_FACTOR * med
    hw["gapped"] = hw["headway_min"] > GAP_FACTOR * med
    return hw


df = load_data()
stops_geo = load_stops()
headways = compute_headways("v1")

# ------------------------------ SIDEBAR ------------------------------
st.sidebar.markdown("### Explore the data")
st.sidebar.caption("Every figure on this page recalculates from these controls.")

routes = sorted(df[COL_ROUTE].unique(), key=lambda r: (len(str(r)), str(r)))
route_choice = st.sidebar.selectbox("Route", ["All routes"] + list(routes))
hour_range = st.sidebar.slider("Hour of arrival", 0, 23, (6, 20))

st.sidebar.markdown("---")
st.sidebar.markdown("**On-time definition**")
early_tol, late_tol = st.sidebar.slider(
    "Minutes early / late still counted as on time", 0, 10, (EARLY_MIN, LATE_MIN)
)
st.sidebar.caption(
    "Default matches the TTC surface-route standard (1 early / 5 late). "
    "Move it and watch every number recalculate  the metric is a policy "
    "choice, not a fact of nature."
)
st.sidebar.markdown("---")
st.sidebar.markdown("[Source code on GitHub]({})".format(GITHUB_URL))

work = df.copy()
work[COL_ON_TIME] = work[COL_DELAY].between(-early_tol, late_tol).astype(int)
work["state"] = pd.cut(
    work[COL_DELAY],
    bins=[-float("inf"), -early_tol, late_tol, float("inf")],
    labels=["Early", "On time", "Late"],
)

filtered = work[work["hour"].between(*hour_range)]
hw_filtered = headways[headways["hour"].between(*hour_range)]
if route_choice != "All routes":
    filtered = filtered[filtered[COL_ROUTE] == route_choice]
    hw_filtered = hw_filtered[hw_filtered[COL_ROUTE] == route_choice]

# ------------------------------ MASTHEAD ------------------------------
st.markdown(
    """
    <div class="masthead">
      <div class="eyebrow">Data engineering portfolio · Shoaib Khan</div>
      <h1>Every bus is late.<br/>Except most of them are early.</h1>
      <p>An end-to-end pipeline that reconstructs TTC arrival events from live GPS feeds,
      models them in dbt, and measures reliability against the published schedule.
      Built to be run, tested, and scheduled, not just charted.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="stagestrip">
      <div class="stage"><div class="n">01 INGEST</div><div class="label">GTFS-Realtime</div><div class="sub">protobuf · 30s poll</div></div>
      <div class="stage"><div class="n">02 LAND</div><div class="label">DuckDB</div><div class="sub">raw snapshots</div></div>
      <div class="stage"><div class="n">03 MODEL</div><div class="label">dbt</div><div class="sub">staging → int → marts</div></div>
      <div class="stage"><div class="n">04 TEST</div><div class="label">dbt test</div><div class="sub">7 tests at scale</div></div>
      <div class="stage"><div class="n">05 ORCHESTRATE</div><div class="label">Airflow</div><div class="sub">Docker · retries</div></div>
      <div class="stage"><div class="n">06 SERVE</div><div class="label">Streamlit</div><div class="sub">parquet serving layer</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------ SCALE STATS ------------------------------
total_arrivals = len(df)
total_routes = df[COL_ROUTE].nunique()
total_stops = df[COL_STOP_ID].nunique()
span_days = (df[COL_ARRIVAL_TS].max() - df[COL_ARRIVAL_TS].min()).days + 1

st.markdown('<div class="sectionlabel">Pipeline output at scale</div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="statrow">
      <div class="stat"><div class="v">{:,}</div><div class="k">Arrival events</div></div>
      <div class="stat"><div class="v">{}</div><div class="k">Routes covered</div></div>
      <div class="stat"><div class="v">{:,}</div><div class="k">Distinct stops</div></div>
      <div class="stat"><div class="v">{}</div><div class="k">Days collected</div></div>
      <div class="stat"><div class="v">SCD 2</div><div class="k">Schedule snapshots</div></div>
    </div>
    """.format(total_arrivals, total_routes, total_stops, span_days),
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class="note">Reconstructing an arrival is the hard part: the realtime feed reports vehicle
    positions, not arrivals. Each event is inferred by matching a GPS reading to its nearest
    scheduled stop within a proximity threshold, then to the nearest scheduled time within a
    30-minute window, a join that, unconstrained, compares billions of row pairs. Pushing the
    temporal filter into the join predicate brought it down to millions and inside memory limits.</p>
    """,
    unsafe_allow_html=True,
)

# ------------------------------ EXPLORER ------------------------------
scope = "the full network" if route_choice == "All routes" else "route {}".format(route_choice)
st.markdown(
    '<div class="sectionlabel">Schedule adherence · {} · {:02d}:00–{:02d}:59</div>'.format(
        scope, hour_range[0], hour_range[1]
    ),
    unsafe_allow_html=True,
)

if filtered.empty:
    st.warning("No arrivals match these filters. Widen the hour range or pick another route.")
    st.stop()

on_time_pct = filtered[COL_ON_TIME].mean() * 100
avg_delay = filtered[COL_DELAY].mean()
early_pct = (filtered[COL_DELAY] < -early_tol).mean() * 100
late_pct = (filtered[COL_DELAY] > late_tol).mean() * 100

st.markdown(
    """
    <div class="statrow">
      <div class="stat"><div class="v">{:.1f}%</div><div class="k">On time</div></div>
      <div class="stat"><div class="v">{:.1f}%</div><div class="k">Running early</div></div>
      <div class="stat"><div class="v">{:.1f}%</div><div class="k">Running late</div></div>
      <div class="stat"><div class="v">{:+.2f}</div><div class="k">Mean delay (min)</div></div>
      <div class="stat"><div class="v">{:,}</div><div class="k">Arrivals in view</div></div>
    </div>
    """.format(on_time_pct, early_pct, late_pct, avg_delay, len(filtered)),
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class="note"><strong>Why the mean lies.</strong> A mean delay near zero suggests a network
    running to schedule. It isn't, it's early buses cancelling out late ones. Early running is the
    characteristic failure mode here, and it's the one riders feel worst: a late bus costs you
    minutes, a bus that left early costs you the whole headway.</p>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown("**Delay distribution (minutes vs schedule)**")
    delay_clipped = filtered[COL_DELAY].clip(-15, 15)
    hist = (
        delay_clipped.round().value_counts().sort_index().rename("arrivals")
    )
    st.bar_chart(hist, color="#2A2F3A", height=300)
    st.caption(
        "Negative = early. The left-of-zero mass is the story a single "
        "on-time percentage hides. Clipped at ±15 min for readability."
    )

with right:
    st.markdown("**On-time rate by hour of day**")
    by_hour = filtered.groupby("hour")[COL_ON_TIME].mean().mul(100).rename("On-time %")
    st.bar_chart(by_hour, color="#DA291C", height=300)
    st.caption(
        "Hours reflect collection windows so far; coverage widens as "
        "collection days accumulate."
    )

# ------------------------------ HEADWAYS ------------------------------
st.markdown(
    '<div class="sectionlabel">Headway regularity — the metric agencies actually manage</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class="note">On frequent routes, riders don't consult schedules they show up and wait.
    What matters is whether buses arrive <em>evenly spaced</em>. The classic failure is
    <strong>bunching</strong>: two buses nose-to-tail, then a gap twice as long as promised.
    Here, each arrival's actual headway is the gap since the previous bus at the same stop and
    direction (a LAG-over-partition computation), compared against that stop's own median headway.
    Below half the median counts as bunched; above 1.5× counts as a gap.</p>
    """,
    unsafe_allow_html=True,
)

if hw_filtered.empty:
    st.info("Not enough consecutive arrivals in this view to measure headways yet.")
else:
    bunched_pct = hw_filtered["bunched"].mean() * 100
    gapped_pct = hw_filtered["gapped"].mean() * 100
    hw_cv = hw_filtered["headway_min"].std() / hw_filtered["headway_min"].mean()
    med_hw = hw_filtered["headway_min"].median()

    st.markdown(
        """
        <div class="statrow">
          <div class="stat"><div class="v">{:.1f}%</div><div class="k">Arrivals bunched</div></div>
          <div class="stat"><div class="v">{:.1f}%</div><div class="k">Arrivals after a gap</div></div>
          <div class="stat"><div class="v">{:.1f}</div><div class="k">Median headway (min)</div></div>
          <div class="stat"><div class="v">{:.2f}</div><div class="k">Headway CV (lower = steadier)</div></div>
        </div>
        """.format(bunched_pct, gapped_pct, med_hw, hw_cv),
        unsafe_allow_html=True,
    )

    hl, hr = st.columns([1, 1], gap="large")
    with hl:
        st.markdown("**Distribution of actual headways**")
        hcounts = (
            hw_filtered.loc[hw_filtered["headway_min"] <= 40, "headway_min"]
            .round()
            .value_counts()
            .sort_index()
        )
        st.bar_chart(hcounts, color="#1F9E8C", height=280)
        st.caption("A spike near zero is bunching made visible.")
    with hr:
        st.markdown("**Most bunching-prone routes in view**")
        route_bunch = (
            hw_filtered.groupby(COL_ROUTE)
            .agg(observed_headways=("bunched", "size"), bunched_pct=("bunched", lambda s: s.mean() * 100))
            .query("observed_headways >= 50")
            .sort_values("bunched_pct", ascending=False)
            .round(1)
            .head(10)
            .reset_index()
        )
        st.dataframe(
            route_bunch,
            use_container_width=True,
            hide_index=True,
            column_config={
                COL_ROUTE: "Route",
                "observed_headways": st.column_config.NumberColumn("Headways observed", format="%d"),
                "bunched_pct": st.column_config.ProgressColumn(
                    "Bunched %", min_value=0, max_value=50, format="%.1f%%"
                ),
            },
        )

# ------------------------------ MAP ------------------------------
st.markdown('<div class="sectionlabel">Geography of unreliability</div>', unsafe_allow_html=True)

if stops_geo is not None:
    stop_perf = (
        filtered.groupby(COL_STOP_ID)
        .agg(
            on_time=(COL_ON_TIME, "mean"),
            arrivals=(COL_ON_TIME, "size"),
            stop_name=(COL_STOP, "first"),
        )
        .reset_index()
        .query("arrivals >= 3")
    )
    geo = stop_perf.merge(stops_geo, on=COL_STOP_ID, how="inner")
    if geo.empty:
        st.info("No mappable stops in this view.")
    else:
        geo["on_time_pct"] = (geo["on_time"] * 100).round(1)

        # Colour scale: teal (reliable) -> red (unreliable), scaled between
        # the 10th and 90th percentile of the view so variation is visible.
        lo = geo["on_time_pct"].quantile(0.10)
        hi = geo["on_time_pct"].quantile(0.90)
        span = max(hi - lo, 1e-9)
        t = ((geo["on_time_pct"] - lo) / span).clip(0, 1)  # 0 = worst, 1 = best
        geo["r"] = (218 + (31 - 218) * t).astype(int)
        geo["g"] = (41 + (158 - 41) * t).astype(int)
        geo["b"] = (28 + (140 - 28) * t).astype(int)

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=geo,
            get_position=["stop_lon", "stop_lat"],
            get_fill_color=["r", "g", "b", 175],
            get_radius=60,
            radius_min_pixels=2,
            radius_max_pixels=8,
            pickable=True,
        )
        view = pdk.ViewState(
            latitude=float(geo["stop_lat"].mean()),
            longitude=float(geo["stop_lon"].mean()),
            zoom=10.2 if route_choice == "All routes" else 11.5,
        )
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view,
                map_style="light",
                tooltip={"text": "{stop_name}\nOn time: {on_time_pct}% ({arrivals} arrivals)"},
            )
        )
        st.caption(
            "{:,} stops with ≥3 observed arrivals. Teal = reliable, red = unreliable, "
            "scaled to this view's 10th–90th percentile so variation stays visible. "
            "Stops below the sample threshold are excluded a ranking built on one bus is noise.".format(len(geo))
        )
else:
    st.info(
        "Map layer not loaded. Run export_stops.py to create data/stops.parquet "
        "(stop_id, stop_lat, stop_lon)."
    )

# ------------------------------ STOP TABLE ------------------------------
st.markdown('<div class="sectionlabel">Worst-performing stops in view</div>', unsafe_allow_html=True)
MIN_ARRIVALS = 3
stop_table = (
    filtered.groupby([COL_STOP, COL_DIRECTION])
    .agg(
        arrivals=(COL_ON_TIME, "size"),
        on_time_pct=(COL_ON_TIME, lambda s: s.mean() * 100),
        avg_delay_min=(COL_DELAY, "mean"),
    )
    .query("arrivals >= {}".format(MIN_ARRIVALS))
    .sort_values("on_time_pct")
    .round(1)
    .reset_index()
    .head(25)
)
st.dataframe(
    stop_table,
    use_container_width=True,
    hide_index=True,
    column_config={
        COL_STOP: "Stop",
        COL_DIRECTION: "Direction",
        "arrivals": st.column_config.NumberColumn("Arrivals", format="%d"),
        "on_time_pct": st.column_config.ProgressColumn(
            "On time %", min_value=0, max_value=100, format="%.1f%%"
        ),
        "avg_delay_min": st.column_config.NumberColumn("Mean delay (min)", format="%.2f"),
    },
)

# ------------------------------ ENGINEERING NOTES ------------------------------
st.markdown('<div class="sectionlabel">Engineering notes</div>', unsafe_allow_html=True)
a, b, c = st.columns(3, gap="large")
with a:
    st.markdown("**Modelling**")
    st.markdown(
        "<p class='note'>Layered dbt project: staging isolates source shape, intermediate carries "
        "the arrival-inference logic, marts serve analysis. Route scope is a dbt <code>var()</code> "
        "rather than a hardcode, so the same project runs for one route or all 181. Schedule "
        "changes are captured as SCD Type 2 snapshots.</p>",
        unsafe_allow_html=True,
    )
with b:
    st.markdown("**Data quality**")
    st.markdown(
        "<p class='note'>Seven tests run at full scale — uniqueness on the arrival grain, not-null "
        "on join keys, accepted ranges on delay. Out-of-service-hours readings are filtered by "
        "design, not by accident: a bus with no scheduled time nearby cannot be measured against "
        "one, and reporting it would be a fabricated metric.</p>",
        unsafe_allow_html=True,
    )
with c:
    st.markdown("**Operations**")
    st.markdown(
        "<p class='note'>Airflow on Docker schedules ingestion, transformation and validation with "
        "dependency ordering and retries. The dashboard reads a Parquet serving layer rather than "
        "the warehouse directly, so presentation is decoupled from storage and the engine can be "
        "swapped for Snowflake or BigQuery with a profile change.</p>",
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <p class="note" style="margin-top:2rem;border-top:1px solid #DFE3E8;padding-top:1rem;">
    Data: City of Toronto Open Data / TTC, under the Open Government Licence – Toronto.
    Full source, architecture diagram and setup instructions: <a href="{}">GitHub</a>.
    </p>
    """.format(GITHUB_URL),
    unsafe_allow_html=True,
)
