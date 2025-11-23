"""
🔬 Sensitivity Analysis

Parameter robustness validation for RT-SI methodology.
Tests how stable the safety index is when parameters are perturbed.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import requests

from app.utils.config import APP_ICON, API_URL

# API configuration
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


def get_sensitivity_analysis(
    intersection: str,
    start_time: datetime,
    end_time: datetime,
    bin_minutes: int = 15,
    perturbation_pct: float = 0.25,
    n_samples: int = 50,
):
    """Fetch sensitivity analysis results."""
    try:
        params = {
            "intersection": intersection,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "bin_minutes": bin_minutes,
            "perturbation_pct": perturbation_pct,
            "n_samples": n_samples,
        }

        with st.spinner(
            f"Computing sensitivity analysis with {n_samples} parameter sets... This may take 30-60 seconds..."
        ):
            response = requests.get(
                f"{API_BASE_URL}/sensitivity-analysis",
                params=params,
                timeout=180,  # 3 minutes timeout
            )
            response.raise_for_status()
            return response.json()
    except requests.Timeout:
        st.error("Request timed out. Try reducing the number of samples or time range.")
        return None
    except Exception as e:
        st.error(f"Error fetching sensitivity analysis: {e}")
        return None


def plot_spearman_distribution(stability_metrics: Dict):
    """Plot distribution of Spearman rank correlations."""
    spearman = stability_metrics.get("spearman_correlations", {})

    # Create a synthetic distribution based on mean and std
    mean = spearman.get("mean", 0)
    std = spearman.get("std", 0)
    min_val = spearman.get("min", 0)
    max_val = spearman.get("max", 1)

    fig = go.Figure()

    # Add indicator gauge
    fig.add_trace(
        go.Indicator(
            mode="gauge+number+delta",
            value=mean,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Mean Spearman ρ<br><sub>(Ranking Stability)</sub>"},
            delta={"reference": 0.8, "increasing": {"color": "green"}},
            gauge={
                "axis": {"range": [0, 1], "tickwidth": 1},
                "bar": {"color": "darkblue"},
                "bgcolor": "white",
                "borderwidth": 2,
                "bordercolor": "gray",
                "steps": [
                    {"range": [0, 0.5], "color": "#ffcccb"},
                    {"range": [0.5, 0.7], "color": "#fff4cc"},
                    {"range": [0.7, 0.9], "color": "#d4edda"},
                    {"range": [0.9, 1.0], "color": "#c3e6cb"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 0.8,
                },
            },
        )
    )

    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=80, b=20),
    )

    # Add interpretation text
    if mean > 0.9:
        interpretation = "🟢 Excellent Stability"
        detail = "Rankings are highly preserved under parameter changes"
    elif mean > 0.7:
        interpretation = "🟢 Good Stability"
        detail = "Rankings generally preserved with minor variations"
    elif mean > 0.5:
        interpretation = "🟡 Moderate Stability"
        detail = "Some ranking changes occur with parameter perturbation"
    else:
        interpretation = "🔴 Poor Stability"
        detail = "Significant ranking changes - parameter sensitivity high"

    return fig, interpretation, detail


def plot_score_changes(stability_metrics: Dict):
    """Plot distribution of score changes."""
    score_changes = stability_metrics.get("score_changes", {})

    mean = score_changes.get("mean", 0)
    std = score_changes.get("std", 0)
    max_change = score_changes.get("max", 0)
    p95 = score_changes.get("percentile_95", 0)

    fig = go.Figure()

    # Create bar chart for statistics
    fig.add_trace(
        go.Bar(
            x=["Mean", "Std Dev", "95th %ile", "Max"],
            y=[mean, std, p95, max_change],
            text=[f"{mean:.2f}", f"{std:.2f}", f"{p95:.2f}", f"{max_change:.2f}"],
            textposition="auto",
            marker=dict(
                color=["#4472C4", "#ED7D31", "#FFC000", "#C00000"],
                line=dict(color="rgb(8,48,107)", width=1.5),
            ),
        )
    )

    fig.update_layout(
        title="RT-SI Score Changes (Absolute Differences)",
        xaxis_title="Statistic",
        yaxis_title="Score Change (0-100 scale)",
        height=350,
        showlegend=False,
        margin=dict(l=20, r=20, t=60, b=40),
    )

    return fig


def plot_tier_changes(stability_metrics: Dict):
    """Plot tier stability metrics."""
    tier_changes = stability_metrics.get("tier_changes", {})

    mean_changes = tier_changes.get("mean", 0)
    max_changes = tier_changes.get("max", 0)
    pct_no_change = tier_changes.get("percentage_no_change", 0)

    # Create donut chart for tier stability
    fig = go.Figure()

    fig.add_trace(
        go.Pie(
            labels=["No Tier Change", "Tier Changed"],
            values=[pct_no_change, 100 - pct_no_change],
            hole=0.4,
            marker=dict(colors=["#28a745", "#dc3545"]),
            textinfo="label+percent",
            textposition="inside",
        )
    )

    fig.update_layout(
        title=f"Risk Tier Stability<br><sub>Max changes: {max_changes} | Mean: {mean_changes:.1f}</sub>",
        height=350,
        showlegend=True,
        margin=dict(l=20, r=20, t=80, b=20),
    )

    return fig


def plot_parameter_importance(parameter_importance: Dict):
    """Plot parameter importance ranking."""
    # Convert to dataframe for easier plotting
    params = []
    correlations = []
    impacts = []

    for param, info in parameter_importance.items():
        params.append(param)
        correlations.append(abs(info["correlation"]))
        impacts.append(info["interpretation"])

    # Sort by correlation (descending)
    sorted_indices = sorted(
        range(len(correlations)), key=lambda i: correlations[i], reverse=True
    )
    params = [params[i] for i in sorted_indices]
    correlations = [correlations[i] for i in sorted_indices]
    impacts = [impacts[i] for i in sorted_indices]

    # Color by impact level
    colors = []
    for impact in impacts:
        if "High" in impact:
            colors.append("#dc3545")
        elif "Moderate" in impact:
            colors.append("#ffc107")
        else:
            colors.append("#28a745")

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=params,
            x=correlations,
            orientation="h",
            text=[f"{c:.3f}" for c in correlations],
            textposition="auto",
            marker=dict(color=colors, line=dict(color="rgb(8,48,107)", width=1)),
        )
    )

    fig.update_layout(
        title="Parameter Impact on RT-SI<br><sub>|Correlation| between parameter deviation and score deviation</sub>",
        xaxis_title="Absolute Correlation",
        yaxis_title="Parameter",
        height=max(400, len(params) * 30),
        showlegend=False,
        margin=dict(l=120, r=20, t=80, b=60),
        yaxis=dict(autorange="reversed"),
    )

    return fig


def plot_baseline_vs_perturbed(baseline: Dict, perturbed_samples: List[Dict]):
    """Plot baseline RT-SI scores vs perturbed samples."""
    timestamps = baseline.get("timestamps", [])
    baseline_scores = baseline.get("rt_si_scores", [])

    # Convert timestamps to datetime for better x-axis
    try:
        timestamps_dt = [datetime.fromisoformat(ts) for ts in timestamps]
    except:
        timestamps_dt = list(range(len(timestamps)))

    fig = go.Figure()

    # Add baseline as thick line
    fig.add_trace(
        go.Scatter(
            x=timestamps_dt,
            y=baseline_scores,
            mode="lines",
            name="Baseline",
            line=dict(color="black", width=3),
            hovertemplate="<b>Baseline</b><br>Time: %{x}<br>RT-SI: %{y:.2f}<extra></extra>",
        )
    )

    # Add perturbed samples as thin lines
    colors = px.colors.qualitative.Plotly
    for i, sample in enumerate(perturbed_samples[:10]):  # Show max 10 samples
        scores = sample.get("scores", [])
        label = sample.get("label", f"Sample {i}")

        fig.add_trace(
            go.Scatter(
                x=timestamps_dt,
                y=scores,
                mode="lines",
                name=label,
                line=dict(color=colors[i % len(colors)], width=1, dash="dot"),
                opacity=0.5,
                hovertemplate=f"<b>{label}</b><br>Time: %{{x}}<br>RT-SI: %{{y:.2f}}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Baseline vs Perturbed RT-SI Scores",
        xaxis_title="Time",
        yaxis_title="RT-SI Score (0-100)",
        height=450,
        hovermode="x unified",
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        margin=dict(l=60, r=150, t=60, b=60),
    )

    return fig


def plot_parameter_heatmap(perturbed_samples: List[Dict]):
    """Plot heatmap of parameter perturbations."""
    if not perturbed_samples:
        return None

    # Extract parameters from samples
    param_names = list(perturbed_samples[0]["params"].keys())

    # Build matrix
    param_matrix = []
    sample_labels = []

    for sample in perturbed_samples[:20]:  # Max 20 samples for readability
        label = sample["label"]
        params = sample["params"]

        # Normalize each parameter to show % deviation from baseline (assumed to be 1.0 multiplier)
        row = []
        for param in param_names:
            row.append(params[param])

        param_matrix.append(row)
        sample_labels.append(label)

    # Transpose for better layout
    param_matrix = list(zip(*param_matrix))

    fig = go.Figure(
        data=go.Heatmap(
            z=param_matrix,
            x=sample_labels,
            y=param_names,
            colorscale="RdBu_r",
            text=np.array(param_matrix).round(3),
            texttemplate="%{text}",
            textfont={"size": 8},
            colorbar=dict(title="Value"),
            hovertemplate="Sample: %{x}<br>Parameter: %{y}<br>Value: %{z:.4f}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Parameter Values Across Perturbed Samples",
        xaxis_title="Sample",
        yaxis_title="Parameter",
        height=max(400, len(param_names) * 40),
        margin=dict(l=150, r=20, t=60, b=100),
    )

    fig.update_xaxes(tickangle=45)

    return fig


def render_sensitivity_analysis():
    """Main render function for sensitivity analysis page."""
    st.title("🔬 Sensitivity Analysis")
    st.markdown(
        """
    **Validate RT-SI robustness** by randomly perturbing parameters and measuring stability.
    
    This analysis tests whether small changes in parameter values (β₁-β₃, k₁-k₅, λ, ω) 
    cause large changes in safety scores or risk rankings. A robust index should maintain
    stable rankings even when parameters vary within reasonable ranges.
    """
    )

    # Sidebar controls
    st.sidebar.header("Analysis Configuration")

    # Get available intersections
    intersections = get_available_intersections()
    if not intersections:
        st.error("No intersections available. Please check API connection.")
        return

    # Intersection selection
    intersection = st.sidebar.selectbox(
        "Select Intersection",
        options=intersections,
        index=(
            intersections.index("glebe-potomac")
            if "glebe-potomac" in intersections
            else 0
        ),
    )

    # Date/time selection
    st.sidebar.subheader("Time Range")

    default_start_date = datetime(2025, 11, 1)
    default_end_date = datetime(2025, 11, 1)

    col_d1, col_d2 = st.sidebar.columns(2)
    start_date = col_d1.date_input("Start Date", value=default_start_date)
    end_date = col_d2.date_input("End Date", value=default_end_date)

    col_t1, col_t2 = st.sidebar.columns(2)
    start_hour = col_t1.time_input(
        "Start Time", value=datetime.strptime("08:00", "%H:%M").time()
    )
    end_hour = col_t2.time_input(
        "End Time", value=datetime.strptime("18:00", "%H:%M").time()
    )

    start_time = datetime.combine(start_date, start_hour)
    end_time = datetime.combine(end_date, end_hour)

    # Bin size
    bin_minutes = st.sidebar.selectbox(
        "Time Bin Size (minutes)",
        options=[15, 30, 60],
        index=0,
    )

    # Perturbation settings
    st.sidebar.subheader("Perturbation Settings")

    perturbation_pct = (
        st.sidebar.slider(
            "Perturbation %",
            min_value=10,
            max_value=50,
            value=25,
            step=5,
            help="Randomly vary parameters by ±X%",
        )
        / 100.0
    )

    n_samples = st.sidebar.selectbox(
        "Number of Samples",
        options=[10, 25, 50, 100],
        index=2,
        help="More samples = more accurate but slower",
    )

    # Calculate button
    if st.sidebar.button(
        "🔬 Run Sensitivity Analysis", type="primary", use_container_width=True
    ):
        st.session_state.sensitivity_data = None  # Clear old data

        # Validate time range
        if end_time <= start_time:
            st.error("End time must be after start time!")
            return

        # Fetch data
        data = get_sensitivity_analysis(
            intersection,
            start_time,
            end_time,
            bin_minutes,
            perturbation_pct,
            n_samples,
        )

        if data:
            st.session_state.sensitivity_data = data
            st.success("✅ Sensitivity analysis completed!")

    # Display results
    if (
        "sensitivity_data" not in st.session_state
        or st.session_state.sensitivity_data is None
    ):
        st.info(
            "👆 Configure parameters in the sidebar and click 'Run Sensitivity Analysis' to begin."
        )

        # Show explanation
        with st.expander("ℹ️ What is Sensitivity Analysis?"):
            st.markdown(
                """
            ### Purpose
            
            Sensitivity analysis validates that the RT-SI methodology produces **stable, reliable results** 
            that aren't overly dependent on specific parameter values.
            
            ### How It Works
            
            1. **Baseline Calculation**: Compute RT-SI with standard parameters
            2. **Parameter Perturbation**: Generate N random parameter sets (within ±X%)
            3. **Recompute Scores**: Calculate RT-SI for each perturbed parameter set
            4. **Measure Stability**: Compare perturbed results to baseline
            
            ### Key Metrics
            
            - **Spearman Correlation**: Measures ranking stability (ρ > 0.8 = robust)
            - **Score Changes**: Magnitude of differences in absolute scores
            - **Tier Changes**: How often risk classifications change (Low/Medium/High)
            - **Parameter Importance**: Which parameters have the most impact
            
            ### Parameters Analyzed
            
            - **β₁, β₂, β₃**: Uplift weights (speed, variance, conflict)
            - **k₁...k₅**: Scaling constants for various factors
            - **λ**: Empirical Bayes shrinkage parameter
            - **ω**: VRU vs Vehicle index blend ratio
            
            ### Interpretation
            
            A **robust index** should show:
            - High Spearman correlation (> 0.8)
            - Small score changes (< 5-10 points typically)
            - Few tier reclassifications (> 80% unchanged)
            - No single parameter dominating the results
            """
            )

        return

    data = st.session_state.sensitivity_data

    # Display results
    st.success("Analysis Complete!")

    # Basic info
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Intersection", data["intersection"])

    with col2:
        time_range = data["time_range"]
        st.metric("Time Points", len(data["baseline"]["timestamps"]))

    with col3:
        settings = data["perturbation_settings"]
        st.metric("Samples Tested", settings["n_samples"])

    with col4:
        st.metric("Perturbation", f"±{settings['perturbation_pct']*100:.0f}%")

    st.divider()

    # Stability Overview
    st.header("📊 Stability Overview")

    stability = data["stability_metrics"]

    col1, col2 = st.columns(2)

    with col1:
        # Spearman correlation gauge
        fig_spearman, interpretation, detail = plot_spearman_distribution(stability)
        st.plotly_chart(fig_spearman, use_container_width=True)

        st.markdown(f"### {interpretation}")
        st.markdown(detail)

    with col2:
        # Tier stability donut
        fig_tier = plot_tier_changes(stability)
        st.plotly_chart(fig_tier, use_container_width=True)

    # Score changes
    st.subheader("Score Change Distribution")
    fig_scores = plot_score_changes(stability)
    st.plotly_chart(fig_scores, use_container_width=True)

    st.divider()

    # Parameter Importance
    st.header("🔍 Parameter Importance")

    st.markdown(
        """
    Shows which parameters have the most impact on RT-SI scores when perturbed.
    Higher correlation = more sensitive to that parameter.
    """
    )

    fig_importance = plot_parameter_importance(data["parameter_importance"])
    st.plotly_chart(fig_importance, use_container_width=True)

    # Parameter importance table
    with st.expander("📋 View Parameter Details"):
        param_df = pd.DataFrame(
            [
                {
                    "Parameter": param,
                    "Correlation": info["correlation"],
                    "Impact Level": info["interpretation"],
                }
                for param, info in data["parameter_importance"].items()
            ]
        )
        param_df = param_df.sort_values("Correlation", key=abs, ascending=False)
        st.dataframe(param_df, use_container_width=True, hide_index=True)

    st.divider()

    # Baseline vs Perturbed
    st.header("📈 Score Trajectories")

    st.markdown(
        """
    Baseline RT-SI scores (thick black line) compared to perturbed samples (colored dotted lines).
    Tight clustering indicates robust performance.
    """
    )

    fig_trajectories = plot_baseline_vs_perturbed(
        data["baseline"], data.get("perturbed_samples", [])
    )
    st.plotly_chart(fig_trajectories, use_container_width=True)

    st.divider()

    # Parameter Heatmap
    st.header("🔥 Parameter Value Heatmap")

    st.markdown(
        """
    Visualization of parameter values across different perturbed samples.
    Shows how parameters vary within the perturbation range.
    """
    )

    fig_heatmap = plot_parameter_heatmap(data.get("perturbed_samples", []))
    if fig_heatmap:
        st.plotly_chart(fig_heatmap, use_container_width=True)

    # Download results
    st.divider()
    st.header("💾 Export Results")

    col1, col2 = st.columns(2)

    with col1:
        # Prepare summary data
        summary_data = {
            "Intersection": data["intersection"],
            "Time Range": f"{time_range['start']} to {time_range['end']}",
            "Samples": settings["n_samples"],
            "Perturbation": f"±{settings['perturbation_pct']*100:.0f}%",
            "Mean Spearman ρ": stability["spearman_correlations"]["mean"],
            "Mean Score Change": stability["score_changes"]["mean"],
            "Max Score Change": stability["score_changes"]["max"],
            "Tier Stability %": stability["tier_changes"]["percentage_no_change"],
        }

        summary_df = pd.DataFrame([summary_data])
        csv = summary_df.to_csv(index=False)

        st.download_button(
            label="📥 Download Summary (CSV)",
            data=csv,
            file_name=f"sensitivity_summary_{intersection}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    with col2:
        # Full results as JSON
        import json

        json_str = json.dumps(data, indent=2)

        st.download_button(
            label="📥 Download Full Results (JSON)",
            data=json_str,
            file_name=f"sensitivity_full_{intersection}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json",
            mime="application/json",
        )


# Main execution
if __name__ == "__main__":
    st.set_page_config(
        page_title="Sensitivity Analysis",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    render_sensitivity_analysis()
