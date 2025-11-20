"""
VCC historical data collection service.

Collects all available historical data from VCC API for building safety indices.
Handles pagination, rate limiting, and batch processing.
"""

import requests
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from .vcc_client import vcc_client
from ..core.config import settings


def collect_historical_vcc_data(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    intersection_id: Optional[int] = None,
    max_retries: int = 3,
    batch_delay: float = 0.2
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Collect all available historical data from VCC API.
    
    Note: VCC API may not have date-range endpoints, so this polls /api/bsm/current
    and /api/psm/current repeatedly. For true historical data, may need to rely on
    previously collected data or API-specific historical endpoints if available.
    
    Args:
        start_date: Start date for collection (optional - VCC API may not support filtering)
        end_date: End date for collection (optional - VCC API may not support filtering)
        intersection_id: Specific intersection ID (optional)
        max_retries: Maximum retry attempts for failed requests
        batch_delay: Delay between batch requests (seconds)
        
    Returns:
        Tuple of (bsm_messages, psm_messages, mapdata_list)
    """
    print(f"\n{'='*80}")
    print("VCC HISTORICAL DATA COLLECTION")
    print(f"{'='*80}")
    
    # Get MapData first (for intersection mapping)
    print("\n[1/3] Collecting MapData...")
    mapdata_list = []
    try:
        if intersection_id:
            mapdata_list = vcc_client.get_mapdata(intersection_id=intersection_id, decoded=True)
        else:
            mapdata_list = vcc_client.get_mapdata(decoded=True)
        print(f"✓ Retrieved {len(mapdata_list)} MapData messages")
    except Exception as e:
        print(f"⚠ Warning: Failed to get MapData: {e}")
        mapdata_list = []
    
    # Collect BSM messages
    print("\n[2/3] Collecting BSM messages...")
    bsm_messages = []
    
    # VCC API /api/bsm/current returns current messages only
    # For historical data, we may need to poll repeatedly or use specific endpoints
    # This is a limitation of the VCC API - it may not provide historical data directly
    retry_count = 0
    while retry_count < max_retries:
        try:
            batch = vcc_client.get_bsm_current()
            if not batch:
                break  # No more data available
            
            # Filter by date if provided (VCC API uses milliseconds)
            if start_date or end_date:
                filtered_batch = []
                for msg in batch:
                    timestamp_ms = msg.get('timestamp', 0)
                    if timestamp_ms == 0:
                        timestamp_ms = msg.get('publishTimestamp', 0)
                    
                    if timestamp_ms == 0:
                        continue  # Skip messages without timestamp
                    
                    msg_time = datetime.fromtimestamp(timestamp_ms / 1000)  # VCC uses milliseconds
                    
                    if start_date and msg_time < start_date:
                        continue
                    if end_date and msg_time > end_date:
                        continue
                    
                    filtered_batch.append(msg)
                batch = filtered_batch
            
            bsm_messages.extend(batch)
            print(f"  Batch {retry_count + 1}: Collected {len(batch)} BSM messages (Total: {len(bsm_messages)})")
            
            # Delay before next request
            time.sleep(batch_delay)
            
            # If no more data or date range exceeded, break
            if len(batch) == 0:
                break
            
            retry_count += 1
            
        except Exception as e:
            print(f"⚠ Error collecting BSM batch {retry_count + 1}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(batch_delay * 2)  # Longer delay on error
            else:
                break
    
    print(f"✓ Collected {len(bsm_messages)} total BSM messages")
    
    # Collect PSM messages
    print("\n[3/3] Collecting PSM messages...")
    psm_messages = []
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            batch = vcc_client.get_psm_current()
            if not batch:
                break
            
            # Filter by date if provided
            if start_date or end_date:
                filtered_batch = []
                for msg in batch:
                    timestamp_ms = msg.get('timestamp', 0)
                    if timestamp_ms == 0:
                        timestamp_ms = msg.get('publishTimestamp', 0)
                    
                    if timestamp_ms == 0:
                        continue
                    
                    msg_time = datetime.fromtimestamp(timestamp_ms / 1000)  # VCC uses milliseconds
                    
                    if start_date and msg_time < start_date:
                        continue
                    if end_date and msg_time > end_date:
                        continue
                    
                    filtered_batch.append(msg)
                batch = filtered_batch
            
            psm_messages.extend(batch)
            print(f"  Batch {retry_count + 1}: Collected {len(batch)} PSM messages (Total: {len(psm_messages)})")
            
            time.sleep(batch_delay)
            
            if len(batch) == 0:
                break
            
            retry_count += 1
            
        except Exception as e:
            print(f"⚠ Error collecting PSM batch {retry_count + 1}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(batch_delay * 2)
            else:
                break
    
    print(f"✓ Collected {len(psm_messages)} total PSM messages")
    
    print(f"\n{'='*80}")
    print("COLLECTION SUMMARY")
    print(f"{'='*80}")
    print(f"MapData: {len(mapdata_list)} messages")
    print(f"BSM: {len(bsm_messages)} messages")
    print(f"PSM: {len(psm_messages)} messages")
    print(f"{'='*80}\n")
    
    return bsm_messages, psm_messages, mapdata_list


def collect_all_vcc_data() -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Collect all available VCC API data (no date filtering).
    
    This is a convenience wrapper for collecting all current data from VCC API.
    For true historical collection, may need to run this periodically or use
    API-specific historical endpoints if available.
    
    Returns:
        Tuple of (bsm_messages, psm_messages, mapdata_list)
    """
    return collect_historical_vcc_data(
        start_date=None,
        end_date=None,
        intersection_id=None
    )


def collect_vcc_data_by_date_range(
    start_date: datetime,
    end_date: datetime,
    intersection_id: Optional[int] = None
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Collect VCC API data for a specific date range.
    
    Note: This filters messages by timestamp after collection, as VCC API
    /api/bsm/current and /api/psm/current may not support date filtering.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        intersection_id: Optional intersection ID filter
        
    Returns:
        Tuple of (bsm_messages, psm_messages, mapdata_list)
    """
    return collect_historical_vcc_data(
        start_date=start_date,
        end_date=end_date,
        intersection_id=intersection_id
    )

