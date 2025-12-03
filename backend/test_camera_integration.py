#!/usr/bin/env python3
"""
Automated test suite for camera integration feature.

This script automates all the manual testing steps from the testing guide.

Usage:
    python test_camera_integration.py
"""

import os
import sys
import time
import requests
import subprocess
from typing import Dict, List, Tuple
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class CameraIntegrationTester:
    """Automated test suite for camera integration"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.backend_process = None
        self.frontend_process = None

        # Check environment
        self.db_url = os.getenv('DATABASE_URL')
        self.vdot_key = os.getenv('VDOT_API_KEY')

    def print_header(self, text: str):
        """Print test section header"""
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{text}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")

    def print_test(self, name: str):
        """Print test name"""
        print(f"{Fore.YELLOW}▶ {name}...{Style.RESET_ALL}", end=" ", flush=True)

    def print_pass(self, message: str = ""):
        """Print test pass"""
        self.passed += 1
        msg = f" ({message})" if message else ""
        print(f"{Fore.GREEN}✓ PASS{msg}{Style.RESET_ALL}")

    def print_fail(self, message: str):
        """Print test failure"""
        self.failed += 1
        print(f"{Fore.RED}✗ FAIL: {message}{Style.RESET_ALL}")

    def print_warning(self, message: str):
        """Print warning"""
        print(f"{Fore.YELLOW}⚠ WARNING: {message}{Style.RESET_ALL}")

    def print_info(self, message: str):
        """Print info"""
        print(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")

    def run_command(self, cmd: List[str], check: bool = True) -> Tuple[int, str, str]:
        """Run shell command and return (returncode, stdout, stderr)"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout, e.stderr

    # ========== Test Suite 1: Environment Setup ==========

    def test_environment(self):
        """Test environment variables"""
        self.print_header("Test Suite 1: Environment Setup")

        # Test DATABASE_URL
        self.print_test("DATABASE_URL is set")
        if self.db_url:
            self.print_pass(f"Set to {self.db_url[:30]}...")
        else:
            self.print_fail("DATABASE_URL not set")
            return False

        # Test VDOT_API_KEY (optional)
        self.print_test("VDOT_API_KEY is set")
        if self.vdot_key:
            self.print_pass("API key configured")
        else:
            self.print_warning("Not set - will use fallback (511 map links)")

        # Test Python version
        self.print_test("Python version >= 3.11")
        version = sys.version_info
        if version.major >= 3 and version.minor >= 11:
            self.print_pass(f"Python {version.major}.{version.minor}.{version.micro}")
        else:
            self.print_fail(f"Python {version.major}.{version.minor} < 3.11")

        return True

    # ========== Test Suite 2: Database ==========

    def test_database(self):
        """Test database migration and setup"""
        self.print_header("Test Suite 2: Database Migration")

        # Test database connection
        self.print_test("Database connection")
        code, stdout, stderr = self.run_command([
            'psql', self.db_url, '-c', 'SELECT version();'
        ], check=False)

        if code == 0:
            self.print_pass("Connected successfully")
        else:
            self.print_fail(f"Cannot connect: {stderr}")
            return False

        # Test camera_urls column exists
        self.print_test("camera_urls column exists")
        code, stdout, stderr = self.run_command([
            'psql', self.db_url, '-t', '-c',
            "SELECT column_name FROM information_schema.columns WHERE table_name='intersections' AND column_name='camera_urls';"
        ], check=False)

        if 'camera_urls' in stdout:
            self.print_pass("Column exists")
        else:
            self.print_fail("Column not found - run migration first")
            self.print_info("Run: psql $DATABASE_URL -f backend/db/init/03_add_camera_urls.sql")
            return False

        # Test validation function exists
        self.print_test("validate_camera_url_structure function exists")
        code, stdout, stderr = self.run_command([
            'psql', self.db_url, '-t', '-c',
            "SELECT proname FROM pg_proc WHERE proname='validate_camera_url_structure';"
        ], check=False)

        if 'validate_camera_url_structure' in stdout:
            self.print_pass("Function exists")
        else:
            self.print_fail("Function not found")

        return True

    # ========== Test Suite 3: Admin Script ==========

    def test_admin_script(self):
        """Test populate_camera_urls.py script"""
        self.print_header("Test Suite 3: Admin Script")

        # Test list command
        self.print_test("List intersections")
        code, stdout, stderr = self.run_command([
            'python', 'scripts/populate_camera_urls.py', '--list'
        ], check=False)

        if code == 0 and 'Intersections' in stdout:
            self.print_pass("Script runs successfully")
        else:
            self.print_fail(f"Script failed: {stderr}")
            return False

        # Test clear command (cleanup)
        self.print_test("Clear test intersection (ID 0)")
        code, stdout, stderr = self.run_command([
            'python', 'scripts/populate_camera_urls.py',
            '--clear', '--intersection-id', '0'
        ], check=False)

        if code == 0:
            self.print_pass("Cleared successfully")
        else:
            self.print_warning(f"Clear failed: {stderr}")

        # Test add command
        self.print_test("Add test camera to intersection 0")
        code, stdout, stderr = self.run_command([
            'python', 'scripts/populate_camera_urls.py',
            '--add',
            '--intersection-id', '0',
            '--source', 'TEST',
            '--url', 'https://511.vdot.virginia.gov/map?lat=37.2&lon=-80.4',
            '--label', 'Automated Test Camera'
        ], check=False)

        if code == 0 and 'Updated' in stdout:
            self.print_pass("Camera added successfully")
        else:
            self.print_fail(f"Add failed: {stderr}")
            return False

        # Verify camera was added
        self.print_test("Verify camera in database")
        code, stdout, stderr = self.run_command([
            'psql', self.db_url, '-t', '-c',
            "SELECT jsonb_array_length(camera_urls) FROM intersections WHERE id=0;"
        ], check=False)

        if '1' in stdout:
            self.print_pass("Camera verified in database")
        else:
            self.print_fail("Camera not found in database")

        return True

    # ========== Test Suite 4: Schema Validation ==========

    def test_schema_validation(self):
        """Test Pydantic schema validation"""
        self.print_header("Test Suite 4: Schema Validation")

        # Test valid camera link
        self.print_test("Valid CameraLink schema")
        try:
            from app.schemas.intersection import CameraLink
            cam = CameraLink(
                source='VDOT',
                url='https://test.com/camera',
                label='Test Camera'
            )
            self.print_pass(f"Valid camera accepted")
        except Exception as e:
            self.print_fail(f"Validation failed: {e}")

        # Test invalid URL
        self.print_test("Invalid URL rejection")
        try:
            from app.schemas.intersection import CameraLink
            cam = CameraLink(
                source='VDOT',
                url='ftp://invalid.com',
                label='Test'
            )
            self.print_fail("Invalid URL accepted (should reject)")
        except Exception:
            self.print_pass("Invalid URL rejected correctly")

        # Test IntersectionRead with camera_urls
        self.print_test("IntersectionRead with camera_urls")
        try:
            from app.schemas.intersection import IntersectionRead
            data = {
                'intersection_id': 1,
                'intersection_name': 'Test',
                'safety_index': 65.0,
                'index_type': 'RT-SI',
                'traffic_volume': 250,
                'longitude': -77.0,
                'latitude': 38.8,
                'camera_urls': [
                    {'source': 'VDOT', 'url': 'https://test.com', 'label': 'Cam1'}
                ]
            }
            intersection = IntersectionRead(**data)
            self.print_pass(f"{len(intersection.camera_urls)} camera(s)")
        except Exception as e:
            self.print_fail(f"Schema validation failed: {e}")

        return True

    # ========== Test Suite 5: VDOT Service ==========

    def test_vdot_service(self):
        """Test VDOT camera service"""
        self.print_header("Test Suite 5: VDOT Camera Service")

        # Test service import
        self.print_test("Import VDOTCameraService")
        try:
            from app.services.vdot_camera_service import VDOTCameraService
            service = VDOTCameraService()
            self.print_pass("Service imported successfully")
        except Exception as e:
            self.print_fail(f"Import failed: {e}")
            return False

        # Test distance calculation
        self.print_test("Haversine distance calculation")
        try:
            from app.services.vdot_camera_service import VDOTCameraService
            service = VDOTCameraService()

            # Richmond to Blacksburg
            distance = service._haversine_distance(37.5407, -77.4360, 37.2296, -80.4139)

            if 160 < distance < 170:
                self.print_pass(f"Distance: {distance:.1f} miles (accurate)")
            else:
                self.print_fail(f"Distance: {distance:.1f} miles (expected ~165)")
        except Exception as e:
            self.print_fail(f"Distance calculation failed: {e}")

        # Test fallback generation
        self.print_test("Fallback map link generation")
        try:
            from app.services.vdot_camera_service import VDOTCameraService
            service = VDOTCameraService()

            fallback = service.get_fallback_map_link(37.5, -77.4)

            if fallback['source'] == '511' and 'lat=37.5' in fallback['url']:
                self.print_pass("Fallback generated correctly")
            else:
                self.print_fail(f"Invalid fallback: {fallback}")
        except Exception as e:
            self.print_fail(f"Fallback generation failed: {e}")

        # Test camera search
        self.print_test("Camera search with fallback")
        try:
            from app.services.vdot_camera_service import VDOTCameraService
            service = VDOTCameraService()

            cameras = service.get_cameras_with_fallback(37.5407, -77.4360, radius_miles=1.0)

            if cameras and len(cameras) > 0:
                self.print_pass(f"Found {len(cameras)} camera(s)")
            else:
                self.print_fail("No cameras returned")
        except Exception as e:
            self.print_fail(f"Camera search failed: {e}")

        return True

    # ========== Test Suite 6: Backend API ==========

    def test_backend_api(self):
        """Test backend API endpoints"""
        self.print_header("Test Suite 6: Backend API")

        # Start backend server
        self.print_test("Starting backend server")
        try:
            self.backend_process = subprocess.Popen(
                ['uvicorn', 'app.main:app', '--port', '8000'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(3)  # Wait for server to start
            self.print_pass("Server started on port 8000")
        except Exception as e:
            self.print_fail(f"Failed to start server: {e}")
            return False

        # Test API endpoint
        self.print_test("GET /api/v1/safety/index/")
        try:
            response = requests.get('http://localhost:8000/api/v1/safety/index/', timeout=5)

            if response.status_code == 200:
                data = response.json()
                self.print_pass(f"Returned {len(data)} intersections")
            else:
                self.print_fail(f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.print_fail(f"Request failed: {e}")
            return False

        # Test camera_urls field presence
        self.print_test("camera_urls field in response")
        try:
            response = requests.get('http://localhost:8000/api/v1/safety/index/', timeout=5)
            data = response.json()

            if data and 'camera_urls' in data[0]:
                cameras = data[0].get('camera_urls', [])
                if cameras:
                    self.print_pass(f"Intersection 0 has {len(cameras)} camera(s)")
                else:
                    self.print_pass("Field present (null/empty)")
            else:
                self.print_fail("camera_urls field missing")
        except Exception as e:
            self.print_fail(f"Field check failed: {e}")

        # Test specific intersection
        self.print_test("GET /api/v1/safety/index/0")
        try:
            response = requests.get('http://localhost:8000/api/v1/safety/index/0', timeout=5)

            if response.status_code == 200:
                data = response.json()
                cameras = data.get('camera_urls', [])
                self.print_pass(f"{len(cameras)} camera(s) for intersection 0")
            else:
                self.print_warning(f"Status code: {response.status_code}")
        except Exception as e:
            self.print_warning(f"Request failed: {e}")

        return True

    # ========== Test Suite 7: Database Queries ==========

    def test_database_queries(self):
        """Test database query functions"""
        self.print_header("Test Suite 7: Database Queries")

        # Test validation function
        self.print_test("validate_camera_url_structure(valid)")
        code, stdout, stderr = self.run_command([
            'psql', self.db_url, '-t', '-c',
            "SELECT validate_camera_url_structure('[{\"source\": \"VDOT\", \"url\": \"https://test.com\", \"label\": \"Test\"}]'::jsonb);"
        ], check=False)

        if 't' in stdout:
            self.print_pass("Valid structure accepted")
        else:
            self.print_fail("Validation function failed")

        # Test invalid structure
        self.print_test("validate_camera_url_structure(invalid)")
        code, stdout, stderr = self.run_command([
            'psql', self.db_url, '-t', '-c',
            "SELECT validate_camera_url_structure('[{\"source\": \"VDOT\"}]'::jsonb);"
        ], check=False)

        if 'f' in stdout:
            self.print_pass("Invalid structure rejected")
        else:
            self.print_fail("Validation function accepted invalid data")

        # Test coverage statistics
        self.print_test("Coverage statistics query")
        code, stdout, stderr = self.run_command([
            'psql', self.db_url, '-t', '-c',
            """SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE camera_urls IS NOT NULL) as with_cameras
            FROM intersections;"""
        ], check=False)

        if code == 0:
            parts = stdout.strip().split('|')
            if len(parts) == 2:
                total = parts[0].strip()
                with_cameras = parts[1].strip()
                self.print_pass(f"{with_cameras}/{total} intersections have cameras")
            else:
                self.print_pass("Query executed")
        else:
            self.print_fail("Query failed")

        return True

    # ========== Cleanup ==========

    def cleanup(self):
        """Cleanup test resources"""
        self.print_header("Cleanup")

        # Stop backend server
        if self.backend_process:
            self.print_info("Stopping backend server...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()

        # Optional: Clear test camera
        self.print_info("Cleaning up test data...")
        code, stdout, stderr = self.run_command([
            'python', 'scripts/populate_camera_urls.py',
            '--clear', '--intersection-id', '0'
        ], check=False)

    # ========== Run All Tests ==========

    def run_all_tests(self):
        """Run all test suites"""
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Camera Integration - Automated Test Suite{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")

        start_time = time.time()

        # Run test suites
        try:
            if not self.test_environment():
                raise Exception("Environment setup failed")

            if not self.test_database():
                raise Exception("Database tests failed")

            self.test_admin_script()
            self.test_schema_validation()
            self.test_vdot_service()
            self.test_backend_api()
            self.test_database_queries()

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Tests interrupted by user{Style.RESET_ALL}")
        except Exception as e:
            print(f"\n{Fore.RED}Test suite aborted: {e}{Style.RESET_ALL}")
        finally:
            self.cleanup()

        # Print summary
        elapsed = time.time() - start_time

        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Test Summary{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")

        print(f"Time: {elapsed:.1f}s")
        print(f"{Fore.GREEN}Passed: {self.passed}{Style.RESET_ALL}")
        print(f"{Fore.RED}Failed: {self.failed}{Style.RESET_ALL}")

        total = self.passed + self.failed
        if total > 0:
            success_rate = (self.passed / total) * 100
            print(f"Success Rate: {success_rate:.1f}%")

        if self.failed == 0:
            print(f"\n{Fore.GREEN}✓ All tests passed!{Style.RESET_ALL}\n")
            return 0
        else:
            print(f"\n{Fore.RED}✗ Some tests failed{Style.RESET_ALL}\n")
            return 1


def main():
    """Main entry point"""
    # Check if colorama is installed
    try:
        import colorama
    except ImportError:
        print("Installing colorama for colored output...")
        subprocess.run(['pip', 'install', 'colorama'], check=True)
        import colorama

    # Check if requests is installed
    try:
        import requests
    except ImportError:
        print("Installing requests for API testing...")
        subprocess.run(['pip', 'install', 'requests'], check=True)
        import requests

    tester = CameraIntegrationTester()
    return tester.run_all_tests()


if __name__ == '__main__':
    sys.exit(main())
