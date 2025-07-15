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

from PySide6.QtCore import Qt

class NavigationLogic:
    def __init__(self, file_tree_model, file_tree_view, actions, get_current_selected_path_callback, on_file_tree_item_selected_callback):
        self.file_tree_model = file_tree_model
        self.file_tree_view = file_tree_view
        self.actions = actions
        self.get_current_selected_path = get_current_selected_path_callback
        self.on_file_tree_item_selected = on_file_tree_item_selected_callback

    def find_first_file_item(self, parent_item):
        """Find the first file item in the tree."""
        for row in range(parent_item.rowCount()):
            child = parent_item.child(row)
            if child.data(Qt.ItemDataRole.UserRole) is not None:
                return child
            if child.hasChildren():
                found = self.find_first_file_item(child)
                if found:
                    return found
        return None

    def find_next_file_item(self, current_index):
        """Find the next file item after the current index."""
        if not current_index.isValid():
            return None
            
        model = self.file_tree_model
        current_item = model.itemFromIndex(current_index)
        
        all_items = []
        self.collect_file_items(model.invisibleRootItem(), all_items)
        
        try:
            current_pos = all_items.index(current_item)
            if current_pos + 1 < len(all_items):
                return model.indexFromItem(all_items[current_pos + 1])
        except ValueError:
            pass
        return None

    def find_previous_file_item(self, current_index):
        """Find the previous file item before the current index."""
        if not current_index.isValid():
            return None
            
        model = self.file_tree_model
        current_item = model.itemFromIndex(current_index)
        
        all_items = []
        self.collect_file_items(model.invisibleRootItem(), all_items)
        
        try:
            current_pos = all_items.index(current_item)
            if current_pos > 0:
                return model.indexFromItem(all_items[current_pos - 1])
        except ValueError:
            pass
        return None

    def find_last_file_item(self):
        """Find the last file item in the tree."""
        all_items = []
        self.collect_file_items(self.file_tree_model.invisibleRootItem(), all_items)
        if all_items:
            return self.file_tree_model.indexFromItem(all_items[-1])
        return None

    def collect_file_items(self, parent_item, items_list):
        """Recursively collect all file items (items with UserRole data) in order."""
        for row in range(parent_item.rowCount()):
            child = parent_item.child(row)
            if child.data(Qt.ItemDataRole.UserRole) is not None:
                items_list.append(child)
            if child.hasChildren():
                self.collect_file_items(child, items_list)

    def find_undecided_item(self, start_index, forward=True):
        """Find the next/previous undecided item starting from start_index."""
        if not start_index or not start_index.isValid():
            return None
            
        model = self.file_tree_model
        all_items = []
        self.collect_file_items(model.invisibleRootItem(), all_items)
        
        start_item = model.itemFromIndex(start_index)
        try:
            start_pos = all_items.index(start_item)
        except ValueError:
            return None
        
        search_range = range(start_pos, len(all_items)) if forward else range(start_pos, -1, -1)
        
        for pos in search_range:
            item = all_items[pos]
            rel_path = item.data(Qt.ItemDataRole.UserRole)
            if rel_path and self.actions.get(rel_path, 0) == 0:
                return model.indexFromItem(item)
        
        return None

    def navigate_down(self):
        """Navigate to the next item in the XMP list."""
        self.file_tree_view.setFocus()
        current_index = self.file_tree_view.currentIndex()
        if not current_index.isValid():
            root_item = self.file_tree_model.invisibleRootItem()
            first_file_item = self.find_first_file_item(root_item)
            if first_file_item:
                index = self.file_tree_model.indexFromItem(first_file_item)
                self.file_tree_view.setCurrentIndex(index)
                self.on_file_tree_item_selected(index)
            return
        
        next_item = self.find_next_file_item(current_index)
        if next_item:
            self.file_tree_view.setCurrentIndex(next_item)
            self.on_file_tree_item_selected(next_item)

    def navigate_up(self):
        """Navigate to the previous item in the XMP list."""
        self.file_tree_view.setFocus()
        current_index = self.file_tree_view.currentIndex()
        if not current_index.isValid():
            return
            
        prev_item = self.find_previous_file_item(current_index)
        if prev_item:
            self.file_tree_view.setCurrentIndex(prev_item)
            self.on_file_tree_item_selected(prev_item)

    def navigate_next_undecided(self):
        """Navigate to the next undecided item."""
        self.file_tree_view.setFocus()
        current_index = self.file_tree_view.currentIndex()
        start_item = self.find_next_file_item(current_index) if current_index.isValid() else None
        
        if not start_item:
            root_item = self.file_tree_model.invisibleRootItem()
            start_item = self.file_tree_model.indexFromItem(self.find_first_file_item(root_item))
        
        undecided_item = self.find_undecided_item(start_item, forward=True)
        if undecided_item:
            self.file_tree_view.setCurrentIndex(undecided_item)
            self.on_file_tree_item_selected(undecided_item)

    def navigate_previous_undecided(self):
        """Navigate to the previous undecided item."""
        self.file_tree_view.setFocus()
        current_index = self.file_tree_view.currentIndex()
        start_item = self.find_previous_file_item(current_index) if current_index.isValid() else None
        
        if not start_item:
            start_item = self.find_last_file_item()
        
        undecided_item = self.find_undecided_item(start_item, forward=False)
        if undecided_item:
            self.file_tree_view.setCurrentIndex(undecided_item)
            self.on_file_tree_item_selected(undecided_item)
