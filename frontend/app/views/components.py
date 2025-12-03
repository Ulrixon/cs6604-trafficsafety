"""
Reusable UI components for the Streamlit app.
"""

import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any

from app.models.intersection import Intersection
from app.utils.scaling import format_number
from app.views.history_components import render_historical_section


def render_kpi_cards(df: pd.DataFrame):
    """
    Render KPI summary cards at the top of the dashboard.

    Args:
        df: DataFrame with intersection data
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="📍 Total Intersections", value=len(df))

    with col2:
        if not df.empty:
            avg_safety = df["safety_index"].mean()
            st.metric(
                label="📊 Avg Final Index",
                value=f"{avg_safety:.1f}",
                help="Average blended safety index (RT-SI + MCDM)",
            )
        else:
            st.metric(label="📊 Avg Final Index", value="N/A")

    with col3:
        if not df.empty:
            high_risk_count = len(df[df["safety_index"] > 75])
            st.metric(
                label="⚠️ High Risk",
                value=high_risk_count,
                delta=f"{(high_risk_count/len(df)*100):.1f}%" if len(df) > 0 else None,
                delta_color="inverse",
            )
        else:
            st.metric(label="⚠️ High Risk", value="N/A")

    with col4:
        if not df.empty:
            total_volume = df["traffic_volume"].sum()
            st.metric(
                label="🚗 Total Traffic Volume", value=format_number(total_volume, 1)
            )
        else:
            st.metric(label="🚗 Total Traffic Volume", value="N/A")


def render_details_card(row: Optional[pd.Series]):
    """
    Render detailed information card for a selected intersection.

    Args:
        row: DataFrame row with intersection data, or None
    """
    if row is None:
        st.info("👆 Click on a marker to view details")
        return

    # Determine risk level and styling
    si = float(row["safety_index"])
    if si < 60:
        risk_level = "Low Risk"
        risk_color = "#2ECC71"
        risk_emoji = "✅"
    elif si <= 75:
        risk_level = "Medium Risk"
        risk_color = "#F39C12"
        risk_emoji = "⚠️"
    else:
        risk_level = "High Risk"
        risk_color = "#E74C3C"
        risk_emoji = "🚨"

    # Header
    st.markdown(f"### 📍 {row['intersection_name']}")

    # Risk badge
    st.markdown(
        f"""
        <div style="
            background-color: {risk_color};
            color: white;
            padding: 8px 16px;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
            margin-bottom: 15px;
        ">
            {risk_emoji} {risk_level}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Metrics
    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            label="Safety Index (Blended)",
            value=f"{si:.1f}",
            help="Final blended safety index combining RT-SI and MCDM",
        )

        # Show RT-SI if available
        if (
            "rt_si_score" in row
            and row["rt_si_score"] is not None
            and not pd.isna(row["rt_si_score"])
        ):
            st.metric(
                label="RT-SI Score",
                value=f"{float(row['rt_si_score']):.1f}",
                help="Real-Time Safety Index based on current conditions",
            )

        st.metric(label="Latitude", value=f"{row['latitude']:.4f}")

    with col2:
        st.metric(
            label="Traffic Volume", value=format_number(float(row["traffic_volume"]), 0)
        )

        # Show MCDM if available
        if (
            "mcdm_index" in row
            and row["mcdm_index"] is not None
            and not pd.isna(row["mcdm_index"])
        ):
            st.metric(
                label="MCDM Index",
                value=f"{float(row['mcdm_index']):.1f}",
                help="Long-term Multi-Criteria Decision Making index",
            )

        st.metric(label="Longitude", value=f"{row['longitude']:.4f}")

    # Show RT-SI sub-indices if available
    if (
        "vru_index" in row
        and row["vru_index"] is not None
        and not pd.isna(row["vru_index"])
    ) or (
        "vehicle_index" in row
        and row["vehicle_index"] is not None
        and not pd.isna(row["vehicle_index"])
    ):
        st.divider()
        st.caption("**RT-SI Sub-Indices:**")

        col1, col2 = st.columns(2)

        with col1:
            if (
                "vru_index" in row
                and row["vru_index"] is not None
                and not pd.isna(row["vru_index"])
            ):
                st.metric(
                    label="VRU Index",
                    value=f"{float(row['vru_index']):.4f}",
                    help="Vulnerable Road User risk component",
                )

        with col2:
            if (
                "vehicle_index" in row
                and row["vehicle_index"] is not None
                and not pd.isna(row["vehicle_index"])
            ):
                st.metric(
                    label="Vehicle Index",
                    value=f"{float(row['vehicle_index']):.4f}",
                    help="Vehicle traffic risk component",
                )

    # Additional info
    st.divider()
    st.caption(f"**Intersection ID:** {row['intersection_id']}")

    # Camera buttons (if camera_urls available)
    if "camera_urls" in row and row["camera_urls"] is not None and len(row["camera_urls"]) > 0:
        render_camera_buttons(row["camera_urls"], max_buttons=3)

    # Historical data toggle button
    st.markdown("")  # Add spacing

    # Initialize session state for history visibility if not exists
    if "show_history" not in st.session_state:
        st.session_state.show_history = False

    # Toggle button
    if st.button(
        (
            "📊 View Historical Data"
            if not st.session_state.show_history
            else "📊 Hide Historical Data"
        ),
        key=f"history_toggle_{row['intersection_id']}",
        use_container_width=True,
    ):
        st.session_state.show_history = not st.session_state.show_history

    # Render historical section if toggled on
    if st.session_state.show_history:
        render_historical_section(str(row["intersection_id"]))


