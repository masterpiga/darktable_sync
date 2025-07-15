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
from PySide6.QtWidgets import QVBoxLayout, QTextEdit, QDialog, QDialogButtonBox
from app_logic import CommandGroup
from typing import Iterable




class ActionDialog(QDialog):
    """A dialog window to show the planned actions and execute them."""

    def __init__(self, groups: Iterable[CommandGroup], dry_run, parent):
        super().__init__(parent)
        self.setWindowTitle("Apply Changes")
        self.setMinimumSize(800, 400)
        self.parent_app = parent  # Store reference to parent app

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFontFamily("monospace")
        command_text = (
            "--- DRY RUN ---\n\n" if dry_run else "--- EXECUTING COMMANDS ---\n\n"
        )


        for grp in groups:
            command_text += f"{grp.xmp_name}: {parent.action_names[grp.action_id]}\n\n"
            command_text += "\n".join(
                [
                    (
                        f"{cmd[0].upper()}: {cmd[1]} -> {cmd[2]}"
                        if len(cmd) > 2
                        else f"INFO: {cmd[1]}"
                    )
                    for cmd in grp.commands
                ]
            )
            command_text += "\n\n"
        self.text_edit.setText(command_text)
        layout.addWidget(self.text_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.execution_log = []
        if not dry_run:
            all_commands = [cmd for grp in groups for cmd in grp.commands]
            self.execute_commands(all_commands)

    def execute_commands(self, commands):
        """Executes the file system operations."""
        try:
            for command, *args in commands:
                if command == "copy":
                    src, dest = args
                    self.execution_log.append(f"COPY: {src} -> {dest}")
                    
                    # Create backup if destination exists and backups are enabled
                    if os.path.exists(dest) and hasattr(self.parent_app, 'logic'):
                        self.parent_app.logic.create_backup(dest)
                    
                    shutil.copy2(src, dest)
                elif command == "duplicate":
                    src, dest_dir = args
                    base, ext = os.path.splitext(os.path.basename(src))
                    # Find a unique name for the duplicate
                    i = 1
                    while True:
                        dest_name = f"{base}_{i}{ext}"
                        dest_path = os.path.join(dest_dir, dest_name)
                        if not os.path.exists(dest_path):
                            break
                        i += 1
                    self.execution_log.append(f"DUPLICATE: {src} -> {dest_path}")
                    # No backup needed for duplicate since it's a new file
                    shutil.copy2(src, dest_path)
            self.execution_log.append(
                "\n--- All operations completed successfully! ---"
            )
        except Exception as e:
            self.execution_log.append(f"\n--- ERROR ---")
            self.execution_log.append(f"An error occurred: {e}")
            self.execution_log.append("Some operations may not have completed.")

        current_text = self.text_edit.toPlainText()
        self.text_edit.setText(current_text + "\n\n" + "\n".join(self.execution_log))
