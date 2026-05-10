"""pytest fixtures + import-order workaround.

The `duckdb` package contains a C extension (`_duckdb.pyd`) whose submodule
loading (`from _duckdb._sqltypes import ...`) breaks under coverage.py's
import tracer if imported lazily. Importing it here, before coverage attaches,
is the documented workaround.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Eager-import duckdb so its C extension submodules are resolved before
# pytest-cov / coverage.py begin tracing imports.
import duckdb  # noqa: F401

# Make the project root importable for `from lib.db import ...` etc.
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
