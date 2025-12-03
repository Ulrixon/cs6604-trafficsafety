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
        # Append the correct endpoint path
        url = f"{API_URL}/safety/index/"
        response = session.get(url, timeout=API_TIMEOUT)
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


@st.cache_data(ttl=300, show_spinner=False)  # Cache for 5 minutes
def fetch_latest_blended_scores(alpha: float = 0.7) -> tuple[List[dict], Optional[str]]:
    """
    Fetch latest safety scores with RT-SI blending for all intersections.

    Strategy:
    1. Call /safety/index/?alpha=X to get blended data from backend
    2. API returns safety_index (blended), rt_si_index, and mcdm_index
    3. Frontend can recalculate blend with different alpha if needed

    Args:
        alpha: Blending coefficient (0.0 = MCDM only, 1.0 = RT-SI only)

    Returns:
        Tuple of (list of intersection dicts with blended scores, error message or None)
    """
    try:
        api_base = API_URL.rstrip("/")
        session = _get_session_with_retries()

        # Call the endpoint with alpha parameter
        params = {
            "alpha": alpha,
            "include_mcdm": "true",
            "bin_minutes": 15
        }

        # Use configured timeout for this heavy calculation endpoint
        response = session.get(
            f"{api_base}/safety/index/", params=params, timeout=API_TIMEOUT
        )
        response.raise_for_status()

        intersections = response.json()

        if not intersections:
            return _load_fallback_data(), "No intersections available"

        # Transform to expected format
        results = []
        for item in intersections:
            # New API structure:
            # - safety_index: Blended score (already calculated by backend)
            # - rt_si_index: Raw RT-SI score
            # - mcdm_index: Raw MCDM score
            
            safety_index = item.get("safety_index", 0.0)
            rt_si = item.get("rt_si_index", 0.0)
            mcdm = item.get("mcdm_index", 0.0)
            
            # Handle None values - convert to 0
            if safety_index is None:
                safety_index = 0.0
            if rt_si is None:
                rt_si = 0.0
            if mcdm is None:
                mcdm = 0.0

            # Frontend can recalculate blend if alpha changes dynamically
            # For now, use the backend-calculated blend
            final_index = safety_index

            intersection_data = {
                "intersection_id": item.get("intersection_id"),
                "intersection_name": item.get("intersection_name"),
                "safety_index": final_index,  # Blended score from backend
                "mcdm_index": mcdm,  # Raw MCDM
                "rt_si_score": rt_si,  # Raw RT-SI (from rt_si_index)
                "rt_si_index": rt_si,  # Also store as rt_si_index
                "final_safety_index": final_index,
                "traffic_volume": float(item.get("traffic_volume", 0)),
                "vru_index": item.get("vru_index"),  # Not in new API
                "vehicle_index": item.get("vehicle_index"),  # Not in new API
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "index_type": item.get("index_type", "MCDM"),
            }
            results.append(intersection_data)

        return results, None

    except Exception as e:
        error_msg = f"Error fetching blended scores: {str(e)}"
        return _load_fallback_data(), error_msg


# ============================================================================
# HISTORICAL DATA API METHODS
# ============================================================================


@st.cache_data(ttl=API_CACHE_TTL, show_spinner=False)
def fetch_intersection_history(
    intersection_id: str, days: int = 7, aggregation: Optional[str] = None
) -> tuple[Optional[dict], Optional[str]]:
    """
    Fetch historical time series data for an intersection.

    Args:
        intersection_id: Unique intersection identifier
        days: Number of days of history to retrieve (default: 7)
        aggregation: Time aggregation level (1min, 1hour, 1day, 1week, 1month)
                    If None, smart default based on date range is used

    Returns:
        Tuple of (history data dict, error message or None)

        History data structure:
        {
            "intersection_id": str,
            "intersection_name": str,
            "data_points": [
                {
                    "timestamp": str (ISO format),
                    "safety_index": float,
                    "vru_index": float or null,
                    "vehicle_index": float or null,
                    "traffic_volume": int,
                    "hour_of_day": int,
                    "day_of_week": int
                },
                ...
            ],
            "start_date": str (ISO format),
            "end_date": str (ISO format),
            "total_points": int,
            "aggregation": str
        }
    """
    try:
        # Construct URL for history endpoint
        url = f"{API_URL}/safety/history/{intersection_id}"

        # Build query parameters
        params: dict = {"days": days}
        if aggregation:
            params["aggregation"] = aggregation

        session = _get_session_with_retries()
        response = session.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        return data, None

    except requests.exceptions.Timeout:
        error_msg = f"History API request timed out after {API_TIMEOUT} seconds"
        return None, error_msg

    except requests.exceptions.ConnectionError:
        error_msg = "Could not connect to history API (connection error)"
        return None, error_msg

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            error_msg = "No historical data found for this intersection"
        else:
            error_msg = f"History API returned error: {e.response.status_code}"
        return None, error_msg

    except json.JSONDecodeError:
        error_msg = "History API returned invalid JSON"
        return None, error_msg

    except Exception as e:
        error_msg = f"Unexpected error fetching history: {str(e)}"
        return None, error_msg


@st.cache_data(ttl=API_CACHE_TTL, show_spinner=False)
def fetch_intersection_stats(
    intersection_id: str, days: int = 7
) -> tuple[Optional[dict], Optional[str]]:
    """
    Fetch aggregated statistics for an intersection over a time period.

    Args:
        intersection_id: Unique intersection identifier
        days: Number of days to aggregate statistics over (default: 7)

    Returns:
        Tuple of (statistics dict, error message or None)

        Statistics structure:
        {
            "intersection_id": str,
            "intersection_name": str,
            "period_start": str (ISO format),
            "period_end": str (ISO format),
            "avg_safety_index": float,
            "min_safety_index": float,
            "max_safety_index": float,
            "std_safety_index": float,
            "total_traffic_volume": int,
            "avg_traffic_volume": float,
            "high_risk_intervals": int,
            "high_risk_percentage": float
        }
    """
    try:
        # Construct URL for history stats endpoint
        url = f"{API_URL}/safety/history/{intersection_id}/stats"

        # Build query parameters
        params = {"days": days}

        session = _get_session_with_retries()
        response = session.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        return data, None

    except requests.exceptions.Timeout:
        error_msg = f"Statistics API request timed out after {API_TIMEOUT} seconds"
        return None, error_msg

    except requests.exceptions.ConnectionError:
        error_msg = "Could not connect to statistics API (connection error)"
        return None, error_msg

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            error_msg = "No statistical data found for this intersection"
        else:
            error_msg = f"Statistics API returned error: {e.response.status_code}"
        return None, error_msg

    except json.JSONDecodeError:
        error_msg = "Statistics API returned invalid JSON"
        return None, error_msg

    except Exception as e:
        error_msg = f"Unexpected error fetching statistics: {str(e)}"
        return None, error_msg


def clear_history_cache():
    """
    Clear only the history-related API caches to force fresh data fetch.

    This is useful when users want to manually refresh historical data
    without clearing the entire application cache.
    """
    # Clear specific cached functions
    fetch_intersection_history.clear()
    fetch_intersection_stats.clear()
