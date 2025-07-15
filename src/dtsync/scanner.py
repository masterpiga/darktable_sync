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
from lxml import etree
from PySide6.QtCore import QObject, Signal

# --- Constants for XML Parsing ---
# We will ignore volatile attributes by their local name, making it namespace-agnostic.
IGNORED_DT_ATTRS = [
    "import_timestamp",
    "export_timestamp",
    "change_timestamp",
    "print_timestamp",
    "history_end",
]


def extract_darktable_data(file_path):
    data = {"top_level_attrs": {}, "tags": [], "history": {}}
    try:
        with open(file_path, "rb") as f:
            xml_content = f.read()
    except IOError as e:
        print(f"Error reading {file_path}: {e}")
        return data

    try:
        parser = etree.XMLParser(remove_blank_text=True, recover=True)
        root = etree.fromstring(xml_content, parser)
    except etree.XMLSyntaxError as e:
        print(f"Error parsing XML in {file_path}: {e}")
        return data

    rdf_ns = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    description_node = root.find(f".//{{{rdf_ns}}}Description")
    if description_node is None:
        description_node = root

    for key, value in description_node.attrib.items():
        try:
            qname = etree.QName(key)
            if (
                "darktable" in qname.namespace
                and qname.localname not in IGNORED_DT_ATTRS
            ):
                data["top_level_attrs"][qname.localname] = value
            # Also capture the hashes even though they are normally ignored for diffing
            if "darktable" in qname.namespace and qname.localname in [
                "history_auto_hash",
                "history_current_hash",
            ]:
                data["top_level_attrs"][qname.localname] = value
        except ValueError:
            continue

    masks_by_num, history_items, tags = {}, {}, []

    for child_node in description_node:
        if not isinstance(child_node.tag, str):
            continue
        try:
            child_qname = etree.QName(child_node.tag)
        except ValueError:
            continue  # Skip comment nodes or other non-element nodes

        if child_qname.localname == "masks_history":
            seq_node = child_node.find(f"{{{rdf_ns}}}Seq")
            if seq_node is not None:
                for li_node in seq_node:
                    num, points = None, None
                    for key, value in li_node.attrib.items():
                        try:
                            qname = etree.QName(key)
                            if qname.localname == "mask_num":
                                num = value
                            if qname.localname == "mask_points":
                                points = value
                        except ValueError:
                            continue
                    if num and points:
                        if num not in masks_by_num:
                            masks_by_num[num] = []
                        masks_by_num[num].append(points)

        elif child_qname.localname == "history":
            seq_node = child_node.find(f"{{{rdf_ns}}}Seq")
            if seq_node is not None:
                for li_node in seq_node:
                    module_info = {}
                    num = None
                    for key, value in li_node.attrib.items():
                        try:
                            qname = etree.QName(key)
                            if qname.localname == "num":
                                num = value
                            if "darktable" in qname.namespace:
                                module_info[qname.localname] = value
                        except ValueError:
                            continue
                    if num is not None:
                        history_items[num] = module_info

        elif child_qname.localname == "subject":
            bag_node = child_node.find(f"{{{rdf_ns}}}Bag")
            if bag_node is not None:
                tags.extend([li.text for li in bag_node if li.text])

    for num in masks_by_num:
        masks_by_num[num].sort()
    for num, module_info in history_items.items():
        module_info["masks"] = masks_by_num.get(num, [])
        data["history"][num] = module_info
    data["tags"] = sorted(list(set(tags)))
    return data


class ScannerWorker(QObject):
    """Worker for scanning directories in the background."""

    file_diff_found = Signal(str, dict)
    scan_progress = Signal(int, int)
    scan_finished = Signal()  # For UI status update
    finished = Signal()  # For thread lifecycle management.

    def __init__(self, session_dir, archive_dir, parent=None):
        super().__init__(parent)
        self.session_dir = session_dir
        self.archive_dir = archive_dir
        self._is_running = True

    def run(self):
        """Scan directories and emit signals for found diffs."""
        xmp_files_to_scan = []
        try:
            for root, _, files in os.walk(self.session_dir):
                for file in files:
                    if file.lower().endswith(".xmp"):
                        xmp_files_to_scan.append(os.path.join(root, file))
        except Exception as e:
            print(f"Error walking directory {self.session_dir}: {e}")
            self.scan_finished.emit()
            self.finished.emit()
            return

        total_files = len(xmp_files_to_scan)
        for i, session_xmp_path in enumerate(xmp_files_to_scan):
            if not self._is_running:
                break

            relative_path = os.path.relpath(session_xmp_path, self.session_dir)
            archive_xmp_path = os.path.join(self.archive_dir, relative_path)

            if os.path.exists(archive_xmp_path):
                try:
                    session_data = extract_darktable_data(session_xmp_path)

                    # If history hashes match, the session copy is considered unedited. Skip it.
                    session_attrs = session_data.get("top_level_attrs", {})
                    auto_hash = session_attrs.get("history_auto_hash")
                    current_hash = session_attrs.get("history_current_hash")
                    if auto_hash is not None and auto_hash == current_hash:
                        continue

                    archive_data = extract_darktable_data(archive_xmp_path)

                    if session_data != archive_data:
                        diff_info = {
                            "session_path": session_xmp_path,
                            "archive_path": archive_xmp_path,
                            "session_data": session_data,
                            "archive_data": archive_data,
                        }
                        self.file_diff_found.emit(relative_path, diff_info)
                except Exception as e:
                    print(f"Could not process or compare file '{relative_path}': {e}")

            self.scan_progress.emit(i + 1, total_files)

        self.scan_finished.emit()
        self.finished.emit()

    def stop(self):
        self._is_running = False
