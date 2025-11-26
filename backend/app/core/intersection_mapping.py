"""
Intersection Name Mapping Utility

Handles name transformation between different data sources:
- hiresdata table: Uses full names like 'birch_st-w_broad_st'
- safety-event table: Uses short names like 'birch-broad'
- vehicle-count, vru-count, speed-distribution: Use full names
- PSM table: Uses original BSM names (no transformation needed)

This module provides bidirectional mapping functionality.
"""

import re
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def normalize_intersection_name(full_name: str) -> str:
    """
    Normalize full intersection name to short format for safety-event table queries.

    Examples:
        'birch_st-w_broad_st' -> 'birch-broad'
        'n_maple_ave-w_broad_st' -> 'broad-maple'
        'e_broad_st-n_washington_st' -> 'broad-washington'
        'hillwood-s_washington_st' -> 'hillwood-washington'
        's_virginia_ave-w_broad_st' -> 'broad-virginia'

    Algorithm:
    1. Split by '-' to get two road names
    2. For each road name:
       - Remove directional prefixes (n_, s_, e_, w_)
       - Remove type suffixes (_st, _ave, _rd, _ct, _place, etc.)
    3. Sort alphabetically for consistency
    4. Join with '-'

    Args:
        full_name: Full intersection name from hiresdata/vehicle-count tables

    Returns:
        Normalized short name for safety-event table
    """
    if not full_name or full_name in ["(All)", "(Custom...)"]:
        return full_name

    # Split into two road names
    parts = full_name.split("-")
    if len(parts) != 2:
        # Handle edge case: return as-is if format is unexpected
        logger.warning(f"Unexpected intersection name format: {full_name}")
        return full_name.lower()

    cleaned_parts = []
    for part in parts:
        # Lowercase
        p = part.lower().strip()

        # Remove directional prefixes (n_, s_, e_, w_)
        p = re.sub(r"^[nsew]_", "", p)

        # Remove type suffixes
        p = re.sub(
            r"_(st|ave|avenue|rd|road|ct|court|place|pl|dr|drive|blvd|boulevard|ln|lane|cir|circle|way)$",
            "",
            p,
        )

        # Remove remaining underscores
        p = p.replace("_", "")

        if p:  # Only add non-empty parts
            cleaned_parts.append(p)

    if not cleaned_parts:
        return full_name.lower()

    # Sort alphabetically for consistency
    cleaned_parts.sort()

    result = "-".join(cleaned_parts)
    logger.debug(f"Mapped '{full_name}' -> '{result}'")
    return result


def create_intersection_mapping(db_client) -> Dict[str, str]:
    """
    Create a mapping dictionary from full intersection names to short names.

    This queries the database to get all unique intersection names from hiresdata
    and creates a mapping to their normalized short names.

    Args:
        db_client: Database client instance

    Returns:
        Dictionary mapping full_name -> short_name
    """
    try:
        # Get all unique intersections from hiresdata
        query = "SELECT DISTINCT intersection FROM hiresdata WHERE intersection IS NOT NULL ORDER BY intersection"
        results = db_client.execute_query(query)

        mapping = {}
        for row in results:
            full_name = row["intersection"]
            short_name = normalize_intersection_name(full_name)
            mapping[full_name] = short_name

        logger.info(f"Created intersection mapping with {len(mapping)} entries")
        return mapping
    except Exception as e:
        logger.error(f"Error creating intersection mapping: {e}")
        return {}


def reverse_lookup_intersection(short_name: str, db_client) -> Optional[str]:
    """
    Given a short intersection name (e.g., 'birch-broad'), find the corresponding
    full name from hiresdata table (e.g., 'birch_st-w_broad_st').

    This is useful when you have a short name and need to query hiresdata.

    Args:
        short_name: Short intersection name (from safety-event or user input)
        db_client: Database client instance

    Returns:
        Full intersection name from hiresdata, or None if not found
    """
    try:
        # Get all intersections and check which one maps to this short name
        query = (
            "SELECT DISTINCT intersection FROM hiresdata WHERE intersection IS NOT NULL"
        )
        results = db_client.execute_query(query)

        normalized_short = short_name.lower().strip()

        for row in results:
            full_name = row["intersection"]
            if normalize_intersection_name(full_name) == normalized_short:
                logger.debug(f"Reverse lookup: '{short_name}' -> '{full_name}'")
                return full_name

        logger.warning(f"No match found for short name '{short_name}'")
        return None
    except Exception as e:
        logger.error(f"Error in reverse lookup for '{short_name}': {e}")
        return None


def validate_intersection_in_tables(
    intersection_name: str, short_name: str, db_client
) -> Dict[str, bool]:
    """
    Check if an intersection exists in various data tables.

    Args:
        intersection_name: Full intersection name for most tables
        short_name: Short name for safety-event table
        db_client: Database client instance

    Returns:
        Dictionary with table names as keys and boolean existence as values
    """
    results = {}
    # For other tables, keep original logic
    tables_with_full_name = [
        "vehicle-count",
        "vru-count",
        "speed-distribution",
        "safety-event",
    ]
    for table in tables_with_full_name:
        try:
            query = f'SELECT 1 FROM "{table}" WHERE intersection = %(name)s LIMIT 1'
            result = db_client.execute_query(query, {"name": short_name})
            results[table] = len(result) > 0
        except Exception as e:
            logger.error(f"Error checking {table} for '{short_name}': {e}")
            results[table] = False
    return results
