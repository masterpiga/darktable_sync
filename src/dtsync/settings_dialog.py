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
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QKeySequenceEdit,
    QFileDialog,
    QCheckBox,
    QLabel,
)
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt
import darktable_detection


class SettingsDialog(QDialog):
    """A modal dialog for application settings."""

    def __init__(self, parent, logic):
        super().__init__(parent)
        self.logic = logic
        self.main_app = parent  # Reference to DarktableSyncApp

        self.setWindowTitle("Preferences")
        self.setMinimumWidth(800)
        self.setModal(True)

        dialog_layout = QVBoxLayout(self)

        # Centering layout
        centering_layout = QHBoxLayout()
        centering_layout.addStretch(1)

        # Main layout for the two columns
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)
        columns_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Left Column ---
        left_column_layout = QVBoxLayout()
        left_column_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- darktable-cli Section ---
        cli_group = QGroupBox("darktable-cli")
        cli_layout = QVBoxLayout(cli_group)
        
        # Path textbox (stretches with container)
        self.darktable_cli_edit = QLineEdit(self.logic.darktable_cli_path)
        self.darktable_cli_edit.textChanged.connect(self.on_cli_path_changed)
        cli_layout.addWidget(QLabel("darktable-cli Path:"))
        cli_layout.addWidget(self.darktable_cli_edit)
        
        # Buttons layout (side by side underneath the textbox)
        buttons_layout = QHBoxLayout()
        self.darktable_cli_btn = QPushButton("Browse...")
        self.darktable_cli_btn.setFixedWidth(90)
        self.darktable_cli_btn.clicked.connect(self.select_darktable_cli)
        
        self.auto_detect_btn = QPushButton("Auto-detect")
        self.auto_detect_btn.setFixedWidth(90)
        self.auto_detect_btn.clicked.connect(self.auto_detect_darktable_cli)
        
        buttons_layout.addWidget(self.darktable_cli_btn)
        buttons_layout.addWidget(self.auto_detect_btn)
        buttons_layout.addStretch()  # Push buttons to the left
        cli_layout.addLayout(buttons_layout)
        
        left_column_layout.addWidget(cli_group)

        # --- Performance Section ---
        perf_group = QGroupBox("Performance")
        perf_form = QFormLayout(perf_group)
        
        self.thread_count_spinbox = QSpinBox()
        self.thread_count_spinbox.setMinimum(1)
        self.thread_count_spinbox.setMaximum(os.cpu_count() * 2 or 16)
        self.thread_count_spinbox.setValue(self.logic.max_threads)
        self.thread_count_spinbox.setFixedWidth(80)
        self.thread_count_spinbox.valueChanged.connect(self.on_thread_count_changed)
        perf_form.addRow("Max Threads:", self.thread_count_spinbox)
        
        left_column_layout.addWidget(perf_group)

        # --- Previews Section ---
        preview_settings_group = QGroupBox("Previews")
        preview_settings_form = QFormLayout(preview_settings_group)
        
        self.preview_max_dimension_spinbox = QSpinBox()
        self.preview_max_dimension_spinbox.setMinimum(100)
        self.preview_max_dimension_spinbox.setMaximum(2000)
        self.preview_max_dimension_spinbox.setFixedWidth(80)
        self.preview_max_dimension_spinbox.setValue(self.logic.preview_max_dimension)
        self.preview_max_dimension_spinbox.valueChanged.connect(self.on_preview_dimension_changed)
        preview_settings_form.addRow("Max Dimension:", self.preview_max_dimension_spinbox)
        
        self.enable_opencl_checkbox = QCheckBox()
        self.enable_opencl_checkbox.setChecked(self.logic.enable_opencl)
        self.enable_opencl_checkbox.stateChanged.connect(self.on_opencl_changed)
        preview_settings_form.addRow("Enable OpenCL:", self.enable_opencl_checkbox)
        
        clear_cache_current_btn = QPushButton("Clear cache for current size")
        clear_cache_current_btn.setFixedWidth(180)
        clear_cache_current_btn.clicked.connect(self.clear_cache_current_size)
        preview_settings_form.addRow("", clear_cache_current_btn)
        
        clear_cache_all_btn = QPushButton("Clear cache for all sizes")
        clear_cache_all_btn.setFixedWidth(180)
        clear_cache_all_btn.clicked.connect(self.clear_cache_all_sizes)
        preview_settings_form.addRow("", clear_cache_all_btn)
        
        left_column_layout.addWidget(preview_settings_group)
        
        # --- Backups Section ---
        backup_group = QGroupBox("Backups")
        backup_form = QFormLayout(backup_group)
        
        self.enable_backups_checkbox = QCheckBox()
        self.enable_backups_checkbox.setChecked(self.logic.enable_backups)
        self.enable_backups_checkbox.stateChanged.connect(self.on_backups_changed)
        backup_form.addRow("Enable backups:", self.enable_backups_checkbox)
        
        left_column_layout.addWidget(backup_group)
        left_column_layout.addStretch(1)
        
        columns_layout.addLayout(left_column_layout)

        # --- Right Column ---
        right_column_layout = QVBoxLayout()
        right_column_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Keyboard Shortcuts Section ---
        shortcuts_group = QGroupBox("Keyboard Shortcuts")
        shortcuts_group.setFixedWidth(300)
        shortcuts_form = QFormLayout(shortcuts_group)
        
        self.shortcut_editors = {}
        
        shortcut_labels = {
            "navigate_up": "Navigate Up:",
            "navigate_down": "Navigate Down:",
            "navigate_prev_undecided": "Previous Undecided:",
            "navigate_next_undecided": "Next Undecided:",
            "action_keep_session": "Keep session:",
            "action_keep_both": "Keep Both:",
            "action_keep_archive": "Keep archive:",
            "action_reset": "Reset to No Action:",
            "zoom_in": "Zoom In:",
            "zoom_out": "Zoom Out:",
            "toggle_orientation": "Toggle Orientation:",
            "scroll_up": "Scroll Up:",
            "scroll_left": "Scroll Left:",
            "scroll_down": "Scroll Down:",
            "scroll_right": "Scroll Right:"
        }
        
        for key, label in shortcut_labels.items():
            editor = QKeySequenceEdit()
            editor.setKeySequence(QKeySequence(self.logic.custom_shortcuts[key]))
            editor.keySequenceChanged.connect(lambda seq, k=key: self.on_shortcut_changed(k, seq))
            self.shortcut_editors[key] = editor
            shortcuts_form.addRow(label, editor)
        
        reset_shortcuts_btn = QPushButton("Reset to Defaults")
        reset_shortcuts_btn.clicked.connect(self.reset_shortcuts_to_defaults)
        shortcuts_form.addRow("", reset_shortcuts_btn)
        
        right_column_layout.addWidget(shortcuts_group)
        right_column_layout.addStretch(1)

        columns_layout.addLayout(right_column_layout)
        
        centering_layout.addLayout(columns_layout)
        centering_layout.addStretch(1)

        dialog_layout.addStretch(1)
        dialog_layout.addLayout(centering_layout)
        dialog_layout.addStretch(1)

    def on_cli_path_changed(self, text):
        self.logic.darktable_cli_path = text
        self.main_app.update_scan_button_state()

    def on_thread_count_changed(self, value):
        self.logic.max_threads = value
        self.main_app.thread_pool.setMaxThreadCount(self.logic.max_threads)
        # Update preview cache manager thread count if available
        if hasattr(self.main_app, 'preview_cache_manager'):
            self.main_app.preview_cache_manager.update_settings(
                self.logic.darktable_cli_path,
                self.logic.preview_max_dimension,
                self.logic.max_threads,
                enable_opencl=self.logic.enable_opencl
            )

    def on_shortcut_changed(self, shortcut_key, key_sequence):
        self.logic.custom_shortcuts[shortcut_key] = key_sequence.toString()
        self.main_app.setup_keyboard_shortcuts()

    def reset_shortcuts_to_defaults(self):
        self.logic.custom_shortcuts = self.logic.default_shortcuts.copy()
        for key, editor in self.shortcut_editors.items():
            editor.setKeySequence(QKeySequence(self.logic.custom_shortcuts[key]))
        self.main_app.setup_keyboard_shortcuts()

    def clear_cache_current_size(self):
        """Clear cache for the current preview size."""
        if hasattr(self.main_app, 'preview_cache_manager'):
            self.main_app.preview_cache_manager.clear_cache_for_dimension(self.logic.preview_max_dimension)
        else:
            print("Warning: Preview cache manager not available")
    
    def clear_cache_all_sizes(self):
        """Clear cache for all preview sizes."""
        if hasattr(self.main_app, 'preview_cache_manager'):
            self.main_app.preview_cache_manager.clear_all_caches()
        else:
            self.logic.clear_preview_cache()

    def select_darktable_cli(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select darktable-cli")
        if path:
            self.darktable_cli_edit.setText(path)
    
    def auto_detect_darktable_cli(self):
        """Auto-detect darktable-cli path and update the text field."""
        try:
            detected_path = darktable_detection.get_default_darktable_cli_path()
            if detected_path:
                self.darktable_cli_edit.setText(detected_path)
            else:
                # Show a message if no path was detected
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Auto-detect",
                    "Could not automatically detect darktable-cli path.\n"
                    "Please use the Browse button to select it manually."
                )
        except Exception as e:
            # Show error message if detection fails
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Auto-detect Error",
                f"An error occurred while trying to detect darktable-cli:\n{str(e)}\n\n"
                "Please use the Browse button to select it manually."
            )

    def on_opencl_changed(self, state):
        """Handle OpenCL setting changes."""
        self.logic.enable_opencl = bool(state)
        
        # Update preview cache manager if available
        if hasattr(self.main_app, 'preview_cache_manager'):
            self.main_app.preview_cache_manager.update_settings(
                self.logic.darktable_cli_path,
                self.logic.preview_max_dimension,
                self.logic.max_threads,
                enable_opencl=self.logic.enable_opencl
            )

    def on_preview_dimension_changed(self, value):
        """Handle preview dimension changes."""
        old_dimension = self.logic.preview_max_dimension
        self.logic.preview_max_dimension = value
        
        # If the dimension actually changed, notify the cache manager
        if old_dimension != value and hasattr(self.main_app, 'preview_cache_manager'):
            self.main_app.preview_cache_manager.clear_cache_for_dimension(old_dimension)
            # The cache manager will be updated with new settings when the dialog closes

    def on_backups_changed(self, state):
        """Handle backup setting changes."""
        self.logic.enable_backups = bool(state)