def render_camera_buttons(camera_urls: List[Dict[str, Any]], max_buttons: int = 3):
    """
    Render camera access buttons for intersection.

    Args:
        camera_urls: List of camera link dictionaries with keys:
                    - source: Camera provider (e.g., "VDOT", "511")
                    - url: Full URL to camera feed or map
                    - label: User-friendly display name
        max_buttons: Maximum number of camera buttons to display (default: 3)
    """
    if not camera_urls or len(camera_urls) == 0:
        return  # No cameras available

    st.markdown("")  # Add spacing
    st.caption("**📹 Traffic Cameras:**")

    # Display up to max_buttons cameras
    for idx, camera in enumerate(camera_urls[:max_buttons]):
        # Validate required fields
        if not all(k in camera for k in ['source', 'url', 'label']):
            continue

        # Icon selection based on source
        icon_map = {
            'VDOT': '📹',
            '511': '🗺️',
            'TrafficLand': '📹',
        }
        icon = icon_map.get(camera['source'], '🔗')

        # Styled link button with hover effect
        button_html = f"""
        <a href="{camera['url']}"
           target="_blank"
           rel="noopener noreferrer"
           style="
               display: inline-block;
               width: 100%;
               padding: 10px 20px;
               margin: 5px 0;
               background-color: #0066cc;
               color: white;
               border-radius: 5px;
               text-decoration: none;
               font-weight: 500;
               text-align: center;
               transition: background-color 0.2s;
               box-shadow: 0 2px 4px rgba(0,0,0,0.1);
           "
           onmouseover="this.style.backgroundColor='#0052a3'"
           onmouseout="this.style.backgroundColor='#0066cc'">
            {icon} {camera['label']}
        </a>
        """
        st.markdown(button_html, unsafe_allow_html=True)

    # Show count if more cameras available
    if len(camera_urls) > max_buttons:
        st.caption(f"*+ {len(camera_urls) - max_buttons} more camera(s) available*")


def render_legend():
    """Render a legend explaining the visual encoding."""
    with st.expander("📖 Legend - How to Read the Map", expanded=False):
        st.markdown(
            """
        #### Marker Size
        - **Larger circles** = Higher traffic volume
        - **Smaller circles** = Lower traffic volume
        
        #### Marker Color
        - 🟢 **Green** = Low risk (Safety Index < 60)
        - 🟠 **Orange** = Medium risk (Safety Index 60-75)
        - 🔴 **Red** = High risk (Safety Index > 75)
        
        #### Interaction
        - **Hover** over a marker to see the intersection name
        - **Click** on a marker to view detailed information
        - Use the details panel on the right to see full metrics
        """
        )


