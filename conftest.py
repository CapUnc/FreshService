"""Pytest bootstrap.

Nexus uses flat top-level modules (config.py, search_tickets.py, ...) rather than
an installed package. Ensure the repo root is importable so the test suite works
no matter how pytest is invoked (`pytest` console script vs `python -m pytest`).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
