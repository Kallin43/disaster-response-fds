"""Data-driven disaster response dashboard for the supplied India EM-DAT extract."""

from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="Data-Driven Disaster Response", page_icon="◉", layout="wide")

DATA_PATH = Path(__file__).parent / "real_india_disasters_70_EMDAT.csv"
NAVY = "#172A3A"
BLUE = "#087FA5"
TEAL = "#238F82"
AMBER = "#B87919"
MUTED = "#788A98"
LINE = "#D9E3E8"
GRID = "#E8EEF1"
WHITE = "#FFFFFF"
PALE = "#F4F7F8"

# Canonical calculation names map to plausible variants in similarly structured extracts.
ALIASES = {
    "disaster_id": ["disaster_id", "emdat_id", "event_id", "id"],
    "date": ["date", "start_date", "event_date"],
    "disaster_type": ["disaster_type", "type", "event_type"],
    "disaster_subtype": ["disaster_subtype", "subtype", "event_subtype"],
    "location": ["location", "locations", "affected_area"],
    "deaths": ["deaths", "total_deaths", "killed"],
    "injured": ["injured", "injuries"],
    "affected": ["affected", "total_affected_people"],
    "homeless": ["homeless", "people_homeless"],
    "total_affected": ["total_affected", "total_affected_population"],
    "economic_loss_000_usd": ["economic_loss_000_usd", "economic_loss", "loss_000_usd"],
    "severity": ["severity", "severity_level", "severity_score"],
    "source": ["source", "data_source"],
}
IMPACTS = {
    "Reported deaths": ("deaths", "people"),
    "Reported affected population": ("total_affected", "people"),
    "Reported homeless population": ("homeless", "people"),
    "Reported economic loss": ("economic_loss_000_usd", "thousand USD"),
}
REQUIRED_FOR_DASHBOARD = ["date", "disaster_type", "severity", "deaths", "total_affected", "economic_loss_000_usd"]


def normalize_header(value: object) -> str:
    """Create a predictable key for matching source headers without changing raw data."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


@st.cache_data(show_spinner="Loading the supplied EM-DAT records…")
def read_source(path: str) -> pd.DataFrame:
    """Read source values while leaving blanks as missing values."""
    return pd.read_csv(path, keep_default_na=True)


def build_calculation_frame(raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Create a separate typed frame; raw remains available for the record table."""
    source_names = {normalize_header(column): column for column in raw.columns}
    resolved: Dict[str, str] = {}
    for canonical, candidates in ALIASES.items():
        for candidate in candidates:
            if candidate in source_names:
                resolved[canonical] = source_names[candidate]
                break

    work = pd.DataFrame(index=raw.index)
    for canonical, source_column in resolved.items():
        work[canonical] = raw[source_column]

    if "date" in work:
        work["_parsed_date"] = pd.to_datetime(work["date"], errors="coerce")
        work["_year"] = work["_parsed_date"].dt.year
    else:
        work["_parsed_date"] = pd.NaT
        work["_year"] = pd.Series(pd.NA, index=raw.index, dtype="Int64")

    for column in ["deaths", "injured", "affected", "homeless", "total_affected", "economic_loss_000_usd", "severity"]:
        if column in work:
            work[column] = pd.to_numeric(work[column], errors="coerce")
        else:
            work[column] = pd.Series(float("nan"), index=raw.index, dtype="float64")
    return work, resolved


def sum_reported(series: pd.Series) -> float:
    """Sum only reported observations; all-missing series remains NaN."""
    return series.sum(min_count=1)


def fmt_count(value: object) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.0f}"


def fmt_loss(value: object) -> str:
    if pd.isna(value):
        return "—"
    # Source unit is thousand USD; keep that unit explicit in the display.
    return f"${value:,.0f}k"


