import streamlit as st
import duckdb
import pandas as pd

st.set_page_config(page_title="TTC Route 102 Reliability", layout="wide")

# ---- load data from the warehouse ----
@st.cache_data
def load_data():
    con = duckdb.connect("ttc.duckdb", read_only=True)
    reliability = con.sql("SELECT * FROM main.fct_route_reliability").df()
    performance = con.sql("SELECT * FROM main.fct_stop_performance").df()
    con.close()
    return reliability, performance

reliability, performance = load_data()

# ---- header ----
st.title("🚌 TTC Route 102 — How Late Is It, Really?")
st.caption("Comparing the published schedule against actual arrivals reconstructed from live GPS data.")

# ---- headline metrics ----
total_arrivals = len(performance)
on_time_pct = round(100 * (performance['delay_minutes'].between(-1, 5)).sum() / total_arrivals, 1)
avg_delay = round(performance['delay_minutes'].mean(), 2)

col1, col2, col3 = st.columns(3)
col1.metric("Arrivals analyzed", f"{total_arrivals:,}")
col2.metric("On-time rate", f"{on_time_pct}%")
col3.metric("Average delay", f"{avg_delay} min")

st.divider()

# ---- delay distribution ----
st.subheader("Delay distribution")
st.caption("How early or late buses actually were (minutes). 0 = on schedule.")
hist = performance['delay_minutes'].value_counts().sort_index()
st.bar_chart(hist)

st.divider()

# ---- worst stops ----
st.subheader("Least reliable stops")
worst = (reliability[reliability['total_arrivals'] >= 3]
         .sort_values('on_time_pct')
         .head(10)
         [['stop_name', 'direction_id', 'total_arrivals', 'avg_delay_min', 'on_time_pct']])
st.dataframe(worst, use_container_width=True, hide_index=True)