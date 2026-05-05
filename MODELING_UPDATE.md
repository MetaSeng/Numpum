# Modeling Update (Committee + Mentor Feedback)

## What was updated
- Added **rule-based classification** (interpretable policy typology) instead of opaque clustering.
- Added **network accessibility proxy**: distance from each indigenous community point to nearest mapped telecom infrastructure from OpenStreetMap.
- Added explicit map-ready variables requested by mentor:
  - flood vulnerability (`risk_score`)
  - network distance (`nearest_tower_km`)
  - population proxy (`est_population_community`)

## New generated files
- `processed_data/07_osm_telecom_towers.geojson`
- `processed_data/07b_osm_water_points.geojson`
- `processed_data/08_digital_desert_communities.geojson`
- `processed_data/09_digital_desert_summary.csv`
- `processed_data/10_model_thresholds.csv`
- `processed_data/11_province_model_metrics.csv`

## How to regenerate
```bash
python build_digital_desert_model.py
```

## Rule-based logic
- `High risk`: flood risk score >= 75th percentile of modeled communities.
- `Low connectivity`: distance to nearest telecom proxy >= 75th percentile.
- `High population`: estimated community population >= 75th percentile.
- Classes:
  - `A`: High risk + low connectivity
  - `B`: High risk + better connectivity
  - `C`: Low risk + low connectivity + high population
  - `D`: Low risk + low connectivity
  - `E`: Lower priority under current data

## Data sources used in this update
- Existing project data under `processed_data/`
- OpenStreetMap (via Overpass API) for telecom infrastructure proxy points
- OpenStreetMap (via Overpass API) for waterways/water proxies
- OpenTopoData (`srtm90m`) for community elevation

## Important interpretation notes
- OSM telecom and water points are **proxies**, not official infrastructure inventories.
- Distances are straight-line geodesic approximations from mapped points.
- Community population is estimated as `num_family * 4.6` (Cambodia average household size used as proxy).
- Flood score is harmonized at community level using:
  - province flood signal (if available),
  - proximity to water proxies,
  - elevation (low elevation = higher flood sensitivity).
