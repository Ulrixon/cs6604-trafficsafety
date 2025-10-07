"""
API client for fetching intersection data with caching and fallback.
"""

import json
import os
from typing import List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import streamlit as st

from app.models.intersection import Intersection
from app.utils.config import (
    API_URL,
    API_TIMEOUT,
    API_MAX_RETRIES,
    API_CACHE_TTL,
    SAMPLE_DATA_PATH,
)


def _get_session_with_retries() -> requests.Session:
    """
    Create a requests session with retry logic.

    Retries on connection errors and 5xx server errors.

    Returns:
        Configured requests.Session
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=API_MAX_RETRIES,
        backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def _load_fallback_data() -> List[dict]:
    """
    Load sample data from local JSON file as fallback.

    Returns:
        List of intersection dictionaries

    Raises:
        FileNotFoundError: If sample data file doesn't exist
    """
    # Try multiple possible paths (handle both running from root and from frontend/)
    possible_paths = [
        SAMPLE_DATA_PATH,
        os.path.join("frontend", SAMPLE_DATA_PATH),
        os.path.join("..", SAMPLE_DATA_PATH),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, list) else data.get("intersections", [])

    # If no file found, return minimal sample
    return [
        {
            "intersection_id": 1,
            "intersection_name": "Sample Intersection (Offline)",
            "safety_index": 50.0,
            "traffic_volume": 1000.0,
            "latitude": 38.86,
            "longitude": -77.055,
        }
    ]


@st.cache_data(ttl=API_CACHE_TTL, show_spinner=False)
def fetch_intersections_from_api() -> tuple[List[dict], Optional[str]]:
    """
    Fetch intersection data from the API with caching.

    This function is cached for API_CACHE_TTL seconds to reduce
    API calls and improve performance.

    Returns:
        Tuple of (list of intersection dicts, error message or None)
    """
    try:
        session = _get_session_with_retries()
        response = session.get(API_URL, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = response.json()

        # Handle different response formats
        if isinstance(data, list):
            intersections = data
        elif isinstance(data, dict) and "intersections" in data:
            intersections = data["intersections"]
        elif isinstance(data, dict) and "data" in data:
            intersections = data["data"]
        else:
            intersections = [data] if isinstance(data, dict) else []

        return intersections, None

    except requests.exceptions.Timeout:
        error_msg = f"API request timed out after {API_TIMEOUT} seconds"
        return _load_fallback_data(), error_msg

    except requests.exceptions.ConnectionError:
        error_msg = "Could not connect to API (connection error)"
        return _load_fallback_data(), error_msg

    except requests.exceptions.HTTPError as e:
        error_msg = f"API returned error: {e.response.status_code}"
        return _load_fallback_data(), error_msg

    except json.JSONDecodeError:
        error_msg = "API returned invalid JSON"
        return _load_fallback_data(), error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        return _load_fallback_data(), error_msg


def get_intersections() -> tuple[List[Intersection], Optional[str], dict]:
    """
    Get validated intersection data.

    Fetches from API (with caching), validates via Pydantic models,
    and provides fallback data on failure.

    Returns:
        Tuple of:
        - List of validated Intersection objects
        - Error message (None if successful)
        - Stats dict with counts of valid/invalid/skipped records
    """
    raw_data, error = fetch_intersections_from_api()

    intersections = []
    stats = {
        "total_raw": len(raw_data),
        "valid": 0,
        "invalid": 0,
        "skipped_reasons": [],
    }

    for item in raw_data:
        try:
            # Validate and parse via Pydantic
            intersection = Intersection(**item)
            intersections.append(intersection)
            stats["valid"] += 1

        except Exception as e:
            stats["invalid"] += 1
            stats["skipped_reasons"].append(
                f"ID {item.get('intersection_id', '?')}: {str(e)}"
            )

    return intersections, error, stats


def clear_cache():
    """Clear the API cache to force fresh data fetch."""
    st.cache_data.clear()
