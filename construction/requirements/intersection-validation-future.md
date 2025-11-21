# Future Feature: Intersection Validation & Camera Integration

**Feature Category**: Validation, Context & Analysis Tools
**Version**: 0.1 (Placeholder)
**Date**: 2025-11-20
**Status**: 📋 Future Spec - Needs Development
**Priority**: Medium (Post-MVP)

---

## Overview

This document captures future feature requirements for enhanced validation and context capabilities. These features were identified during the Intersection History feature planning but are intentionally scoped out of the initial MVP to maintain focus and deliverability.

### Purpose
1. **Validation**: Provide tools to verify data accuracy against ground truth
2. **Context**: Enable users to see real-world conditions at intersections
3. **Investigation**: Support incident analysis with visual evidence
4. **Quality**: Monitor and improve system data quality

---

## Feature 1: Public Camera Feed Integration

### Problem Statement
Traffic engineers and analysts need to **visually verify** safety index events and understand real-world conditions at intersections. Currently, the system only shows computed metrics without visual context, making it difficult to:
- Validate that high safety index readings correspond to actual dangerous conditions
- Investigate specific incidents or anomalies
- Understand ground truth during edge cases or system validation
- Train and improve safety index algorithms

### Proposed Solution
Integrate links to state public traffic camera systems, allowing users to view live or recorded video feeds for intersections directly from the dashboard.

### User Stories

**US-VAL-1: View Camera Feed from Dashboard**
```
As a traffic engineer
I want to click a link/button to view the state's public camera feed for an intersection
So that I can visually verify conditions when investigating a safety event
```

**US-VAL-2: Sync Camera Timestamp with Historical Data**
```
As an analyst investigating an incident
I want to see the camera feed from the same time period as a historical safety index spike
So that I can correlate computed metrics with actual conditions
```

**US-VAL-3: Quick Validation Workflow**
```
As a system validator
I want to quickly toggle between safety index data and camera feed
So that I can efficiently validate system accuracy across multiple intersections
```

### High-Level Requirements

#### Data Requirements
- **Camera URL Mapping**: Database/config file mapping intersection IDs to camera URLs
  - Source: State DOT public camera systems
  - Example: Virginia's VDOT 511 cameras, DC's traffic cameras
  - May need to handle multiple cameras per intersection
- **Camera Availability**: Boolean flag per intersection indicating if camera available
- **Camera Metadata**: Position, angle, field of view, update frequency

#### UI Requirements
- **Indicator**: Camera icon in intersection details panel if feed available
- **Access Methods**:
  - Option A: Button that opens camera feed in new tab/window
  - Option B: Embedded iframe showing live feed inline
  - Option C: Modal/overlay with camera feed
- **Time Sync** (advanced): For historical data, link to archived footage if available
- **Fallback**: Clear message if camera offline or feed unavailable

#### Technical Considerations
- **Authentication**: Some state systems may require API keys or authentication
- **Embedding Restrictions**: iframe embedding may be blocked by CORS policies
- **Performance**: External video streams should not slow down dashboard
- **Privacy**: Ensure compliance with public camera usage policies

### Dependencies
- Access to state DOT camera APIs or public URLs
- Intersection ID to camera ID mapping data
- Understanding of each state's camera system architecture

### Success Criteria
- User can access camera feed within 2 clicks from intersection details
- Camera availability indicated clearly (icon or label)
- Feed loads in <5 seconds (or indicates if unavailable)
- No impact on dashboard performance for intersections without cameras

### Implementation Approach (Draft)

**Phase 1: Data Mapping**
- Research available state camera systems (VDOT, DC, etc.)
- Create mapping file: `camera_mapping.json`
```json
{
  "0.0": {
    "camera_id": "CAM123",
    "camera_url": "https://vdot.virginia.gov/camera/123",
    "description": "Intersection 0.0 - South view",
    "available": true
  }
}
```

**Phase 2: Backend API**
- Add `camera_url` and `camera_available` fields to `IntersectionRead` schema
- Service layer loads camera mapping and enriches intersection data

**Phase 3: Frontend UI**
- Add camera icon to details card if `camera_available=True`
- Implement simple link approach first (opens in new tab)
- Future: Explore embedded iframe or modal with live feed

### Out of Scope (For Now)
- Video clip export functionality
- DVR-style playback controls
- Multi-camera views
- Computer vision analysis on camera feeds
- Direct recording/archival integration

---

## Feature 2: Admin Validation Tools

### Problem Statement
System administrators and data scientists need tools to **verify data accuracy** and **diagnose quality issues**. Currently, there's no easy way to:
- View raw Parquet data directly
- Compare computed aggregations against source data
- Identify data gaps or anomalies
- Download raw data for offline analysis
- Monitor data pipeline health

