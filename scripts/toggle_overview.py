#!/usr/bin/env python3

"""
Example script for opening the overview on the focused monitor.
This script uses the global keybind handler to open the overview
on whichever monitor currently has focus.
"""

import sys
import os
from config.loguru_config import logger

logger = logger.bind(name="Overview", type="Script")

# Add the Ax-Shell directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.global_keybinds import get_global_keybind_handler
    
    handler = get_global_keybind_handler()
    success = handler.open_overview()
    
    if success:
        logger.debug("Overview opened on focused monitor")
        sys.exit(0)
    else:
        logger.error("Failed to open overview")
        sys.exit(1)
        
except ImportError as e:
    logger.error(f"Unable to import Ax-Shell modules: {e}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Unable to open overview: {e}")
    sys.exit(1)