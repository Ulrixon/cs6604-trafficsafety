"""
Frontend test conftest – isolates the frontend 'app' package on sys.path.
"""
import sys
import os

_FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))

# Put frontend at position 0 so 'import app' finds the frontend package
if _FRONTEND not in sys.path:
    sys.path.insert(0, _FRONTEND)
elif sys.path[0] != _FRONTEND:
    try:
        sys.path.remove(_FRONTEND)
    except ValueError:
        pass
    sys.path.insert(0, _FRONTEND)

# Flush any cached 'app.*' that belonged to a different package (e.g. backend)
for _k in list(sys.modules.keys()):
    if _k == "app" or _k.startswith("app."):
        del sys.modules[_k]
