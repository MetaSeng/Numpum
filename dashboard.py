"""
Interactive Dashboard: Digital Desert in North-eastern Cambodia
Bridging the Digital Divide by Uncovering Digital Deserts Hackathon

This Streamlit app visualizes connectivity gaps, flood vulnerability, and 
indigenous community locations across 6 provinces in NE Cambodia.
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json

# ============================================================================
# Page Configuration
# ============================================================================
st.set_page_config(
    page_title="Digital Desert Dashboard",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# Load Data
# ============================================================================
@st.cache_data
def load_data():
    data_dir = Path('./processed_data')
    
    # Load CSV files
    provincial = pd.read_csv(data_dir / '01_provincial_summary.csv')
    flood_risk = pd.read_csv(data_dir / '02_flood_risk_analysis.csv')
    connectivity = pd.read_csv(data_dir / '03_connectivity_statistics.csv')
    
    # Clean provincial data - convert numeric columns
    numeric_cols = ['total_families', 'total_pop_2025', 'area_sq_km', 'avg_findex']
    for col in numeric_cols:
        if col in provincial.columns:
            provincial[col] = pd.to_numeric(provincial[col], errors='coerce').fillna(0)
    
    # Clean flood_risk data
    for col in ['num_family_affected', 'area_flooded_sq_km', 'risk_score']:
        if col in flood_risk.columns:
            flood_risk[col] = pd.to_numeric(flood_risk[col], errors='coerce').fillna(0)
    
    # Load GeoJSON files using json module to avoid fiona compatibility issues
    def load_geojson(path):
        with open(path, 'r') as f:
            geojson_data = json.load(f)
        gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])
        # Clean numeric columns - be selective
        numeric_cols = {'num_family', 'land_size', 'population', 'area_sq_km', 'flooded_pop', 'flooded_area_sq_km', 'risk_score'}
        for col in gdf.columns:
            if col in numeric_cols:
                gdf[col] = pd.to_numeric(gdf[col], errors='coerce')
        return gdf
    
    villages = load_geojson(data_dir / '04_indigenous_villages_mrd.geojson')
    registered_lands = load_geojson(data_dir / '05_indigenous_registered_lands.geojson')
    villages_context = load_geojson(data_dir / '06_villages_with_risk_context.geojson')
    
    return {
        'provincial': provincial,
        'flood_risk': flood_risk,
        'connectivity': connectivity,
        'villages': villages,
        'registered_lands': registered_lands,
        'villages_context': villages_context
    }

data = load_data()

# ============================================================================
# Title & Introduction
# ============================================================================
st.markdown("""
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; margin-bottom: 30px;">
    <h1>🗺️ Digital Desert: North-eastern Cambodia</h1>
    <h3>Bridging the Digital Divide by Uncovering Digital Deserts</h3>
    <p><strong>Objective:</strong> Identify connectivity gaps, vulnerability zones, and strategic intervention points for indigenous communities across 6 provinces in NE Cambodia.</p>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# Sidebar Navigation
# ============================================================================
st.sidebar.title("📊 Dashboard Navigation")
page = st.sidebar.radio(
    "Select a section:",
    ["🏠 Overview", "📍 Interactive Map", "📈 Provincial Analysis", 
     "⚠️ Flood Vulnerability", "👥 Indigenous Communities", "💡 Insights"]
)

