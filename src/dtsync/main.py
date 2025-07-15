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

import sys
from PySide6.QtWidgets import QApplication

import app_ui

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Darktable XMP Sync")
    app.setApplicationVersion("0.1.0")
    main_win = app_ui.DarktableSyncApp()
    main_win.setWindowTitle("Darktable XMP Sync")
    main_win.show()
    sys.exit(app.exec())
