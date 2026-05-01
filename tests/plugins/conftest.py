"""
Plugin test conftest – mirrors the backend conftest path/mock setup so
plugin tests can be run both standalone (`pytest tests/plugins`) and as
part of the full CI suite.
"""
import sys
import os
from unittest.mock import MagicMock

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend"))
_PLUGINS_DIR = os.path.abspath(os.path.dirname(__file__))

if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
elif sys.path[0] != _BACKEND:
    try:
        sys.path.remove(_BACKEND)
    except ValueError:
        pass
    sys.path.insert(0, _BACKEND)

# Allow `from test_mock_plugin import ...` (pre-existing pattern in plugin tests)
if _PLUGINS_DIR not in sys.path:
    sys.path.insert(1, _PLUGINS_DIR)

# Flush stale 'app' cache (in case frontend or a prior suite was loaded)
for _k in list(sys.modules.keys()):
    if _k == "app" or _k.startswith("app."):
        del sys.modules[_k]

# Same mock strategy as tests/backend/conftest.py — only mocks packages
# that are genuinely missing (real packages in CI, mocked locally).
_ALL_MOCKS = [
    "psycopg2", "psycopg2.extras", "psycopg2.extensions", "psycopg2.pool",
    "geoalchemy2", "geoalchemy2.types",
    "alembic", "alembic.op", "alembic.context",
    "trino", "trino.dbapi", "trino.auth",
    "google", "google.cloud", "google.cloud.storage", "google.auth",
    "redis",
    "pandas", "numpy", "numpy.typing", "scipy", "scipy.stats", "pyarrow",
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