### Proposed Solution
Build an admin dashboard or toolset for data validation, quality monitoring, and pipeline diagnostics.

### User Stories

**US-VAL-4: View Raw Data**
```
As a system administrator
I want to view raw 1-minute interval data from Parquet files
So that I can verify computations and diagnose issues
```

**US-VAL-5: Verify Aggregations**
```
As a data scientist
I want to compare aggregated data (hourly, daily) against raw 1-minute data
So that I can ensure aggregation logic is correct
```

**US-VAL-6: Download Raw Datasets**
```
As a researcher
I want to download raw BSM/PSM message data with computed indices
So that I can perform offline analysis and validation
```

**US-VAL-7: Data Quality Dashboard**
```
As an operations engineer
I want to see metrics on data completeness, gaps, and anomalies
So that I can proactively identify and fix data pipeline issues
```

### High-Level Requirements

#### Raw Data Viewer
- **Parquet File Browser**: List all parquet files by date and type (indices, features, raw BSM/PSM)
- **Data Preview**: Display first N rows of any parquet file
- **Column Selection**: Choose which columns to display
- **Filtering**: Basic filters (date range, intersection ID)
- **Pagination**: Handle large files (millions of rows)

#### Aggregation Validator
- **Compare Tool**: Side-by-side view of raw vs aggregated data
- **Verification Tests**:
  - Traffic volume sums match
  - Safety index means are correct
  - No data loss during aggregation
  - Timestamps align properly
- **Visual Comparison**: Charts showing raw vs aggregated overlay

#### Bulk Data Export
- **Export Options**:
  - Date range selection
  - Intersection filter (single or all)
  - Data type (raw, features, indices)
  - Format (Parquet, CSV, JSON)
- **Compression**: Option to compress large exports (gzip, zip)
- **Background Jobs**: Queue large exports, notify when ready

#### Data Quality Metrics
- **Completeness**: % of expected data points present
- **Gaps**: Timeline visualization showing missing intervals
- **Anomalies**: Detection of unusual values (spikes, zeroes, outliers)
- **Collection Status**: Real-time status of data collector service
- **Alerts**: Configurable alerts for data quality issues

### Access Control
- **Admin-Only**: These tools should be restricted to admin users
- **Authentication**: Require login or API key
- **Audit Log**: Track who accessed raw data and when

### Technical Considerations
- **Performance**: Direct Parquet reading can be slow for large date ranges
- **Security**: Raw data may contain sensitive information (vehicle IDs in BSM)
- **Storage**: Bulk exports may consume significant storage space
- **Scalability**: Need to handle growing data volumes over time

### Success Criteria
- Admin can view raw data for any date/intersection within 30 seconds
- Aggregation validation tests run automatically on new data
- Export jobs complete successfully for 30-day ranges
- Data quality dashboard shows real-time metrics

### Implementation Approach (Draft)

**Phase 1: Raw Data Viewer**
- Create admin-only route: `/api/v1/admin/data/raw`
- Implement Parquet file listing and reading
- Simple web UI for browsing and previewing

**Phase 2: Aggregation Validator**
- Automated test suite that runs daily
- Compares sample of raw data against aggregated
- Reports discrepancies to log and/or email

**Phase 3: Export Tool**
- Background job queue (Celery or similar)
- File generation and storage in temp directory
- Download link expires after 24 hours

**Phase 4: Quality Dashboard**
- Metrics collection service
- Time series database (InfluxDB, Prometheus)
- Grafana dashboard for visualization

### Out of Scope (For Now)
- Real-time data editing or correction
- Automated data repair tools
- Machine learning anomaly detection
- Cross-intersection data quality comparison
- Historical quality tracking (before this feature)

---

## Feature 3: Advanced Multi-Intersection Analysis

### Problem Statement
City planners and traffic operations managers need to identify **system-wide patterns** and **correlations** across multiple intersections. The current single-intersection focus makes it difficult to:
- Identify which intersections are dangerous at the same times of day
- Understand congestion propagation across the road network
- Evaluate rerouting opportunities to reduce overall risk
- Prioritize infrastructure investments based on network-level analysis

### Proposed Solution
Build a dedicated "Network Analysis" page with tools for multi-intersection comparison, temporal pattern detection, and congestion correlation.

### User Stories

**US-VAL-8: Identify Simultaneous Hot Spots**
```
As a city planner
I want to see which intersections have high safety indices at the same times
So that I can identify systemic issues and coordinate interventions
```

