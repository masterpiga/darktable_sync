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
import shutil
import subprocess
import uuid
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QGroupBox,
    QPushButton,
    QSlider,
    QFrame,
)
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QEvent, QThreadPool, QMutex, QMutexLocker, QRect
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QPen

import icons
from compare_in_darktable import CompareInDarktableManager


class ImagePreview(QWidget):
    def __init__(self, overlay_text: str):
        super().__init__()
        self.preview_layout = QVBoxLayout(self)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.setSpacing(0)
        self.image_label = PannableLabel()
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area = QScrollArea(alignment=Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(False)
        self.image_label.set_scroll_area(self.scroll_area)
        self.preview_layout.addWidget(self.scroll_area)
        # Overlay label as child of scroll area's viewport
        self.overlay_label = QLabel(overlay_text, self.scroll_area.viewport())
        self.set_style("black")
        self.overlay_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.overlay_label.move(0, 0)
        self.overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.overlay_label.raise_()

    def set_style(self, background_color: str):
        self.overlay_label.setStyleSheet(
            f"color: white; font-weight: bold; background-color: {background_color}; padding: 1px;"
        )


class PannableLabel(QLabel):
    """A QLabel that allows panning by dragging the mouse and pinch-to-zoom."""

    def __init__(self, *args, **kwargs):
        super().__init__("No XMP file selected", **kwargs)
        self._panning = False
        self._pan_start_global = None
        self.scroll_area = None
        self.other_scroll_area = None
        self._zoom_callback = None  # Callback to parent for zoom changes
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.GestureType.PinchGesture)

    def set_scroll_area(self, scroll_area):
        self.scroll_area = scroll_area

    def set_other_scroll_area(self, other_scroll_area):
        self.other_scroll_area = other_scroll_area

    def set_zoom_callback(self, callback):
        self._zoom_callback = callback

    def event(self, event):
        if event.type() == QEvent.Type.Gesture:
            return self.gestureEvent(event)
        return super().event(event)

    def gestureEvent(self, event):
        pinch = event.gesture(Qt.GestureType.PinchGesture)
        if pinch:
            if self._zoom_callback:
                scale_factor = pinch.scaleFactor()
                # Only apply if the gesture is active
                if pinch.state() == Qt.GestureState.GestureUpdated:
                    self._zoom_callback(scale_factor)
            return True
        return False

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.scroll_area
            and self.pixmap()
        ):
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            if h_bar.maximum() > 0 or v_bar.maximum() > 0:
                self._panning = True
                # Use global position for jitter-free panning
                self._pan_start_global = (
                    event.globalPosition()
                    if hasattr(event, "globalPosition")
                    else event.globalPos()
                )
                QApplication.setOverrideCursor(Qt.CursorShape.OpenHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._panning
            and (event.buttons() & Qt.MouseButton.LeftButton)
            and self.scroll_area
        ):
            if QApplication.overrideCursor().shape() != Qt.CursorShape.ClosedHandCursor:
                QApplication.changeOverrideCursor(Qt.CursorShape.ClosedHandCursor)
            # Use global position for delta
            current_global = (
                event.globalPosition()
                if hasattr(event, "globalPosition")
                else event.globalPos()
            )
            delta = current_global - self._pan_start_global
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - int(delta.x()))
            v_bar.setValue(v_bar.value() - int(delta.y()))
            self._pan_start_global = current_global
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._panning:
            self._panning = False
            QApplication.restoreOverrideCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ComparisonSlider(QWidget):
    """A widget that displays two images with a draggable divider for before/after comparison."""
    
    def __init__(self, left_label="Archive copy", right_label="Session copy"):
        super().__init__()
        self.left_label = left_label
        self.right_label = right_label
        self.left_pixmap = None
        self.right_pixmap = None
        self.original_left_pixmap = None
        self.original_right_pixmap = None
        self.divider_position = 0.5  # Position of the divider (0.0 to 1.0)
        self.dragging = False
        self.zoom_factor = 1.0
        self.vertical_divider = True  # True = vertical divider (left/right), False = horizontal divider (top/bottom)
        self.left_label_color = "black"  # Background color for left label
        self.right_label_color = "black"  # Background color for right label
        
        # Pan and zoom functionality
        self._panning = False
        self._pan_start_global = None
        self._zoom_callback = None
        
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        
        # Enable touch events for pinch-to-zoom
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.GestureType.PinchGesture)
        
        # Create a child widget for the actual image display
        self.image_widget = QWidget()
        self.image_widget.setMinimumSize(400, 300)
        self.image_widget.setMouseTracking(True)
        self.image_widget.paintEvent = self.paintEvent
        self.image_widget.mousePressEvent = self.mousePressEvent
        self.image_widget.mouseMoveEvent = self.mouseMoveEvent
        self.image_widget.mouseReleaseEvent = self.mouseReleaseEvent
        
        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.image_widget)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Set up layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)
    
    def set_left_pixmap(self, pixmap):
        """Set the left (archive) image."""
        self.original_left_pixmap = pixmap
        self.update_scaled_pixmaps()
    
    def set_right_pixmap(self, pixmap):
        """Set the right (session) image."""
        self.original_right_pixmap = pixmap
        self.update_scaled_pixmaps()
    
    def set_zoom_factor(self, factor):
        """Set the zoom factor for both images."""
        self.zoom_factor = factor
        self.update_scaled_pixmaps()
    
    def set_vertical_divider(self, vertical):
        """Set whether the divider is vertical (True) or horizontal (False)."""
        self.vertical_divider = vertical
        self.image_widget.update()
    
    def toggle_orientation(self):
        """Toggle between vertical and horizontal divider."""
        self.vertical_divider = not self.vertical_divider
        self.image_widget.update()
    
    def set_label_colors(self, left_color, right_color):
        """Set the background colors for the labels."""
        self.left_label_color = left_color
        self.right_label_color = right_color
        self.image_widget.update()
    
    def set_zoom_callback(self, callback):
        """Set a callback to handle zoom changes from gestures."""
        self._zoom_callback = callback
    
    def event(self, event):
        """Handle gesture events for pinch-to-zoom."""
        if event.type() == QEvent.Type.Gesture:
            return self.gestureEvent(event)
        return super().event(event)
    
    def gestureEvent(self, event):
        """Handle pinch-to-zoom gestures."""
        pinch = event.gesture(Qt.GestureType.PinchGesture)
        if pinch:
            if self._zoom_callback:
                scale_factor = pinch.scaleFactor()
                # Only apply if the gesture is active
                if pinch.state() == Qt.GestureState.GestureUpdated:
                    self._zoom_callback(scale_factor)
            return True
        return False
    
    def update_scaled_pixmaps(self):
        """Update the scaled pixmaps based on zoom factor."""
        if self.original_left_pixmap:
            self.left_pixmap = self.original_left_pixmap.scaled(
                int(self.original_left_pixmap.width() * self.zoom_factor),
                int(self.original_left_pixmap.height() * self.zoom_factor),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        
        if self.original_right_pixmap:
            self.right_pixmap = self.original_right_pixmap.scaled(
                int(self.original_right_pixmap.width() * self.zoom_factor),
                int(self.original_right_pixmap.height() * self.zoom_factor),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        
        # Update widget size to match the largest image
        if self.left_pixmap or self.right_pixmap:
            max_width = max(
                self.left_pixmap.width() if self.left_pixmap else 0,
                self.right_pixmap.width() if self.right_pixmap else 0
            )
            max_height = max(
                self.left_pixmap.height() if self.left_pixmap else 0,
                self.right_pixmap.height() if self.right_pixmap else 0
            )
            self.image_widget.resize(max_width, max_height)
        
        self.image_widget.update()
    
    def paintEvent(self, event):
        """Paint the comparison slider."""
        painter = QPainter(self.image_widget)
        
        if not self.left_pixmap and not self.right_pixmap:
            painter.drawText(self.image_widget.rect(), Qt.AlignmentFlag.AlignCenter, "No images loaded")
            return
        
        if self.vertical_divider:
            # Vertical divider (left/right split)
            divider_pos = int(self.image_widget.width() * self.divider_position)
            
            # Draw the left image (archive) on the left side
            if self.left_pixmap:
                left_rect = QRect(0, 0, divider_pos, self.image_widget.height())
                painter.setClipRect(left_rect)
                
                # Center the image
                x_offset = (self.image_widget.width() - self.left_pixmap.width()) // 2
                y_offset = (self.image_widget.height() - self.left_pixmap.height()) // 2
                painter.drawPixmap(x_offset, y_offset, self.left_pixmap)
            
            # Draw the right image (session) on the right side
            if self.right_pixmap:
                right_rect = QRect(divider_pos, 0, self.image_widget.width() - divider_pos, self.image_widget.height())
                painter.setClipRect(right_rect)
                
                # Center the image
                x_offset = (self.image_widget.width() - self.right_pixmap.width()) // 2
                y_offset = (self.image_widget.height() - self.right_pixmap.height()) // 2
                painter.drawPixmap(x_offset, y_offset, self.right_pixmap)
            
            # Draw the divider line
            painter.setClipRect(self.image_widget.rect())
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(divider_pos, 0, divider_pos, self.image_widget.height())
            
            # Draw labels
            painter.setPen(QPen(QColor(255, 255, 255)))
            
            # Set bold font for labels
            bold_font = painter.font()
            bold_font.setBold(True)
            painter.setFont(bold_font)
            
            if divider_pos > 60:
                # Draw left label with background color and padding at corner (0, 0)
                text_width = painter.fontMetrics().horizontalAdvance(self.left_label)
                text_height = painter.fontMetrics().height()
                padding = 1
                # Position at very corner like side-by-side mode
                painter.fillRect(0, 0, 
                               text_width + 2 * padding,
                               text_height + 2 * padding, 
                               QColor(self.left_label_color))
                painter.drawText(0 + padding, text_height + padding, self.left_label)
            if self.image_widget.width() - divider_pos > 60:
                # Draw right label with background color and padding at corner
                text_width = painter.fontMetrics().horizontalAdvance(self.right_label)
                text_height = painter.fontMetrics().height()
                padding = 1
                # Position at corner of right side
                painter.fillRect(divider_pos, 0,
                               text_width + 2 * padding,
                               text_height + 2 * padding,
                               QColor(self.right_label_color))
                painter.drawText(divider_pos + padding, text_height + padding, self.right_label)
        
        else:
            # Horizontal divider (top/bottom split)
            divider_pos = int(self.image_widget.height() * self.divider_position)
            
            # Draw the top image (archive) on the top side
            if self.left_pixmap:
                top_rect = QRect(0, 0, self.image_widget.width(), divider_pos)
                painter.setClipRect(top_rect)
                
                # Center the image
                x_offset = (self.image_widget.width() - self.left_pixmap.width()) // 2
                y_offset = (self.image_widget.height() - self.left_pixmap.height()) // 2
                painter.drawPixmap(x_offset, y_offset, self.left_pixmap)
            
            # Draw the bottom image (session) on the bottom side
            if self.right_pixmap:
                bottom_rect = QRect(0, divider_pos, self.image_widget.width(), self.image_widget.height() - divider_pos)
                painter.setClipRect(bottom_rect)
                
                # Center the image
                x_offset = (self.image_widget.width() - self.right_pixmap.width()) // 2
                y_offset = (self.image_widget.height() - self.right_pixmap.height()) // 2
                painter.drawPixmap(x_offset, y_offset, self.right_pixmap)
            
            # Draw the divider line
            painter.setClipRect(self.image_widget.rect())
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(0, divider_pos, self.image_widget.width(), divider_pos)
            
            # Draw labels
            painter.setPen(QPen(QColor(255, 255, 255)))
            
            # Set bold font for labels
            bold_font = painter.font()
            bold_font.setBold(True)
            painter.setFont(bold_font)
            
            if divider_pos > 30:
                # Draw top label with background color and padding at corner (0, 0)
                text_width = painter.fontMetrics().horizontalAdvance(self.left_label)
                text_height = painter.fontMetrics().height()
                padding = 1
                # Position at very corner like side-by-side mode
                painter.fillRect(0, 0, 
                               text_width + 2 * padding,
                               text_height + 2 * padding, 
                               QColor(self.left_label_color))
                painter.drawText(0 + padding, text_height + padding, self.left_label)
            if self.image_widget.height() - divider_pos > 30:
                # Draw bottom label with background color and padding at corner
                text_width = painter.fontMetrics().horizontalAdvance(self.right_label)
                text_height = painter.fontMetrics().height()
                padding = 1
                # Position at corner of bottom side
                painter.fillRect(0, divider_pos,
                               text_width + 2 * padding,
                               text_height + 2 * padding,
                               QColor(self.right_label_color))
                painter.drawText(0 + padding, divider_pos + text_height + padding, self.right_label)
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging the divider or panning."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if we're near the divider for divider dragging
            is_near_divider = False
            if self.vertical_divider:
                divider_pos = int(self.image_widget.width() * self.divider_position)
                is_near_divider = abs(event.position().x() - divider_pos) < 10
            else:
                divider_pos = int(self.image_widget.height() * self.divider_position)
                is_near_divider = abs(event.position().y() - divider_pos) < 10
            
            if is_near_divider:
                # Start divider dragging
                self.dragging = True
                self.update_divider_position(event.position().x(), event.position().y())
            else:
                # Check if we can pan (there are images and scrollbars)
                h_bar = self.scroll_area.horizontalScrollBar()
                v_bar = self.scroll_area.verticalScrollBar()
                if (self.left_pixmap or self.right_pixmap) and (h_bar.maximum() > 0 or v_bar.maximum() > 0):
                    self._panning = True
                    # Use global position for jitter-free panning
                    self._pan_start_global = (
                        event.globalPosition()
                        if hasattr(event, "globalPosition")
                        else event.globalPos()
                    )
                    QApplication.setOverrideCursor(Qt.CursorShape.OpenHandCursor)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging the divider or panning."""
        if self.dragging:
            # Handle divider dragging
            if self.vertical_divider:
                self.update_divider_position(event.position().x(), event.position().y())
            else:
                self.update_divider_position(event.position().x(), event.position().y())
        elif self._panning and (event.buttons() & Qt.MouseButton.LeftButton):
            # Handle panning
            if QApplication.overrideCursor() and QApplication.overrideCursor().shape() != Qt.CursorShape.ClosedHandCursor:
                QApplication.changeOverrideCursor(Qt.CursorShape.ClosedHandCursor)
            # Use global position for delta
            current_global = (
                event.globalPosition()
                if hasattr(event, "globalPosition")
                else event.globalPos()
            )
            delta = current_global - self._pan_start_global
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - int(delta.x()))
            v_bar.setValue(v_bar.value() - int(delta.y()))
            self._pan_start_global = current_global
        else:
            # Update cursor when hovering over the divider
            if self.vertical_divider:
                divider_pos = int(self.image_widget.width() * self.divider_position)
                if abs(event.position().x() - divider_pos) < 10:
                    self.image_widget.setCursor(Qt.CursorShape.SplitHCursor)
                else:
                    self.image_widget.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                divider_pos = int(self.image_widget.height() * self.divider_position)
                if abs(event.position().y() - divider_pos) < 10:
                    self.image_widget.setCursor(Qt.CursorShape.SplitVCursor)
                else:
                    self.image_widget.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop dragging or panning."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragging:
                self.dragging = False
            elif self._panning:
                self._panning = False
                QApplication.restoreOverrideCursor()
    
    def update_divider_position(self, x, y):
        """Update the divider position based on mouse coordinates."""
        if self.vertical_divider:
            self.divider_position = max(0.0, min(1.0, x / self.image_widget.width()))
        else:
            self.divider_position = max(0.0, min(1.0, y / self.image_widget.height()))
        self.image_widget.update()


class PreviewSignals(QObject):
    """Holds signals for the PreviewWorker to prevent object lifetime issues."""

    preview_ready = Signal(
        str, str, str
    )  # rel_path, image_type ('session'/'archive'), image_path
    preview_failed = Signal(str, str, str)  # rel_path, image_type, error_message
    preview_retry_requested = Signal(object)  # PreviewWorker instance for retry
    job_finished = Signal(str, str, int) # rel_path, image_type, preview_size


class PreviewWorker(QRunnable):
    """Worker for generating image previews in a thread pool."""

    def __init__(
        self,
        cli_path,
        raw_file_path,
        xmp_file_path,
        rel_path,
        image_type,
        signals,
        history_hash,
        preview_width,
        preview_height,
        retry_count=0,
        max_retries=2,
        enable_opencl=True,
    ):
        super().__init__()
        self.cli_path = cli_path
        self.raw_file_path = raw_file_path
        self.xmp_file_path = xmp_file_path
        self.rel_path = rel_path
        self.image_type = image_type
        self.signals = signals
        self.history_hash = history_hash
        self.preview_width = preview_width
        self.preview_height = preview_height
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.enable_opencl = enable_opencl

        self.mutex = QMutex()
        self._is_cancelled = False
        self._process = None

    @property
    def is_cancelled(self):
        with QMutexLocker(self.mutex):
            return self._is_cancelled

    def cancel(self):
        with QMutexLocker(self.mutex):
            self._is_cancelled = True
            if self._process:
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass # process already finished

    def run(self):
        """Execute darktable-cli to generate a preview."""
        if self.is_cancelled:
            self.signals.job_finished.emit(self.rel_path, self.image_type, self.preview_width)
            return

        print(f"Starting preview generation for {self.rel_path} ({self.image_type})")

        output_dir = os.path.join(Path.home(), ".cache", "dtsync", str(self.preview_width))
        os.makedirs(output_dir, exist_ok=True)

        # Always include a "version" identifier in the filename, even if the hash is missing.
        hash_part = (
            f"{self.history_hash}"
            if self.history_hash
            else str(hash(self.xmp_file_path))
        )
        output_filename = f"{hash_part}_{self.image_type}.jpg"

        output_path = os.path.join(output_dir, output_filename)

        # If a cached preview exists and is valid, use it
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            self.signals.preview_ready.emit(self.rel_path, self.image_type, output_path)
            self.signals.job_finished.emit(self.rel_path, self.image_type, self.preview_width)
            return
        
        if self.is_cancelled:
            self.signals.job_finished.emit(self.rel_path, self.image_type, self.preview_width)
            return

        unique_id = uuid.uuid4().hex[:8]  # Generate a unique ID for this run

        # Create a unique config and temp directory for each darktable-cli instance to enable parallel execution.
        run_temp_dir = f"/tmp/dt_sync_{os.getpid()}_{unique_id}"
        os.makedirs(run_temp_dir, exist_ok=True)

        command = [
            self.cli_path,
            self.raw_file_path,
            self.xmp_file_path,
            output_path,
            "--width",
            str(self.preview_width),
            "--height",
            str(self.preview_height),
            "--core",
            "--conf",
            "plugins/imageio/format/jpeg/quality=90",
            "--library",
            ":memory:",
            "--configdir",
            run_temp_dir,
        ]

        # Add OpenCL configuration if enabled
        if self.enable_opencl:
            command.extend(["--conf", "opencl=TRUE"])

        # Print the command being executed for debugging
        print(f"Executing preview generation command: {' '.join(command)}")

        # Create a custom environment for the subprocess, setting a unique TMPDIR.
        my_env = os.environ.copy()
        my_env["TMPDIR"] = run_temp_dir

        try:
            with QMutexLocker(self.mutex):
                if self._is_cancelled:
                    self.signals.job_finished.emit(self.rel_path, self.image_type, self.preview_width)
                    return
                
                self._process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=my_env,
                )

            try:
                stdout, stderr = self._process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                self._process.kill()
                stdout, stderr = self._process.communicate()
                raise subprocess.TimeoutExpired(command, 30, output=stdout, stderr=stderr)

            if self._process.returncode != 0:
                raise subprocess.CalledProcessError(self._process.returncode, command, output=stdout, stderr=stderr)


            # Verify that the output file was actually created and is not empty.
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                if not self.is_cancelled:
                    print(f"Successfully generated preview for {self.rel_path} ({self.image_type}) -> {output_path}")
                    self.signals.preview_ready.emit(
                        self.rel_path, self.image_type, output_path
                    )
            else:
                error_message = (
                    f"darktable-cli ran but did not create a valid output file."
                )
                print(error_message)
                if not self.is_cancelled:
                    self._handle_preview_failure("Preview failed (empty output).")

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            if not self.is_cancelled:
                error_message = f"Failed to generate {self.image_type} preview."
                print(
                    f"Error generating preview for {self.raw_file_path} with {self.xmp_file_path}"
                )
                if hasattr(e, "stderr"):
                    print(f"Stderr: {e.stderr}")
                if hasattr(e, "stdout"):
                    print(f"Stdout: {e.stdout}")
                self._handle_preview_failure(error_message)
        finally:
            with QMutexLocker(self.mutex):
                self._process = None
            # Clean up the temporary directory for this run.
            shutil.rmtree(run_temp_dir, ignore_errors=True)
            self.signals.job_finished.emit(self.rel_path, self.image_type, self.preview_width)

    def _handle_preview_failure(self, error_message):
        """Handle preview generation failure with retry logic."""
        if self.retry_count < self.max_retries:
            print(f"Preview generation failed for {self.rel_path} ({self.image_type}), retrying ({self.retry_count + 1}/{self.max_retries})")
            # Create a new worker for retry
            retry_worker = PreviewWorker(
                self.cli_path,
                self.raw_file_path,
                self.xmp_file_path,
                self.rel_path,
                self.image_type,
                self.signals,
                self.history_hash,
                self.preview_width,
                self.preview_height,
                self.retry_count + 1,
                self.max_retries,
                self.enable_opencl
            )
            self.signals.preview_retry_requested.emit(retry_worker)
        else:
            print(f"Preview generation failed for {self.rel_path} ({self.image_type}) after {self.max_retries} retries")
            self.signals.preview_failed.emit(
                self.rel_path, self.image_type, error_message
            )


class PreviewManager(QWidget):
    """Manages the preview comparison UI and display functionality only."""
    
    def __init__(self, preview_max_dimension):
        super().__init__()
        self.preview_max_dimension = preview_max_dimension
        self.vertical_layout = True
        self.comparison_mode = False  # False = side-by-side, True = comparison slider
        
        # Cache manager will be set by main app
        self.cache_manager = None
        
        # Compare manager for darktable integration
        self.compare_manager = CompareInDarktableManager(self)
        
        # Current paths for compare functionality
        self.current_session_path = None
        self.current_archive_path = None
        
        # Comparison slider widget
        self.comparison_slider = None
        
        self.setup_ui()

    def generate_previews(self, relative_path, raw_file, session_path, archive_path, session_hash, archive_hash):
        """Request preview generation from the cache manager."""
        if self.cache_manager:
            self.cache_manager.request_preview_generation(
                relative_path, raw_file, session_path, archive_path, session_hash, archive_hash
            )
        else:
            print("Warning: No cache manager available for preview generation")
            
    def update_preview_dimension(self, new_dimension):
        """Update preview dimension setting."""
        self.preview_max_dimension = new_dimension
    
    def setup_ui(self):
        """Initialize the preview UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar_spacing = 20
        
        # Preview comparison group
        self.preview_group = QGroupBox("Preview comparison")
        self.preview_group.setEnabled(False)  # Initially disabled until a file is selected
        preview_group_layout = QVBoxLayout(self.preview_group)
        preview_group_layout.setSpacing(0)  # Reduce spacing between toolbar elements
        
        # Toolbar: Zoom slider + orientation switch + compare button
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(toolbar_spacing)  # Reduce spacing between toolbar elements
        
        # Compare in darktable button
        self.compare_button = QPushButton("Open in darktable")
        self.compare_button.setEnabled(False)  # Initially disabled
        self.compare_button.setToolTip("Compare and edit archive and session versions in darktable")
        self.compare_button.setIcon(QIcon(icons.DARKTABLE_ICON))
        self.compare_button.clicked.connect(self.on_compare_button_clicked)
        toolbar_layout.addWidget(self.compare_button)
        
        toolbar_layout.addStretch()  # Add space between compare button and zoom controls
        
        # Zoom slider
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(50)
        self.zoom_slider.setMaximum(200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickInterval(50)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setToolTip("Adjust preview zoom level (50% - 200%)")
        self.zoom_slider.setMaximumWidth(100)
        self.zoom_slider.valueChanged.connect(self.update_preview_zoom)
        zoom_label = QLabel()
        zoom_label.setPixmap(QIcon(icons.ZOOM_ICON).pixmap(16, 16))
        zoom_label.setToolTip("Zoom in/out of previews")
        toolbar_layout.addWidget(zoom_label)
        toolbar_layout.addSpacing(-1 * toolbar_spacing)
        toolbar_layout.addWidget(self.zoom_slider)
        
        # Orientation switch button
        self.preview_layout_toggle = QPushButton()
        self.preview_layout_toggle.setIcon(QIcon(icons.VERTICAL_LAYOUT_ICON))
        self.preview_layout_toggle.setFixedWidth(32)
        self.preview_layout_toggle.setToolTip("Switch between vertical and horizontal layout")
        self.preview_layout_toggle.clicked.connect(self.toggle_preview_orientation)
        toolbar_layout.addWidget(self.preview_layout_toggle)
        
        # Comparison mode toggle button
        self.comparison_mode_toggle = QPushButton()
        self.comparison_mode_toggle.setText("📊")  # Using emoji as icon
        self.comparison_mode_toggle.setFixedWidth(32)
        self.comparison_mode_toggle.setToolTip("Toggle comparison slider mode")
        self.comparison_mode_toggle.clicked.connect(self.toggle_comparison_mode)
        toolbar_layout.addWidget(self.comparison_mode_toggle)
        
        preview_group_layout.addLayout(toolbar_layout)
        
        # Previews Splitter (for toggling orientation)
        self.previews_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Archive Preview (top or left) with overlay label always on top
        self.archive_preview = ImagePreview("Archive copy")
        self.previews_splitter.addWidget(self.archive_preview)

        # Session Preview (bottom or right) with overlay label always on top
        self.session_preview = ImagePreview("Session copy")
        self.previews_splitter.addWidget(self.session_preview)
        
        # Create comparison slider widget (initially hidden)
        self.comparison_slider = ComparisonSlider("Archive copy", "Session copy")
        
        # Add both widgets to the preview group layout
        preview_group_layout.addWidget(self.previews_splitter)
        preview_group_layout.addWidget(self.comparison_slider)
        
        # Initially hide the comparison slider
        self.comparison_slider.hide()
        
        # Sync scrollbars for side-by-side mode
        self.archive_preview.image_label.set_other_scroll_area(self.session_preview.scroll_area)
        self.session_preview.image_label.set_other_scroll_area(self.archive_preview.scroll_area)
        self.archive_preview.scroll_area.horizontalScrollBar().valueChanged.connect(
            self.session_preview.scroll_area.horizontalScrollBar().setValue
        )
        self.archive_preview.scroll_area.verticalScrollBar().valueChanged.connect(
            self.session_preview.scroll_area.verticalScrollBar().setValue
        )
        self.session_preview.scroll_area.horizontalScrollBar().valueChanged.connect(
            self.archive_preview.scroll_area.horizontalScrollBar().setValue
        )
        self.session_preview.scroll_area.verticalScrollBar().valueChanged.connect(
            self.archive_preview.scroll_area.verticalScrollBar().setValue
        )
        
        preview_group_layout.addWidget(self.previews_splitter)
        preview_group_layout.addWidget(self.comparison_slider)
        
        # Initially hide the comparison slider
        self.comparison_slider.hide()
        
        # Sync scrollbars for side-by-side mode
        self.archive_preview.image_label.set_other_scroll_area(self.session_preview.scroll_area)
        self.session_preview.image_label.set_other_scroll_area(self.archive_preview.scroll_area)
        self.archive_preview.scroll_area.horizontalScrollBar().valueChanged.connect(
            self.session_preview.scroll_area.horizontalScrollBar().setValue
        )
        self.archive_preview.scroll_area.verticalScrollBar().valueChanged.connect(
            self.session_preview.scroll_area.verticalScrollBar().setValue
        )
        self.session_preview.scroll_area.horizontalScrollBar().valueChanged.connect(
            self.archive_preview.scroll_area.horizontalScrollBar().setValue
        )
        self.session_preview.scroll_area.verticalScrollBar().valueChanged.connect(
            self.archive_preview.scroll_area.verticalScrollBar().setValue
        )
        
        layout.addWidget(self.preview_group)
        
        # Connect zoom callbacks for pinch-to-zoom
        self.archive_preview.image_label.set_zoom_callback(self.handle_pinch_zoom)
        self.session_preview.image_label.set_zoom_callback(self.handle_pinch_zoom)
        self.comparison_slider.set_zoom_callback(self.handle_pinch_zoom)
    
    def toggle_comparison_mode(self):
        """Toggle between side-by-side and comparison slider modes."""
        self.comparison_mode = not self.comparison_mode
        
        if self.comparison_mode:
            # Switch to comparison slider mode
            self.previews_splitter.hide()
            self.comparison_slider.show()
            # Keep orientation toggle enabled for comparison slider
            self.comparison_mode_toggle.setToolTip("Switch to side-by-side mode")
            
            # Transfer current images to comparison slider
            if hasattr(self.archive_preview.image_label, 'original_pixmap'):
                self.comparison_slider.set_left_pixmap(self.archive_preview.image_label.original_pixmap)
            if hasattr(self.session_preview.image_label, 'original_pixmap'):
                self.comparison_slider.set_right_pixmap(self.session_preview.image_label.original_pixmap)
            
            # Apply current zoom
            zoom_factor = self.zoom_slider.value() / 100.0
            self.comparison_slider.set_zoom_factor(zoom_factor)
            
            # Set comparison slider orientation to match current orientation
            self.comparison_slider.set_vertical_divider(not self.vertical_layout)
            
        else:
            # Switch to side-by-side mode
            self.comparison_slider.hide()
            self.previews_splitter.show()
            self.comparison_mode_toggle.setToolTip("Switch to comparison slider mode")
        
        # Notify parent if callback is set
        if hasattr(self, '_focus_callback') and self._focus_callback:
            self._focus_callback()
    
    def on_preview_ready(self, rel_path, image_type, image_path):
        """Handle when a preview is ready."""
        # This method should be connected to external validation of current selection
        if hasattr(self, '_current_path_callback') and self._current_path_callback:
            current_rel_path = self._current_path_callback()
            if rel_path != current_rel_path:
                return  # Update only if the item is still selected
        
        # Load the pixmap
        pixmap = QPixmap()
        if not pixmap.load(image_path):
            print(f"Failed to load pixmap from: {image_path}")
            self.on_preview_failed(rel_path, image_type, "Failed to load preview image.")
            return
        
        if pixmap.isNull():
            print(f"Pixmap is null after loading from: {image_path}")
            self.on_preview_failed(rel_path, image_type, "Loaded null preview image.")
            return
        
        # Update side-by-side mode
        label = (
            self.session_preview.image_label
            if image_type == "session"
            else self.archive_preview.image_label
        )
        label.original_pixmap = pixmap
        self.scale_preview(label)
        
        # Update comparison slider mode
        if image_type == "session":
            self.comparison_slider.set_right_pixmap(pixmap)
        else:
            self.comparison_slider.set_left_pixmap(pixmap)
        
        # Apply current zoom to comparison slider
        zoom_factor = self.zoom_slider.value() / 100.0
        self.comparison_slider.set_zoom_factor(zoom_factor)
    
    def on_preview_failed(self, rel_path, image_type, error_message):
        """Handle when preview generation fails."""
        if hasattr(self, '_current_path_callback') and self._current_path_callback:
            current_rel_path = self._current_path_callback()
            if rel_path != current_rel_path:
                return
        
        # Update side-by-side mode
        label = (
            self.session_preview.image_label
            if image_type == "session"
            else self.archive_preview.image_label
        )
        label.setText(error_message)
        
        # Note: For comparison slider mode, we'll just not update the failed image
        # The slider will show whatever was previously loaded or nothing
    
    def scale_preview(self, label):
        """Scale a preview label according to the current zoom factor."""
        if not hasattr(label, "original_pixmap") or not label.original_pixmap:
            return
        
        zoom_factor = self.zoom_slider.value() / 100.0
        scaled_pixmap = label.original_pixmap.scaled(
            int(label.original_pixmap.width() * zoom_factor),
            int(label.original_pixmap.height() * zoom_factor),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(scaled_pixmap)
        label.adjustSize()
    
    def update_preview_zoom(self, value):
        """Update the zoom level for both preview images."""
        # Update side-by-side mode
        self.scale_preview(self.archive_preview.image_label)
        self.scale_preview(self.session_preview.image_label)
        
        # Update comparison slider mode
        zoom_factor = value / 100.0
        self.comparison_slider.set_zoom_factor(zoom_factor)
    
    def handle_pinch_zoom(self, scale_factor):
        """Handle pinch-to-zoom gestures."""
        # Clamp zoom slider to 50-200
        current_zoom = self.zoom_slider.value()
        new_zoom = int(current_zoom * scale_factor)
        new_zoom = max(50, min(200, new_zoom))
        self.zoom_slider.setValue(new_zoom)
    
    def toggle_preview_orientation(self):
        """Switch between vertical and horizontal preview layout."""
        self.vertical_layout = not self.vertical_layout
        
        if self.comparison_mode:
            # In comparison slider mode, toggle the divider orientation
            self.comparison_slider.set_vertical_divider(not self.vertical_layout)
            
            # Update the button icon to match the orientation
            if self.vertical_layout:
                self.preview_layout_toggle.setIcon(QIcon(icons.VERTICAL_LAYOUT_ICON))
            else:
                self.preview_layout_toggle.setIcon(QIcon(icons.HORIZONTAL_LAYOUT_ICON))
        else:
            # In side-by-side mode, toggle the splitter orientation
            session_layout = self.session_preview.preview_layout
            session_scroll = self.session_preview.image_label.scroll_area
            
            # Remove all widgets
            for i in reversed(range(session_layout.count())):
                item = session_layout.itemAt(i)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            
            if self.vertical_layout:
                self.previews_splitter.setOrientation(Qt.Orientation.Vertical)
                self.preview_layout_toggle.setIcon(QIcon(icons.VERTICAL_LAYOUT_ICON))
                session_layout.addWidget(session_scroll)
            else:
                self.previews_splitter.setOrientation(Qt.Orientation.Horizontal)
                self.preview_layout_toggle.setIcon(QIcon(icons.HORIZONTAL_LAYOUT_ICON))
                session_layout.addWidget(session_scroll)
        
        # Notify parent if callback is set
        if hasattr(self, '_focus_callback') and self._focus_callback:
            self._focus_callback()
    
    def zoom_in_preview(self):
        """Zoom in on the preview images."""
        current_zoom = self.zoom_slider.value()
        new_zoom = min(current_zoom + 10, self.zoom_slider.maximum())
        self.zoom_slider.setValue(new_zoom)
        
        if hasattr(self, '_focus_callback') and self._focus_callback:
            self._focus_callback()
    
    def zoom_out_preview(self):
        """Zoom out on the preview images."""
        current_zoom = self.zoom_slider.value()
        new_zoom = max(current_zoom - 10, self.zoom_slider.minimum())
        self.zoom_slider.setValue(new_zoom)
        
        if hasattr(self, '_focus_callback') and self._focus_callback:
            self._focus_callback()
    
    def scroll_preview_up(self):
        """Scroll preview images up."""
        if self.comparison_mode:
            scroll_bar = self.comparison_slider.scroll_area.verticalScrollBar()
            current_value = scroll_bar.value()
            new_value = max(current_value - 50, scroll_bar.minimum())
            scroll_bar.setValue(new_value)
        else:
            if hasattr(self.archive_preview, 'scroll_area'):
                scroll_bar = self.archive_preview.scroll_area.verticalScrollBar()
                current_value = scroll_bar.value()
                new_value = max(current_value - 50, scroll_bar.minimum())
                scroll_bar.setValue(new_value)
        
        if hasattr(self, '_focus_callback') and self._focus_callback:
            self._focus_callback()
    
    def scroll_preview_down(self):
        """Scroll preview images down."""
        if self.comparison_mode:
            scroll_bar = self.comparison_slider.scroll_area.verticalScrollBar()
            current_value = scroll_bar.value()
            new_value = min(current_value + 50, scroll_bar.maximum())
            scroll_bar.setValue(new_value)
        else:
            if hasattr(self.archive_preview, 'scroll_area'):
                scroll_bar = self.archive_preview.scroll_area.verticalScrollBar()
                current_value = scroll_bar.value()
                new_value = min(current_value + 50, scroll_bar.maximum())
                scroll_bar.setValue(new_value)
        
        if hasattr(self, '_focus_callback') and self._focus_callback:
            self._focus_callback()
    
    def scroll_preview_left(self):
        """Scroll preview images left."""
        if self.comparison_mode:
            scroll_bar = self.comparison_slider.scroll_area.horizontalScrollBar()
            current_value = scroll_bar.value()
            new_value = max(current_value - 50, scroll_bar.minimum())
            scroll_bar.setValue(new_value)
        else:
            if hasattr(self.archive_preview, 'scroll_area'):
                scroll_bar = self.archive_preview.scroll_area.horizontalScrollBar()
                current_value = scroll_bar.value()
                new_value = max(current_value - 50, scroll_bar.minimum())
                scroll_bar.setValue(new_value)
        
        if hasattr(self, '_focus_callback') and self._focus_callback:
            self._focus_callback()
    
    def scroll_preview_right(self):
        """Scroll preview images right."""
        if self.comparison_mode:
            scroll_bar = self.comparison_slider.scroll_area.horizontalScrollBar()
            current_value = scroll_bar.value()
            new_value = min(current_value + 50, scroll_bar.maximum())
            scroll_bar.setValue(new_value)
        else:
            if hasattr(self.archive_preview, 'scroll_area'):
                scroll_bar = self.archive_preview.scroll_area.horizontalScrollBar()
                current_value = scroll_bar.value()
                new_value = min(current_value + 50, scroll_bar.maximum())
                scroll_bar.setValue(new_value)
        
        if hasattr(self, '_focus_callback') and self._focus_callback:
            self._focus_callback()
    
    def update_preview_label_styles(self, action_id: int):
        """Update the background colors of preview labels based on the action."""
        # Action IDs: 0=No action, 1=Keep archive, 2=Keep session, 3=Keep both
        ref_color, work_color = "black", "black"  # Default for No action
        if action_id == 1:  # Keep archive
            ref_color, work_color = "green", "red"
        elif action_id == 2:  # Keep session
            work_color, ref_color = "green", "red"
        elif action_id == 3:  # Keep both
            ref_color, work_color = "green", "green"
        
        # Update side-by-side mode
        self.archive_preview.set_style(ref_color)
        self.session_preview.set_style(work_color)
        
        # Update comparison slider mode
        self.comparison_slider.set_label_colors(ref_color, work_color)
    
    def set_enabled(self, enabled: bool):
        """Enable or disable the preview group."""
        self.preview_group.setEnabled(enabled)
    
    def set_current_path_callback(self, callback):
        """Set a callback to get the current selected path."""
        self._current_path_callback = callback
    
    def set_focus_callback(self, callback):
        """Set a callback to restore focus after preview operations."""
        self._focus_callback = callback
    
    def on_compare_button_clicked(self):
        """Handle compare in darktable button click."""
        if self.current_session_path and self.current_archive_path:
            self.compare_manager.compare_in_darktable(
                self.current_session_path, 
                self.current_archive_path
            )
    
    def update_current_paths(self, session_path, archive_path):
        """Update the current paths and enable/disable compare button."""
        self.current_session_path = session_path
        self.current_archive_path = archive_path
        
        # Enable compare button only if both paths are available
        has_paths = bool(session_path and archive_path)
        self.compare_button.setEnabled(has_paths)
    
    def setup_compare_signals(self, main_window):
        """Setup signals for the compare manager to communicate with main window."""
        # Connect the refresh previews signal to main window method
        self.compare_manager.refresh_previews_signal.connect(
            main_window.refresh_previews_after_compare
        )
