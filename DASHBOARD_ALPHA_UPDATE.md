# Dashboard Alpha Integration Summary

## Overview
Added alpha blending functionality to the Dashboard (Page 0) to display real-time blended safety indices combining RT-SI and MCDM methodologies.

## Changes Made

### 1. Dashboard Page (`frontend/pages/0_🏠_Dashboard.py`)

#### Added Alpha Slider (Sidebar):
```python
alpha = st.slider(
    "RT-SI Weight (α)",
    min_value=0.0,
    max_value=1.0,
    value=0.7,
    step=0.1,
    help="Final Index = α×RT-SI + (1-α)×MCDM"
)
```

**Position:** Top of sidebar, before Refresh button
**Features:**
- Range: 0.0 to 1.0
- Default: 0.7 (balanced, recommended)
- Step: 0.1
- Live caption showing blend percentage
- Explanatory help text

#### Updated Data Loading:
- Integrated `fetch_latest_blended_scores(alpha)` function
- Fetches latest safety scores with RT-SI blending for each intersection
- Falls back to standard MCDM if blending fails
- Passes alpha parameter to API

#### Updated About Section:
- Explains blended safety index formula
- Shows current alpha value
- Describes RT-SI and MCDM components
- Provides guidance on adjusting alpha

#### Updated Footer:
- Displays current alpha value
- Shows "RT-SI + MCDM" methodology

### 2. API Client (`frontend/app/services/api_client.py`)

#### New Function: `fetch_latest_blended_scores(alpha)`
```python
@st.cache_data(ttl=300, show_spinner=False)
def fetch_latest_blended_scores(alpha: float = 0.7):
    """
    Fetch latest safety scores with RT-SI blending for all intersections.
    """
```

**Functionality:**
1. Queries `/intersections/list` for available intersections
2. For each intersection (up to 10 for performance):
   - Calls `/time/specific` with current time and alpha
   - Receives blended final_safety_index
3. Transforms data to dashboard format
4. Includes: final_safety_index, rt_si_score, mcdm_index, vru_index, vehicle_index
5. Caches results for 5 minutes

**Performance Optimization:**
- Limits to first 10 intersections to avoid slow loading
- Uses retry logic for failed requests
- Falls back to sample data if API unavailable

### 3. Components (`frontend/app/views/components.py`)

#### Updated `render_kpi_cards()`:
- Changed "Avg Safety Index" → "Avg Final Index"
- Added help text explaining blended index

#### Updated `render_details_card()`:
**New Metrics Display:**
- **Safety Index (Blended)**: Main final index
- **RT-SI Score**: Real-time safety (if available)
- **MCDM Index**: Long-term prioritization (if available)
- **VRU Index**: RT-SI sub-index (if available)
- **Vehicle Index**: RT-SI sub-index (if available)

**Layout:**
```
┌─────────────────────────────────────┐
│ Safety Index (Blended): 70.55       │
│ RT-SI Score: 71.79                  │
├─────────────────────────────────────┤
│ Traffic Volume: 8                   │
│ MCDM Index: 67.66                   │
├─────────────────────────────────────┤
│ RT-SI Sub-Indices:                  │
│ VRU Index: 0.0000                   │
│ Vehicle Index: 0.0705               │
└─────────────────────────────────────┘
```

## User Experience Flow

### 1. Dashboard Load
```
User opens Dashboard
    ↓
Alpha slider defaults to 0.7
    ↓
Dashboard fetches latest data with α=0.7
    ↓
API calculates: Final = 0.7×RT-SI + 0.3×MCDM
    ↓
Map displays intersections with blended scores
```

### 2. Adjusting Alpha
```
User moves alpha slider to 0.5
    ↓
Dashboard clears cache and refetches
    ↓
API recalculates: Final = 0.5×RT-SI + 0.5×MCDM
    ↓
Map and metrics update with new blend
    ↓
User can compare different emphasis levels
```

### 3. Viewing Details
```
User clicks intersection marker
    ↓
Details panel shows:
  - Final blended index (main score)
  - RT-SI score (real-time component)
  - MCDM index (long-term component)
  - VRU & Vehicle sub-indices
    ↓
User understands safety assessment breakdown
```

## Formula Display

The dashboard now prominently shows:

```
Final Index = α × RT-SI + (1-α) × MCDM

Where:
  α = 0.7 (user-adjustable)
  RT-SI = Real-Time Safety Index (0-100, higher=safer)
  MCDM = Multi-Criteria Decision Making (0-100, higher=safer)
```

## Alpha Guidance

**Displayed in UI:**
- **α = 0.0**: Pure MCDM (long-term prioritization)
- **α = 0.7**: Balanced (recommended for dashboards)
- **α = 1.0**: Pure RT-SI (real-time safety focus)

**Use Cases:**
- **Emergency Response** (α=0.9-1.0): Emphasize current conditions
- **General Monitoring** (α=0.6-0.8): Balanced view
- **Planning/Prioritization** (α=0.0-0.4): Emphasize long-term patterns

## Performance Considerations

1. **Caching**: Results cached for 5 minutes
2. **Batch Limit**: First 10 intersections only (configurable)
3. **Timeout**: 10 seconds per intersection query
4. **Fallback**: Graceful degradation to MCDM-only if RT-SI fails

## Example API Call

When user sets α=0.7, dashboard makes:

```bash
GET /api/v1/safety/index/time/specific
  ?intersection=glebe-potomac
  &time=2025-11-22T14:30:00
  &bin_minutes=15
  &alpha=0.7
```

**Response:**
```json
{
  "intersection": "glebe-potomac",
  "final_safety_index": 70.55,
  "rt_si_score": 71.79,
  "mcdm_index": 67.66,
  "vru_index": 0.0,
  "vehicle_index": 0.0705,
  "vehicle_count": 8,
  ...
}
```

## Visual Updates

### Map Markers
- **Color**: Based on final_safety_index (blended)
- **Size**: Based on traffic_volume
- **Popup**: Shows all components (Final, RT-SI, MCDM)

### KPI Cards
- Total Intersections
- **Avg Final Index** (updated label)
- High Risk Count (based on blended index)
- Total Traffic Volume

### Details Panel
- Main blended safety index
- RT-SI and MCDM breakdown
- VRU and Vehicle sub-indices
- Geographic coordinates
- Historical data toggle (existing feature)

## Benefits

1. **Real-time Awareness**: Reflects current traffic conditions
2. **Long-term Stability**: Maintains historical context
3. **User Control**: Adjustable emphasis via alpha
4. **Transparency**: Clear breakdown of components
5. **Consistent UX**: Same alpha control as Trend Analysis page

## Future Enhancements (Optional)

1. **Increase Batch Size**: Support more intersections (currently limited to 10)
2. **Coordinate Lookup**: Fetch actual coordinates from PSM table
3. **Performance Metrics**: Show RT-SI calculation time
4. **Comparison Mode**: Side-by-side view of different alpha values
5. **Alpha Presets**: Quick buttons for common alpha values (0.0, 0.5, 0.7, 1.0)

## Testing Checklist

- [x] Alpha slider functional (0.0 to 1.0)
- [x] Data fetches with alpha parameter
- [x] Blended scores display correctly
- [x] RT-SI components shown when available
- [x] Graceful fallback when RT-SI unavailable
- [x] KPI cards updated with new labels
- [x] Details panel shows all components
- [x] About section explains methodology
- [x] Footer shows current alpha value
- [x] Cache works (5-minute TTL)
- [x] Error handling for API failures
