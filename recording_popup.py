from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, 
    QGraphicsDropShadowEffect, QApplication
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush


class ModernFrame(QFrame):
    """Custom frame with rounded corners and shadow effect"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("modernFrame")
        
        # Set background transparency
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        self.setStyleSheet("""
            #modernFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E9ECEF;
            }
        """)
        
    def paintEvent(self, event):
        # Draw rounded rectangle
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        
        painter.setClipPath(path)
        painter.fillPath(path, QBrush(QColor("#FFFFFF")))


class RecordingPopup(QWidget):
    """Modern recording popup that matches the main UI style"""
    
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0);")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Initialize UI components
        self.setup_ui()
        
        # Initialize animation timers
        self.setup_timers()
        
        # Set initial state
        self.setWindowOpacity(1.0)
        self.hide()
    
    def setup_ui(self):
        """Setup the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Container with modern style
        self.container = ModernFrame()
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 15, 20, 15)
        container_layout.setSpacing(10)
        
        # Recording indicator - pulsing circle
        self.record_indicator = QWidget()
        self.record_indicator.setFixedSize(12, 12)
        self.record_indicator.setStyleSheet("""
            background-color: #DC3545;
            border-radius: 6px;
        """)
        
        # Recording status label
        self.status_label = QLabel("Recording")
        self.status_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
        self.status_label.setStyleSheet("color: #212529; margin-left: 10px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Timer label
        self.timer_label = QLabel("00:00")
        self.timer_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
        self.timer_label.setStyleSheet("color: #212529;")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Arrange indicator and status label horizontally
        indicator_layout = QHBoxLayout()
        indicator_layout.addWidget(self.record_indicator, alignment=Qt.AlignmentFlag.AlignCenter)
        indicator_layout.addWidget(self.status_label)
        indicator_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        container_layout.addLayout(indicator_layout)
        container_layout.addWidget(self.timer_label)
        
        # Information label
        self.info_label = QLabel("Release hotkey to stop recording")
        self.info_label.setFont(QFont("Segoe UI", 10))
        self.info_label.setStyleSheet("color: #6C757D;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Enable word wrapping to handle long text better
        self.info_label.setWordWrap(True)
        # Ensure minimum height for the label to fit text
        self.info_label.setMinimumHeight(20)
        container_layout.addWidget(self.info_label)
        
        # Processing indicator (spinner)
        self.processing_indicator = QLabel("●")
        self.processing_indicator.setFont(QFont("Segoe UI", 20))
        self.processing_indicator.setStyleSheet("color: #28A745;")  # Bootstrap green
        self.processing_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.processing_indicator.hide()
        container_layout.addWidget(self.processing_indicator)
        
        layout.addWidget(self.container)
        # Increase width from 240 to 280 and height from 160 to 180 to accommodate text better
        self.setFixedSize(280, 180)
        
        # Center on screen
        self.center_on_screen()
    
    def setup_timers(self):
        """Setup animation timers"""
        # Pulse animation timer
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.pulse_animation)
        self.pulse_state = True
        
        # Processing animation timer
        self.processing_timer = QTimer()
        self.processing_timer.timeout.connect(self.process_animation)
        self.processing_rotation = 0
        
        # Fade animation
        self.popup_animation = QPropertyAnimation(self, b"windowOpacity")
        self.popup_animation.setDuration(10)
        self.popup_animation.setStartValue(0.8)
        self.popup_animation.setEndValue(1.0)
        self.popup_animation.setEasingCurve(QEasingCurve.Type.Linear)
    
    def center_on_screen(self):
        """Center the popup on the screen"""
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) / 2
        y = (screen_geometry.height() - self.height()) / 2
        self.move(int(x), int(y))
    
    def pulse_animation(self):
        """Animate the recording indicator with a pulse effect"""
        if self.pulse_state:
            self.record_indicator.setStyleSheet("""
                background-color: rgba(220, 53, 69, 0.5);
                border-radius: 6px;
            """)
            self.pulse_state = False
        else:
            self.record_indicator.setStyleSheet("""
                background-color: #DC3545;
                border-radius: 6px;
            """)
            self.pulse_state = True
    
    def process_animation(self):
        """Animate the processing indicator with a rotating effect"""
        symbols = ["◐", "◓", "◑", "◒"]
        self.processing_rotation = (self.processing_rotation + 1) % len(symbols)
        self.processing_indicator.setText(symbols[self.processing_rotation])
    
    def update_timer(self, seconds):
        """Update the displayed recording time"""
        minutes = seconds // 60
        seconds = seconds % 60
        self.timer_label.setText(f"{minutes:02}:{seconds:02}")
    
    def show_recording(self):
        """Show the recording state"""
        self.timer_label.setText("00:00")
        self.status_label.setText("Recording")
        self.info_label.setText("Release hotkey to stop recording")
        self.record_indicator.show()
        self.processing_indicator.hide()
        
        # Show popup immediately
        self.setWindowOpacity(1.0)
        self.show()
        QApplication.processEvents()
        
        # Start pulse animation
        self.pulse_timer.start(800)
    
    def show_processing(self):
        """Show the processing state"""
        self.record_indicator.hide()
        self.processing_indicator.show()
        self.status_label.setText("Processing")
        self.info_label.setText("Transcribing audio...")
        self.processing_timer.start(150)
        QApplication.processEvents()
    
    def hide_popup(self):
        """Hide the popup and stop all animations"""
        self.pulse_timer.stop()
        self.processing_timer.stop()
        self.hide()