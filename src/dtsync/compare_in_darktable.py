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
import shutil
import tempfile
import subprocess
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject, Signal

# Import the XMP comparison function from scanner
from scanner import extract_darktable_data
import path_utils


class CompareInDarktableManager(QObject):
    """Manages comparison of XMP files in darktable."""
    
    # Signal emitted when previews need to be refreshed
    refresh_previews_signal = Signal(str, str, bool, bool)  # archive_path, session_path, ref_changed, work_changed
    
    def __init__(self, preview_manager):
        super().__init__(preview_manager)
        self.preview_manager = preview_manager
    
    def compare_in_darktable(self, session_xmp_path, archive_xmp_path):
        """
        Compare archive and session versions in darktable.
        
        Args:
            session_xmp_path: Path to the session XMP file
            archive_xmp_path: Path to the archive XMP file
        """
        try:
            # Get darktable path from settings via preview manager
            # The preview manager is part of the main window widget hierarchy
            main_window = self.preview_manager
            while main_window and not hasattr(main_window, 'logic'):
                main_window = main_window.parent()
            
            if not main_window or not hasattr(main_window, 'logic'):
                QMessageBox.warning(
                    self.preview_manager,
                    "Configuration Error",
                    "Could not access application settings."
                )
                return
                
            if not main_window.logic.darktable_cli_path:
                QMessageBox.warning(
                    self.preview_manager,
                    "Darktable Not Configured",
                    "Please configure the darktable-cli path in Settings first."
                )
                return
            
            # Find darktable executable (same directory as darktable-cli)
            darktable_cli_dir = os.path.dirname(main_window.logic.darktable_cli_path)
            darktable_path = os.path.join(darktable_cli_dir, "darktable")
            
            if not os.path.exists(darktable_path):
                QMessageBox.warning(
                    self.preview_manager,
                    "Darktable Not Found",
                    f"Darktable executable not found at: {darktable_path}"
                )
                return
            
            # Find raw files for both XMP files
            session_raw = path_utils.infer_raw_file_path(session_xmp_path)
            archive_raw = path_utils.infer_raw_file_path(archive_xmp_path)
            
            if not session_raw:
                QMessageBox.warning(
                    self.preview_manager,
                    "Raw File Not Found",
                    f"Could not find raw file for: {session_xmp_path}"
                )
                return
                
            if not archive_raw:
                QMessageBox.warning(
                    self.preview_manager,
                    "Raw File Not Found", 
                    f"Could not find raw file for: {archive_xmp_path}"
                )
                return
            
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="dtsync_compare_")
            
            try:
                # Get file extension
                session_ext = self._get_file_extension(session_raw)
                archive_ext = self._get_file_extension(archive_raw)
                
                # Copy files to temp directory with standardized names
                temp_session_raw = os.path.join(temp_dir, f"Session{session_ext}")
                temp_session_xmp = os.path.join(temp_dir, f"Session{session_ext}.xmp")
                temp_archive_raw = os.path.join(temp_dir, f"Archive{archive_ext}")
                temp_archive_xmp = os.path.join(temp_dir, f"Archive{archive_ext}.xmp")
                
                # Copy files
                shutil.copy2(session_raw, temp_session_raw)
                shutil.copy2(session_xmp_path, temp_session_xmp)
                shutil.copy2(archive_raw, temp_archive_raw)
                shutil.copy2(archive_xmp_path, temp_archive_xmp)
                
                # Store original XMP data for comparison
                orig_session_xmp_data = extract_darktable_data(temp_session_xmp)
                orig_archive_xmp_data = extract_darktable_data(temp_archive_xmp)
                
                # Launch darktable
                subprocess.run([darktable_path, "--library", ":memory:", temp_dir], check=False)
                
                # Check if XMP files were modified by comparing the actual data
                new_session_xmp_data = extract_darktable_data(temp_session_xmp)
                new_archive_xmp_data = extract_darktable_data(temp_archive_xmp)
                
                session_modified = orig_session_xmp_data != new_session_xmp_data
                archive_modified = orig_archive_xmp_data != new_archive_xmp_data
                
                if session_modified or archive_modified:
                    # Ask user if they want to keep changes
                    modified_files = []
                    if session_modified:
                        modified_files.append("Session")
                    if archive_modified:
                        modified_files.append("Archive")
                    
                    msg = QMessageBox(self.preview_manager)
                    msg.setWindowTitle("XMP Files Modified")
                    msg.setText(f"The following XMP files were modified in darktable:\n\n{', '.join(modified_files)}")
                    msg.setInformativeText("Do you want to keep these changes?")
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    msg.setDefaultButton(QMessageBox.StandardButton.Yes)
                    
                    if msg.exec() == QMessageBox.StandardButton.Yes:
                        # Copy back modified XMP files
                        if session_modified:
                            # Create backup if enabled
                            if main_window.logic.enable_backups:
                                main_window.logic.create_backup(session_xmp_path)
                            shutil.copy2(temp_session_xmp, session_xmp_path)
                        if archive_modified:
                            # Create backup if enabled  
                            if main_window.logic.enable_backups:
                                main_window.logic.create_backup(archive_xmp_path)
                            shutil.copy2(temp_archive_xmp, archive_xmp_path)
                        
                        # Emit signal to refresh previews with specific change information
                        self.refresh_previews_signal.emit(
                            archive_xmp_path, 
                            session_xmp_path, 
                            archive_modified, 
                            session_modified
                        )
                        
                        QMessageBox.information(
                            self.preview_manager,
                            "Changes Saved",
                            "XMP changes have been saved to the original files."
                        )
                
            finally:
                # Clean up temporary directory
                try:
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    print(f"Warning: Could not clean up temporary directory {temp_dir}: {e}")
                    
        except Exception as e:
            QMessageBox.critical(
                self.preview_manager,
                "Error",
                f"An error occurred while comparing in darktable: {str(e)}"
            )
    
    def _get_file_extension(self, file_path):
        """Get the file extension including the dot."""
        return os.path.splitext(file_path)[1]
