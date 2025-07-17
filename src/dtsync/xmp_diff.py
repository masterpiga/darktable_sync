from PySide6.QtWidgets import (
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from PySide6.QtCore import Qt


class XMPDiff(QTableWidget):

    def __init__(self):
        super().__init__()
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(["Step", "Module", "+", "-", "P", "M"])
        # Hide row numbers
        self.verticalHeader().setVisible(False)
        # Enable sorting
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        # Set size policies
        self.horizontalHeader().setStretchLastSection(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Set column widths and behaviors
        self.setColumnWidth(0, 50)  # Step
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Module stretches
        # Fixed width for status columns
        for col in range(2, 6):
            self.setColumnWidth(col, 30)
            self.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
        # Center the checkmark columns
        for col in range(2, 6):
            self.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        # Make the table read-only
        self.setEditTriggers(QTableWidget.NoEditTriggers)

    @classmethod
    def get_summary(cls, session_data, archive_data):
        """Return a list of dictionaries containing the changes for each step."""
        session_history = session_data.get("history", {})
        archive_history = archive_data.get("history", {})
        all_keys = set(session_history.keys()) | set(archive_history.keys())
        result = []
        
        for key in sorted(all_keys, key=lambda x: int(x) if x.isdigit() else x):
            s = session_history.get(key)
            a = archive_history.get(key)
            
            diff = {
                'step': key,
                'module': '',
                'added': False,
                'removed': False,
                'params': False,
                'mask': False
            }
            
            if s and not a:
                # Added
                diff['module'] = s.get('operation', str(key))
                diff['added'] = True
            elif not s and a:
                # Removed
                diff['module'] = a.get('operation', str(key))
                diff['removed'] = True
            elif s and a:
                # Modified
                diff['module'] = s.get('operation', str(key))
                if s.get("params") != a.get("params"):
                    diff['params'] = True
                if s.get("masks") != a.get("masks"):
                    diff['mask'] = True
            
            if diff['added'] or diff['removed'] or diff['params'] or diff['mask']:
                result.append(diff)
        
        return result


    def set_contents(self, session_data, archive_data):
        """Populate the diff table with the changes between session and archive data."""

        diffs = self.get_summary(session_data, archive_data)

        # Temporarily disable sorting while populating
        self.setSortingEnabled(False)
        self.setRowCount(0)  # Clear existing rows
        self.setRowCount(len(diffs))
        
        for row, diff in enumerate(diffs):
            # Step number (store as integer for proper sorting)
            step_item = QTableWidgetItem()
            step_item.setData(Qt.DisplayRole, int(diff['step']))  # For display and sorting
            step_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 0, step_item)
            
            # Module name
            module_item = QTableWidgetItem(diff['module'])
            self.setItem(row, 1, module_item)
            
            # Checkmark columns
            for col, flag in enumerate(['added', 'removed', 'params', 'mask']):
                check_item = QTableWidgetItem()
                # Store boolean for sorting, display checkmark
                check_item.setData(Qt.DisplayRole, '✓' if diff[flag] else '')
                check_item.setData(Qt.UserRole, diff[flag])  # For sorting
                check_item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, col + 2, check_item)
        
        # Re-enable sorting
        self.setSortingEnabled(True)
