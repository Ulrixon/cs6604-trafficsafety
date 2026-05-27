"""
Historical data visualization components.

Provides time series charts, statistics cards, and date range selectors
for viewing intersection safety index history.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.services.api_client import (
    fetch_intersection_history,
    fetch_intersection_stats,
    clear_history_cache
)
from app.utils.config import (
    COLOR_LOW_RISK,
    COLOR_MEDIUM_RISK,
    COLOR_HIGH_RISK,
    COLOR_LOW_THRESHOLD,
    COLOR_HIGH_THRESHOLD
)


def render_date_range_selector() -> tuple[int, Optional[str]]:
    """
    Render time period selector widget.

    Returns:
        Tuple of (days: int, aggregation: Optional[str])
    """
    st.subheader("📅 Time Period")

    col1, col2 = st.columns([2, 1])

    with col1:
        time_period = st.selectbox(
            "Select time range",
            options=[
                ("Last 24 Hours", 1, "1min"),
                ("Last 3 Days", 3, "1hour"),
                ("Last Week", 7, "1hour"),
                ("Last 2 Weeks", 14, "1day"),
                ("Last Month", 30, "1day"),
                ("Last 3 Months", 90, "1week"),
            ],
            format_func=lambda x: x[0],
            index=2,  # Default to "Last Week"
            key="history_time_period"
        )

    with col2:
        if st.button("🔄 Refresh Data", key="refresh_history"):
            clear_history_cache()
            st.rerun()

    # Extract days and aggregation from selected option
    _, days, aggregation = time_period

    return days, aggregation


def render_statistics_cards(stats: Dict) -> None:
    """
    Render statistics summary cards.

    Args:
        stats: Statistics dictionary from API
    """
    st.subheader("📊 Summary Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_si = stats.get("avg_safety_index", 0)
        delta_color = "normal"
        if avg_si > COLOR_HIGH_THRESHOLD:
            delta_color = "inverse"
        elif avg_si < COLOR_LOW_THRESHOLD:
            delta_color = "normal"

        st.metric(
            label="Average Safety Index",
            value=f"{avg_si:.1f}",
            delta=None,
            delta_color=delta_color
        )

    with col2:
        st.metric(
            label="Range",
            value=f"{stats.get('min_safety_index', 0):.1f} - {stats.get('max_safety_index', 0):.1f}",
            delta=None
        )

    with col3:
        high_risk_pct = stats.get("high_risk_percentage", 0)
        st.metric(
            label="High Risk Intervals",
            value=f"{high_risk_pct:.1f}%",
            delta=f"{stats.get('high_risk_intervals', 0)} intervals",
            delta_color="inverse" if high_risk_pct > 20 else "normal"
        )

    with col4:
        avg_volume = stats.get("avg_traffic_volume", 0)
        st.metric(
            label="Avg Traffic Volume",
            value=f"{avg_volume:.0f}",
            delta=None
        )


def render_time_series_chart(history: Dict) -> None:
    """
    Render interactive time series chart with dual y-axes.

    Args:
        history: History data dictionary from API with data_points
    """
    st.subheader("📈 Safety Index Over Time")

    data_points = history.get("data_points", [])

    if not data_points:
        st.warning("No data points available for this time period.")
        return

    # Extract data for plotting
    timestamps = [datetime.fromisoformat(p["timestamp"]) for p in data_points]
    safety_indices = [p["safety_index"] for p in data_points]
    traffic_volumes = [p["traffic_volume"] for p in data_points]

    # Create figure with secondary y-axis
    fig = make_subplots(
        specs=[[{"secondary_y": True}]],
        subplot_titles=("",)
    )

    # Add safety index trace (primary y-axis)
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=safety_indices,
            name="Safety Index",
            mode="lines",
            line=dict(color="#3498db", width=2),
            hovertemplate="<b>%{x}</b><br>Safety Index: %{y:.1f}<extra></extra>"
        ),
        secondary_y=False
    )

    # Add traffic volume trace (secondary y-axis)
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=traffic_volumes,
            name="Traffic Volume",
            mode="lines",
            line=dict(color="#95a5a6", width=1, dash="dot"),
            opacity=0.6,
            hovertemplate="<b>%{x}</b><br>Traffic: %{y}<extra></extra>"
        ),
        secondary_y=True
    )

    # Add horizontal reference lines for risk thresholds
    fig.add_hline(
        y=COLOR_LOW_THRESHOLD,
        line_dash="dash",
        line_color=COLOR_MEDIUM_RISK,
        opacity=0.3,
        secondary_y=False,
        annotation_text="Medium Risk",
        annotation_position="right"
    )

    fig.add_hline(
        y=COLOR_HIGH_THRESHOLD,
        line_dash="dash",
        line_color=COLOR_HIGH_RISK,
        opacity=0.3,
        secondary_y=False,
        annotation_text="High Risk",
        annotation_position="right"
    )

    # Update axes
    fig.update_xaxes(
        title_text="Time",
        gridcolor="rgba(200,200,200,0.2)"
    )

    fig.update_yaxes(
        title_text="Safety Index",
        secondary_y=False,
        gridcolor="rgba(200,200,200,0.2)",
        range=[0, 100]
    )

    fig.update_yaxes(
        title_text="Traffic Volume",
        secondary_y=True,
        gridcolor="rgba(200,200,200,0.1)"
    )

    # Update layout
    fig.update_layout(
        height=500,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=60, t=40, b=60)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show aggregation info
    aggregation = history.get("aggregation", "unknown")
    total_points = history.get("total_points", 0)

    st.caption(
        f"📊 Showing {total_points:,} data points "
        f"(aggregated at **{aggregation}** intervals)"
    )


def render_historical_section(intersection_id: str) -> None:
    """
    Render complete historical analysis section for an intersection.

    This is the main component that combines all historical data views:
    - Date range selector
    - Statistics cards
    - Time series chart

    Args:
        intersection_id: Unique intersection identifier
    """
    st.markdown("---")
    st.header("📊 Historical Analysis")

    # Date range selector
    days, aggregation = render_date_range_selector()

    # Fetch historical data
    with st.spinner("Loading historical data..."):
        history, history_error = fetch_intersection_history(
            intersection_id=intersection_id,
            days=days,
            aggregation=aggregation
        )

        stats, stats_error = fetch_intersection_stats(
            intersection_id=intersection_id,
            days=days
        )

    # Handle errors
    if history_error or stats_error:
        st.error(
            f"⚠️ Unable to load historical data: "
            f"{history_error or stats_error}"
        )

        st.info(
            "💡 **Possible reasons:**\n"
            "- No historical data has been collected yet for this intersection\n"
            "- The selected time period may not have data available\n"
            "- There may be a temporary connection issue\n\n"
            "Try selecting a different time period or refreshing the data."
        )
        return

    # Render statistics cards
    if stats:
        render_statistics_cards(stats)
        st.markdown("")  # Add spacing

    # Render time series chart
    if history:
        render_time_series_chart(history)

    # Additional info expander
    with st.expander("ℹ️ About Historical Data"):
        st.markdown("""
        **Data Collection:**
        - Safety indices are collected every **1 minute** from live traffic cameras
        - Data is automatically aggregated based on the selected time range

        **Aggregation Levels:**
        - **1-minute**: Raw data (available for last 24 hours)
        - **Hourly**: Average over 1-hour periods (1-7 days)
        - **Daily**: Average over 1-day periods (1-30 days)
        - **Weekly**: Average over 1-week periods (30-90 days)
        - **Monthly**: Average over 1-month periods (90+ days)

        **High Risk Threshold:**
        - Intervals with Safety Index > 75 are considered high risk
        - Percentage shown in statistics indicates proportion of time in high-risk state

        **Traffic Volume:**
        - Total vehicle count during the interval
        - Shown as dotted line on the chart (secondary y-axis)
        - Higher traffic volumes can correlate with safety index changes
        """)
