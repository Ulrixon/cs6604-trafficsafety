"""
🏠 Home

Interactive map dashboard for Traffic Safety Index.
Visualize traffic intersections with safety metrics on an interactive map.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
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
from app.utils.config import APP_TITLE, APP_ICON, LAYOUT, MAP_HEIGHT, API_URL, API_TIMEOUT


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

    # ── SafetyChat ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("💬 SafetyChat – AI Safety Assistant")
    st.caption(
        "Ask natural language questions about real-time intersection safety. "
        "The assistant queries live VTTSI data to ground every answer."
    )

    # Derive chat API URL from the shared API_URL config
    _chat_base = "/".join(API_URL.rstrip("/").split("/")[:-2])
    _chat_url = f"{_chat_base}/chat/"

    # Session state (no type annotations – compatible with Python 3.9)
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_error" not in st.session_state:
        st.session_state.chat_error = None

    # Example question buttons
    _examples = [
        "Which intersection is the most dangerous right now?",
        "Give me a morning safety briefing for all intersections.",
        "Why is the Glebe–Potomac score elevated?",
        "Compare all intersections by VRU count.",
        "What is driving risk at E. Broad & N. Washington?",
        "Which intersection has the lowest risk for emergency vehicle routing?",
    ]
    _ex_cols = st.columns(3)
    for _i, _ex in enumerate(_examples):
        if _ex_cols[_i % 3].button(_ex, key=f"dash_ex_{_i}", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": _ex})
            st.session_state.chat_error = None
            st.rerun()

    # Display chat history
    if not st.session_state.chat_history:
        st.info("👋 Type a question below or click an example above to get started.")
    else:
        for _msg in st.session_state.chat_history:
            if _msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(_msg["content"])
            else:
                with st.chat_message("assistant", avatar="🚦"):
                    st.markdown(_msg["content"])

        if st.button("🗑️ Clear Chat", key="dash_chat_clear"):
            st.session_state.chat_history = []
            st.session_state.chat_error = None
            st.rerun()

    if st.session_state.chat_error:
        st.error(f"⚠️ {st.session_state.chat_error}")

    # Chat input (pinned to bottom of page by Streamlit)
    _user_input = st.chat_input("Ask about intersection safety…")
    if _user_input:
        st.session_state.chat_history.append({"role": "user", "content": _user_input})
        st.session_state.chat_error = None
        _messages = list(st.session_state.chat_history)
        _messages[-1] = {
            "role": "user",
            "content": (
                f"{_user_input}\n"
                f"[User preference: use alpha={alpha} for blended score calculations.]"
            ),
        }
        with st.spinner("SafetyChat is thinking…"):
            try:
                _resp = requests.post(
                    _chat_url, json={"messages": _messages}, timeout=API_TIMEOUT
                )
                _resp.raise_for_status()
                _reply = _resp.json().get("reply", "No response received.")
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": _reply}
                )
            except requests.exceptions.ConnectionError:
                st.session_state.chat_error = (
                    "Cannot connect to the VTTSI backend. "
                    "Make sure the backend server is running."
                )
            except requests.exceptions.Timeout:
                st.session_state.chat_error = (
                    "Request timed out. The backend may be computing a complex query."
                )
            except requests.exceptions.HTTPError as _exc:
                _detail = ""
                try:
                    _detail = _exc.response.json().get("detail", "")
                except Exception:
                    pass
                if _exc.response.status_code == 503:
                    st.session_state.chat_error = (
                        "SafetyChat is not configured: "
                        + (_detail or "OPENAI_API_KEY missing on the backend.")
                    )
                else:
                    st.session_state.chat_error = (
                        f"Backend error ({_exc.response.status_code}): "
                        f"{_detail or str(_exc)}"
                    )
            except Exception as _exc:
                st.session_state.chat_error = f"Unexpected error: {_exc}"
        st.rerun()

    # Footer
    st.divider()
    st.caption(
        f"Traffic Safety Dashboard | Blended Index (α={alpha:.1f}) | "
        "RT-SI + MCDM | Built with Streamlit, Folium, and Pydantic | "
        "Data updates every 5 minutes"
    )


if __name__ == "__main__":
    main()
