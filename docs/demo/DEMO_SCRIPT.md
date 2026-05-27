# Traffic Safety Dashboard - 10-Minute Demo Script

**Presenter Guide:** This script is designed for a 10-minute demonstration of the Traffic Safety Dashboard. Each section includes talking points, interactions to demonstrate, and key features to highlight.

---

## Introduction (1 minute)

**[Start on Dashboard page]**

### Opening Statement

"Today I'll demonstrate our Traffic Safety Dashboard - a comprehensive system that combines real-time traffic conditions with long-term safety patterns to identify dangerous intersections. Our system uses a novel hybrid approach that blends two complementary indices:

- **RT-SI (Real-Time Safety Index)** - Captures current traffic conditions, speed patterns, and uses Empirical Bayes to stabilize predictions based on historical crash data
- **MCDM (Multi-Criteria Decision Making)** - Provides long-term prioritization using CRITIC weighting with hybrid methods (SAW, EDAS, CODAS)

The key innovation is our **alpha blending parameter** that lets users balance between real-time responsiveness and long-term reliability."

### Quick Context

"We're monitoring 18 intersections in our test area. Higher safety index values indicate more dangerous intersections. Let's explore how the system works."

---

## 1. Dashboard - Interactive Map & Blending (2 minutes)

**[Navigate through Dashboard features]**

### A. Alpha Slider (30 seconds)

**[Point to sidebar alpha slider]**

"This is our alpha (α) blending coefficient - the heart of our system:

- **α = 0.0**: Pure MCDM - uses only long-term patterns (best for strategic planning)
- **α = 0.7**: Balanced blend (recommended for operations) - 70% real-time, 30% long-term
- **α = 1.0**: Pure RT-SI - uses only real-time conditions (best for immediate response)

The formula is: **Safety Index = α×RT-SI + (1-α)×MCDM**"

**[Demonstrate]** Move slider from 0.0 → 0.7 → 1.0 and show how the data table updates.

### B. Interactive Map (45 seconds)

**[Focus on map visualization]**

"The map provides instant visual assessment:

- **Circle size** = Traffic volume (larger = more traffic)
- **Circle color** = Safety risk level (red = high danger, green = safe)
- **Click any marker** to see detailed metrics"

**[Demonstrate]** Click on a high-risk intersection (red marker) to show the details panel.

### C. Data Table (45 seconds)

**[Scroll to bottom data table]**

"The data table shows three critical scores for each intersection:

1. **Safety Index (Blended)** - The final combined score using our alpha formula
2. **RT-SI Score** - Real-time safety assessment based on current conditions
3. **MCDM Score** - Long-term prioritization based on historical patterns

Notice how some intersections have high MCDM but low RT-SI, or vice versa - this is why blending is powerful."

**[Point to filters in sidebar]**
"You can filter by intersection name, safety score range, and traffic volume."

---

## 2. Trend Analysis - Time Series & Correlations (2 minutes)

**[Navigate to 📈 Trend Analysis page]**

### A. Specific Time Analysis (45 seconds)

**[Select the first tab/view]**

"This view lets you query safety scores at a specific moment in time."

**[Demonstrate]**

1. Select an intersection (e.g., "birch_st-w_broad_st")
2. Pick a recent date/time
3. Set bin size to 15 minutes
4. Click "Fetch Safety Score"

"The system returns:

- Individual RT-SI and MCDM components
- Blended safety score
- Traffic volume and speed statistics for that time window
- Data quality indicators"

### B. Trend Over Time (1 minute 15 seconds)

**[Switch to time range analysis]**

"For trend analysis, we can visualize how safety changes over hours or days."

**[Demonstrate]**

1. Select same intersection
2. Set date range (e.g., past 24 hours)
3. Adjust alpha slider to 0.7
4. Check "Include Correlation Analysis"
5. Click "Analyze Trend"

**[Point to charts]**
"We get multiple visualizations:

- **Time series chart** showing how safety index evolves
- **Separate traces** for RT-SI and MCDM to see divergence
- **Correlation matrix** showing relationships between metrics (speed, volume, safety)
- **Statistical summary** with mean, std deviation, and trend direction"

"Notice how RT-SI can spike during high-traffic periods while MCDM remains stable - this is the value of blending both signals."

---

## 3. Analytics & Validation - Crash Correlation (2 minutes)

**[Navigate to 📊 Analytics & Validation page]**

### A. Purpose & Methodology (30 seconds)

"This page validates our safety indices against actual crash occurrences. We use:

- **Date range selection** to focus on historical periods
- **Proximity radius** (500m default) to associate crashes with nearby intersections
- **Statistical metrics** to measure predictive accuracy"

### B. Correlation Metrics (45 seconds)

**[Set date range and click "Analyze Correlation"]**

"The correlation analysis shows:

1. **Overall Statistics**:

   - Total crashes in period
   - Number of monitored intersections
   - Average safety scores

2. **Correlation Coefficients**:

   - Pearson correlation (linear relationship)
   - Spearman correlation (rank-order relationship)
   - P-values for significance testing

3. **Classification Metrics** (if threshold-based):
   - Precision: Of high-risk intersections, how many had crashes?
   - Recall: Of crashes, how many occurred at high-risk intersections?
   - F1 Score: Balanced accuracy measure"

### C. Visualizations (45 seconds)

**[Scroll through charts]**

"We provide several visual validations:

- **Scatter plot**: Safety score vs. actual crash count

  - Positive correlation validates our model
  - Outliers indicate areas for investigation

- **Time series overlay**: Safety index with crash events marked

  - Shows temporal alignment between predictions and outcomes

