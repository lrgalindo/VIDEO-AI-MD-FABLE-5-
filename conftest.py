"""Root conftest — adds project root to sys.path so local 'tests' package
takes precedence over any system-level 'tests' package."""

import sys
import os

# Ensure project root is first in path so local tests/ and cloud/ are found
# before any system-installed packages with the same names.
_root = os.path.dirname(__file__)
if _root not in sys.path:
    sys.path.insert(0, _root)
