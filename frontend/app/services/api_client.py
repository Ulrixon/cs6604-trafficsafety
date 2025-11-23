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


@st.cache_data(ttl=300, show_spinner=False)  # Cache for 5 minutes
def fetch_latest_blended_scores(alpha: float = 0.7) -> tuple[List[dict], Optional[str]]:
    """
    Fetch latest safety scores with RT-SI blending for all intersections.
    
    This queries each intersection's latest available data point with the
    specified alpha blending coefficient.
    
    Args:
        alpha: Blending coefficient (0.0 = MCDM only, 1.0 = RT-SI only)
        
    Returns:
        Tuple of (list of intersection dicts with blended scores, error message or None)
    """
    try:
        # First, get the list of available intersections
        api_base = API_URL.rstrip("/")
        intersections_url = f"{api_base}/intersections/list"
        
        session = _get_session_with_retries()
        response = session.get(intersections_url, timeout=API_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        intersection_names = data.get("intersections", [])
        
        if not intersection_names:
            return _load_fallback_data(), "No intersections available"
        
        # For each intersection, fetch the latest blended score
        from datetime import datetime, timedelta
        
        results = []
        errors = []
        
        # Use current time as the target
        current_time = datetime.now()
        
        for intersection in intersection_names[:10]:  # Limit to first 10 for performance
            try:
                # Query for latest time point (using current time)
                params = {
                    "intersection": intersection,
                    "time": current_time.isoformat(),
                    "bin_minutes": 15,
                    "alpha": alpha,
                }
                
                score_response = session.get(
                    f"{api_base}/time/specific",
                    params=params,
                    timeout=10
                )
                
                if score_response.status_code == 200:
                    score_data = score_response.json()
                    
                    # Transform to expected format for dashboard
                    intersection_data = {
                        "intersection_id": intersection,  # Use name as ID
                        "intersection_name": score_data.get("intersection", intersection).replace("-", " ").title(),
                        "safety_index": score_data.get("final_safety_index", score_data.get("mcdm_index", 50.0)),
                        "mcdm_index": score_data.get("mcdm_index", 50.0),
                        "rt_si_score": score_data.get("rt_si_score"),
                        "final_safety_index": score_data.get("final_safety_index", score_data.get("mcdm_index", 50.0)),
                        "traffic_volume": float(score_data.get("vehicle_count", 0)),
                        "vru_index": score_data.get("vru_index"),
                        "vehicle_index": score_data.get("vehicle_index"),
                        "latitude": 38.86,  # Default - would need PSM lookup for actual coords
                        "longitude": -77.055,
                    }
                    
                    # Try to get coordinates from a separate lookup if available
                    # For now, use default DC area coordinates
                    
                    results.append(intersection_data)
                    
            except Exception as e:
                errors.append(f"{intersection}: {str(e)}")
                continue
        
        if not results:
            error_msg = f"Failed to fetch blended scores. Errors: {'; '.join(errors[:3])}"
            return _load_fallback_data(), error_msg
        
        error_msg = f"Loaded {len(results)} intersections" + (
            f" (errors: {len(errors)})" if errors else ""
        )
        
        return results, None
        
    except Exception as e:
        error_msg = f"Error fetching blended scores: {str(e)}"
        return _load_fallback_data(), error_msg


# ============================================================================
# HISTORICAL DATA API METHODS
# ============================================================================

@st.cache_data(ttl=API_CACHE_TTL, show_spinner=False)
def fetch_intersection_history(
    intersection_id: str,
    days: int = 7,
    aggregation: Optional[str] = None
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
        # Construct URL - replace /safety/index/ with /safety/history/
        base_url = API_URL.replace("/safety/index/", "/safety/history/")
        url = f"{base_url}{intersection_id}"

        # Build query parameters
        params = {"days": days}
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
    intersection_id: str,
    days: int = 7
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
        # Construct URL - replace /safety/index/ with /safety/history/
        base_url = API_URL.replace("/safety/index/", "/safety/history/")
        url = f"{base_url}{intersection_id}/stats"

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
