"""
Shared pytest fixtures for backend tests.
Sets up sys.path so that 'import app' finds the backend package,
and flushes any cached frontend 'app' that may have been loaded first.
Mocks C-extension database drivers not available in lightweight test envs.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend"))

# Put backend at position 0 so 'import app' finds the backend package
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
elif sys.path[0] != _BACKEND:
    try:
        sys.path.remove(_BACKEND)
    except ValueError:
        pass
    sys.path.insert(0, _BACKEND)

# Flush any cached 'app.*' that belonged to a different package (e.g. frontend)
for _k in list(sys.modules.keys()):
    if _k == "app" or _k.startswith("app."):
        del sys.modules[_k]

# Mock C-extension / system dependencies not present in lightweight CI envs
# Mock dependencies that may be absent in lightweight envs (local dev / minimal CI).
# In CI (pip install -r backend/requirements.txt) these are real packages —
# the try/__import__ guard ensures we only mock what isn't actually installed.
_ALL_MOCKS = [
    # PostgreSQL driver (needs libpq system lib; psycopg2-binary bundles it)
    "psycopg2", "psycopg2.extras", "psycopg2.extensions", "psycopg2.pool",
    # GIS
    "geoalchemy2", "geoalchemy2.types",
    # DB migrations
    "alembic", "alembic.op", "alembic.context",
    # Trino query engine
    "trino", "trino.dbapi", "trino.auth",
    # GCP client libs
    "google", "google.cloud", "google.cloud.storage", "google.auth",
    # Redis (optional caching)
    "redis",
    # Data / science stack
    "pandas", "numpy", "numpy.typing", "scipy", "scipy.stats", "pyarrow",
    # SQLAlchemy
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlalchemy.ext.declarative", "sqlalchemy.dialects",
    "sqlalchemy.dialects.postgresql", "sqlalchemy.pool",
    "sqlalchemy.types", "sqlalchemy.engine", "sqlalchemy.event",
]
for _mod in _ALL_MOCKS:
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except (ModuleNotFoundError, ImportError):
            sys.modules[_mod] = MagicMock()


@pytest.fixture()
def sample_intersection_payload():
    """Valid intersection dict matching the IntersectionRead / API response shape."""
    return {
        "intersection_id": 1,
        "intersection_name": "Glebe_Rd_Potomac_Ave",
        "safety_index": 72.5,
        "index_type": "RT-SI-Full",
        "traffic_volume": 1200.0,
        "latitude": 38.8601,
        "longitude": -77.0750,
        "mcdm_index": 65.0,
        "rt_si_index": 76.0,
    }


# Put backend at position 0 so 'import app' finds the backend package
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
elif sys.path[0] != _BACKEND:
    try:
        sys.path.remove(_BACKEND)
    except ValueError:
        pass
    sys.path.insert(0, _BACKEND)

# Flush any cached 'app.*' that belonged to a different package (e.g. frontend)
for _k in list(sys.modules.keys()):
    if _k == "app" or _k.startswith("app."):
        del sys.modules[_k]


@pytest.fixture()
def sample_intersection_payload():
    """Valid intersection dict matching the IntersectionRead / API response shape."""
    return {
        "intersection_id": 1,
        "intersection_name": "Glebe_Rd_Potomac_Ave",
        "safety_index": 72.5,
        "index_type": "RT-SI-Full",
        "traffic_volume": 1200.0,
        "latitude": 38.8601,
        "longitude": -77.0750,
        "mcdm_index": 65.0,
        "rt_si_index": 76.0,
    }
