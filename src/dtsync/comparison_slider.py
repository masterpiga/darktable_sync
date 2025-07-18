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

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QScrollArea,
)
from PySide6.QtCore import Qt, QEvent, QRect
from PySide6.QtGui import QPainter, QColor, QPen


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