**US-VAL-9: Congestion-Safety Correlation**
```
As a traffic operations manager
I want to see the correlation between traffic volume and safety indices across intersections
So that I can evaluate if congestion reduction improves safety
```

**US-VAL-10: Rerouting Impact Simulation**
```
As a transportation engineer
I want to simulate rerouting scenarios and predict safety impacts
So that I can recommend traffic management strategies
```

### High-Level Requirements

#### Network View
- **Map Overlay**: Show all intersections colored by current or average safety index
- **Time Slider**: Scrub through historical data to see safety evolution
- **Pattern Highlighting**: Auto-detect intersections with similar temporal patterns

#### Comparison Tools
- **Multi-Select**: Choose 2-5 intersections for side-by-side comparison
- **Overlay Charts**: Multiple safety index lines on same time series chart
- **Correlation Matrix**: Heatmap showing correlation between intersections

#### Predictive Analysis
- **Forecasting**: Predict safety indices based on historical patterns
- **What-If Scenarios**: Model impact of interventions (signal timing, lane changes)
- **Hotspot Prediction**: Identify intersections likely to become dangerous

### Dependencies
- Historical data for all intersections
- Advanced analytics capabilities (ML models for prediction)
- Geographic/network data (road connectivity)
- Significant computational resources for network analysis

### Success Criteria
- User can compare up to 5 intersections simultaneously
- Pattern detection identifies clusters of high-risk periods
- Predictions have >70% accuracy for 1-hour ahead forecast

### Out of Scope (Current MVP)
- Real-time prediction
- Optimization algorithms (finding optimal routes)
- Integration with traffic signal control systems
- Agent-based simulation

---

## Prioritization & Sequencing

### Recommended Order
1. **Camera Feed Integration** (Next Sprint)
   - Relatively simple to implement
   - High value for validation and user trust
   - Enables immediate use case (incident investigation)
   - Estimated effort: 1-2 sprints

2. **Admin Validation Tools** (Sprint +2)
   - Critical for long-term system health
   - Foundational for other features
   - Enables data quality monitoring
   - Estimated effort: 2-3 sprints

3. **Network Analysis** (Sprint +4)
   - Most complex, requires robust foundation
   - Depends on proven data quality (from #2)
   - High value but longer implementation
   - Estimated effort: 4-6 sprints

### Dependencies Between Features
```
Camera Feed Integration
    ↓ (validates data quality)
Admin Validation Tools
    ↓ (ensures data reliability)
Network Analysis
    (requires high-quality multi-intersection data)
```

---

## Next Steps

### To Develop Full Specification
1. **Camera Integration**:
   - Research state DOT camera APIs (VDOT, DC, etc.)
   - Define data model for camera mapping
   - Design UI mockups
   - Plan authentication strategy
   - Estimate implementation effort

2. **Admin Tools**:
   - Survey admin users for requirements
   - Design access control mechanism
   - Plan data export architecture
   - Design quality metrics dashboard
   - Estimate storage requirements

3. **Network Analysis**:
   - Define specific use cases with stakeholders
   - Research ML forecasting approaches
   - Design network visualization
   - Plan computational infrastructure
   - Partner with domain experts (traffic engineering)

### Required Resources
- **Camera Integration**: 1 developer, access to state camera systems
- **Admin Tools**: 1-2 developers, sysadmin support
- **Network Analysis**: 2-3 developers, data scientist, domain expert

---

## Appendix: Stakeholder Input

### Camera Feed Feature
**Source**: User discussion during history feature planning (2025-11-20)

**Key Quote**:
> "I was planning to add some tools for verification later to make sure we were looking at matched the data. I was thinking that we would want some tools to allow you to view the raw data against what we are seeing, or download the raw data maybe aggregated, like counts or sums. [...] the user should be provided with a link to the video feed for that intersection from the state's public camera systems."

**Context**: Identified as critical for validation and incident investigation workflows.

### Multi-Intersection Analysis
**Source**: User discussion during UI integration planning (2025-11-20)

**Key Quote**:
> "Eventually it would be good to visual what intersections are hot at the same times of the day and how that links up with congestion and if some sort of rerouting could help ease that."

**Context**: Long-term vision for system-wide traffic management and safety optimization.

---

## Related Documents

- [Intersection History Requirements](./intersection-history-requirements.md)
- [Intersection History Design](../design/intersection-history-design.md)
- [Intersection History Sprint Plan](../sprints/sprint-intersection-history.md)

---

**Document Status**: 📋 Placeholder - Requires Full Specification Development
**Last Updated**: 2025-11-20
**Owner**: TBD
**Next Review**: After History Feature MVP Complete
