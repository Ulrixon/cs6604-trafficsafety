"""
📊 Analytics & Validation

Crash correlation analysis and validation metrics for research and validation.
Shows how well safety indices correlate with actual crash occurrences.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date
import requests
import numpy as np

from app.utils.config import APP_ICON, API_URL, API_TIMEOUT

# API configuration
API_BASE_URL = API_URL.rstrip("/").replace(
    "/safety/index", ""
)  # Remove specific endpoint


def get_correlation_metrics(
    start_date: date,
    end_date: date,
    threshold: float = 60.0,
    proximity_radius: float = 500.0,
):
    """Fetch correlation metrics from API."""
    try:
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "threshold": threshold,
            "proximity_radius": proximity_radius,
        }
        response = requests.get(
            f"{API_BASE_URL}/analytics/correlation", params=params, timeout=API_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching correlation metrics: {e}")
        return None


def get_scatter_data(start_date: date, end_date: date, proximity_radius: float = 500.0):
    """Fetch scatter plot data from API."""
    try:
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "proximity_radius": proximity_radius,
        }
        response = requests.get(
            f"{API_BASE_URL}/analytics/scatter-data", params=params, timeout=API_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching scatter data: {e}")
        return []


def get_time_series_data(
    start_date: date, end_date: date, proximity_radius: float = 500.0
):
    """Fetch time series data with crash overlay from API."""
    try:
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "proximity_radius": proximity_radius,
        }
        response = requests.get(
            f"{API_BASE_URL}/analytics/time-series", params=params, timeout=API_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching time series data: {e}")
        return []


def get_weather_impact(
    start_date: date, end_date: date, proximity_radius: float = 500.0
):
    """Fetch weather impact analysis from API."""
    try:
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "proximity_radius": proximity_radius,
        }
        response = requests.get(
            f"{API_BASE_URL}/analytics/weather-impact",
            params=params,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching weather impact: {e}")
        return []


def create_scatter_plot(data):
    """Create scatter plot: Safety Index vs Crash Occurrence."""
    if not data:
        return None

    df = pd.DataFrame(data)

    # Separate data by crash occurrence
    no_crash = df[df["had_crash"] == False]
    had_crash = df[df["had_crash"] == True]

    fig = go.Figure()

    # Points without crashes
    fig.add_trace(
        go.Scatter(
            x=no_crash["safety_index"],
            y=[0] * len(no_crash),  # Jitter for visibility
            mode="markers",
            name="No Crash",
            marker=dict(size=6, color="rgba(100, 200, 100, 0.4)", symbol="circle"),
            hovertemplate="Safety Index: %{x:.1f}<br>No crash<extra></extra>",
        )
    )

    # Points with crashes
    fig.add_trace(
        go.Scatter(
            x=had_crash["safety_index"],
            y=[1] * len(had_crash),
            mode="markers",
            name="Crash Occurred",
            marker=dict(size=10, color="rgba(255, 100, 100, 0.8)", symbol="x"),
            hovertemplate="Safety Index: %{x:.1f}<br>Crash occurred<extra></extra>",
        )
    )

    fig.update_layout(
        title="Safety Index vs Crash Occurrence",
        xaxis_title="Safety Index",
        yaxis_title="Crash Occurred",
        yaxis=dict(tickvals=[0, 1], ticktext=["No", "Yes"]),
        hovermode="closest",
        height=400,
    )

    return fig


def create_time_series_chart(data):
    """Create time series chart with crash overlay."""
    if not data:
        return None

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig = go.Figure()

    # Safety index line
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["safety_index"],
            mode="lines",
            name="Safety Index",
            line=dict(color="rgb(100, 150, 250)", width=2),
            hovertemplate="%{x}<br>Safety Index: %{y:.1f}<extra></extra>",
        )
    )

    # Crash markers
    crashes = df[df["had_crash"] == True]
    if not crashes.empty:
        fig.add_trace(
            go.Scatter(
                x=crashes["timestamp"],
                y=crashes["safety_index"],
                mode="markers",
                name="Crash",
                marker=dict(
                    size=12,
                    color="red",
                    symbol="x",
                    line=dict(color="darkred", width=2),
                ),
                hovertemplate="%{x}<br>Safety Index: %{y:.1f}<br>⚠️ Crash occurred<extra></extra>",
            )
        )

    fig.update_layout(
        title="Safety Index Over Time with Crash Events",
        xaxis_title="Time",
        yaxis_title="Safety Index",
        hovermode="x unified",
        height=500,
    )

    return fig


def create_confusion_matrix(metrics):
    """Create confusion matrix visualization."""
    if not metrics:
        return None

    # Create confusion matrix data
    matrix = [
        [metrics["true_negatives"], metrics["false_positives"]],
        [metrics["false_negatives"], metrics["true_positives"]],
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=["Predicted: No Crash", "Predicted: Crash"],
            y=["Actual: No Crash", "Actual: Crash"],
            text=matrix,
            texttemplate="%{text}",
            textfont={"size": 20},
            colorscale="RdYlGn",
            showscale=False,
        )
    )

    fig.update_layout(
        title=f"Confusion Matrix (Threshold: {metrics['threshold']})",
        xaxis_title="Predicted",
        yaxis_title="Actual",
        height=400,
    )

    return fig


def create_weather_impact_chart(data):
    """Create weather impact comparison chart."""
    if not data:
        return None

    df = pd.DataFrame(data)
    df = df.sort_values("crash_rate", ascending=False).head(10)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["condition"],
            y=df["crash_rate"] * 100,  # Convert to percentage
            name="Crash Rate",
            marker_color="rgb(255, 100, 100)",
            hovertemplate="%{x}<br>Crash Rate: %{y:.2f}%<br>Crashes: "
            + df["crash_count"].astype(str)
            + "<extra></extra>",
        )
    )

    fig.update_layout(
        title="Crash Rate by Weather Condition",
        xaxis_title="Weather Condition",
        yaxis_title="Crash Rate (%)",
        height=400,
    )

    return fig


def main():
    st.set_page_config(
        page_title="Analytics & Validation", page_icon=APP_ICON, layout="wide"
    )

    st.title("📊 Analytics & Validation")
    st.markdown("Crash correlation analysis for validating safety index effectiveness")

    # Sidebar controls
    st.sidebar.header("Analysis Parameters")

    # Date range
    end_date = st.sidebar.date_input(
        "End Date", value=datetime.now().date(), max_value=datetime.now().date()
    )

    start_date = st.sidebar.date_input(
        "Start Date", value=end_date - timedelta(days=30), max_value=end_date
    )

    # Threshold
    threshold = st.sidebar.slider(
        "Risk Threshold",
        min_value=0.0,
        max_value=100.0,
        value=60.0,
        step=5.0,
        help="Safety index threshold for classifying high risk",
    )

    # Proximity radius
    proximity_radius = st.sidebar.slider(
        "Proximity Radius (m)",
        min_value=100.0,
        max_value=10000.0,
        value=500.0,
        step=100.0,
        help="Maximum distance from intersection to include crashes",
    )

    run_analysis = st.sidebar.button("Run Analysis", type="primary")

    if run_analysis or "metrics" in st.session_state:
        with st.spinner("Loading correlation data..."):
            # Fetch data
            metrics = get_correlation_metrics(
                start_date, end_date, threshold, proximity_radius
            )

            if metrics:
                st.session_state["metrics"] = metrics

                # Display key metrics
                st.subheader("📈 Correlation Metrics")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Total Crashes", metrics["total_crashes"])
                    st.metric("Crash Rate", f"{metrics['crash_rate']*100:.2f}%")

                with col2:
                    st.metric("Precision", f"{metrics['precision']:.3f}")
                    st.metric("Recall", f"{metrics['recall']:.3f}")

                with col3:
                    st.metric("F1 Score", f"{metrics['f1_score']:.3f}")
                    st.metric("Accuracy", f"{metrics['accuracy']:.3f}")

                with col4:
                    st.metric("Pearson Corr", f"{metrics['pearson_correlation']:.3f}")
                    st.metric("Spearman Corr", f"{metrics['spearman_correlation']:.3f}")

                # Confusion Matrix
                st.subheader("🔢 Classification Performance")
                col1, col2 = st.columns([1, 1])

                with col1:
                    fig_cm = create_confusion_matrix(metrics)
                    if fig_cm:
                        st.plotly_chart(fig_cm, use_container_width=True)

                with col2:
                    st.markdown("### Interpretation")

                    # Interpretation based on metrics
                    if metrics["pearson_correlation"] > 0.3:
                        st.success(
                            "✅ **GOOD**: Strong positive correlation between safety index and crashes"
                        )
                    elif metrics["pearson_correlation"] > 0.15:
                        st.warning(
                            "⚠️ **MODERATE**: Moderate correlation - consider weight tuning"
                        )
                    else:
                        st.error(
                            "❌ **WEAK**: Weak correlation - formula needs improvement"
                        )

                    st.markdown(
                        f"""
                    **Metrics Explanation:**
                    - **Precision**: {metrics['precision']:.1%} of high-index periods had crashes
                    - **Recall**: {metrics['recall']:.1%} of crashes had high safety index
                    - **True Positives**: {metrics['true_positives']} (high index + crash)
                    - **False Positives**: {metrics['false_positives']} (high index + no crash)
                    - **True Negatives**: {metrics['true_negatives']} (low index + no crash)
                    - **False Negatives**: {metrics['false_negatives']} (low index + crash)
                    """
                    )

                # Visualizations
                st.subheader("📊 Visualizations")

                tab1, tab2, tab3 = st.tabs(
                    ["Time Series", "Scatter Plot", "Weather Impact"]
                )

                with tab1:
                    st.markdown("### Safety Index Over Time with Crash Events")
                    ts_data = get_time_series_data(
                        start_date, end_date, proximity_radius
                    )
                    fig_ts = create_time_series_chart(ts_data)
                    if fig_ts:
                        st.plotly_chart(fig_ts, use_container_width=True)
                    else:
                        st.info("No time series data available")

                with tab2:
                    st.markdown("### Safety Index vs Crash Occurrence")
                    scatter_data = get_scatter_data(
                        start_date, end_date, proximity_radius
                    )
                    fig_scatter = create_scatter_plot(scatter_data)
                    if fig_scatter:
                        st.plotly_chart(fig_scatter, use_container_width=True)
                    else:
                        st.info("No scatter data available")

                with tab3:
                    st.markdown("### Crash Rate by Weather Condition")
                    weather_data = get_weather_impact(
                        start_date, end_date, proximity_radius
                    )
                    fig_weather = create_weather_impact_chart(weather_data)
                    if fig_weather:
                        st.plotly_chart(fig_weather, use_container_width=True)
                    else:
                        st.info("No weather data available")

                # Export data for paper
                st.subheader("📄 Export for Research Paper")

                col1, col2 = st.columns(2)

                with col1:
                    # Export metrics as CSV
                    metrics_df = pd.DataFrame([metrics])
                    csv = metrics_df.to_csv(index=False)
                    st.download_button(
                        label="Download Metrics CSV",
                        data=csv,
                        file_name=f"correlation_metrics_{start_date}_{end_date}.csv",
                        mime="text/csv",
                    )

                with col2:
                    # Export summary as markdown
                    summary = f"""# Crash Correlation Analysis Results

