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
import re

def infer_raw_file_path(xmp_path):
    """Infer the raw file path from the session XMP file path."""
    # More robustly find the raw file base name, accounting for .ext.xmp patterns
    if xmp_path.lower().endswith(".xmp"):
        raw_file_base = xmp_path[:-4]
    else:
        raw_file_base = os.path.splitext(xmp_path)[0]

    possible_exts = [".nef", ".cr2", ".cr3", ".arw", ".dng", ".raf", ".orf", ".rw2"]

    if any(
        raw_file_base.lower().endswith(x) for x in possible_exts
    ) and os.path.exists(raw_file_base):
        return raw_file_base

    
    # Check for duplicate XMP pattern: <img_name>_<duplicate_number>.<raw_extension>.xmp
    # Example: photo_01.cr2.xmp -> photo.cr2
    duplicate_pattern = re.compile(r'^(.+)_(\d+)\.([^.]+)$')
    match = duplicate_pattern.match(os.path.basename(raw_file_base))
    
    if match:
        # This is a duplicate XMP file
        base_name = match.group(1)  # photo id
        raw_ext = match.group(3)    # extension
        base_dir = os.path.dirname(raw_file_base)
        original_raw_file = os.path.join(base_dir, f"{base_name}.{raw_ext}")
        if os.path.exists(original_raw_file):
            return original_raw_file

    return None
