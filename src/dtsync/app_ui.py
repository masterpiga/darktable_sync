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
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QTreeView,
    QLabel,
    QScrollArea,
    QSplitter,
    QGroupBox,
    QCheckBox,
    QDialog,
    QStyle,
    QSizePolicy,
    QTableWidget,
    QHeaderView,
    QGridLayout,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QCloseEvent, QIcon, QShortcut, QKeySequence
from PySide6.QtCore import Qt, QThreadPool, QThread, QSize, QTimer

import scanner
import action
import preview
import icons
from app_logic import AppLogic
from navigation import NavigationLogic
from preview_cache_manager import PreviewCacheManager
import ui_components
import path_utils
import xmp_diff
from settings_dialog import SettingsDialog


class DarktableSyncApp(QMainWindow):
    """The main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("darktable XMP Sync Tool")
        self.setGeometry(100, 100, 1400, 900)

        self.logic = AppLogic()

        # --- Data storage ---
        self.diff_files = {}
        self.actions = {}
        
        # Store shortcut references for clearing
        self.active_shortcuts = []

        # --- Threading ---
        self.thread_pool = QThreadPool()
        self.scan_thread = None
        self.scanner_worker = None

        # --- Main Widget and Layout ---
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Menu Bar ---
        menu_bar = self.menuBar()
        # On macOS, the menu bar is native and may not appear in the window
        menu_bar.setNativeMenuBar(True) 
        
        file_menu = menu_bar.addMenu("&File")
        
        settings_action = file_menu.addAction("Settings...")
        settings_action.setShortcut(QKeySequence.Preferences)
        settings_action.triggered.connect(self.open_settings_dialog)
        
        file_menu.addSeparator()
        
        quit_action = file_menu.addAction("Quit")
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)

        # --- Main View: Splitter ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.splitterMoved.connect(self.on_splitter_moved)
        main_layout.addWidget(main_splitter, 1)

        # --- Left Panel: File List + Change Summary (Vertical) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        # Input selection group (new)
        input_group = QGroupBox("Input selection")
        input_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Don't stretch vertically
        input_layout = QHBoxLayout(input_group)
        input_layout.setSpacing(8)
        # Left: vertical stack for directory selectors with labels
        dir_selectors_layout = QGridLayout()
        dir_selectors_layout.setVerticalSpacing(8)
        dir_selectors_layout.setHorizontalSpacing(8)
        # Archive Directory
        archive_label = QLabel("Archive directory:")
        archive_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)  # Don't stretch
        self.archive_dir_btn = QPushButton()
        self.archive_dir_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.archive_dir_btn.setIconSize(QSize(16, 16))  # Ensure consistent icon size
        self.archive_dir_btn.setToolTip("Select Archive Directory")
        self.archive_dir_btn.setMinimumWidth(180)
        self.archive_dir_btn.setFixedHeight(32)
        self.archive_dir_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Stretch horizontally
        self.archive_dir_btn.clicked.connect(
            lambda: self.select_directory("archive")
        )
        # Button text will be set after settings are loaded
        dir_selectors_layout.addWidget(archive_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        dir_selectors_layout.addWidget(self.archive_dir_btn, 0, 1)
        # Session Directory
        session_label = QLabel("Session directory:")
        session_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)  # Don't stretch
        self.session_dir_btn = QPushButton()
        self.session_dir_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.session_dir_btn.setIconSize(QSize(16, 16))  # Ensure consistent icon size
        self.session_dir_btn.setToolTip("Select Session Directory")
        self.session_dir_btn.setMinimumWidth(180)
        self.session_dir_btn.setFixedHeight(32)
        self.session_dir_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Stretch horizontally
        self.session_dir_btn.clicked.connect(lambda: self.select_directory("session"))
        # Button text will be set after settings are loaded
        dir_selectors_layout.addWidget(session_label, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        dir_selectors_layout.addWidget(self.session_dir_btn, 1, 1)

        # Scan button
        self.compare_dirs_btn = QPushButton()
        self.compare_dirs_btn.setIcon(QIcon(icons.SCAN_ICON))
        self.compare_dirs_btn.setText("Scan")
        self.compare_dirs_btn.setToolTip("Scan for differing XMP files in the selected directories")
        self.compare_dirs_btn.clicked.connect(self.toggle_scan)

        dir_selectors_layout.addWidget(self.compare_dirs_btn, 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
        
        # Add scan results label under the scan button
        self.scan_results_label = QLabel()
        self.scan_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scan_results_label.setStyleSheet("color: #666; font-size: 11px;")
        self.scan_results_label.setVisible(False)  # Initially hidden
        dir_selectors_layout.addWidget(self.scan_results_label, 3, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        
        input_layout.addLayout(dir_selectors_layout)
        left_layout.addWidget(input_group)
        # XMP diffs group (wrap file list and planned actions)
        self.xmp_diffs_group = QGroupBox("XMPs with differences")
        self.xmp_diffs_group.setEnabled(False)  # Initially disabled
        xmp_diffs_layout = QVBoxLayout(self.xmp_diffs_group)
        # File List (TreeView in ScrollArea)
        file_tree_scroll = QScrollArea()
        file_tree_scroll.setWidgetResizable(True)
        self.file_tree_view = QTreeView()
        self.file_tree_model = QStandardItemModel()
        self.file_tree_view.setModel(self.file_tree_model)
        self.file_tree_view.setHeaderHidden(True)
        self.file_tree_view.clicked.connect(self.on_file_tree_item_selected)
        file_tree_scroll.setWidget(self.file_tree_view)
        xmp_diffs_layout.addWidget(file_tree_scroll, 1)
        # Simplified filter row
        filter_layout = QHBoxLayout()
        filter_layout.addStretch()
        filter_layout.addWidget(QLabel("Include:"))
        
        self.decided_checkbox = QCheckBox("Decided")
        self.decided_checkbox.setChecked(True)
        self.decided_checkbox.stateChanged.connect(self.update_file_tree_view)
        filter_layout.addWidget(self.decided_checkbox)
        
        self.undecided_checkbox = QCheckBox("Undecided")
        self.undecided_checkbox.setChecked(True)
        self.undecided_checkbox.stateChanged.connect(self.update_file_tree_view)
        filter_layout.addWidget(self.undecided_checkbox)
        
        xmp_diffs_layout.addLayout(filter_layout)
        left_layout.addWidget(self.xmp_diffs_group)
        
        # Action names for labels (still needed for display)
        self.action_names = [
            "No action",
            "Keep archive",
            "Keep session",
            "Keep both",
        ]
        
        # --- Selected XMP group (replaces combobox) ---
        self.action_group = QGroupBox("Selected XMP")
        self.action_group.setEnabled(False)  # Initially disabled until a file is selected
        action_grid = QGridLayout(self.action_group)
        # --- Selected XMP label ---
        self.selected_xmp_label = QLabel()
        self.selected_xmp_label.setText("No file selected")
        self.selected_xmp_label.setEnabled(False)
        self.selected_xmp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_xmp_label.setStyleSheet("font-weight: bold")
        action_grid.addWidget(self.selected_xmp_label, 0, 0, 1, 2)
        # --- History diff group (was Diffs in selected XMP) ---
        self.history_diff_group = QGroupBox("Edit history diff")
        history_diff_layout = QVBoxLayout(self.history_diff_group)
        history_diff_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to use full width
        diff_table_scroll = QScrollArea()
        diff_table_scroll.setWidgetResizable(True)
        self.diff_table = xmp_diff.XMPDiff()
        diff_table_scroll.setWidget(self.diff_table)
        history_diff_layout.addWidget(diff_table_scroll, 1)
        # Place history diff group in its own row
        action_grid.addWidget(self.history_diff_group, 1, 0, 1, 2)

        # --- Selected action group ---
        selected_action_group = QGroupBox("Planned action")
        selected_action_layout = QGridLayout(selected_action_group)

        self.action_buttons = []
        action_labels = [
            "Keep archive",
            "Keep session",
            "Keep both",
        ]
        # Updated action_button_to_action_id mapping to match the new order
        self.action_button_to_action_id = [1, 2, 3]
        for i, label in enumerate(action_labels):
            btn = QPushButton(label)
            btn.setEnabled(False)
            btn.clicked.connect(lambda _, idx=i: self.on_action_button_clicked(idx))
            self.action_buttons.append(btn)
            if i < 2:
                # Place the first two buttons in the next row, side by side
                selected_action_layout.addWidget(btn, 0, i)
            else:
                # Place the 'Keep both' button in the row after, spanning both columns
                selected_action_layout.addWidget(btn, 1, 0, 1, 2)
        
        action_grid.addWidget(selected_action_group, 2, 0, 1, 2)

        left_layout.addWidget(self.action_group)
        # --- Dry run and execute planned actions at bottom, right aligned ---
        bottom_btn_row = QHBoxLayout()
        bottom_btn_row.addStretch(1)
        self.dry_run_checkbox = QCheckBox("Dry run")
        self.dry_run_checkbox.setChecked(True)
        bottom_btn_row.addWidget(self.dry_run_checkbox)
        self.apply_btn = QPushButton("Execute planned actions")
        self.apply_btn.clicked.connect(self.apply_changes)
        self.apply_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        bottom_btn_row.addWidget(self.apply_btn)
        left_layout.addLayout(bottom_btn_row)
        # Ensure left_panel is added to the splitter as the first widget
        main_splitter.insertWidget(0, left_panel)

        # --- Right Panel: Previews and Toolbar ---
        # Preview manager will be initialized after loading settings
        
        main_splitter.addWidget(QWidget())  # Temporary placeholder

        main_splitter.setSizes([400, 1000])
        self.load_settings()
        
        # Initialize preview manager after settings are loaded
        self.preview_manager = preview.PreviewManager(
            self.logic.preview_max_dimension
        )
        self.preview_manager.set_current_path_callback(self.get_current_selected_path)
        self.preview_manager.set_focus_callback(lambda: self.file_tree_view.setFocus())
        
        # Setup compare in darktable functionality
        self.preview_manager.setup_compare_signals(self)
        
        # Initialize preview cache manager
        self.preview_cache_manager = PreviewCacheManager(self)
        self.preview_cache_manager.update_settings(
            self.logic.darktable_cli_path,
            self.logic.preview_max_dimension,
            self.logic.max_threads,
            enable_opencl=self.logic.enable_opencl
        )
        
        # Connect cache manager to preview manager for coordination
        self.preview_manager.cache_manager = self.preview_cache_manager
        
        # Initialize preview signals and connect them to preview manager
        self.preview_cache_manager._initialize_signals()
        if self.preview_cache_manager.preview_signals:
            # Connect preview ready/failed signals to preview manager UI
            self.preview_cache_manager.preview_signals.preview_ready.connect(
                self.preview_manager.on_preview_ready
            )
            self.preview_cache_manager.preview_signals.preview_failed.connect(
                self.preview_manager.on_preview_failed
            )
        else:
            print("Warning: Preview cache manager signals not available")
        
        # Replace the placeholder with the preview manager
        main_splitter.replaceWidget(1, self.preview_manager)
        self.update_scan_button_state()
        # Ensure action filter labels are initialized and visible
        self.update_file_tree_view()
        # --- Connect zoom callbacks for pinch-to-zoom ---
        # These are now handled within the PreviewManager

        # Setup navigation logic
        self.navigation = NavigationLogic(self.file_tree_model, self.file_tree_view, self.actions, self.get_current_selected_path, self.on_file_tree_item_selected)

        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
        # Set initial state of the apply button
        self.update_apply_button_state()

    def open_settings_dialog(self):
        """Open the settings dialog."""
        dialog = SettingsDialog(self, self.logic)
        if dialog.exec():
            # Update preview cache manager settings (the only place generating previews)
            self.preview_cache_manager.update_settings(
                self.logic.darktable_cli_path,
                self.logic.preview_max_dimension,
                self.logic.max_threads,
                enable_opencl=self.logic.enable_opencl
            )
            # Update preview manager display settings
            self.preview_manager.update_preview_dimension(self.logic.preview_max_dimension)
            # Update thread pool
            self.thread_pool.setMaxThreadCount(self.logic.max_threads)
        self.logic.save_settings()
        print("Preferences saved.")
        # After closing dialog, update UI elements that might have changed
        self.update_directory_buttons()
        self.update_scan_button_state()

    def update_apply_button_state(self):
        """Update the 'Execute planned actions' button state, text, and style."""
        planned_actions_count = sum(1 for action_id in self.actions.values() if action_id != 0)

        if planned_actions_count > 0:
            self.apply_btn.setEnabled(True)
            self.apply_btn.setText(f"Execute planned actions ({planned_actions_count})")
        else:
            self.apply_btn.setEnabled(False)
            self.apply_btn.setText("Execute planned actions")

    def setup_keyboard_shortcuts(self):
        """Create and connect all keyboard shortcuts."""
        # Clear any existing shortcuts to avoid duplicates
        for shortcut in self.active_shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self.active_shortcuts.clear()

        # Helper to create and store a shortcut
        def add_shortcut(key, function):
            sequence = QKeySequence(self.logic.custom_shortcuts.get(key, ""))
            if not sequence.isEmpty():
                shortcut = QShortcut(sequence, self)
                shortcut.activated.connect(function)
                self.active_shortcuts.append(shortcut)

        # Navigation
        add_shortcut("navigate_up", self.navigation.navigate_up)
        add_shortcut("navigate_down", self.navigation.navigate_down)
        add_shortcut("navigate_prev_undecided", self.navigation.navigate_previous_undecided)
        add_shortcut("navigate_next_undecided", self.navigation.navigate_next_undecided)

        # Actions
        add_shortcut("action_reset", lambda: self.trigger_action_by_id(0))
        add_shortcut("action_keep_ref", lambda: self.trigger_action_by_id(1))
        add_shortcut("action_keep_work", lambda: self.trigger_action_by_id(2))
        add_shortcut("action_keep_both", lambda: self.trigger_action_by_id(3))

        # Previews
        add_shortcut("zoom_in", self.preview_manager.zoom_in_preview)
        add_shortcut("zoom_out", self.preview_manager.zoom_out_preview)
        add_shortcut("toggle_orientation", self.preview_manager.toggle_preview_orientation)
        add_shortcut("scroll_up", self.preview_manager.scroll_preview_up)
        add_shortcut("scroll_down", self.preview_manager.scroll_preview_down)
        add_shortcut("scroll_left", self.preview_manager.scroll_preview_left)
        add_shortcut("scroll_right", self.preview_manager.scroll_preview_right)

    def update_action_filter_counts(self):
        """Update the action filter checkbox labels with current counts."""
        undecided_count = 0
        decided_count = 0
        for rel_path in self.diff_files:
            action_id = self.actions.get(rel_path, 0)
            if action_id == 0:
                undecided_count += 1
            else:
                decided_count += 1
        
        self.undecided_checkbox.blockSignals(True)
        self.undecided_checkbox.setText(f"undecided ({undecided_count} file{'s' if undecided_count != 1 else ''})")
        self.undecided_checkbox.blockSignals(False)
        
        self.decided_checkbox.blockSignals(True)
        self.decided_checkbox.setText(f"decided ({decided_count} file{'s' if decided_count != 1 else ''})")
        self.decided_checkbox.blockSignals(False)

    def closeEvent(self, event: QCloseEvent):
        """Save settings and stop threads when the application is closed."""
        if self.scanner_worker:
            self.scanner_worker.stop()
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.quit()
            self.scan_thread.wait()
        self.thread_pool.clear()  # Clears queued runnables
        self.thread_pool.waitForDone()
        self.logic.save_settings()
        event.accept()



    def load_settings(self):
        """Load application settings from file and update UI."""
        self.logic.load_settings()
        self.thread_pool.setMaxThreadCount(self.logic.max_threads)
        
        self.update_directory_buttons()
        QTimer.singleShot(0, self.update_directory_buttons)
        
        self.update_scan_button_state()

    def select_directory(self, dir_type):
        dir_path = QFileDialog.getExistingDirectory(
            self, f"Select {dir_type.capitalize()} Directory"
        )
        if dir_path:
            if dir_type == "session":
                self.logic.session_dir = dir_path
            elif dir_type == "archive":
                self.logic.archive_dir = dir_path
            self.update_directory_buttons()
            self.update_scan_button_state()

    def update_scan_button_state(self):
        can_scan = (
            self.logic.session_dir
            and self.logic.archive_dir
            and os.path.isfile(self.logic.darktable_cli_path)
        )
        is_scanning = bool(self.scan_thread and self.scan_thread.isRunning())
        # Only disable if a scan is running
        self.compare_dirs_btn.setEnabled(can_scan or is_scanning)

    def clear_scan_thread(self):
        """Clear the reference to the scan thread after it has finished."""
        self.scan_thread = None

    def start_scan(self):
        self.file_tree_model.clear()
        self.diff_files.clear()
        self.actions.clear()
        
        # Hide scan results label and disable XMP diffs group during scan
        self.scan_results_label.setVisible(False)
        self.xmp_diffs_group.setEnabled(False)

        # Parent the QThread to self to ensure its lifetime is managed correctly
        self.scan_thread = QThread(self)
        self.scanner_worker = scanner.ScannerWorker(
            self.logic.session_dir, self.logic.archive_dir
        )
        self.scanner_worker.moveToThread(self.scan_thread)

        self.scanner_worker.file_diff_found.connect(self.add_diff_file_to_tree)

        self.scanner_worker.scan_finished.connect(self.on_scan_finished)
        # When the worker is done, quit the thread
        self.scanner_worker.finished.connect(self.scan_thread.quit)
        self.scanner_worker.finished.connect(self.scanner_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self.clear_scan_thread)

        self.scan_thread.started.connect(self.scanner_worker.run)

        self.scan_thread.start()

    def on_scan_finished(self):
        """Handles UI updates when the scan is complete."""
        message = f"Scan complete. Found {len(self.diff_files)} differing files."
        # Restore scan button icon and clear text
        self.update_scan_button_state()
        print(message)
        
        # Update scan results label
        diff_count = len(self.diff_files)
        if diff_count == 0:
            self.scan_results_label.setText("No differing files found")
            self.xmp_diffs_group.setEnabled(False)
        else:
            self.scan_results_label.setText(f"{diff_count} differing file{'s' if diff_count != 1 else ''} found")
            self.xmp_diffs_group.setEnabled(True)
        self.scan_results_label.setVisible(True)
        
        # Set all actions to 0 (No action) for all diff_files
        for rel_path in self.diff_files:
            self.actions[rel_path] = 0
        self.update_file_tree_view()  # Refresh file list and counts after scan
        
        # Start background preview generation for all diff files
        self.preview_cache_manager.set_diff_files(self.diff_files)
        
        # Select the first item automatically if any diffs were found
        if self.diff_files:
            root_item = self.file_tree_model.invisibleRootItem()
            first_file_item = self.navigation.find_first_file_item(root_item)
            if first_file_item:
                index = self.file_tree_model.indexFromItem(first_file_item)
                self.file_tree_view.setCurrentIndex(index)
                self.on_file_tree_item_selected(index)
        self.update_apply_button_state()
        # After scan, if nothing is selected, ensure UI is disabled
        if not self.get_current_selected_path():
            self.action_group.setEnabled(False)
            self.selected_xmp_label.setEnabled(False)
            self.selected_xmp_label.setText("No file selected")
            self.history_diff_group.setEnabled(False)
            self.preview_manager.set_enabled(False)

    def update_file_tree_view(self):
        """Rebuild the file tree view based on current filters, preserving selection."""
        # Preserve the currently selected path
        selected_path = self.get_current_selected_path()

        # Update action filter counts
        self.update_action_filter_counts()

        # Clear and repopulate the file tree based on checked actions
        self.file_tree_model.clear()
        show_decided = self.decided_checkbox.isChecked()
        show_undecided = self.undecided_checkbox.isChecked()

        item_to_reselect = None

        for relative_path in sorted(self.diff_files.keys()):
            action_id = self.actions.get(relative_path, 0)
            should_show = False
            if action_id == 0 and show_undecided:
                should_show = True
            elif action_id != 0 and show_decided:
                should_show = True
            
            if should_show:
                file_item = self.add_diff_file_to_tree(relative_path, self.diff_files[relative_path], filter_mode=True)
                if file_item and relative_path == selected_path:
                    item_to_reselect = file_item

        self.file_tree_view.expandAll()

        # Reselect the item if it's still visible
        if item_to_reselect:
            index = self.file_tree_model.indexFromItem(item_to_reselect)
            self.file_tree_view.setCurrentIndex(index)
        
        self.update_apply_button_state()

    def add_diff_file_to_tree(self, relative_path, diff_info, filter_mode=False):
        """Add a file to the tree view, creating parent folders as needed."""
        # If called from update_file_tree_view, don't add duplicates
        if not filter_mode:
            self.diff_files[relative_path] = diff_info

        root_item = self.file_tree_model.invisibleRootItem()
        path_components = Path(relative_path).parts
        parent_item = root_item

        for part in path_components[:-1]:
            found = False
            for row in range(parent_item.rowCount()):
                child_item = parent_item.child(row)
                if child_item and child_item.text() == part:
                    parent_item = child_item
                    found = True
                    break
            if not found:
                new_parent = QStandardItem(part)
                new_parent.setEditable(False)
                # Add folder icon
                folder_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
                new_parent.setIcon(folder_icon)
                parent_item.appendRow(new_parent)
                parent_item = new_parent

        filename = path_components[-1]
        action_id = self.actions.get(relative_path, 0)
        label = filename
        if action_id != 0:
            label += f" [" + self.action_names[action_id] + "]"

        file_item = QStandardItem(label)
        file_item.setEditable(False)
        file_item.setData(relative_path, Qt.ItemDataRole.UserRole)
        # Add file icon
        file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        file_item.setIcon(file_icon)
        parent_item.appendRow(file_item)
        return file_item

    def on_file_tree_item_selected(self, index):
        item = self.file_tree_model.itemFromIndex(index)
        relative_path = item.data(Qt.ItemDataRole.UserRole)
        if relative_path and relative_path in self.diff_files:
            action_id = self.actions.get(relative_path, 0)
            self.preview_manager.update_preview_label_styles(action_id)
            # Enable action buttons and highlight selected
            for i, btn in enumerate(self.action_buttons):
                btn.setEnabled(True)
                action_id = self.action_button_to_action_id[i]
                btn.setDefault(self.actions.get(relative_path, 0) == action_id)
            self.display_diff_details(relative_path)
            # Enable action group, label, and preview group
            self.action_group.setEnabled(True)
            self.selected_xmp_label.setEnabled(True)
            self.selected_xmp_label.setText(f"{os.path.basename(relative_path)}")
            self.history_diff_group.setEnabled(True)
            self.preview_manager.set_enabled(True)
        else:
            for btn in self.action_buttons:
                btn.setEnabled(False)
                btn.setDefault(False)
            self.preview_manager.archive_preview.image_label.setText("Select an image to see preview")
            self.preview_manager.session_preview.image_label.setText("Select an image to see preview")
            self.diff_table.setRowCount(0)
            # Disable action group, label, and preview group
            self.action_group.setEnabled(False)
            self.selected_xmp_label.setEnabled(False)
            self.selected_xmp_label.setText("No file selected")
            self.history_diff_group.setEnabled(False)
            self.preview_manager.set_enabled(False)
            self.preview_manager.update_preview_label_styles(0)
            # Clear compare button paths
            self.preview_manager.update_current_paths(None, None)

    def toggle_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scanner_worker.stop()
            self.compare_dirs_btn.setText("Stopping...")
            self.compare_dirs_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
            self.compare_dirs_btn.setEnabled(False)
        else:
            self.start_scan()

    def get_current_selected_path(self):
        """Get the path of the currently selected item."""
        current_index = self.file_tree_view.currentIndex()
        if not current_index.isValid():
            return None
        item = self.file_tree_model.itemFromIndex(current_index)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

 
    def display_diff_details(self, relative_path):
        self.preview_manager.session_preview.image_label.setText("Queued...")
        self.preview_manager.archive_preview.image_label.setText("Queued...")
        self.diff_table.setRowCount(0)

        file_info = self.diff_files.get(relative_path)
        if not file_info:
            return

        self.diff_table.set_contents(file_info["session_data"], file_info["archive_data"])

        session_path = file_info["session_path"]

        raw_file = path_utils.infer_raw_file_path(session_path)

        if not raw_file:
            self.preview_manager.session_preview.image_label.setText("Raw file not found")
            self.preview_manager.archive_preview.image_label.setText("Raw file not found")
        else:
            archive_path = file_info["archive_path"]
            session_hash = (
                file_info["session_data"]
                .get("top_level_attrs", {})
                .get("history_current_hash")
            )
            archive_hash = (
                file_info["archive_data"]
                .get("top_level_attrs", {})
                .get("history_current_hash")
            )

            self.preview_manager.generate_previews(
                relative_path, raw_file, session_path, archive_path, session_hash, archive_hash
            )
            
            # Update paths for compare functionality
            self.preview_manager.update_current_paths(session_path, archive_path)

    def apply_changes(self):
        if not self.actions or all(v == 0 for v in self.actions.values()):
            ui_components.show_error_message(self, "No actions selected.", "Info")
            return
        
        self.logic.diff_files = self.diff_files
        self.logic.actions = self.actions
        commands = self.logic.get_apply_changes_commands()

        dry_run = self.dry_run_checkbox.isChecked()
        dialog = action.ActionDialog(commands, dry_run, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and not dry_run:
            self.start_scan()

    def on_action_button_clicked(self, btn_idx):
        """Handle action button click by updating the action but maintaining current selection."""
        rel_path = self.get_current_selected_path()
        if rel_path and rel_path in self.diff_files:
            action_id = self.action_button_to_action_id[btn_idx]
            self.actions[rel_path] = action_id
            self.preview_manager.update_preview_label_styles(action_id)
            # Update button highlighting
            for i, btn in enumerate(self.action_buttons):
                btn.setDefault(self.action_button_to_action_id[i] == action_id)
            # Update the item's label in the tree view without changing selection
            current_item = self.file_tree_model.itemFromIndex(self.file_tree_view.currentIndex())
            if current_item:
                label = os.path.basename(rel_path)
                if action_id != 0:
                    label += f" [{self.action_names[action_id]}]"
                current_item.setText(label)
            # Update action filter counts
            self.update_action_filter_counts()
            self.update_apply_button_state()

    def trigger_action_by_id(self, action_id):
        """Trigger an action for the selected file using its ID."""
        rel_path = self.get_current_selected_path()
        if rel_path and rel_path in self.diff_files:
            self.actions[rel_path] = action_id
            self.preview_manager.update_preview_label_styles(action_id)
            self.update_file_tree_view()
            self.update_apply_button_state()
            # Re-select to update button states
            current_index = self.file_tree_view.currentIndex()
            if current_index.isValid():
                self.on_file_tree_item_selected(current_index)

    def on_splitter_moved(self, pos, index):
        """Handle splitter movement to update button text."""
        self.update_directory_buttons()

    def showEvent(self, event):
        """Handle initial window show event."""
        super().showEvent(event)
        # Update button states after the window is shown and has proper sizes
        self.update_directory_buttons()

    def resizeEvent(self, event):
        """Handle window resize event to update button text."""
        super().resizeEvent(event)
        self.update_directory_buttons()

    def update_directory_buttons(self):
        """Update the directory button states (icon, text, tooltip)."""
        # Ensure buttons exist and are visible
        if not hasattr(self, 'archive_dir_btn') or not self.isVisible():
            return

        # Force buttons to update their size hints
        self.archive_dir_btn.updateGeometry()
        self.session_dir_btn.updateGeometry()

        # Update archive button
        self.archive_dir_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.archive_dir_btn.setIconSize(QSize(16, 16))
        self.archive_dir_btn.setText(ui_components.format_path_for_button(self.archive_dir_btn, self.logic.archive_dir))
        self.archive_dir_btn.setToolTip(
            self.logic.archive_dir if self.logic.archive_dir else "Select Archive Directory"
        )

        # Update session button
        self.session_dir_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.session_dir_btn.setIconSize(QSize(16, 16))
        self.session_dir_btn.setText(ui_components.format_path_for_button(self.session_dir_btn, self.logic.session_dir))
        self.session_dir_btn.setToolTip(
            self.logic.session_dir if self.logic.session_dir else "Select Session Directory"
        )
    
    def refresh_previews_after_compare(self, archive_path, session_path, archive_changed, session_changed):
        """Refresh previews after XMP files have been modified in darktable."""
        # Get current selection
        current_selected_path = self.get_current_selected_path()
        if not current_selected_path:
            return
            
        # Find the corresponding file_info
        file_info = self.diff_files.get(current_selected_path)
        if not file_info:
            return
        
        # Check if the modified paths match the currently selected file
        file_matches = (file_info["session_path"] == session_path or 
                       file_info["archive_path"] == archive_path)
        
        if file_matches:
            # Re-extract XMP data if files have changed
            if archive_changed or session_changed:
                try:
                    from scanner import extract_darktable_data
                    if session_changed:
                        file_info["session_data"] = extract_darktable_data(file_info["session_path"])
                        
                    if archive_changed:
                        file_info["archive_data"] = extract_darktable_data(file_info["archive_path"])
                    
                    # Update the diff_files with the new data
                    self.diff_files[current_selected_path] = file_info
                    
                except Exception as e:
                    print(f"Error re-extracting XMP data: {e}")
            
            # Clear cache for this specific file to force regeneration
            self.preview_cache_manager.clear_cache_for_file(
                current_selected_path, 
                file_info["session_path"], 
                file_info["archive_path"]
            )
            
            # Only clear and show regenerating message for the changed previews
            if session_changed:
                self.preview_manager.session_preview.image_label.clear()
                self.preview_manager.session_preview.image_label.setText("Regenerating...")
            
            if archive_changed:
                self.preview_manager.archive_preview.image_label.clear()
                self.preview_manager.archive_preview.image_label.setText("Regenerating...")
            
            # If neither changed, don't regenerate anything
            if not session_changed and not archive_changed:
                return
                
            # Update the diff table with the new XMP data
            self.diff_table.set_contents(file_info["session_data"], file_info["archive_data"])
            
            # Only regenerate previews for the files that actually changed
            if session_changed or archive_changed:
                # Get the raw file path for preview generation
                session_path = file_info["session_path"]
                archive_path = file_info["archive_path"]
                
                # Use the infer_raw_file_path method to find the raw file
                raw_file = path_utils.infer_raw_file_path(session_path)

                if raw_file:
                    # Get hashes for preview generation
                    session_hash = file_info["session_data"].get("top_level_attrs", {}).get("history_current_hash")
                    archive_hash = file_info["archive_data"].get("top_level_attrs", {}).get("history_current_hash")
                    
                    # Generate previews selectively using cache manager
                    if session_changed:
                        self.preview_cache_manager.request_single_preview_generation(
                            current_selected_path, raw_file, session_path, "session", session_hash
                        )
                    
                    if archive_changed:
                        self.preview_cache_manager.request_single_preview_generation(
                            current_selected_path, raw_file, archive_path, "archive", archive_hash
                        )