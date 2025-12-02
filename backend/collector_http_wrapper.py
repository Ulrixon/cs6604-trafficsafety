"""
HTTP wrapper for data_collector.py to make it Cloud Run compatible.

This script runs a simple HTTP health check server on port 8080
while the data collector runs in a background thread.
"""

import os
import sys
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Import the data collector
from data_collector import DataCollector

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global collector instance for health checks
collector = None


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks"""

    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health' or self.path == '/':
            # Return health status
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            # Build health response
            health_data = {
                "status": "healthy",
                "service": "data-collector",
                "timestamp": datetime.now().isoformat(),
            }

            if collector:
                health_data["stats"] = {
                    "total_collections": collector.stats.get('collections', 0),
                    "total_bsm": collector.stats.get('total_bsm', 0),
                    "total_psm": collector.stats.get('total_psm', 0),
                    "total_mapdata": collector.stats.get('total_mapdata', 0),
                    "db_writes": collector.stats.get('db_writes', 0),
                    "gcs_uploads": collector.stats.get('gcs_uploads', 0),
                }
                if collector.stats.get('last_collection'):
                    health_data["last_collection"] = collector.stats['last_collection'].isoformat()

            import json
            self.wfile.write(json.dumps(health_data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP logging to reduce noise"""
        pass


def run_collector():
    """Run the data collector in a background thread"""
    global collector

    try:
        # Get configuration from environment or defaults
        interval = int(os.getenv('COLLECTION_INTERVAL', '60'))
        storage_path = os.getenv('PARQUET_STORAGE_PATH', '/app/data/parquet')

        logger.info(f"Starting data collector (interval={interval}s, storage={storage_path})")

        # Create and run collector
        collector = DataCollector(
            collection_interval=interval,
            realtime_mode=False,
            storage_path=storage_path
        )

        collector.run()

    except Exception as e:
        logger.error(f"Data collector failed: {e}", exc_info=True)
        raise


def run_http_server():
    """Run the HTTP health check server"""
    port = int(os.getenv('PORT', '8080'))

    logger.info(f"Starting HTTP health check server on port {port}")

    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"✓ HTTP server listening on 0.0.0.0:{port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"HTTP server failed: {e}", exc_info=True)
        raise


def main():
    """Main entry point"""
    logger.info("="*80)
    logger.info("VCC DATA COLLECTOR WITH HTTP WRAPPER")
    logger.info("="*80)

    # Start HTTP server in background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    logger.info("✓ HTTP health check server started in background")

    # Run data collector in main thread (needs to be main for signal handlers)
    run_collector()


if __name__ == '__main__':
    main()
