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

from importlib import resources
import os


def get_icon_path(icon_name):
    try:
        return str(resources.files('resources.icons').joinpath(icon_name))
    except ModuleNotFoundError as e:
        # Fallback for when running outside of a package
        raise FileNotFoundError(
            f"Icon '{icon_name}' not found in resources. Ensure the package is installed correctly."
        ) from e

DARKTABLE_ICON = get_icon_path("darktable.png")
SCAN_ICON = get_icon_path("scan.png")
HORIZONTAL_LAYOUT_ICON = get_icon_path("horizontal_layout.png")
VERTICAL_LAYOUT_ICON = get_icon_path("vertical_layout.png")
ZOOM_ICON = get_icon_path("zoom.png")