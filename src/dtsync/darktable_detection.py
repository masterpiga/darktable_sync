"""
Darktable XMP Sync Tool
Copyright (C) 2025 Daniele Pighin

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import platform
import shutil
from pathlib import Path


def get_default_darktable_cli_path():
    """
    Returns the default darktable-cli path based on the current OS.
    
    Returns:
        str: The default path to darktable-cli executable, or empty string if not found
    """
    try:
        system = platform.system()
        
        # Common paths to check for each OS
        paths_to_check = []
        
        if system == "Darwin":  # macOS
            paths_to_check = [
                "/Applications/darktable.app/Contents/MacOS/darktable-cli",
                "/usr/local/bin/darktable-cli",
                "/opt/homebrew/bin/darktable-cli",
                "/usr/local/darktable/bin/darktable-cli"
            ]
        elif system == "Windows":  # Windows
            # Check common installation directories
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
            
            paths_to_check = [
                os.path.join(program_files, "darktable", "bin", "darktable-cli.exe"),
                os.path.join(program_files_x86, "darktable", "bin", "darktable-cli.exe"),
                os.path.join(program_files, "darktable", "darktable-cli.exe"),
                os.path.join(program_files_x86, "darktable", "darktable-cli.exe"),
                "C:\\darktable\\bin\\darktable-cli.exe"
            ]
        elif system == "Linux":  # Linux
            paths_to_check = [
                "/usr/bin/darktable-cli",
                "/usr/local/bin/darktable-cli",
                "/opt/darktable/bin/darktable-cli",
                "/snap/bin/darktable-cli",
                "/usr/local/darktable/bin/darktable-cli"
            ]
        
        # First check the system PATH
        try:
            cli_in_path = shutil.which("darktable-cli")
            if cli_in_path and os.path.isfile(cli_in_path):
                return cli_in_path
        except Exception:
            pass  # Continue to check specific paths
        
        # Then check the platform-specific paths
        for path in paths_to_check:
            try:
                if os.path.isfile(path):
                    return path
            except Exception:
                continue  # Skip paths that cause errors
        
        # Return empty string if not found
        return ""
    
    except Exception:
        # If any error occurs, return empty string to fail gracefully
        return ""


def validate_darktable_cli_path(path):
    """
    Validates that the provided path is a valid darktable-cli executable.
    
    Args:
        path (str): Path to the darktable-cli executable
        
    Returns:
        bool: True if the path is valid, False otherwise
    """
    try:
        if not path or not os.path.isfile(path):
            return False
        
        # Check if it's executable
        if not os.access(path, os.X_OK):
            return False
        
        # Check filename contains darktable-cli
        filename = os.path.basename(path).lower()
        return "darktable-cli" in filename
    
    except Exception:
        # If any error occurs during validation, return False
        return False
