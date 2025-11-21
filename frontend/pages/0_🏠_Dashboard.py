"""
🏠 Home

Interactive map dashboard for Traffic Safety Index.
Visualize traffic intersections with safety metrics on an interactive map.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from streamlit_folium import st_folium

from app.services.api_client import get_intersections, clear_cache
from app.controllers.map_controller import build_map, add_legend_to_map
from app.views.components import (
    render_kpi_cards,
    render_details_card,
    render_legend,
    render_data_status,
    render_filters,
    apply_filters,
    render_data_table,
)
from app.utils.config import APP_TITLE, APP_ICON, LAYOUT, MAP_HEIGHT


def main():
    """Main application entry point."""

    # Header
    st.title(f"{APP_ICON} Traffic Safety Dashboard")
    st.markdown(
        "Interactive visualization of traffic intersections with safety metrics. "
        "**Higher safety index = More dangerous.**"
    )

    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Controls")

        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            clear_cache()
            st.rerun()

        st.divider()

        # Load data
        with st.spinner("Loading intersection data..."):
            intersections, error, stats = get_intersections()

        # Show data status
        render_data_status(error, stats)

        st.divider()

        # Convert to DataFrame
        if intersections:
            df = pd.DataFrame([i.to_dict() for i in intersections])
        else:
            df = pd.DataFrame()

        # Render filters
        search_text, safety_range, volume_range = render_filters(df)

        st.divider()

        # Legend
        render_legend()

        # About section
        with st.expander("ℹ️ About"):
            st.markdown(
                """
            This dashboard visualizes traffic intersection safety data.
            
            **Data Source:** Traffic Safety API
            
            **Visual Encoding:**
            - Circle size represents traffic volume
            - Circle color represents safety risk level
            
            **Safety Index:** A higher value indicates a more dangerous intersection.
            
            **Navigation:**
            - Trend Analysis: Time-based analysis and trend charts (Home Page)
            - Dashboard: Interactive map and overview
            """
            )

    # Apply filters
    if not df.empty:
        filtered_df = apply_filters(df, search_text, safety_range, volume_range)
    else:
        filtered_df = df

    # Show KPI cards
    render_kpi_cards(filtered_df)

    st.divider()

    # Main layout: Map and Details side by side
    col_map, col_details = st.columns([2, 1])

    # Initialize map_data
    map_data = None

    with col_map:
        st.subheader("🗺️ Interactive Map")

        if filtered_df.empty:
            st.warning(
                "No intersections match the current filters. Try adjusting the filter values."
            )
        else:
            # Show filter results count
            if len(filtered_df) < len(df):
                st.info(
                    f"Showing **{len(filtered_df)}** of **{len(df)}** intersections "
                    f"(filtered by criteria)"
                )

            # Build and render map
            with st.spinner("Building map..."):
                folium_map = build_map(filtered_df, fit_bounds=True)
                folium_map = add_legend_to_map(folium_map)

                # Render map with click detection
                map_data = st_folium(
                    folium_map,
                    height=MAP_HEIGHT,
                    width=None,
                    returned_objects=["last_object_clicked"],
                )

    with col_details:
        st.subheader("📊 Details")

        # Check if a marker was clicked
        clicked = map_data.get("last_object_clicked") if map_data else None

        if clicked and clicked.get("lat") and clicked.get("lng"):
            # Find the clicked intersection by coordinates
            clicked_lat = clicked["lat"]
            clicked_lng = clicked["lng"]

            # Match with small tolerance for floating point comparison
            tolerance = 0.0001
            matched = filtered_df[
                (abs(filtered_df["latitude"] - clicked_lat) < tolerance)
                & (abs(filtered_df["longitude"] - clicked_lng) < tolerance)
            ]

            if not matched.empty:
                # Show details for the first match
                render_details_card(matched.iloc[0])
            else:
                st.info("👆 Click on a marker to view details")
        else:
            st.info("👆 Click on a marker to view details")

    # Data table at the bottom
    st.divider()
    render_data_table(filtered_df)

    # Footer
    st.divider()
    st.caption(
        "Traffic Safety Index Dashboard | "
        "Built with Streamlit, Folium, and Pydantic | "
        "Data updates every 5 minutes"
    )


if __name__ == "__main__":
    main()
