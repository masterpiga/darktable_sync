#!/usr/bin/env python3
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Try to import the detection module
try:
    from dtsync.darktable_detection import get_default_darktable_cli_path
    print("✓ Successfully imported darktable_detection module")
    
    path = get_default_darktable_cli_path()
    print(f"✓ Detection function executed successfully: '{path}'")
    
    # Now try to import the modified app_logic
    from dtsync.app_logic import AppLogic
    print("✓ Successfully imported modified app_logic module")
    
    # Test creating an instance
    logic = AppLogic()
    print(f"✓ AppLogic instance created with CLI path: '{logic.darktable_cli_path}'")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
