"""
Configuration constants for the Traffic Safety Index application.
Loads from .env file if available, otherwise uses defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from frontend directory
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# API Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "60"))  # seconds (increased for RT-SI calculation)
API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
API_CACHE_TTL = int(os.getenv("API_CACHE_TTL", "300"))  # seconds (5 minutes)

# Map Configuration
DEFAULT_LATITUDE = float(os.getenv("DEFAULT_LATITUDE", "38.86"))
DEFAULT_LONGITUDE = float(os.getenv("DEFAULT_LONGITUDE", "-77.055"))
DEFAULT_CENTER = (
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
)  # Default to D.C. area, will be computed from data
DEFAULT_ZOOM = int(os.getenv("DEFAULT_ZOOM", "13"))
MAP_HEIGHT = int(os.getenv("MAP_HEIGHT", "650"))
MAP_TILES = "CartoDB positron"  # Clean, minimal base map

# Visual Encoding - Radius
MIN_RADIUS_PX = int(os.getenv("MIN_RADIUS_PX", "6"))
MAX_RADIUS_PX = int(os.getenv("MAX_RADIUS_PX", "30"))
RADIUS_SCALE_FACTOR = MAX_RADIUS_PX - MIN_RADIUS_PX

# Visual Encoding - Color Thresholds
COLOR_LOW_THRESHOLD = int(
    os.getenv("COLOR_LOW_THRESHOLD", "60")
)  # Below this: green (low risk)
COLOR_HIGH_THRESHOLD = int(
    os.getenv("COLOR_HIGH_THRESHOLD", "75")
)  # Above this: red (high risk)

# Colors (Hex codes)
COLOR_LOW_RISK = "#2ECC71"  # Green
COLOR_MEDIUM_RISK = "#F39C12"  # Orange
COLOR_HIGH_RISK = "#E74C3C"  # Red

# Risk level definitions
RISK_LEVELS = {
    "Low": {"threshold": (0, COLOR_LOW_THRESHOLD), "color": COLOR_LOW_RISK},
    "Medium": {
        "threshold": (COLOR_LOW_THRESHOLD, COLOR_HIGH_THRESHOLD),
        "color": COLOR_MEDIUM_RISK,
    },
    "High": {"threshold": (COLOR_HIGH_THRESHOLD, 100), "color": COLOR_HIGH_RISK},
}

# UI Configuration
APP_TITLE = "Traffic Safety Index Dashboard"
APP_ICON = "🚦"
LAYOUT = "wide"

# Data paths
SAMPLE_DATA_PATH = "app/data/sample.json"

# Filter defaults
DEFAULT_SAFETY_RANGE = (0.0, 100.0)
DEFAULT_VOLUME_MIN = 0

# Styling
MARKER_OPACITY = 0.85
MARKER_WEIGHT = 1  # Border width
MARKER_FILL = True
