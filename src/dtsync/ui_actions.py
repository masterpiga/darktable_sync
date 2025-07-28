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

ALL_ACTIONS: dict[str, "UIAction"] = {}

class UIAction:
    def __init__(self, action_id: str, label: str, default_shortcut: str):
        self.action_id = action_id
        self.label = label
        self.default_shortcut = default_shortcut
        ALL_ACTIONS[self.action_id] = self

PREV_XMP = UIAction(
    "prev_xmp",
    "Previous XMP",
    "Up"
)
NEXT_XMP = UIAction(
    "next_xmp",
    "Next XMP",
    "Down"
)
PREV_UNDECIDED_XMP = UIAction(
    "prev_undecided_xmp",
    "Previous undecided XMP",
    "Left"
)
NEXT_UNDECIDED_XMP = UIAction(
    "next_undecided_xmp",
    "Next undecided XMP",
    "Right"
)
ACTION_KEEP_ARCHIVE = UIAction(
    "action_keep_archive",
    "Keep archive",
    "1"
)
ACTION_KEEP_BOTH = UIAction(
    "action_keep_both",
    "Keep both",
    "2"
)
ACTION_KEEP_SESSION = UIAction(
    "action_keep_session",
    "Keep session",
    "3"
)
ACTION_RESET = UIAction(
    "action_reset",
    "No action",
    "`"
)
ZOOM_IN = UIAction(
    "zoom_in",
    "Zoom in",
    "E"
)
ZOOM_OUT = UIAction(
    "zoom_out",
    "Zoom out",
    "Q"
)
TOGGLE_ORIENTATION = UIAction(
    "toggle_orientation",
    "Toggle orientation",
    "R"
)
TOGGLE_COMPARISON_MODE = UIAction(
    "toggle_comparison_mode",
    "Toggle comparison mode",
    "T"
)
SCROLL_UP = UIAction(
    "scroll_up",
    "Scroll up",
    "W"
)
SCROLL_DOWN = UIAction(
    "scroll_down",
    "Scroll down",
    "S"
)
SCROLL_LEFT = UIAction(
    "scroll_left",
    "Scroll left",
    "A"
)
SCROLL_RIGHT = UIAction(
    "scroll_right",
    "Scroll right",
    "D"
)
INCREASE_SESSION_AREA = UIAction(
    "increase_session_area",
    "Increase session area",
    "Z"
)
DECREASE_SESSION_AREA = UIAction(
    "decrease_session_area",
    "Decrease session area",
    "C"
)
CENTER_PREVIEW_SEPARATOR = UIAction(
    "center_preview_separator",
    "Center preview separator",
    "X"
)