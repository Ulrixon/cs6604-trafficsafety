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
from typing import Optional
from datetime import datetime, timedelta
import requests

from app.utils.config import APP_ICON, API_URL

# API configuration - use the full API_URL as base (already includes /api/v1/safety/index/)
API_BASE_URL = API_URL.rstrip("/") + "/safety/index"


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
    """Fetch safety score for specific time (returns MCDM and RT-SI separately)."""
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
    intersection: str,
    start_time: datetime,
    end_time: datetime,
    bin_minutes: int = 15,
):
    """Fetch safety score trend over time range (returns MCDM and RT-SI separately)."""
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


def blend_safety_scores(mcdm: float, rt_si: Optional[float], alpha: float) -> float:
    """Blend MCDM and RT-SI scores with alpha coefficient.

    Formula: Final = α*RT-SI + (1-α)*MCDM
    If RT-SI is None, returns MCDM only.
    """
    if rt_si is not None:
        return alpha * rt_si + (1 - alpha) * mcdm
    return mcdm


def render_single_time_view(
    intersection: str, selected_time: datetime, bin_minutes: int, alpha: float
):
    """Render view for single time point analysis."""
    st.subheader("📍 Single Time Point Analysis")

    with st.spinner("Fetching safety score..."):
        data = get_safety_score_at_time(intersection, selected_time, bin_minutes)

    if not data:
        st.warning(
            f"No data available for **{intersection}** at **{selected_time.strftime('%Y-%m-%d %H:%M')}**"
        )
        st.info("💡 Try selecting a different time or intersection.")
        return

    # Blend scores in frontend
    mcdm = data.get("mcdm_index", data.get("safety_score", 50.0))
    rt_si = data.get("rt_si_score")
    final_index = blend_safety_scores(mcdm, rt_si, alpha)

    # Display metrics in cards
    st.markdown(f"### {data['intersection'].replace('-', ' ').title()}")
    st.caption(f"Time Bin: {data['time_bin']}")

    # Main safety indices
    st.markdown("#### 🎯 Safety Indices")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Final Safety Index",
            f"{final_index:.2f}",
            help=f"Blended safety index: {alpha:.1f}×RT-SI + {1-alpha:.1f}×MCDM (0-100, higher = safer)",
        )

    with col2:
        if data.get("rt_si_score") is not None:
            st.metric(
                "RT-SI Score",
                f"{data['rt_si_score']:.2f}",
                help="Real-Time Safety Index (0-100, higher = safer)",
            )
        else:
            st.metric(
                "RT-SI Score",
                "N/A",
                help="Real-Time Safety Index not available for this intersection/time",
            )

    with col3:
        st.metric(
            "MCDM Index",
            f"{data['mcdm_index']:.2f}",
            help="Multi-Criteria Decision Making index (0-100, higher = safer)",
        )

    with col4:
        st.metric(
            "Safety Score",
            f"{data['safety_score']:.2f}",
            help="Overall MCDM safety score (0-100, higher = safer)",
        )

    # RT-SI Sub-indices (if available)
    if data.get("rt_si_score") is not None:
        st.markdown("#### 🚦 RT-SI Sub-Indices")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "VRU Index",
                f"{data.get('vru_index', 0):.4f}",
                help="Vulnerable Road User sub-index from RT-SI calculation",
            )

        with col2:
            st.metric(
                "Vehicle Index",
                f"{data.get('vehicle_index', 0):.4f}",
                help="Vehicle sub-index from RT-SI calculation",
            )

        with col3:
            # Calculate blend percentage
            final_index = data.get("final_safety_index") or 0
            rt_si_contribution = (
                (alpha * data["rt_si_score"]) / final_index * 100
                if final_index > 0
                else 0
            )
            st.metric(
                "RT-SI Weight",
                f"{alpha*100:.0f}%",
                help=f"RT-SI contributes {alpha*100:.0f}% to final index, MCDM contributes {(1-alpha)*100:.0f}%",
            )

    st.divider()

    # Traffic metrics
    st.markdown("#### 🚗 Traffic Metrics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Vehicle Count",
            data["vehicle_count"],
            help="Number of vehicles detected in time bin",
        )

    with col2:
        st.metric(
            "VRU Count",
            data["vru_count"],
            help="Vulnerable road users (pedestrians, cyclists)",
        )

    with col3:
        st.metric(
            "Incidents",
            data["incident_count"],
            help="Number of safety events detected",
        )

    with col4:
        st.metric(
            "Average Speed",
            f"{data['avg_speed']:.1f} mph",
            help="Average vehicle speed",
        )

    col1, col2 = st.columns(2)

    with col1:
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
    intersection: str,
    start_time: datetime,
    end_time: datetime,
    bin_minutes: int,
    alpha: float,
):
    """Render view for time range trend analysis."""
    st.subheader("📈 Trend Analysis")

    # Validate time range
    if end_time <= start_time:
        st.error("End time must be after start time!")
        return

    with st.spinner("Fetching trend data..."):
        data = get_safety_score_trend(intersection, start_time, end_time, bin_minutes)

    if not data:
        st.warning(
            f"No data available for **{intersection}** between "
            f"**{start_time.strftime('%Y-%m-%d %H:%M')}** and **{end_time.strftime('%Y-%m-%d %H:%M')}**"
        )
        st.info("💡 Try selecting a different time range or intersection.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(data)
    df["time_bin"] = pd.to_datetime(df["time_bin"])

    # Blend scores in frontend for each row
    df["final_safety_index"] = df.apply(
        lambda row: blend_safety_scores(
            row.get("mcdm_index", row.get("safety_score", 50.0)),
            row.get("rt_si_score"),
            alpha,
        ),
        axis=1,
    )

    st.success(f"✅ Found **{len(df)}** data points for **{intersection}**")

    # Check if RT-SI data is available
    has_rt_si = "rt_si_score" in df.columns and df["rt_si_score"].notna().any()
    has_final_index = (
        "final_safety_index" in df.columns and df["final_safety_index"].notna().any()
    )

    # Summary statistics
    st.markdown("### Summary Statistics")

    if has_final_index:
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric("Avg Final Index", f"{df['final_safety_index'].mean():.2f}")

        with col2:
            if has_rt_si:
                avg_rt_si = df["rt_si_score"].dropna().mean()
                st.metric("Avg RT-SI", f"{avg_rt_si:.2f}")
            else:
                st.metric("Avg RT-SI", "N/A")

        with col3:
            st.metric("Avg MCDM", f"{df['mcdm_index'].mean():.2f}")

        with col4:
            st.metric("Avg Safety Score", f"{df['safety_score'].mean():.2f}")

        with col5:
            st.metric("Total Vehicles", f"{df['vehicle_count'].sum():,}")

        with col6:
            st.metric("Total Incidents", f"{df['incident_count'].sum()}")
    else:
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

    # Final Safety Index (if available)
    if has_final_index:
        st.markdown("#### 🎯 Final Blended Safety Index")
        st.caption(f"α={alpha:.1f}: {alpha*100:.0f}% RT-SI + {(1-alpha)*100:.0f}% MCDM")

        fig_final = go.Figure()

        # Add Final Index
        fig_final.add_trace(
            go.Scatter(
                x=df["time_bin"],
                y=df["final_safety_index"],
                mode="lines+markers",
                name="Final Safety Index",
                line=dict(color="#e74c3c", width=3),
                marker=dict(size=8),
                hovertemplate="<b>Final Index</b>: %{y:.2f}<extra></extra>",
            )
        )

        # Add RT-SI if available
        if has_rt_si:
            fig_final.add_trace(
                go.Scatter(
                    x=df["time_bin"],
                    y=df["rt_si_score"],
                    mode="lines+markers",
                    name="RT-SI Score",
                    line=dict(color="#3498db", width=2, dash="dot"),
                    marker=dict(size=6),
                    hovertemplate="<b>RT-SI</b>: %{y:.2f}<extra></extra>",
                )
            )

        # Add MCDM
        fig_final.add_trace(
            go.Scatter(
                x=df["time_bin"],
                y=df["mcdm_index"],
                mode="lines+markers",
                name="MCDM Index",
                line=dict(color="#2ecc71", width=2, dash="dash"),
                marker=dict(size=6),
                hovertemplate="<b>MCDM</b>: %{y:.2f}<extra></extra>",
            )
        )

        fig_final.update_layout(
            title=f"Final Blended Safety Index (α={alpha:.1f})",
            xaxis_title="Time",
            yaxis_title="Safety Index (0-100)",
            hovermode="x unified",
            height=400,
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )

        st.plotly_chart(fig_final, use_container_width=True)

        # RT-SI Sub-indices (if available)
        if has_rt_si and "vru_index" in df.columns and "vehicle_index" in df.columns:
            st.markdown("#### 🚦 RT-SI Sub-Indices")

            fig_sub = go.Figure()

            fig_sub.add_trace(
                go.Scatter(
                    x=df["time_bin"],
                    y=df["vru_index"],
                    mode="lines+markers",
                    name="VRU Index",
                    line=dict(color="#9b59b6", width=2),
                    marker=dict(size=6),
                    hovertemplate="<b>VRU Index</b>: %{y:.4f}<extra></extra>",
                )
            )

            fig_sub.add_trace(
                go.Scatter(
                    x=df["time_bin"],
                    y=df["vehicle_index"],
                    mode="lines+markers",
                    name="Vehicle Index",
                    line=dict(color="#f39c12", width=2),
                    marker=dict(size=6),
                    hovertemplate="<b>Vehicle Index</b>: %{y:.4f}<extra></extra>",
                )
            )

            fig_sub.update_layout(
                title="RT-SI Sub-Indices (VRU vs Vehicle Risk)",
                xaxis_title="Time",
                yaxis_title="Risk Index",
                hovermode="x unified",
                height=350,
                margin=dict(l=0, r=0, t=40, b=0),
            )

            st.plotly_chart(fig_sub, use_container_width=True)

    # Safety Score Trend
    fig1 = create_trend_chart(
        df, "safety_score", "MCDM Safety Score Over Time", "#1f77b4"
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Traffic Metrics
    col1, col2 = st.columns(2)

    with col1:
        fig2 = create_trend_chart(df, "vehicle_count", "Vehicle Count", "#2ca02c")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        fig3 = create_trend_chart(df, "incident_count", "Incident Count", "#d62728")
        st.plotly_chart(fig3, use_container_width=True)

    # VRU and Speed Metrics
    col1, col2 = st.columns(2)

    with col1:
        fig_vru = create_trend_chart(
            df, "vru_count", "VRU Count (Pedestrians & Cyclists)", "#17becf"
        )
        st.plotly_chart(fig_vru, use_container_width=True)

    with col2:
        fig4 = create_trend_chart(df, "avg_speed", "Average Speed (mph)", "#ff7f0e")
        st.plotly_chart(fig4, use_container_width=True)

    # Speed Variance
    fig5 = create_trend_chart(df, "speed_variance", "Speed Variance", "#9467bd")
    st.plotly_chart(fig5, use_container_width=True)

    # MCDM Methods Comparison
    st.markdown("### MCDM Methods Comparison")

    fig6 = go.Figure()

    # Add MCDM Index (the combined average)
    fig6.add_trace(
        go.Scatter(
            x=df["time_bin"],
            y=df["mcdm_index"],
            mode="lines+markers",
            name="MCDM Index",
            line=dict(width=3, dash="solid"),
            marker=dict(size=7),
        )
    )

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
        title="MCDM Method Scores Comparison (including Combined Index)",
        xaxis_title="Time",
        yaxis_title="Score",
        hovermode="x unified",
        height=400,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    st.plotly_chart(fig6, use_container_width=True)

    # Normalized All Variables Comparison
    st.markdown("### All Variables Normalized (0-100 Scale)")
    st.caption("All metrics normalized to 0-100 scale for easy comparison")

    # Create normalized DataFrame
    df_normalized = df.copy()

    # List of variables to normalize
    variables_to_normalize = [
        ("mcdm_index", "MCDM Index"),
        ("safety_score", "Safety Score"),
        ("vehicle_count", "Vehicle Count"),
        ("incident_count", "Incident Count"),
        ("vru_count", "VRU Count"),
        ("avg_speed", "Avg Speed"),
        ("speed_variance", "Speed Variance"),
    ]

    # Normalize each variable to 0-100 scale
    for col, label in variables_to_normalize:
        if col in df_normalized.columns:
            col_max = df_normalized[col].max()
            if col_max > 0:
                # If max is greater than 100, normalize to 0-100
                if col_max > 100:
                    df_normalized[f"{col}_normalized"] = (
                        df_normalized[col] / col_max
                    ) * 100
                else:
                    # If max is already <= 100, keep as is
                    df_normalized[f"{col}_normalized"] = df_normalized[col]
            else:
                df_normalized[f"{col}_normalized"] = 0

    # Create the combined chart
    fig_combined = go.Figure()

    # Define colors for each variable
    colors = {
        "mcdm_index": "#1f77b4",
        "safety_score": "#ff7f0e",
        "vehicle_count": "#2ca02c",
        "incident_count": "#d62728",
        "vru_count": "#17becf",
        "avg_speed": "#bcbd22",
        "speed_variance": "#9467bd",
    }

    # Add traces for each variable
    for col, label in variables_to_normalize:
        if col in df.columns and f"{col}_normalized" in df_normalized.columns:
            fig_combined.add_trace(
                go.Scatter(
                    x=df_normalized["time_bin"],
                    y=df_normalized[f"{col}_normalized"],
                    mode="lines+markers",
                    name=label,
                    line=dict(color=colors.get(col, "#000000"), width=2),
                    marker=dict(size=4),
                    hovertemplate=f"<b>{label}</b><br>Normalized: %{{y:.2f}}<br>Original: {df[col].round(2).astype(str)}<extra></extra>",
                )
            )

    fig_combined.update_layout(
        title={
            "text": "All Variables Normalized to 0-100 Scale",
            "y": 0.98,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
        },
        xaxis_title="Time",
        yaxis_title="Normalized Value (0-100)",
        yaxis_range=[0, 105],  # Slight padding at top
        hovermode="x unified",
        height=550,
        margin=dict(l=0, r=0, t=80, b=0),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            xanchor="center",
            x=0.5,
        ),
    )

    st.plotly_chart(fig_combined, use_container_width=True)

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

        # Alpha blending coefficient
        st.subheader("⚖️ Index Blending")
        alpha = st.slider(
            "RT-SI Weight (α)",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help=f"Final Index = α×RT-SI + (1-α)×MCDM\n\n"
            f"• α=0.0: Use only MCDM (long-term prioritization)\n"
            f"• α=0.7: Balanced (recommended for real-time dashboards)\n"
            f"• α=1.0: Use only RT-SI (real-time safety focus)",
        )

        st.caption(
            f"📊 Current blend: {alpha*100:.0f}% RT-SI + {(1-alpha)*100:.0f}% MCDM"
        )

        st.divider()

        if analysis_mode == "Single Time Point":
            st.subheader("🕐 Select Time")

            # Default to current date at 10:00 AM
            default_date = datetime.now().date()
            default_time = datetime.strptime("10:00", "%H:%M").time()

            selected_date = st.date_input(
                "Date",
                value=default_date,
                help="Select date",
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

            # Default to current date 8 AM - 6 PM
            today = datetime.now().date()
            default_start = datetime.combine(
                today, datetime.strptime("08:00", "%H:%M").time()
            )
            default_end = datetime.combine(
                today, datetime.strptime("18:00", "%H:%M").time()
            )

            # Initialize session state for time range if not exists
            if "start_datetime" not in st.session_state:
                st.session_state.start_datetime = default_start
            if "end_datetime" not in st.session_state:
                st.session_state.end_datetime = default_end

            start_date = st.date_input(
                "Start Date",
                value=st.session_state.start_datetime.date(),
                help="Select start date",
            )

            start_time = st.time_input(
                "Start Time",
                value=st.session_state.start_datetime.time(),
                help="Select start time",
            )

            end_date = st.date_input(
                "End Date",
                value=st.session_state.end_datetime.date(),
                help="Select end date",
            )

            end_time = st.time_input(
                "End Time",
                value=st.session_state.end_datetime.time(),
                help="Select end time",
            )

            # Update session state with manual input changes
            start_datetime = datetime.combine(start_date, start_time)
            end_datetime = datetime.combine(end_date, end_time)

            # Update session state if values changed manually
            if start_datetime != st.session_state.start_datetime:
                st.session_state.start_datetime = start_datetime
            if end_datetime != st.session_state.end_datetime:
                st.session_state.end_datetime = end_datetime

        st.divider()

        # Quick time range presets (only for trend mode)
        if analysis_mode == "Time Range Trend":
            st.subheader("⚡ Quick Presets")
            st.caption("Click to set time range based on selected start date/time")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("2 Hours", use_container_width=True):
                    st.session_state.start_datetime = datetime.combine(
                        start_date, start_time
                    )
                    st.session_state.end_datetime = (
                        st.session_state.start_datetime + timedelta(hours=2)
                    )
                    st.rerun()

            with col2:
                if st.button("6 Hours", use_container_width=True):
                    st.session_state.start_datetime = datetime.combine(
                        start_date, start_time
                    )
                    st.session_state.end_datetime = (
                        st.session_state.start_datetime + timedelta(hours=6)
                    )
                    st.rerun()

            col1, col2 = st.columns(2)

            with col1:
                if st.button("12 Hours", use_container_width=True):
                    st.session_state.start_datetime = datetime.combine(
                        start_date, start_time
                    )
                    st.session_state.end_datetime = (
                        st.session_state.start_datetime + timedelta(hours=12)
                    )
                    st.rerun()

            with col2:
                if st.button("24 Hours", use_container_width=True):
                    st.session_state.start_datetime = datetime.combine(
                        start_date, start_time
                    )
                    st.session_state.end_datetime = (
                        st.session_state.start_datetime + timedelta(hours=24)
                    )
                    st.rerun()

            col1, col2 = st.columns(2)

            with col1:
                if st.button("1 Month", use_container_width=True):
                    st.session_state.start_datetime = datetime.combine(
                        start_date, start_time
                    )
                    st.session_state.end_datetime = (
                        st.session_state.start_datetime + timedelta(days=30)
                    )
                    st.rerun()

            with col2:
                if st.button("3 Months", use_container_width=True):
                    st.session_state.start_datetime = datetime.combine(
                        start_date, start_time
                    )
                    st.session_state.end_datetime = (
                        st.session_state.start_datetime + timedelta(days=90)
                    )
                    st.rerun()

            if st.button("1 Year", use_container_width=True):
                st.session_state.start_datetime = datetime.combine(
                    start_date, start_time
                )
                st.session_state.end_datetime = (
                    st.session_state.start_datetime + timedelta(days=365)
                )
                st.rerun()

        # About section
        with st.expander("ℹ️ About"):
            st.markdown(
                """
            ### Blended Safety Index Methodology
            
            The system combines two complementary safety assessment approaches:
            
            #### 1. RT-SI (Real-Time Safety Index)
            - **Historical Crash Data**: Uses 2017-2024 VDOT crash data
            - **Empirical Bayes Stabilization**: Smooths rates with λ=100,000
            - **Real-Time Uplift Factors**: 
              - Speed reduction (congestion)
              - Speed variance (erratic driving)
              - Conflict potential (VRU-vehicle interactions)
            - **Sub-Indices**: Separate VRU and Vehicle risk indices
            - **Scale**: 0-100 (higher = safer)
            
            #### 2. MCDM (Multi-Criteria Decision Making)
            - **CRITIC Weighting**: Determines criterion importance from 24-hour lookback
            - **Three Methods**: SAW, EDAS, CODAS
            - **Final Score**: Weighted average of all three methods
            - **Scale**: 0-100 (higher = safer)
            
            #### 3. Final Blended Index
            ```
            Final Index = α × RT-SI + (1-α) × MCDM
            ```
            - **α = 0.7** (recommended): Emphasizes real-time conditions
            - **α = 0.0**: Long-term prioritization (MCDM only)
            - **α = 1.0**: Real-time focus (RT-SI only)
            
            **Higher safety index = Safer intersection**
            
            ### Data Sources
            - VDOT crash data (2017-2024)
            - Real-time BSM/PSM messages
            - Vehicle counts & speed distributions
            - Safety events & incidents
            """
            )

    # Main content area
    if analysis_mode == "Single Time Point":
        render_single_time_view(
            selected_intersection, selected_datetime, bin_minutes, alpha
        )
    else:
        render_trend_view(
            selected_intersection, start_datetime, end_datetime, bin_minutes, alpha
        )

    # Footer
    st.divider()
    st.caption(
        "Traffic Safety Trend Analysis | Built with Streamlit & Plotly | "
        "Powered by RT-SI + MCDM Blended Safety Index API"
    )


if __name__ == "__main__":
    main()
