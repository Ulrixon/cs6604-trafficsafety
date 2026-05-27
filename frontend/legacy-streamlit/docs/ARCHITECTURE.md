# System Architecture

## Overview

The Traffic Safety Index Dashboard follows a clean **Model-View-Controller (MVC)** architecture pattern, ensuring separation of concerns, maintainability, and scalability.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                             │
│                      (http://localhost:8501)                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTP
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    STREAMLIT APPLICATION                         │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    VIEW LAYER                               │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  main.py                                             │  │ │
│  │  │  - Page layout & routing                            │  │ │
│  │  │  - Event handling (clicks, filters)                 │  │ │
│  │  │  - Component composition                            │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  components.py                                       │  │ │
│  │  │  - KPI Cards                                         │  │ │
│  │  │  - Details Panel                                     │  │ │
│  │  │  - Filter Controls                                   │  │ │
│  │  │  - Data Table                                        │  │ │
│  │  │  - Legend                                            │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                │                                  │
│                                ↓                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                 CONTROLLER LAYER                            │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  map_controller.py                                   │  │ │
│  │  │  - Build Folium map                                  │  │ │
│  │  │  - Create markers with visual encoding              │  │ │
│  │  │  - Generate popups & tooltips                       │  │ │
│  │  │  - Compute map center & bounds                      │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                │                                  │
│                                ↓                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   SERVICE LAYER                             │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  api_client.py                                       │  │ │
│  │  │  - Fetch data from API                               │  │ │
│  │  │  - HTTP retry logic                                  │  │ │
│  │  │  - Response caching (@st.cache_data)                │  │ │
│  │  │  - Fallback to sample.json                          │  │ │
│  │  │  - Error handling                                    │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                │                                  │
│                                ↓                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    MODEL LAYER                              │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  intersection.py (Pydantic)                          │  │ │
│  │  │  - Data validation                                   │  │ │
│  │  │  - Type checking                                     │  │ │
│  │  │  - Field constraints                                 │  │ │
│  │  │  - Helper methods (to_dict, get_risk_level)         │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    UTILS LAYER                              │ │
│  │  ┌──────────────┐  ┌────────────────────────────────────┐  │ │
│  │  │  config.py   │  │  scaling.py                        │  │ │
│  │  │  - Constants │  │  - scale_radius()                  │  │ │
│  │  │  - API URL   │  │  - get_color_for_safety_index()   │  │ │
│  │  │  - Thresholds│  │  - interpolate_color()            │  │ │
│  │  └──────────────┘  │  - format_number()                │  │ │
│  │                    └────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SERVICES                           │
│                                                                   │
│  ┌────────────────────────────┐  ┌──────────────────────────┐   │
│  │  Traffic Safety API        │  │  Local Fallback Data     │   │
│  │  (GCP Cloud Run)           │  │  (sample.json)           │   │
│  │                            │  │                          │   │
│  │  GET /api/v1/safety/index/ │  │  10 sample intersections │   │
│  └────────────────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Application Startup

```
User → Browser → Streamlit Server → main.py
                                        ↓
                                  Initialize UI
                                        ↓
                                  Load Configuration
                                        ↓
                                  Call api_client.get_intersections()
```

### 2. Data Loading

```
api_client.get_intersections()
    ↓
Check cache (@st.cache_data)
    ↓
    ├─ Cache Hit → Return cached data
    │
    └─ Cache Miss → fetch_intersections_from_api()
                         ↓
                    HTTP GET request
                         ↓
                    ├─ Success → Parse JSON → Validate with Pydantic
                    │                              ↓
                    │                         Return Intersection[]
                    │
                    └─ Error → Load sample.json
                                   ↓
                              Return fallback data
```

### 3. Map Rendering

```
Validated Intersections
    ↓
Convert to DataFrame
    ↓
Apply Filters (name, safety_index, traffic_volume)
    ↓
map_controller.build_map(filtered_df)
    ↓
For each intersection:
    ├─ Calculate radius: scale_radius(volume, min, max)
    ├─ Calculate color: get_color_for_safety_index(safety_index)
    ├─ Create popup: create_popup_html(row)
    └─ Add CircleMarker to Folium map
        ↓
    Return Folium map
        ↓
st_folium() → Render in browser
```

### 4. User Interaction

```
User clicks marker
    ↓
st_folium returns last_object_clicked
    ↓
Extract coordinates (lat, lng)
    ↓
Match with DataFrame row
    ↓
components.render_details_card(matched_row)
    ↓
Display in right panel
```

## Component Responsibilities

### Views (UI Layer)

- **Responsibility**: User interface, layout, event handling
- **Dependencies**: Controllers, Services, Models, Utils
- **Output**: Rendered HTML/JavaScript via Streamlit

### Controllers (Business Logic)

- **Responsibility**: Map building, visual encoding, data transformation
- **Dependencies**: Models, Utils
- **Input**: Validated DataFrame
- **Output**: Folium Map object

### Services (Data Layer)

- **Responsibility**: External API communication, caching, error handling
- **Dependencies**: Models, Utils
- **Output**: List of validated Intersection objects

### Models (Data Schema)

- **Responsibility**: Data validation, type safety, constraints
- **Dependencies**: Pydantic
- **Output**: Validated data objects

### Utils (Helpers)

- **Responsibility**: Reusable functions, configuration, calculations
- **Dependencies**: None
- **Output**: Computed values, constants

## Caching Strategy

```
┌─────────────────────────────────────────────────────────┐
│  @st.cache_data(ttl=300)                                │
│  fetch_intersections_from_api()                         │
│                                                          │
│  First call:                                            │
│    - API request executed                               │
│    - Result stored in memory                            │
│    - TTL timer started (5 minutes)                      │
│                                                          │
│  Subsequent calls (within 5 min):                       │
│    - Return cached result                               │
│    - No API call                                        │
│                                                          │
│  After TTL expires:                                     │
│    - Cache invalidated                                  │
│    - Next call fetches fresh data                       │
└─────────────────────────────────────────────────────────┘
```

## Error Handling Flow

```
API Request
    ↓
    ├─ Timeout (10s)
    │    ↓
    │  Load sample.json
    │    ↓
    │  Show warning banner
    │
    ├─ Connection Error
    │    ↓
    │  Load sample.json
    │    ↓
    │  Show warning banner
    │
    ├─ HTTP Error (4xx, 5xx)
    │    ↓
    │  Load sample.json
    │    ↓
    │  Show warning banner
    │
    └─ Success
         ↓
       Validate with Pydantic
         ↓
         ├─ Validation Error
         │    ↓
         │  Skip invalid record
         │    ↓
         │  Log to stats
         │    ↓
         │  Show data quality warning
         │
         └─ Valid
              ↓
            Return data
```

## Performance Optimizations

1. **API Response Caching**: 5-minute TTL reduces API calls
2. **Lazy Loading**: Map only rendered when data available
3. **Efficient Filtering**: Pandas vectorized operations
4. **Minimal Re-renders**: Streamlit's smart caching
5. **Lightweight Markers**: CircleMarkers instead of full icons

## Security Considerations

1. **Input Validation**: Pydantic models validate all data
2. **XSS Protection**: Streamlit auto-escapes HTML (unsafe_allow_html used carefully)
3. **XSRF Protection**: Enabled in config.toml
4. **Secrets Management**: Support for .streamlit/secrets.toml
5. **API Timeout**: Prevents hanging requests

## Scalability

### Current Capacity

- **Markers**: Handles ~1000 intersections smoothly
- **API Calls**: Cached for 5 minutes
- **Memory**: ~50MB typical usage

### Scaling Options

1. **Large Datasets**: Add MarkerCluster plugin
2. **High Traffic**: Deploy on Streamlit Cloud or container orchestration
3. **Real-time Updates**: WebSocket integration
4. **Multiple Regions**: CDN for static assets

---

**Architecture Version**: 1.0  
**Last Updated**: October 2025