def render_data_status(error: Optional[str], stats: dict):
    """
    Render data loading status and warnings.

    Args:
        error: Error message from API, or None if successful
        stats: Dictionary with data loading statistics
    """
    if error:
        st.warning(
            f"⚠️ **Using fallback data**: {error}\n\n"
            "The application is displaying sample data because the API is unavailable."
        )

    # Show data quality issues if any
    if stats.get("invalid", 0) > 0:
        with st.expander(
            f"⚠️ Data Quality Warning: {stats['invalid']} invalid records skipped"
        ):
            st.write("The following records could not be loaded:")
            for reason in stats.get("skipped_reasons", [])[:10]:  # Show max 10
                st.caption(f"- {reason}")
            if len(stats.get("skipped_reasons", [])) > 10:
                st.caption(f"... and {len(stats['skipped_reasons']) - 10} more")


def render_filters(
    df: pd.DataFrame,
) -> tuple[str, tuple[float, float], tuple[float, float]]:
    """
    Render filter controls and return filter values.

    Args:
        df: DataFrame with intersection data

    Returns:
        Tuple of (search_text, safety_range, volume_range)
    """
    st.subheader("🔍 Filters")

    # Search by name
    search_text = st.text_input(
        "Search by name",
        placeholder="Type intersection name...",
        help="Filter intersections by name (case-insensitive)",
    )

    # Safety index range
    if not df.empty:
        min_si = float(df["safety_index"].min())
        max_si = float(df["safety_index"].max())
        # Handle case where min and max are the same
        if min_si == max_si:
            # Expand range slightly to allow slider to work
            min_si = max(0.0, min_si - 1.0)
            max_si = min(100.0, max_si + 1.0)
    else:
        min_si, max_si = 0.0, 100.0

    safety_range = st.slider(
        "Safety Index Range",
        min_value=0.0,
        max_value=100.0,
        value=(min_si, max_si),
        help="Filter by safety index (higher = more dangerous)",
    )

    # Traffic volume range
    if not df.empty:
        min_vol = float(df["traffic_volume"].min())
        max_vol = float(df["traffic_volume"].max())

        # Handle edge case where all values are the same
        if min_vol == max_vol:
            # Add a small buffer to allow the slider to work
            min_vol = max(0, min_vol - 1)
            max_vol = max_vol + 1
    else:
        min_vol, max_vol = 0.0, 10000.0

    volume_range = st.slider(
        "Traffic Volume Range",
        min_value=min_vol,
        max_value=max_vol,
        value=(min_vol, max_vol if max_vol > min_vol else min_vol),
        format="%.0f",
        help="Filter by traffic volume",
    )

    return search_text, safety_range, volume_range


def apply_filters(
    df: pd.DataFrame,
    search_text: str,
    safety_range: tuple[float, float],
    volume_range: tuple[float, float],
) -> pd.DataFrame:
    """
    Apply filters to the DataFrame.

    Args:
        df: Original DataFrame
        search_text: Search string for name filtering
        safety_range: (min, max) for safety index
        volume_range: (min, max) for traffic volume

    Returns:
        Filtered DataFrame
    """
    filtered = df.copy()

    # Apply search filter
    if search_text:
        filtered = filtered[
            filtered["intersection_name"].str.contains(
                search_text, case=False, na=False
            )
        ]

    # Apply safety index filter
    filtered = filtered[
        (filtered["safety_index"] >= safety_range[0])
        & (filtered["safety_index"] <= safety_range[1])
    ]

    # Apply volume filter
    filtered = filtered[
        (filtered["traffic_volume"] >= volume_range[0])
        & (filtered["traffic_volume"] <= volume_range[1])
    ]

    return filtered


def render_data_table(df: pd.DataFrame):
    """
    Render sortable data table.

    Args:
        df: DataFrame with intersection data
    """
    st.subheader("📋 Data Table")

    if df.empty:
        st.info("No data to display. Adjust filters or check data source.")
        return

    # Format for display
    display_df = df.copy()
    display_df = display_df.sort_values("safety_index", ascending=False)

    # Round numeric columns
    display_df["safety_index"] = display_df["safety_index"].round(1)
    display_df["traffic_volume"] = display_df["traffic_volume"].round(0)
    display_df["latitude"] = display_df["latitude"].round(4)
    display_df["longitude"] = display_df["longitude"].round(4)

    # Rename columns for better display
    display_df = display_df.rename(
        columns={
            "intersection_id": "ID",
            "intersection_name": "Intersection Name",
            "safety_index": "Safety Index",
            "traffic_volume": "Traffic Volume",
            "latitude": "Latitude",
            "longitude": "Longitude",
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # Download button
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="traffic_safety_data.csv",
        mime="text/csv",
    )
