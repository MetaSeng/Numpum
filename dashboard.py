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
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium


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
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap');
:root {
  --bg1: #f7fafc;
  --bg2: #e6f0ff;
  --ink: #0f172a;
  --accent: #0b6bcb;
}
.stApp {
  font-family: 'Manrope', sans-serif;
  background: radial-gradient(circle at 5% 0%, #0f172a 0%, #020617 45%, #000814 100%);
}
.stButton > button {
  border-radius: 999px;
  border: 1px solid #334155;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(90deg, #2563eb 0%, #14b8a6 100%);
  color: white;
  border: none;
}
.story-hero {
  background: linear-gradient(120deg, #f8fafc 0%, #dbeafe 42%, #e0f2fe 100%);
  border: 1px solid #93c5fd;
  border-radius: 14px;
  padding: 20px 24px;
  color: var(--ink);
  margin-bottom: 16px;
}
.story-pill {
  display: inline-block;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  padding: 4px 10px;
  font-size: 12px;
  margin-right: 8px;
}
.nav-wrap {
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 10px 14px 2px 14px;
  background: #f8fbff;
  margin-bottom: 10px;
}
.filter-wrap {
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 12px 14px 10px 14px;
  background: #ffffff;
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
  background: linear-gradient(135deg, #0b1220 0%, #13233a 100%);
  border: 1px solid #1e3a5f;
  color: #e2e8f0;
  border-radius: 12px;
  padding: 14px;
  min-height: 98px;
}
.diagram-card h5 {
  margin: 0 0 8px 0;
  color: #93c5fd;
  font-size: 14px;
}
.diagram-arrow {
  align-self: center;
  color: #22d3ee;
  font-size: 22px;
  padding: 0 2px;
}
.mini-note {
  border-left: 4px solid #22d3ee;
  background: #0b1529;
  border-radius: 8px;
  padding: 10px 12px;
  color: #cbd5e1;
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
  <div class="story-pill"><i class="fa-solid fa-circle-check"></i> Interpretability First</div>
  <div class="story-pill"><i class="fa-solid fa-landmark"></i> Policy-Oriented</div>
  <h1 style="margin: 8px 0 4px 0; color:#0f172a;">Digital Desert Story: North-eastern Cambodia</h1>
  <p style="margin: 0; color:#334155;">
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
    st.subheader("Data")
    source_df = pd.DataFrame(
        [
            ["MRD Indigenous Villages", "Community location and ethnicity", "Village-level context"],
            ["Registered Communal Lands", "Community points and family counts", "Community-level profiling"],
            ["Flood Risk Analysis", "Province flood signal where available", "One component in flood vulnerability"],
            ["OpenStreetMap / Overpass (Waterways)", "Rivers/streams/water points", "Flood proximity proxy"],
            ["OpenTopoData (SRTM90m)", "Community elevation", "Low elevation flood sensitivity proxy"],
            ["OpenStreetMap / Overpass", "Telecom structure proxy points", "Network-distance proxy"],
        ],
        columns=["Source", "What it contributes", "Why it matters"],
    )
    st.dataframe(source_df, use_container_width=True, hide_index=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        by_province = data["province_model_metrics"].copy() if data["province_model_metrics"] is not None else data["lands"]["province"].value_counts().reset_index()
        if "communities" not in by_province.columns:
            by_province.columns = ["province", "communities"]
        fig = px.bar(
            by_province,
            x="province",
            y="communities",
            title="Communities Covered by Province",
            color="communities",
            color_continuous_scale="Tealgrn",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        flood = data["province_model_metrics"].copy() if data["province_model_metrics"] is not None else pd.DataFrame(columns=["province", "risk_score"])
        if "avg_flood_score" in flood.columns:
            flood = flood.sort_values("avg_flood_score", ascending=False)
            ycol = "avg_flood_score"
            title = "Flood Vulnerability Score by Province (Harmonized)"
        else:
            flood = data["flood"].copy()
            flood["risk_score"] = pd.to_numeric(flood["risk_score"], errors="coerce")
            flood = flood.dropna(subset=["risk_score"]).sort_values("risk_score", ascending=False)
            ycol = "risk_score"
            title = "Flood Risk Score by Province"
        fig = px.bar(
            flood,
            x="province",
            y=ycol,
            title=title,
            color=ycol,
            color_continuous_scale="OrRd",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col3:
        if data["province_model_metrics"] is not None:
            net = data["province_model_metrics"].copy().sort_values("avg_network_distance_km", ascending=False)
            fig = px.bar(
                net,
                x="province",
                y="avg_network_distance_km",
                title="Average Distance to Telecom by Province",
                color="avg_network_distance_km",
                color_continuous_scale="Blues",
            )
            st.plotly_chart(fig, use_container_width=True)

    water_points = 0 if data["osm_water_points"] is None else len(data["osm_water_points"])
    st.caption(f"Harmonized ETL now uses {water_points:,} water points + elevation + telecom proxies at community level.")


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


def render_page_architecture():
    st.subheader("Architecture & ETL Flow")
    st.markdown("#### End-to-End Solution")
    st.markdown(
        """
        <div class="diagram-row">
          <div class="diagram-card"><h5>1) Source Data</h5>MRD community points, flood inputs, OSM telecom, OSM waterways, elevation API.</div>
          <div class="diagram-arrow">➜</div>
          <div class="diagram-card"><h5>2) ETL Pipeline</h5>CRS normalization, null handling, distance features, and flood proxy construction.</div>
          <div class="diagram-arrow">➜</div>
          <div class="diagram-card"><h5>3) Modeling</h5>Transparent rule-based classes A-E from flood risk, connectivity distance, and population.</div>
          <div class="diagram-arrow">➜</div>
          <div class="diagram-card"><h5>4) Dashboard</h5>Interactive map + policy table + explainable visuals for committee review.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("#### ETL Layers")
    st.markdown(
        """
        <div class="diagram-row">
          <div class="diagram-card"><h5>Bronze</h5>Raw files and API pulls.</div>
          <div class="diagram-arrow">➜</div>
          <div class="diagram-card"><h5>Silver</h5>Standardized geometry, cleaned fields, derived distances and elevation.</div>
          <div class="diagram-arrow">➜</div>
          <div class="diagram-card"><h5>Gold</h5>Community risk dataset + summary tables ready for dashboard.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("#### Modeling Logic")
    st.markdown(
        """
        <div class="diagram-row">
          <div class="diagram-card"><h5>Inputs</h5>Flood proxy score, distance to tower, population proxy.</div>
          <div class="diagram-arrow">➜</div>
          <div class="diagram-card"><h5>Rules</h5>Threshold-based interpretability (no black-box clustering).</div>
          <div class="diagram-arrow">➜</div>
          <div class="diagram-card"><h5>Output</h5>Classes A-E + priority ranking for interventions.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="mini-note">
        <b>Why this design:</b> the committee can trace every score back to data and rules, making policy decisions auditable.
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
    shortlist = model.sort_values(["priority_score"], ascending=False).head(12)

    view = shortlist[
        [
            "ip_name",
            "province",
            "num_family",
            "est_population_community",
            "nearest_tower_km",
            "risk_score",
            "priority_score",
            "digital_desert_class",
        ]
    ].copy()
    view.columns = [
        "Community",
        "Province",
        "Families",
        "Est. Population",
        "Distance to Telecom (km)",
        "Flood Risk Score",
        "Priority Score",
        "Class",
    ]
    st.dataframe(view, use_container_width=True, hide_index=True, height=380)

    st.markdown(
        """
### Suggested phased plan
1. **First 3 months**: target the farthest high-priority communities with emergency alert channels.
2. **Months 4-9**: add community internet access points and local digital training.
3. **Months 10-18**: evaluate outcomes and expand to next tier communities.
        """
    )

    st.warning(
        "Important: This model is intentionally simple and interpretable. "
        "It is for transparent prioritization, not for replacing detailed field validation."
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
    ("🏠 Overview", "Overview"),
    ("🧾 Data Sources", "Data Sources"),
    ("🧠 Model Logic", "Model Logic"),
    ("🗺️ Risk Map", "Risk Map"),
    ("🎯 Action Plan", "Action Plan"),
    ("🧩 Architecture", "Architecture"),
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
    render_page_architecture()
else:
    render_page_actions(data)

st.divider()
st.caption(
    "Hackathon project: Bridging the Digital Divide by Uncovering Digital Deserts. "
    "Sources include MRD records, flood-risk inputs, OSM telecom proxy points, and team ETL outputs."
)
