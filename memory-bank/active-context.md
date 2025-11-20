# Active Context

## What are you working on this week?

Implementing the Safety Index system, including:
- Collecting real-time data from the VCC Public API (BSM, SPAT, MapData, PSM messages)
- Processing V2X message streams to extract safety-relevant features
- Developing the safety index calculation algorithms
- Building real-time index update mechanisms that continuously refresh scores as new data arrives

## What decisions are you facing?

What data sources will we use beyond just VCC? Key considerations:
- Should we incorporate weather data (precipitation, visibility, road conditions)?
- Historical crash data from VDOT to validate and calibrate safety scores?
- Traffic volume data from other sources to supplement BSM counts?
- Road surface condition sensors or camera feeds?
- Time-of-day and seasonal patterns from historical databases?
- Integration with third-party map providers for additional context?

## What's unclear?

Some of the math is still a little foggy, particularly:
- The exact formulas for computing safety scores from raw V2X data
- Weighting schemes for different risk factors (speed differentials, brake events, signal violations, etc.)
- Temporal decay functions - how quickly should past events fade from the safety score?
- Statistical normalization approaches to make scores comparable across different intersection types
- Thresholds for categorizing safety levels (e.g., safe/moderate/dangerous)
- Conflict detection algorithms - mathematical definitions of "near-miss" scenarios
