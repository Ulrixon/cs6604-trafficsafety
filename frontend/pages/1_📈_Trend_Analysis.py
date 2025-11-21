"""
📈 Trend Analysis

Time-based trend analysis view for Traffic Safety Dashboard.
Analyze safety scores at specific times or visualize trends over time ranges.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests

from app.utils.config import APP_ICON, API_URL

# API configuration - derive base URL from main API_URL
API_BASE_URL = (
    API_URL.rstrip("/").rsplit("/", 1)[0] if API_URL.endswith("/") else API_URL
)


def get_available_intersections():
    """Fetch list of available intersections."""
    try:
        response = requests.get(f"{API_BASE_URL}/intersections/list", timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("intersections", [])
    except Exception as e:
        st.error(f"Error fetching intersections: {e}")
        return []


def get_safety_score_at_time(intersection: str, time: datetime, bin_minutes: int = 15):
    """Fetch safety score for specific time."""
    try:
        params = {
            "intersection": intersection,
            "time": time.isoformat(),
            "bin_minutes": bin_minutes,
        }
        response = requests.get(
            f"{API_BASE_URL}/time/specific", params=params, timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return None
        raise
    except Exception as e:
        st.error(f"Error fetching safety score: {e}")
        return None


def get_safety_score_trend(
    intersection: str, start_time: datetime, end_time: datetime, bin_minutes: int = 15
):
    """Fetch safety score trend over time range."""
    try:
        params = {
            "intersection": intersection,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "bin_minutes": bin_minutes,
        }
        response = requests.get(f"{API_BASE_URL}/time/range", params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return []
        raise
    except Exception as e:
        st.error(f"Error fetching trend data: {e}")
        return []


def render_single_time_view(
    intersection: str, selected_time: datetime, bin_minutes: int
):
    """Render view for single time point analysis."""
    st.subheader("📍 Single Time Point Analysis")

    with st.spinner("Fetching safety score..."):
        data = get_safety_score_at_time(intersection, selected_time, bin_minutes)

    if not data:
        st.warning(
            f"No data available for **{intersection}** at **{selected_time.strftime('%Y-%m-%d %H:%M')}**"
        )
        st.info(
            "💡 Try selecting a different time or intersection. Available data up to November 9, 2025."
        )
        return

    # Display metrics in cards
    st.markdown(f"### {data['intersection'].replace('-', ' ').title()}")
    st.caption(f"Time Bin: {data['time_bin']}")

    # Main metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Safety Score",
            f"{data['safety_score']:.2f}",
            help="Overall MCDM safety score (0-100, higher = safer)",
        )

    with col2:
        st.metric(
            "Vehicle Count",
            data["vehicle_count"],
            help="Number of vehicles detected in time bin",
        )

    with col3:
        st.metric(
            "Incidents",
            data["incident_count"],
            help="Number of safety events detected",
        )

    with col4:
        st.metric(
            "VRU Count",
            data["vru_count"],
            help="Vulnerable road users (pedestrians, cyclists)",
        )

    st.divider()

    # Traffic metrics
    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Average Speed",
            f"{data['avg_speed']:.1f} mph",
            help="Average vehicle speed",
        )

    with col2:
        st.metric(
            "Speed Variance",
            f"{data['speed_variance']:.1f}",
            help="Variance in speed distribution",
        )

    st.divider()

    # MCDM method scores
    st.markdown("#### MCDM Method Breakdown")
    st.caption(
        "Different multi-criteria decision making methods used in the calculation"
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "SAW Score",
            f"{data['saw_score']:.2f}",
            help="Simple Additive Weighting method",
        )

    with col2:
        st.metric(
            "EDAS Score",
            f"{data['edas_score']:.2f}",
            help="Evaluation based on Distance from Average Solution",
        )

    with col3:
        st.metric(
            "CODAS Score",
            f"{data['codas_score']:.2f}",
            help="Combinative Distance-based Assessment",
        )

    # Show raw data in expander
    with st.expander("📋 View Raw Data"):
        st.json(data)


def create_trend_chart(df: pd.DataFrame, metric: str, title: str, color: str):
    """Create a plotly line chart for trend visualization."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["time_bin"],
            y=df[metric],
            mode="lines+markers",
            name=title,
            line=dict(color=color, width=2),
            marker=dict(size=6),
            hovertemplate=f"<b>%{{x}}</b><br>{title}: %{{y:.2f}}<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title=title,
        hovermode="x unified",
        height=350,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    return fig


