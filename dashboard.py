import streamlit as st
import duckdb
import pandas as pd

st.set_page_config(page_title="TTC Transit Reliability", layout="wide")

@st.cache_data
def load_data():
    con = duckdb.connect("ttc.duckdb", read_only=True)
    perf = con.sql("SELECT * FROM main.fct_stop_performance").df()
    rel = con.sql("SELECT * FROM main.fct_route_reliability").df()
    con.close()
    return perf, rel

perf, rel = load_data()

st.title("TTC Transit Reliability — How Late Are Toronto's Buses, Really?")
st.caption("Actual arrivals reconstructed from live GPS, compared against the published schedule. Across the TTC surface network.")

# ---- 1. CITY-WIDE HEADLINE ----
total = len(perf)
routes = perf['route_id'].nunique()
on_time = round(100 * perf['delay_minutes'].between(-1, 5).sum() / total, 1)
avg_delay = round(perf['delay_minutes'].mean(), 2)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Routes analyzed", f"{routes}")
c2.metric("Arrivals analyzed", f"{total:,}")
c3.metric("On-time rate", f"{on_time}%")
c4.metric("Average delay", f"{avg_delay} min")

st.divider()

# ---- 2. CITY-WIDE BELL CURVE ----
st.subheader("Delay distribution — entire network")
st.caption("How early or late arrivals were across all routes (minutes). 0 = on schedule.")
city_hist = perf['delay_minutes'].round().value_counts().sort_index()
st.bar_chart(city_hist)

st.divider()

# ---- 3. EXPLORE A ROUTE ----
st.subheader("Explore a route")
route_list = sorted(perf['route_id'].unique(), key=lambda x: (len(x), x))
selected = st.selectbox("Pick a route", route_list, index=route_list.index('102') if '102' in route_list else 0)

route_perf = perf[perf['route_id'] == selected]
r_total = len(route_perf)
r_on_time = round(100 * route_perf['delay_minutes'].between(-1, 5).sum() / r_total, 1) if r_total else 0
r_avg = round(route_perf['delay_minutes'].mean(), 2) if r_total else 0

rc1, rc2, rc3 = st.columns(3)
rc1.metric(f"Route {selected} arrivals", f"{r_total:,}")
rc2.metric("On-time rate", f"{r_on_time}%")
rc3.metric("Average delay", f"{r_avg} min")

st.caption(f"Delay distribution for route {selected} (minutes). 0 = on schedule.")
route_hist = route_perf['delay_minutes'].value_counts().sort_index()
st.bar_chart(route_hist)

st.caption(f"Least reliable stops on route {selected} (min. 3 arrivals)")
route_rel = rel[rel['route_id'] == selected]
worst_stops = (route_rel[route_rel['total_arrivals'] >= 3]
               .sort_values('on_time_pct')
               .head(10)[['stop_name', 'direction_id', 'total_arrivals', 'avg_delay_min', 'on_time_pct']])
if len(worst_stops):
    st.dataframe(worst_stops, use_container_width=True, hide_index=True)
else:
    st.info("Not enough per-stop data for this route yet.")

st.divider()

# ---- 4. LEAST RELIABLE ROUTES (city-wide) ----
st.subheader("Least reliable routes")
st.caption("Routes with at least 100 arrivals, ranked by on-time %.")
route_summary = (perf.groupby('route_id')
                 .agg(arrivals=('delay_minutes', 'size'),
                      avg_delay_min=('delay_minutes', 'mean'),
                      on_time_pct=('delay_minutes', lambda x: round(100 * x.between(-1, 5).sum() / len(x), 1)))
                 .reset_index())
route_summary['avg_delay_min'] = route_summary['avg_delay_min'].round(2)
worst_routes = route_summary[route_summary['arrivals'] >= 100].sort_values('on_time_pct').head(15)
worst_routes.columns = ['Route', 'Arrivals', 'Avg delay (min)', 'On-time %']
st.dataframe(worst_routes, use_container_width=True, hide_index=True)