def count_chart(data: pd.DataFrame) -> go.Figure:
    yearly = data.dropna(subset=["_year"]).groupby("_year").size().rename("events").reset_index()
    yearly = yearly.sort_values("_year")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=yearly["_year"], y=yearly["events"], mode="lines+markers", name="Events",
        line=dict(color=BLUE, width=2.5), marker=dict(size=7, color=BLUE, line=dict(color=WHITE, width=2)),
        hovertemplate="Year %{x}<br>Events %{y:,}<extra></extra>",
    ))
    fig.update_layout(
        height=310, margin=dict(l=10, r=18, t=12, b=10), paper_bgcolor=WHITE, plot_bgcolor=WHITE,
        font=dict(family="Arial, sans-serif", color=NAVY, size=12), showlegend=False,
        xaxis=dict(title="Year", tickformat="d", dtick=2, showgrid=False, zeroline=False, linecolor=LINE),
        yaxis=dict(title="Disaster events", rangemode="tozero", dtick=1, gridcolor=GRID, zeroline=False),
        hovermode="x unified",
    )
    return fig


def impact_chart(data: pd.DataFrame, impact_column: str, impact_unit: str) -> go.Figure:
    grouped = data.groupby("disaster_type", dropna=False)[impact_column].agg(
        total=lambda values: values.sum(min_count=1),
        reported="count",
    ).reset_index()
    grouped["disaster_type"] = grouped["disaster_type"].fillna("Unspecified")
    grouped = grouped.dropna(subset=["total"]).sort_values("total", ascending=True)
    fig = go.Figure(go.Bar(
        x=grouped["total"], y=grouped["disaster_type"], orientation="h",
        marker=dict(color=BLUE, line=dict(width=0)),
        customdata=grouped["reported"],
        hovertemplate="%{y}<br>Reported impact: %{x:,.0f}<br>Records with values: %{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=max(310, min(470, 42 * len(grouped) + 80)), margin=dict(l=10, r=18, t=12, b=10),
        paper_bgcolor=WHITE, plot_bgcolor=WHITE, font=dict(family="Arial, sans-serif", color=NAVY, size=12),
        showlegend=False,
        xaxis=dict(title=impact_unit, rangemode="tozero", gridcolor=GRID, zeroline=False),
        yaxis=dict(title="", automargin=True, showgrid=False),
    )
    return fig


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700;800&display=swap');
        :root { --navy:#172A3A; --blue:#087FA5; --teal:#238F82; --amber:#B87919; --muted:#788A98; --line:#D9E3E8; --paper:#F4F7F8; --success:#EFF8F5; --warning:#FFF6E5; }
        .stApp, .stApp [data-testid="stMain"], .stApp [data-testid="stSidebar"] { font-family:'DM Sans', sans-serif; color:var(--navy); }
        .stApp { background:var(--paper); }
        /* Streamlit's toolbar remains visible. Reserve a clear band below it for app content. */
        [data-testid="stMainBlockContainer"] { max-width:1440px; padding-top:3.75rem; padding-bottom:2rem; }
        .stApp h1,.stApp h2,.stApp h3 { color:var(--navy); letter-spacing:-.045em; }
        .micro { font-family:'DM Mono',monospace; font-size:.68rem; text-transform:uppercase; letter-spacing:.12em; color:var(--muted); }
        .brandline { display:flex; gap:11px; align-items:center; padding:13px 0 12px; color:var(--navy); }
        .brandmark { width:28px; height:28px; border-radius:50%; display:inline-flex; justify-content:center; align-items:center; color:#fff; background:var(--navy); font-size:15px; }
        .brandname { font-size:.79rem; font-weight:800; letter-spacing:.08em; white-space:nowrap; }
        .brandmeta { margin-left:8px; padding-left:13px; border-left:1px solid var(--line); }
        .toprule { border-bottom:1px solid var(--line); margin:0 0 30px; }
        .hero { padding:10px 0 24px; }
        .hero-eyebrow { margin-bottom:15px; color:var(--teal); }
        .hero-title { font-size:clamp(2.7rem,6vw,5.4rem); line-height:.96; letter-spacing:-.065em; font-weight:800; margin:0; color:var(--navy); }
        .hero-title .accent { color:var(--blue); }
        .hero-subtitle { margin-top:19px; color:#53687A; font-size:1.08rem; }
        .hero-aside { max-width:340px; margin:30px 0 0 auto; color:#536B7B; font-size:.91rem; line-height:1.65; border-left:2px solid #BFDDE5; padding-left:18px; }
        .integrity { color:var(--teal); font-family:'DM Mono',monospace; font-size:.69rem; letter-spacing:.05em; text-transform:uppercase; margin-top:13px; }
        .integrity:before { content:'●'; margin-right:8px; color:var(--teal); }
        .st-key-global_filters { scroll-margin-top:1rem; }
        .st-key-global_filters [data-testid="stVerticalBlockBorderWrapper"] { padding:12px 16px 15px; }
        [data-testid="stButton"] button { border-radius:2px; border:1px solid var(--line); background:#fff; color:var(--navy); min-height:38px; transition:background-color .15s,border-color .15s,color .15s; }
        [data-testid="stButton"] button:hover { border-color:var(--blue); color:var(--blue); background:#F0F8FA; }
        [data-testid="stButton"] button:focus-visible, [data-testid="stPopover"] button:focus-visible { outline:2px solid var(--blue); outline-offset:2px; }
        [data-testid="stPopover"] button { color:var(--blue); }
        [data-testid="stMain"] a, [data-testid="stMain"] a:visited { color:var(--blue); }
        [data-testid="stMain"] [data-baseweb="tag"] { background-color:var(--blue); color:#fff; border:1px solid var(--blue); border-radius:2px; max-width:100%; }
        [data-testid="stMain"] [data-baseweb="tag"] svg { fill:#fff; }
        [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div { min-height:42px; height:auto; flex-wrap:wrap; row-gap:4px; overflow:visible; }
        [data-testid="stMain"] [data-baseweb="select"]:focus-within, [data-testid="stMain"] [data-baseweb="input"]:focus-within, [data-testid="stMain"] textarea:focus, [data-testid="stMain"] input:focus { border-color:var(--blue); box-shadow:0 0 0 1px var(--blue); }
        .stApp [role="option"][aria-selected="true"] { background:#E5F2F5; color:var(--navy); }
        .stApp [role="option"]:hover { background:#F0F7F8; color:var(--navy); }
        [data-testid="stMain"] [data-testid="stSlider"] { color:var(--navy); }
        [data-testid="stMain"] [data-testid="stSlider"] [role="slider"] { background-color:var(--blue); border:2px solid #fff; box-shadow:0 0 0 1px var(--blue); }
        [data-testid="stMain"] [data-testid="stSlider"] [role="slider"]:focus { box-shadow:0 0 0 3px rgba(8,127,165,.24); }
        [data-testid="stMain"] [data-testid="stSlider"] label, [data-testid="stMain"] [data-testid="stSlider"] [data-testid="stTickBar"] { color:var(--muted); }
        [data-testid="stMetric"] { position:relative; border:1px solid var(--line); border-top:2px solid var(--blue); border-radius:2px; background:#fff; padding:17px 17px 15px; min-height:125px; box-shadow:none; }
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"]:nth-child(3) [data-testid="stMetric"] { border-top-color:var(--teal); }
        [data-testid="stVerticalBlockBorderWrapper"] { border:1px solid var(--line); border-radius:2px; background:#fff; }
        [data-testid="stMetric"]:after { content:'↗'; position:absolute; right:15px; top:12px; color:#91A4B2; font-size:14px; }
        [data-testid="stMetricLabel"] p { color:var(--muted); font-size:.76rem; font-weight:600; }
        [data-testid="stMetricValue"] { font-weight:800; color:var(--navy); font-size:1.8rem; letter-spacing:-.045em; }
        .metric-foot { color:var(--muted); font-size:.72rem; margin-top:0; }
        .section-kicker { font-family:'DM Mono',monospace; font-size:.68rem; color:var(--blue); letter-spacing:.1em; text-transform:uppercase; margin-bottom:5px; }
        .section-title { font-size:1.45rem; font-weight:700; letter-spacing:-.035em; color:var(--navy); margin:0 0 10px; }
        .chartbox { border:1px solid var(--line); background:#fff; padding:17px 18px 7px; min-height:390px; }
        .tablebox { border:1px solid var(--line); background:#fff; padding:17px 18px 12px; }
        .method { background:var(--success); border:1px solid #CFE4DE; padding:19px 22px; color:#294C4D; }
        .method h3 { margin-top:0; color:var(--navy); }
        .method li { margin:.34rem 0; }
        .warning { background:var(--warning); color:var(--amber); border:1px solid #E9D6AE; padding:14px 17px; margin:14px 0; }
        .success { background:var(--success); color:#276C5C; border:1px solid #D2E7DF; padding:11px 14px; font-size:.84rem; margin:10px 0 24px; }
        .stDataFrame { border:0; }
        footer { visibility:hidden; }
        @media (max-width:760px) {
          [data-testid="stMainBlockContainer"] { padding-left:1rem; padding-right:1rem; padding-top:3.25rem; }
          .hero { padding-top:0; }
          .hero-aside { margin:14px 0 0; }
          .brandmeta { display:none; }
          .hero-title { font-size:2.8rem; }
          [data-testid="stMetricValue"] { font-size:1.45rem; }
          .chartbox { padding:12px; }
          .st-key-global_filters [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:last-child { flex-direction:column; gap:.65rem; }
          .st-key-global_filters [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:last-child > [data-testid="column"] { flex:1 1 100% !important; width:100% !important; min-width:100% !important; }
          .brandline { flex-wrap:wrap; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_styles()

# Thin header and interactive notes popover.
nav_left, nav_right = st.columns([8, 1.4], vertical_alignment="center")
with nav_left:
    st.markdown(
        '<div class="brandline"><span class="brandmark">⌁</span><span class="brandname">Data-Driven Disaster Response: Predicting Relief Needs and Optimizing Resource Allocation</span>'
        '<span class="brandmeta micro">INDIA · EM-DAT PUBLIC TABLE</span></div>',
        unsafe_allow_html=True,
    )
with nav_right:
    with st.popover("ⓘ  Data notes", use_container_width=True):
        st.markdown("**Read the source, not into it.**")
        st.write("Impact totals use reported values only. Missing values stay missing. Losses are stored in thousand USD. Severity is shown as provided and is not described as an official EM-DAT classification.")
st.markdown('<div class="toprule"></div>', unsafe_allow_html=True)


if not DATA_PATH.exists():
    st.markdown(
        f'<div class="warning"><b>Dataset not found.</b><br>Place <code>{DATA_PATH.name}</code> in the same folder as <code>app.py</code> to load the dashboard. No sample or synthetic values are shown.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

try:
    raw_df = read_source(str(DATA_PATH))
    if raw_df.empty:
        st.error("The supplied CSV contains a header but no event records.")
        st.stop()
    data, resolved_columns = build_calculation_frame(raw_df)
except (pd.errors.ParserError, UnicodeDecodeError, OSError, ValueError) as error:
    st.error(f"The supplied CSV could not be read. Check that it is a valid CSV beside app.py. Details: {error}")
    st.stop()

missing_fields = [field for field in REQUIRED_FOR_DASHBOARD if field not in resolved_columns]
if missing_fields:
    st.warning("Some expected fields are unavailable: " + ", ".join(missing_fields) + ". Related filters, charts, or impact KPIs will be limited; records will not be fabricated.")
else:
    st.markdown('<div class="success">Source integrity preserved · CSV loaded successfully · unreported impact values remain unreported</div>', unsafe_allow_html=True)

all_years = sorted(data["_year"].dropna().astype(int).unique().tolist())
dataset_span = f"{all_years[0]}–{all_years[-1]} DATASET" if all_years else "ALL AVAILABLE DATES"
hero_left, hero_right = st.columns([7, 3], vertical_alignment="center")
with hero_left:
    st.markdown(f'<div class="micro hero-eyebrow">RELIEF PLANNING INTELLIGENCE · {dataset_span}</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Data-Driven<br><span class="accent">Disaster Response</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Predicting relief needs and optimizing resource allocation.</div>', unsafe_allow_html=True)
with hero_right:
    st.markdown(
        '<div class="hero-aside">A focused view of recorded disaster events and reported impacts across India, supporting evidence-led relief planning.'
        '<div class="integrity">Built and developed by Noel Kallingal and Ayman Mohammed</div></div>',
        unsafe_allow_html=True,
    )


# One connected filter area. State is set before widgets are created so Clear all works.
type_options = sorted(data["disaster_type"].dropna().astype(str).unique().tolist()) if "disaster_type" in data else []
severity_options = sorted(data["severity"].dropna().unique().tolist()) if "severity" in data else []
with st.container(border=True, key="global_filters"):
    filter_title, clear_col = st.columns([8, 1.2], vertical_alignment="center")
    with filter_title:
        st.markdown('<div class="micro">GLOBAL FILTERS</div>', unsafe_allow_html=True)
    with clear_col:
        clear_clicked = st.button("Clear all", key="clear_filters", use_container_width=True)

    if clear_clicked:
        st.session_state["filter_types"] = type_options
        st.session_state["filter_severity"] = severity_options
        if all_years:
            st.session_state["filter_years"] = (all_years[0], all_years[-1])
        st.rerun()

    default_years = (all_years[0], all_years[-1]) if all_years else None
    st.session_state.setdefault("filter_types", type_options)
    st.session_state.setdefault("filter_severity", severity_options)
    if default_years:
        st.session_state.setdefault("filter_years", default_years)

    filter_type_col, filter_year_col, filter_severity_col = st.columns([1.15, 1.35, 1.0], gap="large")
    with filter_type_col:
        selected_types = st.multiselect(
            "Disaster type", type_options, key="filter_types", disabled=not bool(type_options),
            help="Select one or more disaster types."
        )
        if not type_options:
            st.caption("Disaster type field unavailable.")
    with filter_year_col:
        if len(all_years) > 1:
            selected_year_range = st.slider("Year range", min_value=all_years[0], max_value=all_years[-1], key="filter_years")
        elif len(all_years) == 1:
            selected_year_range = (all_years[0], all_years[0])
            st.text_input("Year range", value=str(all_years[0]), disabled=True)
        else:
            selected_year_range = None
            st.text_input("Year range", value="No valid dates", disabled=True)
    with filter_severity_col:
        selected_severity = st.multiselect(
            "Severity source level", severity_options, key="filter_severity", format_func=lambda value: f"Level {value:g}",
            disabled=not bool(severity_options), help="Numeric levels as supplied in the source file."
        )
        if not severity_options:
            st.caption("Severity field unavailable.")

filtered_mask = pd.Series(True, index=data.index)
if type_options:
    filtered_mask &= data["disaster_type"].astype("string").isin(selected_types)
if selected_year_range is not None:
    filtered_mask &= data["_year"].between(selected_year_range[0], selected_year_range[1])
if severity_options:
    filtered_mask &= data["severity"].isin(selected_severity)
filtered = data.loc[filtered_mask].copy()
filtered_raw = raw_df.loc[filtered_mask].copy()

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
kpis = st.columns(4, gap="medium")
events_count = len(filtered)
death_total = sum_reported(filtered["deaths"])
affected_total = sum_reported(filtered["total_affected"])
loss_average = filtered["economic_loss_000_usd"].mean()
death_n = int(filtered["deaths"].notna().sum())
affected_n = int(filtered["total_affected"].notna().sum())
loss_n = int(filtered["economic_loss_000_usd"].notna().sum())
kpi_values = [
    ("Disaster events", fmt_count(events_count), f"{events_count:,} source records in this view", BLUE),
    ("Reported deaths", fmt_count(death_total), f"Reported in {death_n:,} of {events_count:,} records", BLUE),
    ("Reported affected", fmt_count(affected_total), f"Reported in {affected_n:,} of {events_count:,} records", TEAL),
    ("Avg. economic loss", fmt_loss(loss_average), f"USD (thousands) · {loss_n:,} reports", BLUE),
]
for column, (label, value, foot, accent) in zip(kpis, kpi_values):
    with column:
        st.markdown(f'<div style="--card-accent:{accent}"></div>', unsafe_allow_html=True)
        st.metric(label, value, help=foot)
        st.markdown(f'<div class="metric-foot">{foot}</div>', unsafe_allow_html=True)

st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
chart_left, chart_right = st.columns(2, gap="large")
with chart_left:
    with st.container(border=True):
        st.markdown('<div class="section-kicker">01 / FREQUENCY</div><div class="section-title">Annual disaster events</div>', unsafe_allow_html=True)
        if filtered["_year"].notna().any():
            st.plotly_chart(count_chart(filtered), use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No valid dates are available for the selected records.")

with chart_right:
    with st.container(border=True):
        st.markdown('<div class="section-kicker">02 / IMPACT PROFILE</div><div class="section-title">By disaster type</div>', unsafe_allow_html=True)
        available_impact_labels = [label for label, (column, _) in IMPACTS.items() if column in resolved_columns]
        if "disaster_type" not in data:
            st.info("The disaster type field is unavailable in this CSV.")
        elif available_impact_labels:
            impact_choice = st.selectbox("Impact measure", available_impact_labels, label_visibility="collapsed", key="impact_measure")
            impact_column, impact_unit = IMPACTS[impact_choice]
            if filtered[impact_column].notna().any():
                st.plotly_chart(impact_chart(filtered, impact_column, impact_unit), use_container_width=True, config={"displayModeBar": False})
                st.caption(f"Reported {impact_choice.lower()} only · blanks excluded · unit: {impact_unit}")
            else:
                st.info(f"No reported {impact_choice.lower()} values in this filtered view.")
        else:
            st.info("No supported numeric impact fields are available in this CSV.")


st.markdown("<div style='height:25px'></div>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown('<div class="section-kicker">03 / SOURCE RECORDS</div><div class="section-title">Event records</div>', unsafe_allow_html=True)
    table_info, search_col = st.columns([1.2, 2], vertical_alignment="center")
    with table_info:
        st.markdown(f'<div class="micro">{len(filtered_raw):,} FILTERED RECORDS</div>', unsafe_allow_html=True)
    with search_col:
        search_text = st.text_input("Search event records", placeholder="Search ID, event type, subtype, place…", label_visibility="collapsed", key="record_search")

    # Keep source column names and cell values from the original CSV in the visible table.
    preferred_columns = ["disaster_id", "date", "disaster_type", "disaster_subtype", "location", "severity", "deaths", "total_affected", "economic_loss_000_usd", "source"]
    table_columns = []
    for canonical in preferred_columns:
        source_col = resolved_columns.get(canonical)
        if source_col in filtered_raw.columns and source_col not in table_columns:
            table_columns.append(source_col)
    table_columns.extend(column for column in filtered_raw.columns if column not in table_columns)
    if not table_columns:
        table_columns = filtered_raw.columns.tolist()
    source_table = filtered_raw[table_columns].copy()
    if search_text.strip():
        search_mask = source_table.astype("string").apply(
            lambda series: series.str.contains(search_text.strip(), case=False, regex=False, na=False)
        ).any(axis=1)
        source_table = source_table.loc[search_mask]
    st.dataframe(source_table, use_container_width=True, hide_index=True, height=365)
    st.caption(f"Showing {len(source_table):,} visible records · original source values and column names preserved")


st.markdown("<div style='height:23px'></div>", unsafe_allow_html=True)
st.markdown(
    """
    <div class="method">
      <div class="section-kicker">DATA NOTES / METHODOLOGY</div>
      <h3>Read the source, not into it.</h3>
      <ul>
        <li>This dashboard uses only the supplied EM-DAT records. It does not create event rows or infer impact values.</li>
        <li>Blank impact fields remain missing. KPI sums and averages use reported values only; an impact with no reported values displays an em dash.</li>
        <li><code>total_affected</code> is the affected-population field supplied in this project dataset.</li>
        <li><code>economic_loss_000_usd</code> is recorded in thousand USD.</li>
        <li><code>severity</code> is presented as a numeric field supplied in the CSV. The extract does not document its derivation, so this dashboard does not describe it as an official EM-DAT classification.</li>
        <li>Dates that cannot be parsed are excluded from the year chart and year filter; their original values remain in the source-record table.</li>
        <li>This dashboard analyzes the supplied extract but does not independently verify the underlying records.</li>
      </ul>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div style="border-top:1px solid #D9E3E8;margin-top:22px;padding-top:12px;display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;color:#788A98;font-family:DM Mono,monospace;font-size:.65rem;letter-spacing:.08em">'
            f'<span>DATA-DRIVEN DISASTER RESPONSE NOEL KALLINGAL-23BCE0612 AYMAN MOHAMMED-23BCE2218</span><span>{len(raw_df):,} SOURCE RECORDS · INDIA · EM-DAT PUBLIC TABLE</span></div>',
            unsafe_allow_html=True)

