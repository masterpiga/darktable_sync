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

import dataclasses
import os
import json
import shutil
import time
from pathlib import Path
import darktable_detection
import ui_actions


@dataclasses.dataclass
class CommandGroup:
    action_id: str
    xmp_name: str
    commands: list[list[str]] = dataclasses.field(default_factory=list)


class AppLogic:
    """Encapsulates the business logic of the application."""

    def __init__(self):
        # --- Data storage ---
        self.session_dir = ""
        self.archive_dir = ""
        
        # Try to detect darktable-cli path, fallback to empty string if detection fails
        try:
            self.darktable_cli_path = darktable_detection.get_default_darktable_cli_path()
        except Exception:
            self.darktable_cli_path = ""
        
        self.diff_files = {}
        self.actions = {}
        self.max_threads = os.cpu_count() or 4
        self.preview_max_dimension = 800
        self.enable_opencl = True  # Enable OpenCL by default
        self.enable_backups = True  # Enable backups by default
        
        # --- Default keyboard shortcuts ---
        self.default_shortcuts = {x: y.default_shortcut for x, y in ui_actions.ALL_ACTIONS.items()}
        self.custom_shortcuts = self.default_shortcuts.copy()
        
        # --- Settings Path ---
        self.settings_dir = os.path.join(Path.home(), ".config", "dtsync")
        self.settings_path = os.path.join(self.settings_dir, "settings.json")

    def load_settings(self):
        """Load application settings from file."""
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r") as f:
                    settings = json.load(f)
                    saved_cli_path = settings.get("darktable_cli_path", "")
                    
                    # Use saved path if it exists and is valid, otherwise use detected default
                    try:
                        if saved_cli_path and darktable_detection.validate_darktable_cli_path(saved_cli_path):
                            self.darktable_cli_path = saved_cli_path
                        else:
                            # If saved path is invalid, try to detect a new one
                            detected_path = darktable_detection.get_default_darktable_cli_path()
                            if detected_path:
                                self.darktable_cli_path = detected_path
                    except Exception:
                        # If detection fails, keep the saved path (even if invalid)
                        self.darktable_cli_path = saved_cli_path
                    
                    self.session_dir = settings.get("session_dir", "")
                    self.archive_dir = settings.get("archive_dir", "")
                    self.max_threads = settings.get("max_threads", os.cpu_count() or 4)
                    self.preview_max_dimension = settings.get("preview_max_dimension", 800)
                    self.enable_opencl = settings.get("enable_opencl", True)
                    self.enable_backups = settings.get("enable_backups", True)
                    
                    # Load custom shortcuts
                    saved_shortcuts = settings.get("custom_shortcuts", {})
                    self.custom_shortcuts.update(saved_shortcuts)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Could not load settings: {e}")
            # If loading fails, ensure we have a default CLI path
            try:
                if not self.darktable_cli_path:
                    self.darktable_cli_path = darktable_detection.get_default_darktable_cli_path()
            except Exception:
                pass  # Keep existing path or empty string

    def save_settings(self):
        os.makedirs(self.settings_dir, exist_ok=True)
        settings = {
            "darktable_cli_path": self.darktable_cli_path,
            "session_dir": self.session_dir,
            "archive_dir": self.archive_dir,
            "max_threads": self.max_threads,
            "preview_max_dimension": self.preview_max_dimension,
            "enable_opencl": self.enable_opencl,
            "enable_backups": self.enable_backups,
            "custom_shortcuts": self.custom_shortcuts,
        }
        with open(self.settings_path, "w") as f:
            json.dump(settings, f, indent=4)

    def get_keep_both_commands(self, session_path, archive_path):
        """
        Returns a list of copy commands to:
        - Copy the session XMP to the archive dir with a unique suffix
        - Copy the archive XMP to the session dir with a unique suffix
        - Ensure both sides have both XMPs, with the same content for each suffixed file
        """
        commands = []
        def get_unique_name(base_name, archive_dir, session_dir):
            img_name, xmp_ext = os.path.splitext(base_name)
            raw_base, raw_ext = os.path.splitext(img_name)
            i = 1
            while True:
                candidate = f"{raw_base}_{i:02d}{raw_ext}{xmp_ext}"
                if not (os.path.exists(os.path.join(archive_dir, candidate)) or os.path.exists(os.path.join(session_dir, candidate))):
                    return candidate
                if i == 99:
                    raise ValueError("Too many copies, cannot generate unique name")
                i += 1
        # Target paths
        archive_dir = os.path.dirname(archive_path)
        session_dir = os.path.dirname(session_path)
        base_name = os.path.basename(archive_path)
        new_base_name = get_unique_name(base_name, archive_dir, session_dir)
        new_archive_path = os.path.join(archive_dir, new_base_name)
        new_session_path = os.path.join(session_dir, new_base_name)
        commands.append(("copy", archive_path, new_archive_path))
        commands.append(("copy", new_archive_path, new_session_path))
        commands.append(("copy", session_path, archive_path))
        return commands


    def get_apply_changes_commands(self):
        """Generate the list of commands for the selected actions."""
        commands = []
        for relative_path, action_id in self.actions.items():
            command = CommandGroup(action_id, os.path.basename(relative_path))
            if action_id == 0:
                continue
            file_info = self.diff_files[relative_path]
            session_path = file_info["session_path"]
            archive_path = file_info["archive_path"]
            if action_id == 1:
                command.commands.append(("copy", session_path, archive_path))
            elif action_id == 2:
                command.commands.append(("copy", archive_path, session_path))
            elif action_id == 3:
                # Keep both: copy each XMP to the other side with a unique suffix, and align both sides
                command.commands.extend(self.get_keep_both_commands(session_path, archive_path))
            commands.append(command)
        return commands

    def create_backup(self, file_path):
        """Create a backup of the file with .dtsync.bak extension."""
        if not self.enable_backups or not os.path.exists(file_path):
            return
            
        # Create backup filename: .<original_xmp_name>.<timestamp>.dtsync.bak
        directory = os.path.dirname(file_path)
        original_name = os.path.basename(file_path)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_name = f".{original_name}.{timestamp}.dtsync.bak"
        backup_path = os.path.join(directory, backup_name)
        
        try:
            shutil.copy2(file_path, backup_path)
            print(f"Created backup: {backup_path}")
        except Exception as e:
            print(f"Warning: Could not create backup for {file_path}: {e}")
