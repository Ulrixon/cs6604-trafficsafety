# Traffic Safety Trend Analysis - User Guide

## Overview

The Trend Analysis page provides interactive time-based analysis of intersection safety scores using the MCDM (Multi-Criteria Decision Making) methodology.

## Features

### 1. Single Time Point Analysis
View detailed safety metrics for a specific intersection at a specific time:

- **Safety Score**: Overall MCDM safety score (0-100, higher = safer)
- **Vehicle Count**: Number of vehicles detected
- **Incident Count**: Number of safety events
- **VRU Count**: Vulnerable road users (pedestrians, cyclists)
- **Average Speed**: Mean vehicle speed (mph)
- **Speed Variance**: Variability in speed distribution
- **MCDM Breakdown**: Individual scores from SAW, EDAS, and CODAS methods

### 2. Time Range Trend Analysis
Visualize safety trends over time with interactive charts:

- **Safety Score Trend**: Line chart showing how safety changes over time
- **Traffic Metrics**: Vehicle count and incident count trends
- **Speed Metrics**: Average speed and variance trends
- **MCDM Comparison**: Compare SAW, EDAS, and CODAS scores
- **Summary Statistics**: Aggregated metrics (avg, min, max)

## How to Use

### Running the Application

1. **Start the Backend API** (required):
   ```bash
   cd /path/to/project
   uvicorn backend.app.main:app --reload --port 8000
   ```

2. **Install Frontend Dependencies**:
   ```bash
   cd frontend
   pip install -r requirements.txt
   ```

3. **Run the Trend Analysis Page**:
   ```bash
   streamlit run app/views/trend_analysis.py
   ```

### Single Time Point Mode

1. Select **"Single Time Point"** in the sidebar
2. Choose an intersection from the dropdown
3. Select a date and time
4. Adjust time bin size if needed (15, 30, or 60 minutes)
5. View detailed metrics and MCDM breakdown

**Example**: View safety score for glebe-potomac on Nov 9, 2025 at 10:00 AM

### Time Range Trend Mode

1. Select **"Time Range Trend"** in the sidebar
2. Choose an intersection from the dropdown
3. Set start date/time and end date/time
4. Use quick presets for common time ranges:
   - Last 2 Hours
   - Last 6 Hours
   - Business Hours (9 AM - 5 PM)
   - Full Day
5. View trend charts and summary statistics

**Example**: View safety trends for glebe-potomac from 8 AM to 6 PM on Nov 9, 2025

### Configuration Options

- **Time Bin Size**: 15, 30, or 60-minute bins
  - Smaller bins = more granular data
  - Larger bins = smoother trends
  
- **Intersection Selection**: Choose from available intersections
  - Currently available: glebe-potomac
  - More intersections may be added as data becomes available

## Data Availability

- **Intersection**: glebe-potomac
- **Date Range**: Up to November 9, 2025
- **Time Resolution**: 15-minute bins (default)
- **Historical Lookback**: 24 hours for MCDM calculation

## Understanding the Metrics

### Safety Score (0-100)
- **Higher = Safer**: A score of 75 is safer than 50
- Calculated using hybrid MCDM approach
- Considers multiple criteria weighted by importance

### MCDM Methods

1. **SAW (Simple Additive Weighting)**
   - Weighted sum of normalized criteria
   - Simple and intuitive

2. **EDAS (Evaluation based on Distance from Average Solution)**
   - Measures distance from average performance
   - Good for comparing alternatives

3. **CODAS (Combinative Distance-based Assessment)**
   - Uses Euclidean and Taxicab distances
   - Robust to outliers

**Final Score**: Average of SAW, EDAS, and CODAS

### Traffic Metrics

- **Vehicle Count**: Total vehicles detected in time bin
- **VRU Count**: Pedestrians and cyclists
- **Average Speed**: Mean speed of vehicles (mph)
- **Speed Variance**: Spread in speed distribution
  - High variance = mixed speeds (potentially less safe)
  - Low variance = consistent speeds
- **Incident Count**: Safety events detected

## Tips & Best Practices

### For Single Time Analysis
- Compare different times of day (rush hour vs. off-peak)
- Look at the MCDM breakdown to understand which method identifies risks
- Check incident count alongside safety score

### For Trend Analysis
- Use 15-minute bins for detailed analysis
- Use 60-minute bins for daily overviews
- Look for patterns:
  - Morning/evening rush hours
  - Correlation between vehicle count and incidents
  - Speed variance during high traffic

### Interpreting Results

**Safe Conditions** (High Safety Score):
- Low incident count
- Consistent speeds (low variance)
- Manageable traffic volume
- Few VRUs in conflict zones

**Unsafe Conditions** (Low Safety Score):
- High incident count
- High speed variance
- Very high or very low traffic
- VRUs present with fast traffic

## Troubleshooting

### No Data Available
- **Check date range**: Data only available up to Nov 9, 2025
- **Try different time**: Not all time bins have data
- **Check API**: Ensure backend is running on port 8000

### API Connection Error
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check intersections list
curl http://localhost:8000/api/v1/safety/index/intersections/list
```

### Time Range Too Large
- Maximum time range: 7 days
- Use smaller ranges for better performance
- Consider using larger time bins (60 min) for long ranges

## Technical Details

### API Endpoints Used

1. **GET /api/v1/safety/index/intersections/list**
   - Returns available intersections

2. **GET /api/v1/safety/index/time/specific**
   - Parameters: intersection, time, bin_minutes
   - Returns single time point data

3. **GET /api/v1/safety/index/time/range**
   - Parameters: intersection, start_time, end_time, bin_minutes
   - Returns time series data

### Data Processing

1. **Time Binning**: Data aggregated into time bins (15/30/60 min)
2. **CRITIC Weighting**: 24-hour historical data determines criteria weights
3. **Normalization**: All criteria normalized to 0-1 scale
4. **MCDM Calculation**: Three methods computed and averaged
5. **Scaling**: Final score scaled to 0-100 range

## Future Enhancements

Potential features for future versions:
- Export data to CSV
- Comparison mode (multiple intersections)
- Prediction/forecasting
- Anomaly detection
- Custom time bin sizes
- Weather data integration
- Crash data correlation

## Support

For issues or questions:
1. Check backend API logs: `/tmp/backend.log`
2. Verify database connection
3. Check data availability for selected time range
4. Review API documentation: `backend/API_ENDPOINTS.md`

---

**Version**: 1.0  
**Last Updated**: December 2024  
**Platform**: Streamlit + FastAPI + PostgreSQL