def render_trend_view(
    intersection: str, start_time: datetime, end_time: datetime, bin_minutes: int
):
    """Render view for time range trend analysis."""
    st.subheader("📈 Trend Analysis")

    # Validate time range
    if end_time <= start_time:
        st.error("End time must be after start time!")
        return

    time_delta = end_time - start_time
    if time_delta.days > 7:
        st.error("Time range cannot exceed 7 days!")
        return

    with st.spinner("Fetching trend data..."):
        data = get_safety_score_trend(intersection, start_time, end_time, bin_minutes)

    if not data:
        st.warning(
            f"No data available for **{intersection}** between "
            f"**{start_time.strftime('%Y-%m-%d %H:%M')}** and **{end_time.strftime('%Y-%m-%d %H:%M')}**"
        )
        st.info(
            "💡 Try selecting a different time range or intersection. Available data up to November 9, 2025."
        )
        return

    # Convert to DataFrame
    df = pd.DataFrame(data)
    df["time_bin"] = pd.to_datetime(df["time_bin"])

    st.success(f"✅ Found **{len(df)}** data points for **{intersection}**")

    # Summary statistics
    st.markdown("### Summary Statistics")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Avg Safety Score", f"{df['safety_score'].mean():.2f}")

    with col2:
        st.metric("Min Safety Score", f"{df['safety_score'].min():.2f}")

    with col3:
        st.metric("Max Safety Score", f"{df['safety_score'].max():.2f}")

    with col4:
        st.metric("Total Vehicles", f"{df['vehicle_count'].sum():,}")

    with col5:
        st.metric("Total Incidents", f"{df['incident_count'].sum()}")

    st.divider()

    # Charts
    st.markdown("### Trend Charts")

    # Safety Score Trend
    fig1 = create_trend_chart(df, "safety_score", "Safety Score Over Time", "#1f77b4")
    st.plotly_chart(fig1, use_container_width=True)

    # Traffic Metrics
    col1, col2 = st.columns(2)

    with col1:
        fig2 = create_trend_chart(df, "vehicle_count", "Vehicle Count", "#2ca02c")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        fig3 = create_trend_chart(df, "incident_count", "Incident Count", "#d62728")
        st.plotly_chart(fig3, use_container_width=True)

    # Speed Metrics
    col1, col2 = st.columns(2)

    with col1:
        fig4 = create_trend_chart(df, "avg_speed", "Average Speed (mph)", "#ff7f0e")
        st.plotly_chart(fig4, use_container_width=True)

    with col2:
        fig5 = create_trend_chart(df, "speed_variance", "Speed Variance", "#9467bd")
        st.plotly_chart(fig5, use_container_width=True)

    # MCDM Methods Comparison
    st.markdown("### MCDM Methods Comparison")

    fig6 = go.Figure()

    fig6.add_trace(
        go.Scatter(
            x=df["time_bin"],
            y=df["saw_score"],
            mode="lines+markers",
            name="SAW",
            line=dict(width=2),
        )
    )

    fig6.add_trace(
        go.Scatter(
            x=df["time_bin"],
            y=df["edas_score"],
            mode="lines+markers",
            name="EDAS",
            line=dict(width=2),
        )
    )

    fig6.add_trace(
        go.Scatter(
            x=df["time_bin"],
            y=df["codas_score"],
            mode="lines+markers",
            name="CODAS",
            line=dict(width=2),
        )
    )

    fig6.update_layout(
        title="MCDM Method Scores Comparison",
        xaxis_title="Time",
        yaxis_title="Score",
        hovermode="x unified",
        height=400,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    st.plotly_chart(fig6, use_container_width=True)

    # Data table
    with st.expander("📊 View Data Table"):
        st.dataframe(
            df.style.format(
                {
                    "safety_score": "{:.2f}",
                    "mcdm_index": "{:.2f}",
                    "avg_speed": "{:.2f}",
                    "speed_variance": "{:.2f}",
                    "saw_score": "{:.2f}",
                    "edas_score": "{:.2f}",
                    "codas_score": "{:.2f}",
                }
            ),
            use_container_width=True,
        )


def main():
    """Main application entry point."""

    # Header
    st.title(f"{APP_ICON} Traffic Safety Trend Analysis")
    st.markdown(
        "Analyze safety scores at specific times or visualize trends over time ranges. "
        "Uses MCDM (Multi-Criteria Decision Making) methodology with historical data."
    )

    st.divider()

    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Load intersections
        with st.spinner("Loading intersections..."):
            intersections = get_available_intersections()

        if not intersections:
            st.error("No intersections available. Please check API connection.")
            st.info("Make sure the backend API is running on http://localhost:8000")
            return

        # Intersection selection
        selected_intersection = st.selectbox(
            "Select Intersection",
            intersections,
            format_func=lambda x: x.replace("-", " ").title(),
        )

        st.divider()

        # Analysis mode
        analysis_mode = st.radio(
            "Analysis Mode",
            ["Single Time Point", "Time Range Trend"],
            help="Choose between analyzing a specific time or viewing trends over a period",
        )

        st.divider()

        # Time bin configuration
        bin_minutes = st.selectbox(
            "Time Bin Size (minutes)",
            [15, 30, 60],
            index=0,
            help="Size of time bins for aggregation",
        )

        st.divider()

        if analysis_mode == "Single Time Point":
            st.subheader("🕐 Select Time")

            # Default to Nov 9, 2025 10:00 AM
            default_date = datetime(2025, 11, 9)
            default_time = datetime.strptime("10:00", "%H:%M").time()

            selected_date = st.date_input(
                "Date",
                value=default_date,
                max_value=datetime(2025, 11, 9),  # Data only available up to Nov 9
                help="Select date (data available up to Nov 9, 2025)",
            )

            selected_time = st.time_input(
                "Time",
                value=default_time,
                help="Select time of day",
            )

            # Combine date and time
            selected_datetime = datetime.combine(selected_date, selected_time)

        else:  # Time Range Trend
            st.subheader("📅 Select Time Range")

            # Default to Nov 9, 2025 8 AM - 6 PM
            default_start = datetime(2025, 11, 9, 8, 0)
            default_end = datetime(2025, 11, 9, 18, 0)

            start_date = st.date_input(
                "Start Date",
                value=default_start.date(),
                max_value=datetime(2025, 11, 9),
                help="Select start date",
            )

            start_time = st.time_input(
                "Start Time",
                value=default_start.time(),
                help="Select start time",
            )

            end_date = st.date_input(
                "End Date",
                value=default_end.date(),
                max_value=datetime(2025, 11, 9),
                help="Select end date",
            )

            end_time = st.time_input(
                "End Time",
                value=default_end.time(),
                help="Select end time",
            )

            start_datetime = datetime.combine(start_date, start_time)
            end_datetime = datetime.combine(end_date, end_time)

        st.divider()

        # Quick time range presets (only for trend mode)
        if analysis_mode == "Time Range Trend":
            st.subheader("⚡ Quick Presets")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Last 2 Hours", use_container_width=True):
                    end_datetime = datetime(2025, 11, 9, 23, 45)
                    start_datetime = end_datetime - timedelta(hours=2)
                    st.rerun()

            with col2:
                if st.button("Last 6 Hours", use_container_width=True):
                    end_datetime = datetime(2025, 11, 9, 23, 45)
                    start_datetime = end_datetime - timedelta(hours=6)
                    st.rerun()

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Business Hours", use_container_width=True):
                    start_datetime = datetime(2025, 11, 9, 9, 0)
                    end_datetime = datetime(2025, 11, 9, 17, 0)
                    st.rerun()

            with col2:
                if st.button("Full Day", use_container_width=True):
                    start_datetime = datetime(2025, 11, 9, 0, 0)
                    end_datetime = datetime(2025, 11, 9, 23, 59)
                    st.rerun()

        # About section
        with st.expander("ℹ️ About"):
            st.markdown(
                """
            ### MCDM Methodology
            
            The safety scores are calculated using a hybrid Multi-Criteria Decision Making approach:
            
            1. **CRITIC Weighting**: Determines importance of each criterion using historical data (24-hour lookback)
            2. **Three Methods**:
               - SAW (Simple Additive Weighting)
               - EDAS (Distance from Average)
               - CODAS (Combinative Distance)
            3. **Final Score**: Average of all three methods
            
            **Higher safety score = Safer intersection**
            
            ### Data Criteria
            - Vehicle count
            - VRU (pedestrian/cyclist) count
            - Average speed
            - Speed variance
            - Incident count
            """
            )

    # Main content area
    if analysis_mode == "Single Time Point":
        render_single_time_view(selected_intersection, selected_datetime, bin_minutes)
    else:
        render_trend_view(
            selected_intersection, start_datetime, end_datetime, bin_minutes
        )

    # Footer
    st.divider()
    st.caption(
        "Traffic Safety Trend Analysis | Built with Streamlit & Plotly | "
        "Powered by MCDM Safety Index API"
    )


if __name__ == "__main__":
    main()
