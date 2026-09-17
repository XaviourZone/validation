#!/usr/bin/env python3
"""Convenience runner script for the Validation Data Router Service."""

import os
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH
script_dir = Path(__file__).resolve().parent
router_dir = script_dir.parent
validation_dir = router_dir.parent
workspace_dir = validation_dir.parent

for p in [str(workspace_dir), str(validation_dir), str(router_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from Validation.Data_Router.app.main import main

if __name__ == "__main__":
    main()
