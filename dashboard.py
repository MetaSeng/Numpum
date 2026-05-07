"""
Interpretability-first dashboard for identifying digital deserts in NE Cambodia.

Story flow:
1) Problem framing
2) Evidence and source data
3) Rule-based model logic
4) Mapped results
5) Policy actions
"""

from pathlib import Path
import json

import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

px.defaults.template = "plotly_dark"
px.defaults.color_discrete_sequence = ["#38bdf8", "#2dd4bf", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6"]


st.set_page_config(
    page_title="Digital Desert Story Dashboard",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).resolve().parent / "processed_data"
RAW_CRS = "EPSG:32648"
MAP_CRS = "EPSG:4326"
HOUSEHOLD_SIZE_PROXY = 4.6

CLASS_COLORS = {
    "A: High Risk + Low Connectivity": "#B91C1C",
    "B: High Risk + Better Connectivity": "#EA580C",
    "C: Low Risk + Low Connectivity + High Population": "#CA8A04",
    "D: Low Risk + Low Connectivity": "#2563EB",
    "E: Lower Priority (Current Data)": "#15803D",
}


def _get_point_coords(geometry):
    """Return (lat, lon) for Point/MultiPoint geometries, else None."""
    if geometry is None or geometry.is_empty:
        return None
    if geometry.geom_type == "Point":
        return (geometry.y, geometry.x)
    if hasattr(geometry, "geoms") and len(geometry.geoms) > 0:
        first_geom = geometry.geoms[0]
        if first_geom.geom_type == "Point":
            return (first_geom.y, first_geom.x)
    return None


def _safe_number(value):
    num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(num) if not pd.isna(num) else None


def _infer_input_crs(gdf):
    """Infer CRS from coordinate ranges when CRS metadata is absent."""
    sample = None
    for geom in gdf.geometry:
        coords = _get_point_coords(geom)
        if coords is not None:
            sample = coords
            break
    if sample is None:
        return MAP_CRS

    lat, lon = sample
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return MAP_CRS
    return RAW_CRS


def _get_threshold(threshold_df, metric):
    if threshold_df is None or threshold_df.empty:
        return None
    row = threshold_df[threshold_df["metric"] == metric]
    if row.empty:
        return None
    value = _safe_number(row.iloc[0].get("value"))
    return value


@st.cache_data(show_spinner=False)
def load_data():
    required = [
        "01_provincial_summary.csv",
        "02_flood_risk_analysis.csv",
        "03_connectivity_statistics.csv",
        "04_indigenous_villages_mrd.geojson",
        "05_indigenous_registered_lands.geojson",
        "06_villages_with_risk_context.geojson",
    ]
    missing = [f for f in required if not (DATA_DIR / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required files in {DATA_DIR}: {', '.join(missing)}"
        )

    def load_geojson(path):
        with open(path, "r", encoding="utf-8") as fh:
            gj = json.load(fh)
        gdf = gpd.GeoDataFrame.from_features(gj["features"])
        inferred_crs = _infer_input_crs(gdf)
        if gdf.crs is None:
            gdf = gdf.set_crs(inferred_crs, allow_override=True)
        gdf = gdf.to_crs(MAP_CRS)
        numeric_cols = {
            "num_family",
            "land_size",
            "risk_score",
            "total_pop_exposed",
            "total_area_flooded_km2",
            "nearest_tower_km",
            "est_population_community",
            "est_population_need_connectivity",
        }
        for col in numeric_cols:
            if col in gdf.columns:
                gdf[col] = pd.to_numeric(gdf[col], errors="coerce")
        return gdf

    provincial = pd.read_csv(DATA_DIR / "01_provincial_summary.csv")
    flood = pd.read_csv(DATA_DIR / "02_flood_risk_analysis.csv")
    connectivity = pd.read_csv(DATA_DIR / "03_connectivity_statistics.csv")
    villages = load_geojson(DATA_DIR / "04_indigenous_villages_mrd.geojson")
    lands = load_geojson(DATA_DIR / "05_indigenous_registered_lands.geojson")
    villages_context = load_geojson(DATA_DIR / "06_villages_with_risk_context.geojson")

    model_communities = None
    osm_towers = None
    model_summary = None
    model_thresholds = None
    province_model_metrics = None
    osm_water_points = None

    if (DATA_DIR / "08_digital_desert_communities.geojson").exists():
        model_communities = load_geojson(DATA_DIR / "08_digital_desert_communities.geojson")
    if (DATA_DIR / "07_osm_telecom_towers.geojson").exists():
        osm_towers = load_geojson(DATA_DIR / "07_osm_telecom_towers.geojson")
    if (DATA_DIR / "07b_osm_water_points.geojson").exists():
        osm_water_points = load_geojson(DATA_DIR / "07b_osm_water_points.geojson")
    if (DATA_DIR / "09_digital_desert_summary.csv").exists():
        model_summary = pd.read_csv(DATA_DIR / "09_digital_desert_summary.csv")
    if (DATA_DIR / "10_model_thresholds.csv").exists():
        model_thresholds = pd.read_csv(DATA_DIR / "10_model_thresholds.csv")
    if (DATA_DIR / "11_province_model_metrics.csv").exists():
        province_model_metrics = pd.read_csv(DATA_DIR / "11_province_model_metrics.csv")

    return {
        "provincial": provincial,
        "flood": flood,
        "connectivity": connectivity,
        "villages": villages,
        "lands": lands,
        "villages_context": villages_context,
        "model_communities": model_communities,
        "osm_towers": osm_towers,
        "osm_water_points": osm_water_points,
        "model_summary": model_summary,
        "model_thresholds": model_thresholds,
        "province_model_metrics": province_model_metrics,
    }


def style_dashboard():
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Source+Sans+3:wght@400;600;700&display=swap');
:root {
  --surface: #0f172a;
  --surface-2: #111827;
  --panel: rgba(15, 23, 42, 0.78);
  --ink: #e5e7eb;
  --muted: #94a3b8;
  --line: #334155;
  --brand: #2b6cf3;
  --brand-2: #06b6d4;
  --warm: #f59e0b;
}
.stApp {
  font-family: 'Source Sans 3', sans-serif;
  background: radial-gradient(1100px 600px at 10% -8%, #1e293b 0%, #0b1220 36%, #050b17 100%);
  color: var(--ink);
}
.stButton > button {
  border-radius: 12px;
  border: 1px solid var(--line);
  background: linear-gradient(180deg, #111b2f 0%, #0d1526 100%);
  color: #dbeafe;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 600;
  letter-spacing: 0.1px;
  transition: all 180ms ease;
  min-height: 42px;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(94deg, var(--brand) 0%, var(--brand-2) 100%);
  color: #f8fafc;
  border: 1px solid transparent;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.28);
}
.stButton > button:hover {
  transform: translateY(-1px);
  border-color: #60a5fa;
  box-shadow: 0 8px 18px rgba(2, 6, 23, 0.35);
}
.story-hero {
  background:
    radial-gradient(800px 300px at 85% 10%, rgba(59,130,246,0.18) 0%, rgba(15,23,42,0) 55%),
    linear-gradient(160deg, #111b2f 0%, #0b1324 60%, #0a1020 100%);
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 22px 24px;
  color: #e2e8f0;
  margin-bottom: 14px;
  box-shadow: 0 20px 40px rgba(2, 6, 23, 0.38);
}
.story-pill {
  display: inline-block;
  border-radius: 10px;
  border: 1px solid #334155;
  background: #0f1a2e;
  color: #cbd5e1;
  padding: 4px 10px;
  font-size: 12px;
  margin-right: 8px;
  font-family: 'Space Grotesk', sans-serif;
}
.nav-wrap {
  border: 1px solid #243449;
  border-radius: 12px;
  padding: 10px 14px 2px 14px;
  background: var(--panel);
  backdrop-filter: blur(8px);
  margin-bottom: 12px;
}
.filter-wrap {
  border: 1px solid #243449;
  border-radius: 12px;
  padding: 12px 14px 10px 14px;
  background: rgba(12, 19, 35, 0.86);
  margin-bottom: 14px;
}
.diagram-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin: 8px 0 14px 0;
}
.diagram-card {
  flex: 1 1 180px;
  background: linear-gradient(135deg, #101a30 0%, #0f1d33 100%);
  border: 1px solid #304663;
  color: #e2e8f0;
  border-radius: 12px;
  padding: 14px;
  min-height: 98px;
}
.diagram-card h5 {
  margin: 0 0 8px 0;
  color: #7dd3fc;
  font-size: 14px;
  font-family: 'Space Grotesk', sans-serif;
}
.diagram-arrow {
  align-self: center;
  color: #38bdf8;
  font-size: 22px;
  padding: 0 2px;
}
.mini-note {
  border-left: 4px solid #38bdf8;
  background: rgba(9, 16, 30, 0.9);
  border-radius: 8px;
  padding: 10px 12px;
  color: #cbd5e1;
}
.insight-card {
  border: 1px solid #2a3f5d;
  background: linear-gradient(170deg, rgba(17, 26, 46, 0.95) 0%, rgba(12, 20, 35, 0.95) 100%);
  border-radius: 14px;
  padding: 12px 14px 8px 14px;
}
.insight-title {
  font-family: 'Space Grotesk', sans-serif;
  color: #f8fafc;
  font-size: 16px;
  margin-bottom: 4px;
}
.insight-sub {
  color: #9fb3c8 !important;
  font-size: 13px;
  margin-bottom: 10px;
}
.flow-wrap {
  border: 1px solid #2f445f;
  border-radius: 14px;
  padding: 14px;
  background: rgba(12, 20, 35, 0.85);
}
.flow-row {
  display: flex;
  align-items: stretch;
  gap: 10px;
  flex-wrap: wrap;
}
.flow-node {
  flex: 1 1 190px;
  border: 1px solid #335173;
  border-radius: 12px;
  padding: 12px;
  background: linear-gradient(160deg, #12213a 0%, #0d182b 100%);
}
.flow-node h5 {
  margin: 0 0 6px 0;
  color: #a5d8ff;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 14px;
}
.flow-arrow {
  align-self: center;
  color: #60a5fa;
  font-size: 24px;
  padding: 0 2px;
}
.phase-card {
  border: 1px solid #31507b;
  border-radius: 12px;
  padding: 12px;
  background: linear-gradient(165deg, rgba(18, 30, 53, 0.95) 0%, rgba(12, 22, 40, 0.95) 100%);
}
.source-card {
  border: 1px solid #2b425f;
  border-radius: 12px;
  background: linear-gradient(165deg, rgba(17, 27, 48, 0.95) 0%, rgba(13, 22, 39, 0.95) 100%);
  padding: 12px 14px;
  min-height: 98px;
}
.source-card h5 {
  margin: 0 0 5px 0;
  font-size: 14px;
  color: #bfdbfe;
  font-family: 'Space Grotesk', sans-serif;
}
.source-card p {
  margin: 0;
  font-size: 13px;
  color: #b9c7d8 !important;
}
.action-card {
  border: 1px solid #2a3f5d;
  border-radius: 12px;
  padding: 12px;
  background: linear-gradient(160deg, rgba(15, 27, 48, 0.95) 0%, rgba(12, 20, 36, 0.95) 100%);
}
.action-card h5 {
  margin: 0 0 6px 0;
  font-size: 14px;
  color: #93c5fd;
  font-family: 'Space Grotesk', sans-serif;
}
h1, h2, h3, h4 {
  font-family: 'Space Grotesk', sans-serif !important;
  color: #f8fafc !important;
  letter-spacing: -0.2px;
}
p, span, label, .stMarkdown, .stCaption {
  color: #cbd5e1 !important;
}
div[data-testid="stMetric"] {
  background: linear-gradient(180deg, rgba(16, 25, 44, 0.92) 0%, rgba(10, 17, 30, 0.92) 100%);
  border: 1px solid #2a3c54;
  border-radius: 12px;
  padding: 10px 12px;
}
div[data-baseweb="select"] > div {
  background: #0f1a2d;
  border-color: #334155;
}
div[data-baseweb="select"] * {
  color: #e2e8f0 !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def get_story_metrics(data):
    lands = data["lands"].copy()
    families = pd.to_numeric(lands.get("num_family"), errors="coerce").fillna(0)
    est_pop = int((families * HOUSEHOLD_SIZE_PROXY).sum())
    provinces = lands["province"].dropna().nunique()
    towers = 0 if data["osm_towers"] is None else len(data["osm_towers"])
    return {
        "communities": len(lands),
        "families": int(families.sum()),
        "estimated_population": est_pop,
        "provinces": int(provinces),
        "towers": int(towers),
    }


def build_priority_frame(model_df, thresholds):
    df = model_df.copy()
    risk_cut = _get_threshold(thresholds, "high_risk_cutoff") or 1.0
    dist_cut = _get_threshold(thresholds, "low_connectivity_km_cutoff") or 1.0
    pop_cut = _get_threshold(thresholds, "high_population_cutoff") or 1.0

    df["risk_score"] = pd.to_numeric(df.get("risk_score"), errors="coerce").fillna(0.0)
    df["nearest_tower_km"] = pd.to_numeric(df.get("nearest_tower_km"), errors="coerce").fillna(0.0)
    df["est_population_community"] = pd.to_numeric(df.get("est_population_community"), errors="coerce").fillna(0.0)

    # Transparent composite score for ranking only.
    df["score_risk"] = (df["risk_score"] / risk_cut).clip(0, 3)
    df["score_distance"] = (df["nearest_tower_km"] / dist_cut).clip(0, 3)
    df["score_population"] = (df["est_population_community"] / pop_cut).clip(0, 3)
    df["priority_score"] = (0.5 * df["score_risk"]) + (0.3 * df["score_distance"]) + (0.2 * df["score_population"])
    return df


def render_global_filters(model_df):
    provinces = sorted(model_df["province"].dropna().unique().tolist())
    classes = sorted(model_df["digital_desert_class"].dropna().unique().tolist())

    if "flt_provinces" not in st.session_state:
        st.session_state.flt_provinces = provinces
    if "flt_classes" not in st.session_state:
        st.session_state.flt_classes = classes
    if "flt_show_towers" not in st.session_state:
        st.session_state.flt_show_towers = True
    if "flt_priority_only" not in st.session_state:
        st.session_state.flt_priority_only = False

    st.markdown('<div class="filter-wrap">', unsafe_allow_html=True)
    with st.form("global_filters"):
        c1, c2, c3, c4 = st.columns([2.4, 2.4, 1.1, 1.1])
        with c1:
            cur_prov = st.session_state.get("flt_provinces", provinces)
            all_prov = st.checkbox("All Provinces", value=len(cur_prov) == len(provinces))
            selected_prov = st.multiselect(
                "Province",
                provinces,
                default=provinces if all_prov else cur_prov,
            )
        with c2:
            cur_cls = st.session_state.get("flt_classes", classes)
            all_cls = st.checkbox("All Classes", value=len(cur_cls) == len(classes))
            selected_cls = st.multiselect(
                "Class",
                classes,
                default=classes if all_cls else cur_cls,
            )
        with c3:
            show_towers = st.checkbox("Show telecom", value=st.session_state.get("flt_show_towers", True))
        with c4:
            priority_only = st.checkbox("Priority only", value=st.session_state.get("flt_priority_only", False))
        applied = st.form_submit_button("Apply Filters", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if applied:
        st.session_state.flt_provinces = selected_prov if selected_prov else provinces
        st.session_state.flt_classes = selected_cls if selected_cls else classes
        st.session_state.flt_show_towers = show_towers
        st.session_state.flt_priority_only = priority_only

    filtered = model_df[
        model_df["province"].isin(st.session_state.get("flt_provinces", provinces))
        & model_df["digital_desert_class"].isin(st.session_state.get("flt_classes", classes))
    ].copy()
    if st.session_state.get("flt_priority_only", False) and not filtered.empty:
        filtered = filtered[filtered["priority_score"] >= filtered["priority_score"].quantile(0.7)]

    return filtered


def render_header():
    st.markdown(
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="story-hero">
  <div class="story-pill">Interpretability First</div>
  <div class="story-pill">Policy-Oriented</div>
  <h1 style="margin: 8px 0 4px 0; color:#f8fafc;">Digital Desert Story: North-eastern Cambodia</h1>
  <p style="margin: 0; color:#cbd5e1;">
    A guided narrative to identify where communities face the double burden of flood vulnerability and weak network access.
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_page_start(data):
    st.subheader("Overview")
    metrics = get_story_metrics(data)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Communities", f"{metrics['communities']:,}")
    c2.metric("Families", f"{metrics['families']:,}")
    c3.metric("Est. People", f"{metrics['estimated_population']:,}")
    c4.metric("Provinces in Model", metrics["provinces"])
    c5.metric("OSM Telecom Points", metrics["towers"])

    st.info("Goal: find communities with high flood vulnerability and poor network proximity, then rank them for action.")


def render_page_data(data):
    st.subheader("Data Sources")
    if data["model_communities"] is None:
        st.warning("Model outputs not found. Run `python build_digital_desert_model.py` first.")
        return

    model = data["model_communities"].copy()
    model["risk_score"] = pd.to_numeric(model["risk_score"], errors="coerce")
    model["nearest_tower_km"] = pd.to_numeric(model["nearest_tower_km"], errors="coerce")
    model["nearest_water_km"] = pd.to_numeric(model["nearest_water_km"], errors="coerce")
    model["elevation_m"] = pd.to_numeric(model["elevation_m"], errors="coerce")

    p = data["province_model_metrics"].copy() if data["province_model_metrics"] is not None else None

    st.markdown("#### Source-to-Feature Map")
    src_cards = st.columns(6)
    card_payload = [
        ("MRD Indigenous Villages", "Community location and indigenous context"),
        ("Registered Communal Lands", "Family counts and local population proxy"),
        ("Flood Risk Inputs", "Provincial flood signal for vulnerability"),
        ("OSM Waterways", "Water proximity proxy for flood exposure"),
        ("OpenTopoData Elevation", "Terrain sensitivity signal"),
        ("OSM Telecom Infrastructure", "Nearest network-distance proxy"),
    ]
    for idx, (title, desc) in enumerate(card_payload):
        with src_cards[idx]:
            st.markdown(f'<div class="source-card"><h5>{title}</h5><p>{desc}</p></div>', unsafe_allow_html=True)

    st.markdown("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="insight-card"><div class="insight-title">MRD + Communal Lands</div><div class="insight-sub">Who and where are the target communities?</div></div>', unsafe_allow_html=True)
        by_prov = model["province"].value_counts().reset_index()
        by_prov.columns = ["province", "communities"]
        fig = px.bar(by_prov, x="province", y="communities", color="communities", color_continuous_scale="Tealgrn")
        fig.update_layout(height=320, margin=dict(l=8, r=8, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Community records come from official indigenous communal land data.")

    with c2:
        st.markdown('<div class="insight-card"><div class="insight-title">Flood Vulnerability Inputs</div><div class="insight-sub">Flood signal + water proximity + elevation</div></div>', unsafe_allow_html=True)
        flood_df = p.sort_values("avg_flood_score", ascending=False) if p is not None else pd.DataFrame()
        if not flood_df.empty:
            fig = px.bar(flood_df, x="province", y="avg_flood_score", color="avg_flood_score", color_continuous_scale="OrRd")
        else:
            tmp = model.groupby("province", as_index=False)["risk_score"].mean().rename(columns={"risk_score": "avg_flood_score"})
            fig = px.bar(tmp, x="province", y="avg_flood_score", color="avg_flood_score", color_continuous_scale="OrRd")
        fig.update_layout(height=320, margin=dict(l=8, r=8, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Flood score is harmonized at community level and mapped to provinces for comparison.")

    with c3:
        st.markdown('<div class="insight-card"><div class="insight-title">Connectivity Inputs</div><div class="insight-sub">Distance to nearest telecom infrastructure</div></div>', unsafe_allow_html=True)
        net_df = p.sort_values("avg_network_distance_km", ascending=False) if p is not None else model.groupby("province", as_index=False)["nearest_tower_km"].mean()
        ycol = "avg_network_distance_km" if "avg_network_distance_km" in net_df.columns else "nearest_tower_km"
        fig = px.bar(net_df, x="province", y=ycol, color=ycol, color_continuous_scale="Blues")
        fig.update_layout(height=320, margin=dict(l=8, r=8, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Higher values indicate weaker network accessibility for communities.")

    c4, c5, c6 = st.columns(3)
    with c4:
        st.markdown('<div class="insight-card"><div class="insight-title">Waterway Proxy Density</div><div class="insight-sub">Free OSM water points supporting flood proxy</div></div>', unsafe_allow_html=True)
        water_count = 0 if data["osm_water_points"] is None else len(data["osm_water_points"])
        tower_count = 0 if data["osm_towers"] is None else len(data["osm_towers"])
        src_counts = pd.DataFrame({"source": ["Water points", "Cell towers"], "count": [water_count, tower_count]})
        fig = px.bar(src_counts, x="source", y="count", color="source", color_discrete_sequence=["#38bdf8", "#a78bfa"])
        fig.update_layout(height=300, margin=dict(l=8, r=8, t=10, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("OpenStreetMap contributes free geospatial proxies for exposure and connectivity.")

    with c5:
        st.markdown('<div class="insight-card"><div class="insight-title">Elevation Context</div><div class="insight-sub">Topographic sensitivity from OpenTopoData</div></div>', unsafe_allow_html=True)
        elev = model[["province", "elevation_m"]].dropna()
        fig = px.box(elev, x="province", y="elevation_m", color="province")
        fig.update_layout(height=300, margin=dict(l=8, r=8, t=10, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Lower elevations contribute to higher flood vulnerability in the proxy model.")

    with c6:
        st.markdown('<div class="insight-card"><div class="insight-title">Model Coverage</div><div class="insight-sub">How much data is modeled end-to-end</div></div>', unsafe_allow_html=True)
        stages = pd.DataFrame(
            {
                "stage": ["Communities Ingested", "Flood Proxies Enriched", "Connectivity Enriched", "Final Scored"],
                "count": [len(model), len(model.dropna(subset=["risk_score"])), len(model.dropna(subset=["nearest_tower_km"])), len(model.dropna(subset=["priority_score"]) if "priority_score" in model.columns else model)],
            }
        )
        fig = px.funnel(stages, x="count", y="stage", color="stage")
        fig.update_layout(height=300, margin=dict(l=8, r=8, t=10, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("This shows the full data pipeline coverage from ingestion to model-ready scoring.")


def render_page_model(data):
    st.subheader("Model Logic")
    if data["model_communities"] is None:
        st.warning("Model outputs not found. Run `python build_digital_desert_model.py` first.")
        return

    thresholds = data["model_thresholds"]
    high_risk = _get_threshold(thresholds, "high_risk_cutoff")
    low_conn = _get_threshold(thresholds, "low_connectivity_km_cutoff")
    high_pop = _get_threshold(thresholds, "high_population_cutoff")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("High Risk Cutoff", f"{0 if high_risk is None else high_risk:,.2f}")
    with col2:
        st.metric("Low Connectivity Cutoff", f"{0 if low_conn is None else low_conn:.2f} km")
    with col3:
        st.metric("High Population Cutoff", f"{0 if high_pop is None else high_pop:,.0f} people")

    model_df = build_priority_frame(data["model_communities"], thresholds)
    class_counts = model_df["digital_desert_class"].value_counts().reset_index()
    class_counts.columns = ["digital_desert_class", "communities"]
    fig = px.bar(
        class_counts,
        x="digital_desert_class",
        y="communities",
        title="Community Count by Rule-Based Class",
        color="digital_desert_class",
        color_discrete_map=CLASS_COLORS,
    )
    fig.update_xaxes(tickangle=-25)
    st.plotly_chart(fig, use_container_width=True)

    if high_risk is not None and low_conn is not None:
        scatter = px.scatter(
            model_df,
            x="nearest_tower_km",
            y="risk_score",
            color="digital_desert_class",
            size="est_population_community",
            color_discrete_map=CLASS_COLORS,
            hover_name="ip_name",
            title="Interpretability Lens: Flood Risk vs Network Distance",
            labels={
                "nearest_tower_km": "Distance to Nearest Telecom Proxy (km)",
                "risk_score": "Flood Risk Score",
            },
        )
        scatter.add_vline(x=low_conn, line_dash="dash", line_color="#1d4ed8")
        scatter.add_hline(y=high_risk, line_dash="dash", line_color="#b91c1c")
        st.plotly_chart(scatter, use_container_width=True)

    st.caption("Top-right quadrant = high flood risk + far telecom distance (highest concern).")


def render_page_map(data):
    st.subheader("Digital Desert Risk Map")
    if data["model_communities"] is None:
        st.warning("Model outputs not found. Run `python build_digital_desert_model.py` first.")
        return

    model = build_priority_frame(data["model_communities"], data["model_thresholds"])
    provinces = sorted(model["province"].dropna().unique().tolist())
    classes = sorted(model["digital_desert_class"].dropna().unique().tolist())

    if "map_prov" not in st.session_state:
        st.session_state.map_prov = provinces
    if "map_classes" not in st.session_state:
        st.session_state.map_classes = classes
    if "map_show_heat" not in st.session_state:
        st.session_state.map_show_heat = True
    if "map_show_points" not in st.session_state:
        st.session_state.map_show_points = True
    if "map_show_towers" not in st.session_state:
        st.session_state.map_show_towers = False
    if "map_priority_only" not in st.session_state:
        st.session_state.map_priority_only = False
    if "map_basemap" not in st.session_state:
        st.session_state.map_basemap = "Light"

    left, right = st.columns([1, 3], gap="medium")
    with left:
        st.markdown("### Map Controls")
        with st.form("map_controls_form"):
            all_prov = st.checkbox("All Provinces", value=len(st.session_state.map_prov) == len(provinces))
            prov_selected = st.multiselect("Province", provinces, default=provinces if all_prov else st.session_state.map_prov)
            all_cls = st.checkbox("All Classes", value=len(st.session_state.map_classes) == len(classes))
            cls_selected = st.multiselect("Class", classes, default=classes if all_cls else st.session_state.map_classes)
            show_heat = st.checkbox("Flood heatmap", value=st.session_state.map_show_heat)
            show_points = st.checkbox("Community points", value=st.session_state.map_show_points)
            show_towers = st.checkbox("Cell towers", value=st.session_state.map_show_towers)
            priority_only = st.checkbox("Priority hotspots only", value=st.session_state.map_priority_only)
            basemap = st.selectbox("Basemap", ["Light", "Dark", "Street"], index=["Light", "Dark", "Street"].index(st.session_state.map_basemap))
            hotspot_n = st.slider("Top hotspots", min_value=5, max_value=20, value=10)
            apply = st.form_submit_button("Update Map", use_container_width=True)

        if apply:
            st.session_state.map_prov = prov_selected if prov_selected else provinces
            st.session_state.map_classes = cls_selected if cls_selected else classes
            st.session_state.map_show_heat = show_heat
            st.session_state.map_show_points = show_points
            st.session_state.map_show_towers = show_towers
            st.session_state.map_priority_only = priority_only
            st.session_state.map_basemap = basemap
        else:
            show_heat = st.session_state.map_show_heat
            show_points = st.session_state.map_show_points
            show_towers = st.session_state.map_show_towers
            priority_only = st.session_state.map_priority_only
            basemap = st.session_state.map_basemap
            hotspot_n = 10

    filtered = model[
        model["province"].isin(st.session_state.map_prov)
        & model["digital_desert_class"].isin(st.session_state.map_classes)
    ].copy()
    if priority_only and not filtered.empty:
        filtered = filtered.sort_values("priority_score", ascending=False).head(hotspot_n)

    if filtered.empty:
        st.info("No communities match the current map filters.")
        return

    coords = [_get_point_coords(g) for g in filtered.geometry]
    coords = [c for c in coords if c is not None]
    center = [sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)] if coords else [13.5, 106.8]

    tile_name = {"Light": "CartoDB positron", "Dark": "CartoDB dark_matter", "Street": "OpenStreetMap"}.get(basemap, "CartoDB positron")
    m = folium.Map(location=center, zoom_start=8, tiles=tile_name, max_bounds=True)
    comm_layer = folium.FeatureGroup(name="Communities", show=show_points).add_to(m)
    tower_layer = folium.FeatureGroup(name="Cell Towers", show=show_towers).add_to(m)
    heat_layer = folium.FeatureGroup(name="Flood Heatmap", show=show_heat).add_to(m)

    if show_heat:
        heat_data = []
        for _, row in filtered.iterrows():
            c = _get_point_coords(row.geometry)
            if c is None:
                continue
            heat_data.append([c[0], c[1], _safe_number(row.get("risk_score")) or 0.0])
        if heat_data:
            HeatMap(
                heat_data,
                radius=26,
                blur=20,
                min_opacity=0.35,
                gradient={0.1: "#60a5fa", 0.35: "#22d3ee", 0.6: "#facc15", 0.85: "#fb923c", 1.0: "#ef4444"},
            ).add_to(heat_layer)

    if show_points:
        for _, row in filtered.iterrows():
            c = _get_point_coords(row.geometry)
            if c is None:
                continue
            est_pop = _safe_number(row.get("est_population_community"))
            radius = 4 if est_pop is None else max(4, min(10, 3 + est_pop / 300))
            cls = row.get("digital_desert_class", "")
            class_color = CLASS_COLORS.get(cls, "#1e40af")
            popup = (
                f"<b>{row.get('ip_name', 'Community')}</b><br>"
                f"Province: {row.get('province', 'N/A')}<br>"
                f"Flood score: {0 if _safe_number(row.get('risk_score')) is None else _safe_number(row.get('risk_score')):,.0f}<br>"
                f"Tower distance: {0 if _safe_number(row.get('nearest_tower_km')) is None else _safe_number(row.get('nearest_tower_km')):.1f} km<br>"
                f"Class: {row.get('digital_desert_class', 'N/A')}"
            )
            folium.CircleMarker(
                location=c,
                radius=radius,
                color="#ffffff",
                fill=True,
                fill_color=class_color,
                fill_opacity=0.95,
                weight=1.2,
                popup=folium.Popup(popup, max_width=280),
            ).add_to(comm_layer)

    if show_towers and data["osm_towers"] is not None and len(data["osm_towers"]) > 0:
        for _, row in data["osm_towers"].iterrows():
            c = _get_point_coords(row.geometry)
            if c is None:
                continue
            folium.Marker(
                location=c,
                icon=folium.Icon(color="purple", icon="signal", prefix="fa"),
                tooltip="Cell tower proxy",
            ).add_to(tower_layer)

    legend_html = """
    <div style="
      position: fixed;
      bottom: 18px;
      left: 18px;
      z-index: 9999;
      background: rgba(12, 18, 31, 0.92);
      color: #e2e8f0;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 12px;
      line-height: 1.35;
      min-width: 220px;
    ">
      <div style="font-weight:700; margin-bottom:6px;">Map Legend</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:99px;background:#b91c1c;margin-right:6px;"></span>Community class A (highest concern)</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:99px;background:#ea580c;margin-right:6px;"></span>Community class B</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:99px;background:#ca8a04;margin-right:6px;"></span>Community class C</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:99px;background:#2563eb;margin-right:6px;"></span>Community class D</div>
      <div><span style="display:inline-block;width:10px;height:10px;border-radius:99px;background:#15803d;margin-right:6px;"></span>Community class E</div>
      <div style="margin-top:6px;">🗼 Purple icon: cell tower proxy</div>
      <div>Heat layer: higher flood vulnerability = warmer colors</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    with right:
        st_folium(m, width=1200, height=700)


def render_page_architecture(data):
    st.subheader("Architecture")
    st.markdown("#### One End-to-End Flow (Data → ETL → Modeling → Policy Action)")

    st.markdown(
        """
        <div class="flow-wrap">
          <div class="flow-row">
            <div class="flow-node"><h5>Source Layer</h5>MRD villages + communal lands, flood references, OSM telecom/water points, elevation API.</div>
            <div class="flow-arrow">➜</div>
            <div class="flow-node"><h5>ETL Layer</h5>CRS alignment, null handling, deduplication, distance enrichment, standardized community feature store.</div>
            <div class="flow-arrow">➜</div>
            <div class="flow-node"><h5>Modeling Layer</h5>Rule-based thresholds for flood, low connectivity, and population pressure to produce classes A-E.</div>
            <div class="flow-arrow">➜</div>
            <div class="flow-node"><h5>Decision Layer</h5>Hotspot prioritization, phased intervention packages, and transparent monitoring indicators.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if data["model_communities"] is not None:
        model = build_priority_frame(data["model_communities"], data["model_thresholds"])
        raw_count = len(model)
        etl_ready = len(model.dropna(subset=["risk_score", "nearest_tower_km", "est_population_community"]))
        scored = len(model.dropna(subset=["priority_score"]))
        hotspots = model[model["priority_score"] >= model["priority_score"].quantile(0.7)]
        hotspot_count = len(hotspots)

        left, right = st.columns([1.4, 1], gap="medium")
        with left:
            sankey = go.Figure(
                data=[
                    go.Sankey(
                        arrangement="snap",
                        node=dict(
                            pad=24,
                            thickness=18,
                            line=dict(color="#1e293b", width=1),
                            label=["Source Records", "ETL Harmonized", "Scored by Rules", "Priority Portfolio", "Action Queue"],
                            color=["#1d4ed8", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444"],
                        ),
                        link=dict(
                            source=[0, 1, 2, 3],
                            target=[1, 2, 3, 4],
                            value=[raw_count, etl_ready, scored, hotspot_count],
                            color=["rgba(59,130,246,0.35)", "rgba(6,182,212,0.35)", "rgba(20,184,166,0.35)", "rgba(245,158,11,0.35)"],
                        ),
                    )
                ]
            )
            sankey.update_layout(
                title="Pipeline Throughput (Simple Flow)",
                height=360,
                margin=dict(l=8, r=8, t=48, b=8),
                font=dict(size=13),
            )
            st.plotly_chart(sankey, use_container_width=True)

        with right:
            class_counts = (
                model["digital_desert_class"]
                .fillna("Unknown")
                .value_counts()
                .rename_axis("class")
                .reset_index(name="count")
            )
            pie = px.pie(
                class_counts,
                names="class",
                values="count",
                hole=0.52,
                color="class",
                color_discrete_map=CLASS_COLORS,
                title="Modeled Class Mix",
            )
            pie.update_layout(height=360, margin=dict(l=8, r=8, t=48, b=8), legend_title="")
            st.plotly_chart(pie, use_container_width=True)

        stage_df = pd.DataFrame(
            {
                "Stage": ["Source Records", "ETL Harmonized", "Rule Scored", "Top Priority"],
                "Count": [raw_count, etl_ready, scored, hotspot_count],
            }
        )
        bars = px.bar(
            stage_df,
            x="Count",
            y="Stage",
            orientation="h",
            color="Stage",
            text="Count",
            color_discrete_sequence=["#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b"],
        )
        bars.update_layout(height=280, margin=dict(l=8, r=8, t=18, b=8), showlegend=False)
        bars.update_traces(textposition="outside")
        st.plotly_chart(bars, use_container_width=True)

    st.markdown(
        """
        <div class="mini-note">
        <b>Why this architecture works:</b> each policy decision can be audited back to one transformed feature and one explicit rule, which keeps the model interpretable for committee review and implementation teams.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_actions(data):
    st.subheader("Action Plan")
    if data["model_communities"] is None:
        st.warning("Model outputs not found. Run `python build_digital_desert_model.py` first.")
        return

    model = build_priority_frame(data["model_communities"], data["model_thresholds"])
    shortlist = model.sort_values(["priority_score"], ascending=False).head(15).copy()
    shortlist["community"] = shortlist["ip_name"].fillna("Unknown")

    c1, c2 = st.columns([1.2, 1], gap="medium")
    with c1:
        fig = px.bar(
            shortlist.sort_values("priority_score", ascending=True),
            x="priority_score",
            y="community",
            color="digital_desert_class",
            color_discrete_map=CLASS_COLORS,
            orientation="h",
            labels={"priority_score": "Priority score", "community": "Community"},
            title="Top Priority Communities",
        )
        fig.update_layout(height=520, margin=dict(l=8, r=8, t=48, b=8), legend_title="")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        bubble = px.scatter(
            shortlist,
            x="nearest_tower_km",
            y="risk_score",
            size="est_population_community",
            color="digital_desert_class",
            color_discrete_map=CLASS_COLORS,
            hover_name="community",
            title="Risk-Connectivity-Scale Lens",
            labels={
                "nearest_tower_km": "Distance to telecom (km)",
                "risk_score": "Flood risk score",
            },
        )
        bubble.update_layout(height=520, margin=dict(l=8, r=8, t=48, b=8), legend_title="")
        st.plotly_chart(bubble, use_container_width=True)

    st.markdown("#### Phased Intervention Plan")
    p1, p2, p3 = st.columns(3, gap="medium")
    with p1:
        st.markdown(
            """
            <div class="phase-card">
              <h5>Phase 1 (0-3 months)</h5>
              Emergency connectivity and flood-alert readiness for top A/B communities with longest tower distance.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            """
            <div class="phase-card">
              <h5>Phase 2 (4-9 months)</h5>
              Add shared internet points, school/health digital access hubs, and targeted digital-skills support.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with p3:
        st.markdown(
            """
            <div class="phase-card">
              <h5>Phase 3 (10-18 months)</h5>
              Expand to next-priority communities using monitored improvements in risk exposure and access distance.
            </div>
            """,
            unsafe_allow_html=True,
        )

    prov_actions = (
        shortlist.groupby("province", as_index=False)
        .agg(
            hotspot_count=("community", "count"),
            avg_priority=("priority_score", "mean"),
            avg_distance_km=("nearest_tower_km", "mean"),
        )
        .sort_values("avg_priority", ascending=False)
    )
    fig2 = px.bar(
        prov_actions,
        x="province",
        y="hotspot_count",
        color="avg_priority",
        color_continuous_scale="Sunset",
        title="Where to Start First (Province Portfolio)",
        hover_data=["avg_distance_km"],
    )
    fig2.update_layout(height=340, margin=dict(l=8, r=8, t=48, b=8))
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown(
        """
        <div class="mini-note">
        <b>How the solution architecture executes this plan:</b> the ETL layer refreshes community features, the rule-based model recalculates class and priority scores, and the dashboard updates province portfolios so decision-makers can re-sequence interventions using the same transparent logic every cycle.
        </div>
        """,
        unsafe_allow_html=True,
    )


style_dashboard()

try:
    data = load_data()
except Exception as exc:
    st.error("Data loading failed. Please verify `processed_data/` and rerun ETL/model scripts.")
    st.exception(exc)
    st.stop()

render_header()
if "page" not in st.session_state:
    st.session_state.page = "Overview"

st.markdown('<div class="nav-wrap">', unsafe_allow_html=True)
nav_items = [
    ("Overview", "Overview"),
    ("Data Sources", "Data Sources"),
    ("Model Logic", "Model Logic"),
    ("Risk Map", "Risk Map"),
    ("Action Plan", "Action Plan"),
    ("Architecture", "Architecture"),
]
nav_cols = st.columns(len(nav_items))
for idx, (label, value) in enumerate(nav_items):
    current_page = st.session_state.get("page", "Overview")
    btn_type = "primary" if current_page == value else "secondary"
    if nav_cols[idx].button(label, key=f"nav_btn_{idx}", use_container_width=True, type=btn_type):
        st.session_state.page = value
st.markdown("</div>", unsafe_allow_html=True)

current_page = st.session_state.get("page", "Overview")
if current_page == "Overview":
    render_page_start(data)
elif current_page == "Data Sources":
    render_page_data(data)
elif current_page == "Model Logic":
    render_page_model(data)
elif current_page == "Risk Map":
    render_page_map(data)
elif current_page == "Architecture":
    render_page_architecture(data)
else:
    render_page_actions(data)

st.divider()
st.caption(
    "Hackathon project: Bridging the Digital Divide by Uncovering Digital Deserts. "
    "Sources include MRD records, flood-risk inputs, OSM telecom proxy points, and team ETL outputs."
)
