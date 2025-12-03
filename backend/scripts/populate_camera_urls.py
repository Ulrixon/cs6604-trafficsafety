#!/usr/bin/env python3
"""
Admin script to populate camera URLs for intersections.

This script provides utilities to:
- Automatically find cameras near intersections using VDOT API
- Manually add camera URLs to specific intersections
- Bulk update multiple intersections
- View current camera configurations

Usage:
    # Auto-populate all intersections
    python populate_camera_urls.py --auto-all

    # Auto-populate ONLY new intersections (without cameras)
    python populate_camera_urls.py --auto-new-only

    # Auto-populate specific intersection
    python populate_camera_urls.py --auto --intersection-id 0

    # Manually add camera
    python populate_camera_urls.py --add --intersection-id 0 \
        --source VDOT --url "https://..." --label "Camera Name"

    # List all intersections with cameras
    python populate_camera_urls.py --list

    # Clear cameras for intersection
    python populate_camera_urls.py --clear --intersection-id 0
"""

import os
import sys
import argparse
import json
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.vdot_camera_service import VDOTCameraService
from app.db.connection import get_db_session, init_db
from sqlalchemy import text


class CameraURLPopulator:
    """Admin utility for populating camera URLs in the database"""

    def __init__(self):
        """Initialize with database connection and VDOT service"""
        self.db = None
        self.camera_service = VDOTCameraService()

        # Initialize database if not already initialized
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        try:
            init_db(database_url)
        except Exception:
            # Database may already be initialized, which is fine
            pass

    def get_db_connection(self):
        """Get database connection"""
        if self.db is None:
            self.db = get_db_session()
        return self.db

    def list_intersections(self) -> List[Dict]:
        """
        List all intersections in the database

        Returns:
            List of intersection dictionaries
        """
        db = self.get_db_connection()

        query = text("""
            SELECT
                id,
                name,
                latitude,
                longitude,
                camera_urls,
                CASE
                    WHEN camera_urls IS NOT NULL THEN jsonb_array_length(camera_urls)
                    ELSE 0
                END as camera_count
            FROM intersections
            ORDER BY id
        """)

        result = db.execute(query)
        intersections = []

        for row in result:
            intersections.append({
                'id': row.id,
                'name': row.name,
                'latitude': row.latitude,
                'longitude': row.longitude,
                'camera_urls': row.camera_urls,
                'camera_count': row.camera_count
            })

        return intersections

    def get_intersection(self, intersection_id: int) -> Optional[Dict]:
        """
        Get a single intersection by ID

        Args:
            intersection_id: Intersection ID

        Returns:
            Intersection dictionary or None
        """
        db = self.get_db_connection()

        query = text("""
            SELECT id, name, latitude, longitude, camera_urls
            FROM intersections
            WHERE id = :id
        """)

        result = db.execute(query, {'id': intersection_id}).fetchone()

        if result:
            return {
                'id': result.id,
                'name': result.name,
                'latitude': result.latitude,
                'longitude': result.longitude,
                'camera_urls': result.camera_urls
            }
        return None

    def auto_populate_intersection(
        self,
        intersection_id: int,
        radius_miles: float = 0.5,
        max_cameras: int = 3
    ) -> bool:
        """
        Automatically populate camera URLs for an intersection using VDOT API

        Args:
            intersection_id: Intersection ID
            radius_miles: Search radius in miles (default 0.5)
            max_cameras: Maximum cameras to add (default 3)

        Returns:
            True if successful, False otherwise
        """
        # Get intersection details
        intersection = self.get_intersection(intersection_id)
        if not intersection:
            print(f"[ERROR] Intersection {intersection_id} not found")
            return False

        print(f"* Processing: {intersection['name']} (ID: {intersection_id})")
        print(f"   Location: ({intersection['latitude']:.4f}, {intersection['longitude']:.4f})")

        # Find nearby cameras
        cameras = self.camera_service.get_cameras_with_fallback(
            intersection['latitude'],
            intersection['longitude'],
            radius_miles=radius_miles,
            max_results=max_cameras
        )

        if not cameras or len(cameras) == 0:
            print(f"⚠️  No cameras found within {radius_miles} miles")
            return False

        # Update database
        return self.update_camera_urls(intersection_id, cameras)

    def update_camera_urls(self, intersection_id: int, camera_urls: List[Dict]) -> bool:
        """
        Update camera URLs for an intersection

        Args:
            intersection_id: Intersection ID
            camera_urls: List of camera URL dictionaries

        Returns:
            True if successful, False otherwise
        """
        db = self.get_db_connection()

        try:
            # Convert to JSON
            camera_json = json.dumps(camera_urls)

            query = text("""
                UPDATE intersections
                SET camera_urls = CAST(:camera_urls AS jsonb),
                    updated_at = NOW()
                WHERE id = :id
            """)

            db.execute(query, {'id': intersection_id, 'camera_urls': camera_json})
            db.commit()

            print(f"[SUCCESS] Updated intersection {intersection_id} with {len(camera_urls)} camera(s)")
            for cam in camera_urls:
                print(f"   - {cam['source']}: {cam['label']}")

            return True

        except Exception as e:
            db.rollback()
            print(f"[ERROR] Error updating intersection {intersection_id}: {e}")
            return False

    def add_camera_url(
        self,
        intersection_id: int,
        source: str,
        url: str,
        label: str
    ) -> bool:
        """
        Add a camera URL to an intersection (appends to existing)

        Args:
            intersection_id: Intersection ID
            source: Camera source (e.g., "VDOT", "511")
            url: Camera URL
            label: Camera label

        Returns:
            True if successful, False otherwise
        """
        # Get existing cameras
        intersection = self.get_intersection(intersection_id)
        if not intersection:
            print(f"[ERROR] Intersection {intersection_id} not found")
            return False

        # Get current camera URLs
        current_cameras = intersection.get('camera_urls', [])
        if current_cameras is None:
            current_cameras = []
        elif isinstance(current_cameras, str):
            current_cameras = json.loads(current_cameras)

        # Add new camera
        new_camera = {
            'source': source,
            'url': url,
            'label': label
        }
        current_cameras.append(new_camera)

        # Update
        return self.update_camera_urls(intersection_id, current_cameras)

    def clear_camera_urls(self, intersection_id: int) -> bool:
        """
        Clear all camera URLs for an intersection

        Args:
            intersection_id: Intersection ID

        Returns:
            True if successful, False otherwise
        """
        db = self.get_db_connection()

        try:
            query = text("""
                UPDATE intersections
                SET camera_urls = NULL,
                    updated_at = NOW()
                WHERE id = :id
            """)

            db.execute(query, {'id': intersection_id})
            db.commit()

            print(f"[SUCCESS] Cleared camera URLs for intersection {intersection_id}")
            return True

        except Exception as e:
            db.rollback()
            print(f"[ERROR] Error clearing cameras for intersection {intersection_id}: {e}")
            return False

    def auto_populate_all(self, radius_miles: float = 0.5, max_cameras: int = 3):
        """
        Auto-populate camera URLs for all intersections

        Args:
            radius_miles: Search radius in miles
            max_cameras: Maximum cameras per intersection
        """
        intersections = self.list_intersections()

        print(f"🔄 Auto-populating cameras for {len(intersections)} intersections")
        print(f"   Radius: {radius_miles} miles")
        print(f"   Max cameras: {max_cameras}")
        print()

        success_count = 0
        failed_count = 0

        for intersection in intersections:
            success = self.auto_populate_intersection(
                intersection['id'],
                radius_miles=radius_miles,
                max_cameras=max_cameras
            )

            if success:
                success_count += 1
            else:
                failed_count += 1

            print()  # Spacing

        print("=" * 60)
        print(f"[SUCCESS] Successfully populated: {success_count}")
        print(f"[ERROR] Failed: {failed_count}")

    def auto_populate_new_only(self, radius_miles: float = 0.5, max_cameras: int = 3):
        """
        Auto-populate camera URLs ONLY for intersections without cameras

        This is useful for populating newly added intersections without
        re-processing existing ones.

        Args:
            radius_miles: Search radius in miles
            max_cameras: Maximum cameras per intersection
        """
        intersections = self.list_intersections()

        # Filter to only intersections without cameras
        new_intersections = [i for i in intersections if i['camera_count'] == 0]

        print(f"🔄 Auto-populating NEW intersections only")
        print(f"   Total intersections: {len(intersections)}")
        print(f"   Without cameras: {len(new_intersections)}")
        print(f"   Radius: {radius_miles} miles")
        print(f"   Max cameras: {max_cameras}")
        print()

        if len(new_intersections) == 0:
            print("[SUCCESS] All intersections already have cameras!")
            return

        success_count = 0
        failed_count = 0

        for intersection in new_intersections:
            success = self.auto_populate_intersection(
                intersection['id'],
                radius_miles=radius_miles,
                max_cameras=max_cameras
            )

            if success:
                success_count += 1
            else:
                failed_count += 1

            print()  # Spacing

        print("=" * 60)
        print(f"[SUCCESS] Successfully populated: {success_count}")
        print(f"[ERROR] Failed: {failed_count}")
        print(f"📊 Coverage: {len(intersections) - len(new_intersections) + success_count}/{len(intersections)} intersections have cameras")

    def display_intersections(self, with_cameras_only: bool = False):
        """
        Display all intersections with their camera status

        Args:
            with_cameras_only: Only show intersections with cameras
        """
        intersections = self.list_intersections()

        if with_cameras_only:
            intersections = [i for i in intersections if i['camera_count'] > 0]

        print(f"* Intersections ({len(intersections)} total)")
        print("=" * 80)

        for intersection in intersections:
            camera_indicator = "[CAM]" if intersection['camera_count'] > 0 else "[ - ]"
            print(f"{camera_indicator} ID {intersection['id']}: {intersection['name']}")
            print(f"   Location: ({intersection['latitude']:.4f}, {intersection['longitude']:.4f})")
            print(f"   Cameras: {intersection['camera_count']}")

            if intersection['camera_urls'] and intersection['camera_count'] > 0:
                cameras = intersection['camera_urls']
                if isinstance(cameras, str):
                    cameras = json.loads(cameras)

                for cam in cameras:
                    print(f"      - {cam.get('source')}: {cam.get('label')}")

            print()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Populate camera URLs for intersections',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all intersections
  python populate_camera_urls.py --list

  # Auto-populate all intersections
  python populate_camera_urls.py --auto-all

  # Auto-populate ONLY new intersections (without cameras)
  python populate_camera_urls.py --auto-new-only

  # Auto-populate specific intersection
  python populate_camera_urls.py --auto --intersection-id 0

  # Manually add camera
  python populate_camera_urls.py --add --intersection-id 0 \\
      --source VDOT --url "https://511virginia.org/camera/CAM123" \\
      --label "VDOT Camera - Main St"

  # Clear cameras for intersection
  python populate_camera_urls.py --clear --intersection-id 0
        """
    )

    # Actions
    parser.add_argument('--list', action='store_true',
                        help='List all intersections with camera status')
    parser.add_argument('--list-cameras', action='store_true',
                        help='List only intersections with cameras')
    parser.add_argument('--auto-all', action='store_true',
                        help='Auto-populate all intersections')
    parser.add_argument('--auto-new-only', action='store_true',
                        help='Auto-populate ONLY intersections without cameras (for new intersections)')
    parser.add_argument('--auto', action='store_true',
                        help='Auto-populate specific intersection (requires --intersection-id)')
    parser.add_argument('--add', action='store_true',
                        help='Manually add camera (requires --intersection-id, --source, --url, --label)')
    parser.add_argument('--clear', action='store_true',
                        help='Clear cameras for intersection (requires --intersection-id)')

    # Parameters
    parser.add_argument('--intersection-id', type=int,
                        help='Intersection ID')
    parser.add_argument('--radius', type=float, default=0.5,
                        help='Search radius in miles (default: 0.5)')
    parser.add_argument('--max-cameras', type=int, default=3,
                        help='Maximum cameras to add (default: 3)')
    parser.add_argument('--source', type=str,
                        help='Camera source (e.g., VDOT, 511)')
    parser.add_argument('--url', type=str,
                        help='Camera URL')
    parser.add_argument('--label', type=str,
                        help='Camera label')

    args = parser.parse_args()

    # Initialize populator
    populator = CameraURLPopulator()

    # Execute actions
    if args.list:
        populator.display_intersections()

    elif args.list_cameras:
        populator.display_intersections(with_cameras_only=True)

    elif args.auto_all:
        populator.auto_populate_all(
            radius_miles=args.radius,
            max_cameras=args.max_cameras
        )

    elif args.auto_new_only:
        populator.auto_populate_new_only(
            radius_miles=args.radius,
            max_cameras=args.max_cameras
        )

    elif args.auto:
        if args.intersection_id is None:
            print("[ERROR] Error: --intersection-id required for --auto")
            return 1

        populator.auto_populate_intersection(
            args.intersection_id,
            radius_miles=args.radius,
            max_cameras=args.max_cameras
        )

    elif args.add:
        if args.intersection_id is None or not args.source or not args.url or not args.label:
            print("[ERROR] Error: --intersection-id, --source, --url, and --label required for --add")
            return 1

        populator.add_camera_url(
            args.intersection_id,
            args.source,
            args.url,
            args.label
        )

    elif args.clear:
        if args.intersection_id is None:
            print("[ERROR] Error: --intersection-id required for --clear")
            return 1

        populator.clear_camera_urls(args.intersection_id)

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