# ============================================================================
# PAGE 1: OVERVIEW
# ============================================================================
if page == "🏠 Overview":
    st.header("Executive Summary")
    
    # Key Statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🏘️ Indigenous Villages",
            f"{data['villages'].shape[0]}",
            "MRD-identified communities"
        )
    
    with col2:
        st.metric(
            "📍 Registered Land Areas",
            f"{data['registered_lands'].shape[0]}",
            "Communal lands"
        )
    
    with col3:
        total_families = data['provincial']['total_families'].sum()
        st.metric(
            "👨‍👩‍👧‍👦 Total Families",
            f"{int(total_families):,}",
            "In registered communities"
        )
    
    with col4:
        avg_risk = data['flood_risk']['risk_score'].mean()
        st.metric(
            "⚠️ Avg Risk Score",
            f"{avg_risk:.0f}",
            "Population exposure + area"
        )
    
    st.divider()
    
    # Context Cards
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🌍 Geographic Focus")
        provinces = ", ".join(data['provincial']['province'].dropna().unique())
        st.write(f"""
        **Target Provinces:** {provinces}
        
        These 6 provinces in the northeastern highlands represent 
        areas with the lowest digital connectivity and highest indigenous 
        population concentrations in Cambodia.
        """)
    
    with col2:
        st.subheader("🎯 Challenge")
        st.write("""
        Indigenous communities in remote areas face:
        - **Limited infrastructure** (poor/no cell coverage)
        - **High flood risk** (critical for early warning systems)
        - **Language barriers** (restricts access to services)
        - **Economic vulnerability** (limited market access)
        - **Digital skills gaps** (limited training opportunities)
        """)
    
    st.divider()
    st.subheader("📊 Quick View: Top Risk Provinces")
    
    flood_sorted = data['flood_risk'].sort_values('risk_score', ascending=False).head(5)
    fig = px.bar(
        flood_sorted,
        x='province',
        y='risk_score',
        color='total_pop_exposed',
        title='Higher risk scores = more vulnerable',
        labels={'risk_score': 'Risk Score', 'province': 'Province'},
        color_continuous_scale='Reds'
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# PAGE 2: INTERACTIVE MAP
# ============================================================================
elif page == "📍 Interactive Map":
    st.header("Interactive Village & Risk Map")
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.subheader("Map Controls")
        show_villages = st.checkbox("🏘️ Villages", value=True)
        show_lands = st.checkbox("📍 Registered Lands", value=False)
        show_flood_zones = st.checkbox("🌊 Flood Zones", value=True)
        
        selected_ethnic = st.selectbox(
            "Filter by ethnic group:",
            ["All"] + sorted(data['villages']['ethnic'].dropna().unique().tolist())
        )
    
    with col1:
        # Create folium map
        m = folium.Map(
            location=[13.5, 106.8],
            zoom_start=8,
            tiles="OpenStreetMap"
        )
        
        # Filter data
        villages_to_plot = data['villages'].copy()
        if selected_ethnic != "All":
            villages_to_plot = villages_to_plot[villages_to_plot['ethnic'] == selected_ethnic]
        
        # Add village markers
        if show_villages and len(villages_to_plot) > 0:
            for idx, row in villages_to_plot.iterrows():
                # Extract coordinates - handle both Point and MultiPoint geometries
                try:
                    if hasattr(row.geometry, 'geoms'):  # MultiPoint
                        coords = (row.geometry.geoms[0].y, row.geometry.geoms[0].x)
                    else:  # Point
                        coords = (row.geometry.y, row.geometry.x)
                except:
                    continue
                
                popup_text = f"""
                <b>{row.get('village', 'Unknown')}</b><br>
                Ethnic: {row.get('ethnic', 'N/A')}<br>
                District: {row.get('district', 'N/A')}<br>
                Province: {row.get('province', 'N/A')}
                """
                folium.Marker(
                    location=coords,
                    popup=folium.Popup(popup_text, max_width=250),
                    icon=folium.Icon(color='blue', icon='info-sign'),
                    tooltip=row.get('village', 'Village')
                ).add_to(m)
        
        # Add registered lands
        if show_lands and len(data['registered_lands']) > 0:
            for idx, row in data['registered_lands'].iterrows():
                # Extract coordinates - handle both Point and MultiPoint geometries
                try:
                    if hasattr(row.geometry, 'geoms'):  # MultiPoint
                        coords = (row.geometry.geoms[0].y, row.geometry.geoms[0].x)
                    else:  # Point
                        coords = (row.geometry.y, row.geometry.x)
                    
                    num_fam = int(row.get('num_family', 0)) if isinstance(row.get('num_family'), (int, float)) else 0
                    land_sz = float(row.get('land_size', 0)) if isinstance(row.get('land_size'), (int, float)) else 0
                except:
                    continue
                    
                popup_text = f"""
                <b>{row.get('ip_name', 'IP Community')}</b><br>
                Families: {num_fam}<br>
                Land Area: {land_sz:.2f} sq km<br>
                Province: {row.get('province', 'N/A')}
                """
                folium.Marker(
                    location=coords,
                    popup=folium.Popup(popup_text, max_width=250),
                    icon=folium.Icon(color='green', icon='leaf'),
                    tooltip=row.get('ip_name', 'Registered Land')
                ).add_to(m)
        
        st_folium(m, width=1000, height=600)

# ============================================================================
# PAGE 3: PROVINCIAL ANALYSIS
# ============================================================================
elif page == "📈 Provincial Analysis":
    st.header("Provincial-Level Analysis")
    
    tab1, tab2, tab3 = st.tabs(["Summary Table", "Comparisons", "Time Context"])
    
    with tab1:
        st.subheader("Provincial Statistics")
        provincial_display = data['provincial'].fillna('-')
        st.dataframe(provincial_display, use_container_width=True, height=400)
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            # Indigenous communities by province
            mrd_data = data['provincial'][['province', 'mrd_villages']].dropna()
            fig1 = px.bar(
                mrd_data,
                x='province',
                y='mrd_villages',
                title='MRD-Identified Indigenous Villages by Province',
                labels={'mrd_villages': 'Number of Villages'},
                color='mrd_villages',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Registered lands by province
            reg_data = data['provincial'][['province', 'registered_areas']].dropna()
            if len(reg_data) > 0:
                fig2 = px.bar(
                    reg_data,
                    x='province',
                    y='registered_areas',
                    title='Registered Communal Land Areas by Province',
                    labels={'registered_areas': 'Number of Areas'},
                    color='registered_areas',
                    color_continuous_scale='Greens'
                )
                st.plotly_chart(fig2, use_container_width=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Flood exposure
            flood_data = data['flood_risk'].sort_values('risk_score', ascending=False)
            fig3 = px.bar(
                flood_data,
                x='province',
                y='total_pop_exposed',
                title='Population Exposed to Flooding (3-month period)',
                labels={'total_pop_exposed': 'Population Exposed'},
                color='total_pop_exposed',
                color_continuous_scale='Reds'
            )
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            # Area flooded
            fig4 = px.bar(
                flood_data,
                x='province',
                y='total_area_flooded_km2',
                title='Total Area Flooded (sq km)',
                labels={'total_area_flooded_km2': 'Area Flooded (sq km)'},
                color='total_area_flooded_km2',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig4, use_container_width=True)
    
    with tab3:
        st.info("""
        **Data Snapshot:** April 2, 2026
        
        - Findex data: World Bank Global Findex Database 2025
        - Flood events: FAO EVE Global Flood Monitoring System (March-April 2026)
        - Indigenous communities: Ministry of Rural Development records
        - Registered lands: Sub-decrees via Government Gazette
        
        This represents the most recent monitoring and administrative records available.
        """)

# ============================================================================
# PAGE 4: FLOOD VULNERABILITY
# ============================================================================
elif page == "⚠️ Flood Vulnerability":
    st.header("Flood Risk & Vulnerability Analysis")
    
    # Risk Matrix
    col1, col2 = st.columns(2)
    
    with col1:
        # Risk Score Distribution
        fig_scatter = px.scatter(
            data['flood_risk'],
            x='total_pop_exposed',
            y='total_area_flooded_km2',
            size='risk_score',
            color='risk_score',
            hover_name='province',
            title='Population Exposure vs Area Flooded',
            labels={
                'total_pop_exposed': 'Population Exposed',
                'total_area_flooded_km2': 'Area Flooded (sq km)'
            },
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    with col2:
        # Risk Ranking
        risk_ranking = data['flood_risk'].sort_values('risk_score', ascending=False)[
            ['province', 'risk_score', 'total_pop_exposed', 'affected_districts']
        ]
        
        fig_risk = px.bar(
            risk_ranking,
            y='province',
            x='risk_score',
            orientation='h',
            color='risk_score',
            title='Risk Score Ranking',
            color_continuous_scale='Reds',
            labels={'risk_score': 'Risk Score (Pop Exposed + Area Flooded)'}
        )
        st.plotly_chart(fig_risk, use_container_width=True)
    
    st.divider()
    st.subheader("🚨 Critical Findings")
    
    highest_risk = data['flood_risk'].loc[data['flood_risk']['risk_score'].idxmax()]
    highest_pop = data['flood_risk'].loc[data['flood_risk']['total_pop_exposed'].idxmax()]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Highest Overall Risk",
            highest_risk['province'],
            f"Score: {highest_risk['risk_score']:.0f}"
        )
    
    with col2:
        st.metric(
            "Highest Population Exposure",
            highest_pop['province'],
            f"{int(highest_pop['total_pop_exposed']):,} people"
        )
    
    with col3:
        total_exposed = data['flood_risk']['total_pop_exposed'].sum()
        st.metric(
            "Total Regional Exposure",
            f"{int(total_exposed):,}",
            "Across all provinces"
        )
    
    st.info("""
    **Why This Matters for Digital Inclusion:**
    
    Communities without reliable internet connectivity **cannot receive early warning alerts** 
    for floods. This creates a critical safety gap where vulnerable populations are exposed 
    to environmental hazards with no means of rapid communication or emergency response.
    """)

# ============================================================================
# PAGE 5: INDIGENOUS COMMUNITIES
# ============================================================================
elif page == "👥 Indigenous Communities":
    st.header("Indigenous Communities Profile")
    
    tab1, tab2, tab3 = st.tabs(["Ethnic Distribution", "Geographic Spread", "Registered Lands"])
    
    with tab1:
        st.subheader("Ethnic Composition")
        
        ethnic_counts = data['villages']['ethnic'].value_counts()
        fig = px.pie(
            values=ethnic_counts.values,
            names=ethnic_counts.index,
            title='Indigenous Ethnic Groups in NE Cambodia',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Ethnic Group Details")
        for ethnic, count in ethnic_counts.items():
            st.write(f"• **{ethnic}**: {count} villages identified")
    
    with tab2:
        st.subheader("Village Distribution by Province")
        
        village_by_prov = data['villages']['province'].value_counts()
        fig = px.bar(
            x=village_by_prov.index,
            y=village_by_prov.values,
            title='Villages by Province',
            labels={'x': 'Province', 'y': 'Number of Villages'},
            color=village_by_prov.values,
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Registered Communal Lands")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Families per property
            families_data = data['registered_lands'].dropna(subset=['num_family'])
            fig1 = px.histogram(
                families_data,
                x='num_family',
                nbins=10,
                title='Distribution of Family Counts',
                labels={'num_family': 'Number of Families per Property'},
                color_discrete_sequence=['#636EFA']
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Land area distribution
            area_data = data['registered_lands'].dropna(subset=['land_size'])
            fig2 = px.histogram(
                area_data,
                x='land_size',
                nbins=10,
                title='Distribution of Land Sizes',
                labels={'land_size': 'Land Area (sq km)'},
                color_discrete_sequence=['#00CC96']
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # Summary statistics
        st.subheader("Land Statistics Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        # Convert to numeric safely
        num_family_data = pd.to_numeric(data['registered_lands']['num_family'], errors='coerce').fillna(0)
        land_size_data = pd.to_numeric(data['registered_lands']['land_size'], errors='coerce').fillna(0)
        
        total_families = int(num_family_data.sum())
        avg_families = num_family_data.mean()
        total_area = land_size_data.sum()
        avg_area = land_size_data.mean()
        
        with col1:
            st.metric("Total Families", f"{total_families:,}")
        with col2:
            st.metric("Avg Family Count", f"{avg_families:.0f}")
        with col3:
            st.metric("Total Land Area", f"{total_area:.0f} sq km")
        with col4:
            st.metric("Avg Area/Property", f"{avg_area:.0f} sq km")

# ============================================================================
# PAGE 6: INSIGHTS & RECOMMENDATIONS
# ============================================================================
elif page == "💡 Insights":
    st.header("Key Insights & Recommendations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔍 Digital Desert Typologies")
        st.markdown("""
        **Type A: High-Risk/Low-Coverage Zones**
        - Kampong Thom, Kratie
        - Highest population exposure to flooding
        - Most critical for early warning infrastructure
        
        **Type B: Remote Indigenous Areas**
        - Ratanakiri, Mondulkiri, Stung Treng
        - Concentrated indigenous populations
        - Cultural & language barriers compound connectivity gaps
        
        **Type C: Under-resourced Regions**
        - Preah Vihear
        - Limited existing infrastructure data
        - Strategic opportunity for targeted intervention
        """)
    
    with col2:
        st.subheader("💼 Strategic Recommendations")
        st.markdown("""
        **Priority Infrastructure**
        1. Deploy emergency communication systems in flood-prone villages
        2. Establish community Wi-Fi hubs in district centers
        3. Partner with NGOs for digital literacy training
        
        **Phased Approach**
        - Phase 1: Cover 10 highest-risk villages (20% of target)
        - Phase 2: Expand to 30 villages (50% coverage)
        - Phase 3: Full coverage with locally-owned infrastructure
        
        **Economic Integration**
        - Enable e-commerce for agricultural products
        - Facilitate online services access
        - Support digital skill development
        """)
    
    st.divider()
    
    # Metric comparisons
    st.subheader("📊 Comparative Analysis")
    
    # Create a summary dataframe for easy comparison
    summary = data['provincial'][['province', 'mrd_villages', 'registered_areas', 'total_families']].copy()
    summary = summary.merge(
        data['flood_risk'][['province', 'risk_score', 'total_pop_exposed']],
        on='province',
        how='left'
    )
    summary = summary.fillna('-')
    
    st.dataframe(summary, use_container_width=True)
    
    st.divider()
    st.subheader("🎯 Proposed Intervention Framework")
    
    framework_data = {
        'Intervention Type': [
            'Network Infrastructure',
            'Digital Literacy',
            'Emergency Systems',
            'Economic Inclusion',
            'Community Engagement'
        ],
        'Target Communities': [
            '58 villages',
            '4,234+ families',
            'High-risk zones',
            'Remote areas',
            'All identified groups'
        ],
        'Expected Impact': [
            'Enable basic connectivity',
            'Build digital skills',
            'Save lives (flood warnings)',
            'Create market access',
            'Sustainable adoption'
        ],
        'Timeline': [
            '12-18 months',
            'Ongoing',
            '6-12 months',
            '18-24 months',
            'Continuous'
        ]
    }
    
    framework_df = pd.DataFrame(framework_data)
    st.table(framework_df)
    
    st.success("""
    ✅ **This dashboard provides data-driven evidence for policymakers and development organizations 
    to design targeted interventions that meaningfully improve digital equity and safety in 
    North-eastern Cambodia.**
    """)

# ============================================================================
# Footer
# ============================================================================
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p><small>Data Hackathon: Bridging the Digital Divide by Uncovering Digital Deserts</small></p>
    <p><small>Data sources: World Bank Findex, FAO EVE, Ministry of Rural Development, Open Development Cambodia</small></p>
    <p><small>Generated: April 2, 2026</small></p>
</div>
""", unsafe_allow_html=True)
