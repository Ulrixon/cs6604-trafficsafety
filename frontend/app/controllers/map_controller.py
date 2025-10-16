"""
Map controller for building Folium maps with intersection markers.
"""

from typing import Tuple, Optional
import pandas as pd
import folium
from folium import IFrame

from app.utils.scaling import scale_radius, get_color_for_safety_index, format_number
from app.utils.config import (
    MAP_TILES,
    DEFAULT_ZOOM,
    MARKER_OPACITY,
    MARKER_WEIGHT,
    MARKER_FILL,
)


def compute_map_center(df: pd.DataFrame) -> Tuple[float, float]:
    """
    Compute the center point of the map based on data.

    Args:
        df: DataFrame with 'latitude' and 'longitude' columns

    Returns:
        Tuple of (latitude, longitude) for map center
    """
    if df.empty:
        return (38.86, -77.055)  # Default fallback

    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()

    return (center_lat, center_lon)


def compute_bounds(df: pd.DataFrame) -> Optional[list]:
    """
    Compute bounding box for the map to fit all markers.

    Args:
        df: DataFrame with 'latitude' and 'longitude' columns

    Returns:
        List of [[min_lat, min_lon], [max_lat, max_lon]] or None
    """
    if df.empty:
        return None

    return [
        [df["latitude"].min(), df["longitude"].min()],
        [df["latitude"].max(), df["longitude"].max()],
    ]


def create_popup_html(row: pd.Series) -> str:
    """
    Create HTML content for marker popup.

    Args:
        row: DataFrame row with intersection data

    Returns:
        HTML string for popup
    """
    # Determine risk level
    si = row["safety_index"]
    if si < 60:
        risk_level = "Low"
        risk_color = "#2ECC71"
    elif si <= 75:
        risk_level = "Medium"
        risk_color = "#F39C12"
    else:
        risk_level = "High"
        risk_color = "#E74C3C"

    html = f"""
    <div style="font-family: Arial, sans-serif; width: 250px;">
        <h4 style="margin-top: 0; margin-bottom: 10px; color: #333;">
            {row['intersection_name']}
        </h4>
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Safety Index:</td>
                <td style="padding: 5px; text-align: right;">
                    <span style="color: {risk_color}; font-weight: bold;">
                        {row['safety_index']:.1f}
                    </span>
                </td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Risk Level:</td>
                <td style="padding: 5px; text-align: right;">
                    <span style="
                        background-color: {risk_color};
                        color: white;
                        padding: 2px 8px;
                        border-radius: 3px;
                        font-size: 11px;
                        font-weight: bold;
                    ">
                        {risk_level}
                    </span>
                </td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Traffic Volume:</td>
                <td style="padding: 5px; text-align: right;">
                    {format_number(row['traffic_volume'], 0)}
                </td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px; font-weight: bold;">Location:</td>
                <td style="padding: 5px; text-align: right; font-size: 11px;">
                    {row['latitude']:.4f}, {row['longitude']:.4f}
                </td>
            </tr>
            <tr>
                <td style="padding: 5px; font-weight: bold;">ID:</td>
                <td style="padding: 5px; text-align: right;">
                    {row['intersection_id']}
                </td>
            </tr>
        </table>
    </div>
    """
    return html


def build_map(
    df: pd.DataFrame,
    center: Optional[Tuple[float, float]] = None,
    zoom: int = DEFAULT_ZOOM,
    fit_bounds: bool = True,
) -> folium.Map:
    """
    Build a Folium map with intersection markers.

    Markers are sized by traffic volume and colored by safety index.

    Args:
        df: DataFrame with intersection data including:
            - latitude, longitude
            - safety_index, traffic_volume
            - intersection_name, intersection_id
        center: Optional map center (lat, lon). If None, computed from data.
        zoom: Initial zoom level
        fit_bounds: Whether to fit map to show all markers

    Returns:
        folium.Map object ready to render
    """
    # Compute center if not provided
    if center is None:
        center = compute_map_center(df)

    # Create base map
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=MAP_TILES,
        control_scale=True,
    )

    # If no data, return empty map
    if df.empty:
        return m

    # Compute min/max for scaling
    min_volume = df["traffic_volume"].min()
    max_volume = df["traffic_volume"].max()

    # Add markers
    for idx, row in df.iterrows():
        # Skip if missing coordinates
        if pd.isna(row["latitude"]) or pd.isna(row["longitude"]):
            continue

        # Compute visual encoding
        radius = scale_radius(row["traffic_volume"], min_volume, max_volume)
        color = get_color_for_safety_index(row["safety_index"])

        # Create popup
        popup_html = create_popup_html(row)
        popup = folium.Popup(IFrame(popup_html, width=270, height=200))

        # Create tooltip (hover text)
        tooltip = f"{row['intersection_name']}"

        # Add circle marker
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=radius,
            color=color,
            fill=MARKER_FILL,
            fill_color=color,
            fill_opacity=MARKER_OPACITY,
            weight=MARKER_WEIGHT,
            popup=popup,
            tooltip=tooltip,
        ).add_to(m)

    # Fit bounds to show all markers
    if fit_bounds and not df.empty:
        bounds = compute_bounds(df)
        if bounds:
            m.fit_bounds(bounds, padding=(30, 30))

    return m


def add_legend_to_map(m: folium.Map) -> folium.Map:
    """
    Add a legend to the map.

    Args:
        m: Folium map object

    Returns:
        Map with legend added
    """
    legend_html = """
    <div style="
        position: fixed;
        bottom: 50px;
        right: 50px;
        width: 180px;
        background-color: white;
        padding: 12px;
        border: 2px solid grey;
        border-radius: 5px;
        font-family: Arial, sans-serif;
        font-size: 11px;
        z-index: 9999;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    ">
        <h4 style="margin: 0 0 8px 0; font-size: 13px;">Legend</h4>
        <div style="margin-bottom: 6px;">
            <strong>Size:</strong> Traffic Volume<br/>
            <span style="font-size: 9px; color: #666;">Larger = Higher Volume</span>
        </div>
        <div>
            <strong>Color:</strong> Safety Index<br/>
            <div style="margin-top: 3px;">
                <span style="color: #2ECC71; font-size: 16px;">●</span>
                <span style="font-size: 10px;"> Low (&lt;60)</span><br/>
                <span style="color: #F39C12; font-size: 16px;">●</span>
                <span style="font-size: 10px;"> Medium (60-75)</span><br/>
                <span style="color: #E74C3C; font-size: 16px;">●</span>
                <span style="font-size: 10px;"> High (&gt;75)</span>
            </div>
        </div>
    </div>
    """

    m.get_root().html.add_child(folium.Element(legend_html))
    return m
