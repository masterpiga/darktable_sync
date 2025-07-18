#!/usr/bin/env python3
import os
import platform
import shutil

def get_default_darktable_cli_path():
    """
    Returns the default darktable-cli path based on the current OS.
    
    Returns:
        str: The default path to darktable-cli executable, or empty string if not found
    """
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
    cli_in_path = shutil.which("darktable-cli")
    if cli_in_path and os.path.isfile(cli_in_path):
        return cli_in_path
    
    # Then check the platform-specific paths
    for path in paths_to_check:
        if os.path.isfile(path):
            return path
    
    # Return empty string if not found
    return ""

if __name__ == "__main__":
    print("Testing darktable detection on", platform.system())
    result = get_default_darktable_cli_path()
    print(f"Detected path: '{result}'")
    print("Test completed successfully!")