**Analysis Period**: {start_date} to {end_date}
**Threshold**: {threshold}
**Proximity Radius**: {proximity_radius}m

## Key Metrics

- **Total Crashes**: {metrics['total_crashes']}
- **Total Intervals**: {metrics['total_intervals']}
- **Crash Rate**: {metrics['crash_rate']*100:.2f}%

## Classification Performance

- **Precision**: {metrics['precision']:.3f}
- **Recall**: {metrics['recall']:.3f}
- **F1 Score**: {metrics['f1_score']:.3f}
- **Accuracy**: {metrics['accuracy']:.3f}

## Correlation

- **Pearson Correlation**: {metrics['pearson_correlation']:.3f}
- **Spearman Correlation**: {metrics['spearman_correlation']:.3f}

## Confusion Matrix

|                  | Predicted: No Crash | Predicted: Crash |
|------------------|---------------------|------------------|
| Actual: No Crash | {metrics['true_negatives']} | {metrics['false_positives']} |
| Actual: Crash    | {metrics['false_negatives']} | {metrics['true_positives']} |
"""
                    st.download_button(
                        label="Download Summary Markdown",
                        data=summary,
                        file_name=f"analysis_summary_{start_date}_{end_date}.md",
                        mime="text/markdown",
                    )
            else:
                st.error(
                    "Failed to load correlation metrics. Please check the API connection."
                )
    else:
        st.info(
            "👈 Configure analysis parameters in the sidebar and click 'Run Analysis'"
        )

        # Show example info
        st.markdown(
            """
        ### About This Analysis

        This page provides crash correlation analysis to validate the effectiveness of our safety index formula.

        **Key Features:**
        - **Correlation Metrics**: Precision, recall, F1 score, accuracy
        - **Visualizations**: Time series, scatter plots, confusion matrix
        - **Weather Impact**: Analysis of crash rates by weather condition
        - **Export Tools**: Download data and summaries for research papers

        **How to Use:**
        1. Select date range and analysis parameters in the sidebar
        2. Click "Run Analysis" to fetch data from the database
        3. Review metrics and visualizations
        4. Export data for your research paper
        """
        )


if __name__ == "__main__":
    main()
