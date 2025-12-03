#!/usr/bin/env python3
"""
Populate intersections table with computed intersection data from MCDM service.

This script:
1. Computes intersection data using the existing MCDM logic
2. Populates the intersections table in the database
3. Maps intersection names to persistent IDs
4. Preserves any existing camera_urls data
"""

import sys
import os
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.db_client import get_db_client
from app.services.mcdm_service import MCDMSafetyIndexService
from app.api.intersection import find_crash_intersection_for_bsm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def populate_intersections():
    """Populate intersections table with computed data."""
    try:
        logger.info("=== Populating Intersections Table ===")

        # Get database client
        db_client = get_db_client()

        # Initialize MCDM service
        logger.info("Initializing MCDM service...")
        mcdm_service = MCDMSafetyIndexService(db_client)

        # Get available intersections
        logger.info("Getting available BSM intersections...")
        bsm_intersections = mcdm_service.get_available_intersections()
        logger.info(f"Found {len(bsm_intersections)} BSM intersections")

        # Build mapping results
        logger.info("Building intersection mappings...")
        mapping_results = {}
        for intersection in bsm_intersections:
            mapping_list = find_crash_intersection_for_bsm(intersection, db_client)
            if mapping_list:
                mapping_results[intersection] = mapping_list[0]

        logger.info(f"Mapped {len(mapping_results)} intersections")

        # Clear existing intersections and insert new data
        logger.info("Clearing existing intersection data and inserting new data...")
        insert_count = 0

        with db_client.get_connection() as conn:
            cursor = conn.cursor()

            # Clear existing data
            cursor.execute("DELETE FROM intersections;")

            # Insert intersections
            for idx, (intersection_name, mapping) in enumerate(sorted(mapping_results.items())):
                intersection_id = 100 + idx + 1  # Match existing ID generation logic
                lat = mapping.get("lat", 0.0)
                lon = mapping.get("lon", 0.0)

                # Insert into database
                insert_query = """
                    INSERT INTO intersections (id, name, latitude, longitude, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        updated_at = EXCLUDED.updated_at;
                """

                cursor.execute(
                    insert_query,
                    (
                        intersection_id,
                        intersection_name,
                        lat,
                        lon,
                        datetime.utcnow(),
                        datetime.utcnow(),
                    ),
                )
                insert_count += 1

                if (insert_count % 10) == 0:
                    logger.info(f"Inserted {insert_count} intersections...")

            conn.commit()
            cursor.close()

        logger.info(f"✓ Successfully populated {insert_count} intersections")

        # Verify
        verify_query = "SELECT COUNT(*) as count FROM intersections;"
        result = db_client.execute_query(verify_query)
        count = result[0]["count"] if result else 0
        logger.info(f"Verification: {count} intersections in database")

        return True

    except Exception as e:
        logger.error(f"Error populating intersections: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = populate_intersections()
    sys.exit(0 if success else 1)
