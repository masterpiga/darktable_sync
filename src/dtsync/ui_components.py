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
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDialogButtonBox,
    QTableWidgetItem,
)
from PySide6.QtCore import Qt

def show_error_message(parent, message, title="Error"):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(message))
    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    button_box.accepted.connect(dialog.accept)
    layout.addWidget(button_box)
    dialog.exec()

def format_path_for_button(button, path):
    """Format a path to fit in a button, showing prefix and suffix with ellipsis in the middle."""
    if not path:
        return "Select..."

    button_width = button.width()
    # Account for padding and icon:
    # - Icon (16px) + icon margin (8px)
    # - Left padding (12px) + right padding (12px)
    available_width = button_width - 48  
    
    # Approximate pixels per character (using a somewhat conservative estimate)
    char_width = 7
    total_chars = max(10, available_width // char_width)
    
    if len(path) <= total_chars:
        return path
    
    # Reserve 3 characters for the ellipsis
    chars_for_text = total_chars - 3
    # Split remaining space equally between prefix and suffix
    half_chars = chars_for_text // 2
    
    # Always show at least 3 characters on each side
    half_chars = max(3, half_chars)
    
    return f"{path[:half_chars]}...{path[-half_chars:]}"
