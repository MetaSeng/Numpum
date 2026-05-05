# Architecture and Process Diagrams

Use these Mermaid diagrams in your final report or presentation.

## 1) Solution Architecture (End-to-End)

```mermaid
flowchart LR
  A["Source Data"] --> B["ETL and Cleaning"]
  B --> C["Modeling Layer (Rule-Based)"]
  C --> D["Gold Outputs (Dashboard-Ready Files)"]
  D --> E["Story Dashboard (Streamlit)"]
  E --> F["Policy Decisions and Action Plan"]

  A1["MRD villages / communal lands"] --> A
  A2["Flood risk table"] --> A
  A3["OSM telecom proxies (Overpass API)"] --> A
```

## 2) ETL Architecture (Bronze / Silver / Gold)

```mermaid
flowchart LR
  S["Sources"] --> B["Bronze Layer<br/>Raw files in processed_data/"]
  B --> SI["Silver Layer<br/>Standardize CRS, clean types, fix nulls"]
  SI --> G["Gold Layer<br/>Business-ready analytical files"]
  G --> C["Consumption<br/>Story dashboard + committee reporting"]

  B1["CSV + GeoJSON + API JSON"] --> B
  G1["08_digital_desert_communities.geojson"] --> G
  G2["09_digital_desert_summary.csv"] --> G
  G3["10_model_thresholds.csv"] --> G
```

## 3) Modeling Logic Flow (Interpretability First)

```mermaid
flowchart TD
  I["Input Features per Community"] --> R1["Rule 1: Flood risk >= cutoff?"]
  I --> R2["Rule 2: Nearest telecom distance >= cutoff?"]
  I --> R3["Rule 3: Population proxy >= cutoff?"]

  R1 --> M["Rule Combiner"]
  R2 --> M
  R3 --> M

  M --> A["Class A<br/>High risk + low connectivity (+ high pop)"]
  M --> B["Class B<br/>High risk + better connectivity"]
  M --> C["Class C<br/>Low risk + low connectivity + high pop"]
  M --> D["Class D<br/>Low risk + low connectivity"]
  M --> E["Class E<br/>Lower priority with current data"]
```

## 4) Operational Workflow (How We Did It)

```mermaid
flowchart LR
  P1["Collect data from MRD, flood files, OSM"] --> P2["Run ETL notebook"]
  P2 --> P3["Run build_digital_desert_model.py"]
  P3 --> P4["Generate 07/08/09/10 outputs"]
  P4 --> P5["Load into dashboard.py narrative pages"]
  P5 --> P6["Review with mentor and committee feedback"]
  P6 --> P7["Refine thresholds, map, and policy story"]
```

