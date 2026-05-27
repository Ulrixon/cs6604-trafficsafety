"""
Utility functions for scaling and color mapping.
"""

from typing import Tuple
from app.utils.config import (
    MIN_RADIUS_PX,
    MAX_RADIUS_PX,
    RADIUS_SCALE_FACTOR,
    COLOR_LOW_RISK,
    COLOR_MEDIUM_RISK,
    COLOR_HIGH_RISK,
    COLOR_LOW_THRESHOLD,
    COLOR_HIGH_THRESHOLD,
)


def scale_radius(volume: float, min_volume: float, max_volume: float) -> float:
    """
    Scale traffic volume to marker radius in pixels.

    Uses linear scaling from [min_volume, max_volume] to [6, 30] pixels.
    Handles edge case where all volumes are the same.

    Args:
        volume: Traffic volume for this intersection
        min_volume: Minimum volume in dataset
        max_volume: Maximum volume in dataset

    Returns:
        Radius in pixels, clamped to [6, 30]
    """
    # Handle zero variance (all volumes the same)
    if max_volume == min_volume or (max_volume - min_volume) < 1e-9:
        return (MIN_RADIUS_PX + MAX_RADIUS_PX) / 2  # Return middle value

    # Linear scaling
    normalized = (volume - min_volume) / (max_volume - min_volume)
    radius = MIN_RADIUS_PX + RADIUS_SCALE_FACTOR * normalized

    # Clamp to valid range
    return max(MIN_RADIUS_PX, min(MAX_RADIUS_PX, radius))


def get_color_for_safety_index(safety_index: float) -> str:
    """
    Map safety index to color using threshold-based approach.

    Color scheme (higher safety index = more dangerous = redder):
    - safety_index < 60: Green (#2ECC71) - Low risk
    - 60 ≤ safety_index ≤ 75: Orange (#F39C12) - Medium risk
    - safety_index > 75: Red (#E74C3C) - High risk

    Args:
        safety_index: Safety index value (0-100)

    Returns:
        Hex color code
    """
    if safety_index < COLOR_LOW_THRESHOLD:
        return COLOR_LOW_RISK
    elif safety_index <= COLOR_HIGH_THRESHOLD:
        return COLOR_MEDIUM_RISK
    else:
        return COLOR_HIGH_RISK


def interpolate_color(
    value: float, min_val: float = 0.0, max_val: float = 100.0
) -> str:
    """
    Interpolate color along a gradient from green → yellow → red.

    This is an alternative to threshold-based coloring, providing
    a smooth gradient. Currently not used but available for future use.

    Args:
        value: Value to map to color
        min_val: Minimum value (maps to green)
        max_val: Maximum value (maps to red)

    Returns:
        Hex color code
    """
    # Normalize to [0, 1]
    if max_val == min_val:
        normalized = 0.5
    else:
        normalized = (value - min_val) / (max_val - min_val)
    normalized = max(0.0, min(1.0, normalized))

    # Green → Yellow → Red gradient
    if normalized < 0.5:
        # Green to Yellow
        r = int(46 + (255 - 46) * (normalized * 2))
        g = int(204 + (255 - 204) * (normalized * 2))
        b = int(113 - 113 * (normalized * 2))
    else:
        # Yellow to Red
        r = 255
        g = int(255 - 255 * ((normalized - 0.5) * 2))
        b = int(0)

    return f"#{r:02x}{g:02x}{b:02x}"


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value to a range.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def get_legend_html() -> str:
    """
    Generate HTML for the map legend.

    Returns:
        HTML string for legend
    """
    return """
    <div style="
        position: fixed;
        bottom: 50px;
        right: 50px;
        background-color: white;
        padding: 15px;
        border: 2px solid grey;
        border-radius: 5px;
        font-family: Arial, sans-serif;
        font-size: 12px;
        z-index: 9999;
    ">
        <h4 style="margin-top: 0; margin-bottom: 10px;">Legend</h4>
        <div style="margin-bottom: 8px;">
            <strong>Size:</strong> Traffic Volume<br/>
            <span style="font-size: 10px;">Larger = Higher Volume</span>
        </div>
        <div>
            <strong>Color:</strong> Safety Index<br/>
            <span style="color: #2ECC71;">● Low Risk (&lt;60)</span><br/>
            <span style="color: #F39C12;">● Medium Risk (60-75)</span><br/>
            <span style="color: #E74C3C;">● High Risk (&gt;75)</span>
        </div>
    </div>
    """


def format_number(value: float, decimals: int = 2) -> str:
    """
    Format a number for display.

    Args:
        value: Number to format
        decimals: Number of decimal places

    Returns:
        Formatted string
    """
    if value >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.{decimals}f}K"
    else:
        return f"{value:.{decimals}f}"
