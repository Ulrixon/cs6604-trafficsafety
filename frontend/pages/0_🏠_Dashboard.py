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

        # Alpha blending coefficient
        st.subheader("⚖️ Safety Index Blending")
        alpha = st.slider(
            "RT-SI Weight (α)",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help=f"Final Index = α×RT-SI + (1-α)×MCDM\n\n"
            f"• α=0.0: Use only MCDM (long-term prioritization)\n"
            f"• α=0.7: Balanced (recommended for dashboards)\n"
            f"• α=1.0: Use only RT-SI (real-time safety focus)",
        )

        st.caption(
            f"📊 Current blend: {alpha*100:.0f}% RT-SI + {(1-alpha)*100:.0f}% MCDM"
        )
        st.caption(
            "Note: Final Index combines real-time conditions (RT-SI) with long-term patterns (MCDM)"
        )

        st.divider()

        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            clear_cache()
            st.rerun()

        st.divider()

        # Load data - use blended scores if alpha is configured
        with st.spinner("Loading intersection data..."):
            # Import the new function
            from app.services.api_client import fetch_latest_blended_scores

            # Use blended scores to incorporate RT-SI
            raw_data, blend_error = fetch_latest_blended_scores(alpha)

            if raw_data:
                # Convert to Intersection objects
                intersections = []
                stats = {
                    "total_raw": len(raw_data),
                    "valid": 0,
                    "invalid": 0,
                    "skipped_reasons": [],
                }

                for item in raw_data:
                    try:
                        from app.models.intersection import Intersection

                        intersection = Intersection(**item)
                        intersections.append(intersection)
                        stats["valid"] += 1
                    except Exception as e:
                        stats["invalid"] += 1
                        stats["skipped_reasons"].append(
                            f"ID {item.get('intersection_id', '?')}: {str(e)}"
                        )

                error = blend_error
            else:
                # Fallback to original method
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
                f"""
            This dashboard visualizes traffic intersection safety data using a blended safety index.
            
            **Data Source:** Traffic Safety API (Real-time + Historical)
            
            **Visual Encoding:**
            - Circle size represents traffic volume
            - Circle color represents safety risk level
            
            **Safety Index:** A higher value indicates a more dangerous intersection.
            
            **Blended Safety Index (α={alpha:.1f}):**
            ```
            Final Index = {alpha:.1f} × RT-SI + {1-alpha:.1f} × MCDM
            ```
            
            - **RT-SI (Real-Time Safety Index):** Based on current traffic conditions, speed patterns, and historical crash data with Empirical Bayes stabilization
            - **MCDM (Multi-Criteria Decision Making):** Long-term prioritization using CRITIC weighting and hybrid methods (SAW, EDAS, CODAS)
            - **Alpha (α):** Controls the balance between real-time (RT-SI) and long-term (MCDM) assessment
            
            **Adjust α slider above to change emphasis:**
            - α=0.0: Pure MCDM (long-term patterns)
            - α=0.7: Balanced (recommended)
            - α=1.0: Pure RT-SI (real-time focus)
            
            **Navigation:**
            - Dashboard: Interactive map with latest blended safety scores
            - Trend Analysis: Time-based analysis and detailed trend charts
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
        f"Traffic Safety Dashboard | Blended Index (α={alpha:.1f}) | "
        "RT-SI + MCDM | Built with Streamlit, Folium, and Pydantic | "
        "Data updates every 5 minutes"
    )


if __name__ == "__main__":
    main()