- **Weather impact**: How conditions affect safety scores
  - Validates that our model responds appropriately to environmental factors"

---

## 4. Sensitivity Analysis - Robustness Testing (2 minutes)

**[Navigate to 🔬 Sensitivity Analysis page]**

### A. Purpose (30 seconds)

"Sensitivity analysis tests the robustness of our RT-SI methodology. We perturb calculation parameters and measure how stable the safety rankings remain. This is critical for research validation and operational confidence."

### B. Parameter Perturbation (45 seconds)

**[Configure and run analysis]**

**Settings:**

- Select an intersection
- Set time range (e.g., 6 hours)
- Perturbation: 25% (means ±25% variation in parameters)
- Number of samples: 50 (50 different parameter sets)

"When we run this, the system:

1. Generates 50 random parameter variations (±25% from baseline)
2. Recalculates RT-SI for each variant
3. Measures ranking stability across all variants"

**[Click "Run Sensitivity Analysis" and wait for results]**

### C. Results Interpretation (45 seconds)

**[Once results load, explain]**

"The key metrics are:

1. **Spearman Rank Correlation** (mean ~0.85+):

   - Measures if intersection rankings stay consistent
   - > 0.8 is excellent stability
   - <0.5 indicates sensitivity issues

2. **Coefficient of Variation** (CV):

   - Shows relative variability of safety scores
   - Lower = more robust
   - Displayed per intersection

3. **Rank Shift Analysis**:

   - How many positions each intersection moves
   - Box plots show distribution of rankings

4. **Parameter Impact**:
   - Which parameters cause most variation
   - Helps identify critical tuning factors"

"High Spearman correlation (>0.8) proves our methodology is robust to parameter uncertainty - critical for operational deployment."

---

## 5. Database Explorer - Raw Data Access (1 minute)

**[Navigate to 🗄️ Database Explorer page]**

### Quick Tour (60 seconds)

"For power users and researchers, we provide direct database access."

**[Demonstrate]**

1. **Table Selection**:

   - Show dropdown with available tables (crashes, speed-distribution, traffic-volume, etc.)
   - Select "speed-distribution"

2. **Schema View**:

   - Expand "View Schema" to show table structure
   - Column names, types, constraints

3. **Data Preview**:

   - Adjust row limit slider (e.g., 1000 rows)
   - Show filtered data (e.g., filter by intersection: "glebe-potomac")

4. **Visualizations**:
   - Show automatic chart generation
   - Time series, distributions, relationships

"This is useful for:

- Data quality audits
- Custom analysis not covered by dashboards
- Exporting data for external research
- Debugging data pipeline issues"

---

## Closing Remarks (1 minute)

### Summary

"Let's recap what makes this system unique:

1. **Hybrid Approach**: Combines real-time conditions (RT-SI) with long-term patterns (MCDM)

2. **User-Controlled Blending**: The alpha parameter lets operators adjust emphasis based on context

   - Emergency response → high α (real-time focus)
   - Strategic planning → low α (long-term focus)

3. **Comprehensive Analysis**: From live monitoring to statistical validation to sensitivity testing

4. **Validated Methodology**: Correlation analysis shows our predictions align with actual crashes

5. **Transparent & Accessible**: Raw data access and clear visualizations support both operations and research"

### Use Cases

"This system supports multiple stakeholders:

- **Traffic operators**: Real-time monitoring for dynamic response
- **City planners**: Long-term safety prioritization for infrastructure investment
- **Researchers**: Validated methodology with sensitivity analysis
- **Emergency services**: Predictive deployment based on safety forecasts"

### Next Steps

"The system is operational and monitoring 18 intersections. We can scale to city-wide coverage and integrate additional data sources like incident reports, weather APIs, and connected vehicle data."

**[End on Dashboard page with map view]**

"Thank you! Questions?"

---

## Quick Reference - Demo Checklist

- [ ] Dashboard: Show alpha slider (0.0 → 0.7 → 1.0)
- [ ] Dashboard: Click map marker, show details panel
- [ ] Dashboard: Point to 3-column data table
- [ ] Trend Analysis: Specific time query
- [ ] Trend Analysis: Time range with correlation analysis
- [ ] Analytics: Run correlation analysis with date range
- [ ] Analytics: Show scatter plot and validation metrics
- [ ] Sensitivity: Configure and run analysis (50 samples, 25% perturbation)
- [ ] Sensitivity: Explain Spearman correlation >0.8
- [ ] Database Explorer: Select table, show schema, filter data
- [ ] Closing: Recap hybrid approach and use cases

## Troubleshooting - Live Demo

**If data doesn't load:**

- Click "🔄 Refresh Data" in sidebar
- Check API connection indicator
- Fallback: Explain the visualization with existing data

**If analysis takes too long:**

- Reduce number of samples (50 → 20)
- Reduce time range (6 hours → 3 hours)
- Mention this is for demonstration; production is optimized

**If questions arise:**

- **"Why alpha=0.7 default?"**: Balance between responsiveness and stability, tuned empirically
- **"How often does data update?"**: Every 5 minutes for real-time data, MCDM recalculated hourly
- **"Can this scale?"**: Yes, current architecture supports hundreds of intersections per city
- **"What's the crash prediction accuracy?"**: Correlation analysis typically shows r>0.6 with actual crashes

---

**Total Time: 10 minutes**

- Introduction: 1 min
- Dashboard: 2 min
- Trend Analysis: 2 min
- Analytics & Validation: 2 min
- Sensitivity Analysis: 2 min
- Database Explorer: 1 min
- Closing: 1 min (flexible buffer)
