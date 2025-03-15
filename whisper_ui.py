import sys
import os
import json
import time
from datetime import timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, 
                           QWidget, QLabel, QTextEdit, QFrame, QTabWidget, QLineEdit,
                           QGridLayout, QComboBox, QDialog, QDialogButtonBox, QMessageBox,
                           QSpacerItem, QSizePolicy, QGroupBox, QFormLayout, QSystemTrayIcon, QMenu,
                           QToolButton, QScrollArea, QFileDialog, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QEvent, QSize, QPoint
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QAction, QPen
import math

class StatsManager:
    """Klasa do zarządzania statystykami użytkownika"""
    
    def __init__(self):
        self.settings_file = "whisper_stats.json"
        self.stats = self._load_stats()
    
    def _load_stats(self):
        default_stats = {
            "total_recordings": 0,
            "total_seconds": 0,
            "total_characters": 0,
            "api_calls": 0,
            "last_used": None
        }
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except:
                return default_stats
        return default_stats
    
    def save_stats(self):
        with open(self.settings_file, 'w') as f:
            json.dump(self.stats, f)
    
    def update_recording_stats(self, duration_seconds, text_length):
        self.stats["total_recordings"] += 1
        self.stats["total_seconds"] += duration_seconds
        self.stats["total_characters"] += text_length
        self.stats["api_calls"] += 1
        self.stats["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save_stats()
    
    def get_time_saved(self):
        # Zakładamy, że mówimy 3x szybciej niż piszemy
        # Przyjmijmy, że przeciętna prędkość pisania to 40 WPM (200 znaków/min)
        # Więc czas zaoszczędzony to (znaki / 200) - (czas nagrywania w min)
        chars = self.stats["total_characters"]
        recording_minutes = self.stats["total_seconds"] / 60
        typing_minutes = chars / 200
        return typing_minutes - recording_minutes
    
    def get_formatted_stats(self):
        total_time = timedelta(seconds=self.stats["total_seconds"])
        total_time_str = str(total_time).split('.')[0]  # Bez mikrosekund
        
        time_saved = timedelta(minutes=self.get_time_saved())
        time_saved_str = str(time_saved).split('.')[0]
        
        return {
            "total_recordings": self.stats["total_recordings"],
            "total_time": total_time_str,
            "total_characters": self.stats["total_characters"],
            "api_calls": self.stats["api_calls"],
            "time_saved": time_saved_str,
            "last_used": self.stats["last_used"] or "Nigdy"
        }
    
    def clear_stats(self):
        """Czyści wszystkie statystyki użytkownika"""
        default_stats = {
            "total_recordings": 0,
            "total_seconds": 0,
            "total_characters": 0,
            "api_calls": 0,
            "last_used": None
        }
        self.stats = default_stats
        self.save_stats()

    def update_last_recording_stats(self, duration_seconds, text):
        """Updates statistics after recording completion"""
        chars = len(text)
        
        # Update general statistics
        self.stats_manager.update_recording_stats(duration_seconds, chars)
        
        # If we're in the main view, refresh the statistics section
        if hasattr(self, 'main_content') and self.main_content.isVisible():
            # Remove the old statistics section
            for i in reversed(range(self.main_content.layout().count())):
                item = self.main_content.layout().itemAt(i)
                if isinstance(item.widget(), QWidget) and item.widget().height() == 80:
                    item.widget().deleteLater()
                    break
            
            # Add the new statistics section
            self.main_content.layout().addWidget(self.create_statistics_section())

class ApiKeyDialog(QDialog):
    """Dialog for entering API key"""
    
    def __init__(self, parent=None, current_openai_key="", current_deepinfra_key="", selected_provider="openai"):
        super().__init__(parent)
        self.setWindowTitle("API Settings")
        self.setMinimumWidth(400)
        
        # Set dialog style
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FC;
            }
            QLabel {
                color: #212529;
            }
            QComboBox, QLineEdit {
                background-color: #FFFFFF;
                color: #212529;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 8px;
            }
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6C757D;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # API provider selection
        provider_layout = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenAI", "DeepInfra"])
        self.provider_combo.setCurrentText("OpenAI" if selected_provider == "openai" else "DeepInfra")
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addRow("API Provider:", self.provider_combo)
        layout.addLayout(provider_layout)
        
        # OpenAI information
        self.openai_info_label = QLabel("Enter your OpenAI API key:")
        self.openai_info_label.setWordWrap(True)
        
        # OpenAI key input
        self.openai_key_input = QLineEdit()
        self.openai_key_input.setText(current_openai_key)
        self.openai_key_input.setPlaceholderText("sk-...")
        self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        # DeepInfra information
        self.deepinfra_info_label = QLabel("Enter your DeepInfra API key:")
        self.deepinfra_info_label.setWordWrap(True)
        
        # DeepInfra key input
        self.deepinfra_key_input = QLineEdit()
        self.deepinfra_key_input.setText(current_deepinfra_key)
        self.deepinfra_key_input.setPlaceholderText("udhgGPY...")
        self.deepinfra_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        # API fields container
        self.api_container = QVBoxLayout()
        self.api_container.addWidget(self.openai_info_label)
        self.api_container.addWidget(self.openai_key_input)
        self.api_container.addWidget(self.deepinfra_info_label)
        self.api_container.addWidget(self.deepinfra_key_input)
        layout.addLayout(self.api_container)
        
        # Show/hide key button
        self.show_key_button = QPushButton("Show Keys")
        self.show_key_button.setCheckable(True)
        self.show_key_button.clicked.connect(self.toggle_key_visibility)
        layout.addWidget(self.show_key_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                     QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # Set initial field visibility
        self.on_provider_changed(self.provider_combo.currentText())
    
    def on_provider_changed(self, provider):
        """Updates interface based on selected API provider"""
        is_openai = provider == "OpenAI"
        self.openai_info_label.setVisible(is_openai)
        self.openai_key_input.setVisible(is_openai)
        self.deepinfra_info_label.setVisible(not is_openai)
        self.deepinfra_key_input.setVisible(not is_openai)
    
    def toggle_key_visibility(self):
        """Toggles API key visibility"""
        mode = QLineEdit.EchoMode.Normal if self.show_key_button.isChecked() else QLineEdit.EchoMode.Password
        self.openai_key_input.setEchoMode(mode)
        self.deepinfra_key_input.setEchoMode(mode)
        self.show_key_button.setText("Hide Keys" if self.show_key_button.isChecked() else "Show Keys")
    
    def get_api_settings(self):
        """Returns API settings"""
        provider = "openai" if self.provider_combo.currentText() == "OpenAI" else "deepinfra"
        openai_key = self.openai_key_input.text().strip()
        deepinfra_key = self.deepinfra_key_input.text().strip()
        return {
            "provider": provider,
            "openai_key": openai_key,
            "deepinfra_key": deepinfra_key
        }

class HotkeyDialog(QDialog):
    """Dialog for setting hotkeys"""
    
    def __init__(self, parent=None, current_hotkeys=None):
        super().__init__(parent)
        self.setWindowTitle("Hotkey Settings")
        self.setMinimumWidth(400)
        
        # Set dialog style
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FC;
            }
            QLabel {
                color: #212529;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #212529;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 8px;
            }
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6C757D;
            }
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
            }
        """)
        
        self.current_hotkeys = current_hotkeys or ["Ctrl", "Shift"]
        self.new_hotkeys = []
        self.listening = False
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Instructions
        info_label = QLabel("Press the key combination you want to use as a hotkey.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Current hotkey display
        current_hotkey_text = " + ".join(self.current_hotkeys)
        self.current_hotkey_label = QLabel(f"Current hotkey: {current_hotkey_text}")
        layout.addWidget(self.current_hotkey_label)
        
        # Hotkey input frame
        hotkey_frame = QFrame()
        hotkey_frame.setMinimumHeight(60)
        hotkey_layout = QVBoxLayout(hotkey_frame)
        
        self.hotkey_display = QLineEdit()
        self.hotkey_display.setReadOnly(True)
        self.hotkey_display.setPlaceholderText("Click 'Start Listening' and press keys...")
        self.hotkey_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_layout.addWidget(self.hotkey_display)
        
        layout.addWidget(hotkey_frame)
        
        # Listen button
        self.listen_button = QPushButton("Start Listening")
        self.listen_button.clicked.connect(self.toggle_listening)
        layout.addWidget(self.listen_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                     QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # Install event filter for key press events
        self.installEventFilter(self)
    
    def toggle_listening(self):
        """Toggles key listening mode"""
        if self.listening:
            self.stop_listening()
        else:
            self.start_listening()
    
    def start_listening(self):
        """Starts listening for key presses"""
        self.listening = True
        self.new_hotkeys = []
        self.hotkey_display.clear()
        self.hotkey_display.setPlaceholderText("Press keys now...")
        self.listen_button.setText("Stop Listening")
        self.listen_button.setStyleSheet("""
            QPushButton {
                background-color: #DC3545;
                color: white;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
        """)
    
    def stop_listening(self):
        """Stops listening for key presses"""
        self.listening = False
        self.listen_button.setText("Start Listening")
        self.listen_button.setStyleSheet("")
        
        if not self.new_hotkeys:
            self.hotkey_display.setPlaceholderText("Click 'Start Listening' and press keys...")
        else:
            self.hotkey_display.setText(" + ".join(self.new_hotkeys))
    
    def eventFilter(self, obj, event):
        """Filters key press events"""
        if self.listening and event.type() == QEvent.Type.KeyPress:
            key_text = self._get_key_text(event)
            
            if key_text and key_text not in self.new_hotkeys:
                self.new_hotkeys.append(key_text)
                self.hotkey_display.setText(" + ".join(self.new_hotkeys))
            
            return True
        
        return super().eventFilter(obj, event)
    
    def _get_key_text(self, event):
        """Converts key event to standardized key name"""
        # Special keys mapping - simplified to only include the keys we use
        special_keys = {
            Qt.Key.Key_Control: "Ctrl",
            Qt.Key.Key_Shift: "Shift",
            Qt.Key.Key_Alt: "Alt",
        }
        
        key = event.key()
        
        # Handle special keys
        if key in special_keys:
            return special_keys[key]
        
        # Handle regular keys (letters, numbers, etc.)
        text = event.text().upper()
        if text and text.isprintable():
            return text
        
        # If we can't determine the key, return None
        return None
    
    def get_hotkey(self):
        """Returns the new hotkey combination"""
        return self.new_hotkeys if self.new_hotkeys else None

class WhisperMainWindow(QMainWindow):
    """Główne okno aplikacji Whisper"""
    
    api_settings_changed = pyqtSignal(dict)
    hotkey_changed = pyqtSignal(list)
    option_changed = pyqtSignal(str, bool)
    microphone_changed = pyqtSignal(str)  # New signal for microphone changes
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper Transcriber")
        self.setMinimumSize(800, 600)
        
        # Ustawienia
        self.settings = QSettings("WhisperApp", "TranscriberSettings")
        self.api_provider = self.settings.value("api_provider", "openai")
        self.openai_key = self.settings.value("openai_key", "")
        self.deepinfra_key = self.settings.value("deepinfra_key", "")
        self.hotkey = self.settings.value("hotkey", ["Ctrl", "Shift"])
        self.selected_microphone = self.settings.value("selected_microphone", "")
        
        # Opcje dodatkowe
        self.auto_paste_enabled = self.settings.value("auto_paste_enabled", True, type=bool)
        self.tray_notifications_enabled = self.settings.value("tray_notifications_enabled", True, type=bool)
        self.startup_enabled = self.settings.value("startup_enabled", False, type=bool)
        
        # Statystyki
        self.stats_manager = StatsManager()
        
        # UI
        self.init_ui()
        
        # Show main view by default
        self.show_main_view()
        
        # System Tray
        self.setup_system_tray()
    
    def init_ui(self):
        # Główny widget i layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create top navigation bar
        self.create_top_navigation()
        
        # Create content container that will hold either main or settings view
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # Add content container to main layout
        self.main_layout.addWidget(self.content_container)
        
        # Style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F8F9FC;
            }
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QLabel {
                color: #212529;
                font-size: 14px;
            }
            QTextEdit, QLineEdit {
                background-color: #FFFFFF;
                color: #212529;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
            }
            QTextEdit::placeholder, QLineEdit::placeholder {
                color: #6C757D;
            }
            QComboBox {
                background-color: #FFFFFF;
                color: #212529;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 8px;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox::down-arrow {
                width: 14px;
                height: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #212529;
                selection-background-color: #007BFF;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QToolButton {
                background-color: transparent;
                border: none;
            }
            QToolButton:hover {
                background-color: rgba(0, 123, 255, 0.1);
                border-radius: 4px;
            }
        """)
    
    def create_top_navigation(self):
        """Creates the top navigation bar"""
        # Create top navigation bar
        nav_bar = QWidget(self)
        nav_bar.setFixedHeight(60)
        nav_bar.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E9ECEF;
            }
        """)
        
        # Set the nav bar to be at the top of the window
        nav_bar.setGeometry(0, 0, self.width(), 60)
        
        # Layout for navigation bar
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(20, 0, 20, 0)
        
        # Application title with microphone icon
        title_layout = QHBoxLayout()
        
        # Create microphone icon
        mic_icon = QLabel()
        mic_pixmap = QPixmap(24, 24)
        mic_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(mic_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw microphone icon
        painter.setPen(QPen(QColor("#212529"), 2))
        painter.setBrush(QColor("#212529"))
        # Base of microphone
        painter.drawRoundedRect(8, 4, 8, 12, 2, 2)
        # Stand of microphone
        painter.drawLine(12, 16, 12, 20)
        painter.drawLine(8, 20, 16, 20)
        painter.end()
        
        mic_icon.setPixmap(mic_pixmap)
        title_layout.addWidget(mic_icon)
        
        # Application title
        app_title = QLabel("Whisper Transcriber")
        app_title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #212529;
        """)
        title_layout.addWidget(app_title)
        
        nav_layout.addLayout(title_layout)
        nav_layout.addStretch()
        
        # Navigation buttons
        nav_buttons_layout = QHBoxLayout()
        
        # Main button (active)
        self.main_button = QPushButton("Main")
        self.main_button.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: #FFFFFF;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
        """)
        self.main_button.clicked.connect(self.show_main_view)
        nav_buttons_layout.addWidget(self.main_button)
        
        # Settings button (inactive)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: #F8F9FC;
                color: #212529;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #E9ECEF;
            }
        """)
        
        # Create gear icon
        gear_icon = QPixmap(16, 16)
        gear_icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(gear_icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#212529"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw a simple gear
        center = QPoint(8, 8)
        painter.drawEllipse(center, 3, 3)
        painter.drawEllipse(center, 6, 6)
        
        # Draw gear teeth
        for i in range(8):
            angle = i * 45
            x1 = center.x() + 6 * math.cos(math.radians(angle))
            y1 = center.y() + 6 * math.sin(math.radians(angle))
            x2 = center.x() + 8 * math.cos(math.radians(angle))
            y2 = center.y() + 8 * math.sin(math.radians(angle))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        painter.end()
        
        self.settings_button.setIcon(QIcon(gear_icon))
        self.settings_button.clicked.connect(self.show_settings_view)
        nav_buttons_layout.addWidget(self.settings_button)
        
        nav_layout.addLayout(nav_buttons_layout)
        
        # Make sure the nav bar stays at the top when window is resized
        self.resizeEvent = lambda event: nav_bar.setGeometry(0, 0, self.width(), 60)
        
        # Store references to content widgets
        self.main_content = None
        self.settings_content = None
    
    def create_recording_section(self):
        """Creates the centered recording section with microphone button"""
        section = QWidget()
        section.setMinimumHeight(200)
        section.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E9ECEF;
            }
        """)
        
        layout = QVBoxLayout(section)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)
        
        # Create large microphone button
        self.record_button = QToolButton()
        self.record_button.setFixedSize(80, 80)
        
        # Create microphone icon
        record_pixmap = QPixmap(80, 80)
        record_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(record_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw blue circle background
        painter.setBrush(QColor("#007BFF"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 80, 80)
        
        # Draw microphone icon
        painter.setPen(QPen(Qt.GlobalColor.white, 3))
        painter.setBrush(Qt.GlobalColor.white)
        # Base of microphone
        painter.drawRoundedRect(32, 20, 16, 24, 4, 4)
        # Stand of microphone
        painter.drawLine(40, 44, 40, 52)
        painter.drawLine(30, 52, 50, 52)
        painter.end()
        
        self.record_icon = QIcon(record_pixmap)
        
        # Create stop icon
        stop_pixmap = QPixmap(80, 80)
        stop_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(stop_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw blue circle background
        painter.setBrush(QColor("#007BFF"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 80, 80)
        
        # Draw stop icon (square)
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawRect(26, 26, 28, 28)
        painter.end()
        
        self.stop_icon = QIcon(stop_pixmap)
        
        # Set initial icon
        self.record_button.setIcon(self.record_icon)
        self.record_button.setIconSize(QSize(80, 80))
        self.record_button.setToolTip("Press to start recording")
        
        # Style the button
        self.record_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
            }
            QToolButton:hover {
                background-color: rgba(0, 123, 255, 0.1);
                border-radius: 40px;
            }
        """)
        
        layout.addWidget(self.record_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Instructional text
        instruction_label = QLabel("Press to start recording")
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_label.setStyleSheet("""
            color: #6C757D;
            font-size: 14px;
        """)
        layout.addWidget(instruction_label)
        
        # Hotkey container - increase width to fit longer text
        hotkey_container = QFrame()
        hotkey_container.setFixedHeight(35)
        hotkey_container.setMinimumWidth(120)  # Increase minimum width
        hotkey_container.setStyleSheet("""
            QFrame {
                background-color: #E9ECEF;
                border-radius: 15px;
                padding: 5px 10px;
            }
        """)
        
        hotkey_layout = QHBoxLayout(hotkey_container)
        hotkey_layout.setContentsMargins(10, 0, 10, 0)
        
        # Set hotkey text with proper width
        hotkey_text = QLabel(" + ".join(self.hotkey))
        hotkey_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_text.setStyleSheet("""
            color: #6C757D;
            font-size: 12px;
        """)
        
        # Ensure the label will expand horizontally
        hotkey_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        hotkey_text.setMinimumWidth(100)
        
        hotkey_layout.addWidget(hotkey_text)
        layout.addWidget(hotkey_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Connect the button to the recording function
        self.record_button.clicked.connect(self.toggle_recording_from_ui)
        
        return section
        
    def toggle_recording_from_ui(self):
        """Handles recording button click from the UI"""
        # This will be connected to the transcriber in whisper_app.py
        # For now, just toggle the button appearance
        if self.record_button.icon().cacheKey() == self.record_icon.cacheKey():
            self.record_button.setIcon(self.stop_icon)
            self.record_button.setToolTip("Press to stop recording")
        else:
            self.record_button.setIcon(self.record_icon)
            self.record_button.setToolTip("Press to start recording")
            
        # This will be properly connected in whisper_app.py
        self.toggle_recording_from_tray()
    
    def toggle_recording_icon(self, is_recording):
        """Toggles the recording button icon based on recording state"""
        if is_recording:
            self.record_button.setIcon(self.stop_icon)
            self.record_button.setToolTip("Press to stop recording")
        else:
            self.record_button.setIcon(self.record_icon)
            self.record_button.setToolTip("Press to start recording")
    
    def create_transcription_section(self):
        """Creates the transcription section"""
        section = QWidget()
        section.setMinimumHeight(150)
        section.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E9ECEF;
            }
        """)
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header with title and action buttons
        header_layout = QHBoxLayout()
        
        # Title
        title_label = QLabel("Transcription")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #212529;
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        # Clear button (trash icon)
        clear_button = QToolButton()
        clear_button.setFixedSize(32, 32)
        clear_pixmap = QPixmap(16, 16)
        clear_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(clear_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw trash icon
        painter.setPen(QPen(QColor("#6C757D"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Trash can body
        painter.drawRect(3, 5, 10, 10)
        # Trash can lid
        painter.drawLine(2, 5, 14, 5)
        painter.drawLine(6, 2, 10, 2)
        painter.drawLine(6, 2, 6, 5)
        painter.drawLine(10, 2, 10, 5)
        # Trash can lines
        painter.drawLine(6, 8, 6, 12)
        painter.drawLine(10, 8, 10, 12)
        painter.end()
        
        clear_button.setIcon(QIcon(clear_pixmap))
        clear_button.setIconSize(QSize(16, 16))
        clear_button.setToolTip("Clear transcription")
        clear_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: rgba(220, 53, 69, 0.1);
            }
        """)
        clear_button.clicked.connect(self.clear_transcript)
        
        # Copy button (clipboard icon)
        copy_button = QToolButton()
        copy_button.setFixedSize(32, 32)
        copy_pixmap = QPixmap(16, 16)
        copy_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(copy_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw clipboard icon
        painter.setPen(QPen(QColor("#007BFF"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Clipboard body
        painter.drawRect(3, 3, 10, 12)
        # Clipboard top
        painter.drawRect(5, 1, 6, 3)
        # Clipboard lines
        painter.drawLine(6, 7, 10, 7)
        painter.drawLine(6, 9, 10, 9)
        painter.drawLine(6, 11, 10, 11)
        painter.end()
        
        copy_button.setIcon(QIcon(copy_pixmap))
        copy_button.setIconSize(QSize(16, 16))
        copy_button.setToolTip("Copy to clipboard")
        copy_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: rgba(0, 123, 255, 0.1);
            }
        """)
        copy_button.clicked.connect(self.copy_transcript)
        
        # Save button (save icon)
        save_button = QToolButton()
        save_button.setFixedSize(32, 32)
        save_pixmap = QPixmap(16, 16)
        save_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(save_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw save icon
        painter.setPen(QPen(QColor("#28A745"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Floppy disk body
        painter.drawRect(2, 2, 12, 12)
        # Floppy disk top
        painter.drawRect(4, 3, 8, 4)
        # Floppy disk hole
        painter.drawRect(10, 4, 2, 2)
        # Floppy disk bottom lines
        painter.drawLine(4, 10, 12, 10)
        painter.drawLine(4, 12, 12, 12)
        painter.end()
        
        save_button.setIcon(QIcon(save_pixmap))
        save_button.setIconSize(QSize(16, 16))
        save_button.setToolTip("Save transcription")
        save_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: rgba(40, 167, 69, 0.1);
            }
        """)
        save_button.clicked.connect(self.save_transcript)
        
        # Add buttons to layout
        buttons_layout.addWidget(clear_button)
        buttons_layout.addWidget(copy_button)
        buttons_layout.addWidget(save_button)
        
        header_layout.addLayout(buttons_layout)
        
        layout.addLayout(header_layout)
        
        # Create transcript text area
        self.transcript_text = QTextEdit()
        self.transcript_text.setPlaceholderText("Transcriptions will appear here...")
        self.transcript_text.setReadOnly(True)
        self.transcript_text.setMinimumHeight(100)
        self.transcript_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        
        layout.addWidget(self.transcript_text)
        
        return section
        
    def save_transcript(self):
        """Saves the transcription to a file"""
        if not self.transcript_text.toPlainText():
            QMessageBox.information(self, "Save Transcription", "There is no transcription to save.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Transcription",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.transcript_text.toPlainText())
                QMessageBox.information(self, "Save Transcription", "Transcription saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save transcription: {str(e)}")
    
    def create_statistics_section(self):
        """Creates the statistics section at the bottom of the window"""
        section = QWidget()
        section.setFixedHeight(80)
        section.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E9ECEF;
            }
        """)
        
        layout = QHBoxLayout(section)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        # Load statistics
        stats = self.stats_manager.get_formatted_stats()
        
        # Create stat widgets
        self.create_stat_widget(layout, "🎤", "#007BFF", "Recordings", str(stats["total_recordings"]))
        self.create_stat_widget(layout, "⏳", "#FFC107", "Total Time", stats["total_time"])
        self.create_stat_widget(layout, "📄", "#28A745", "Characters", f"{stats['total_characters']:,}")
        
        # For the last session, we'll use the time saved instead
        self.create_stat_widget(layout, "⏱", "#6F42C1", "Time Saved", stats["time_saved"])
        
        return section
    
    def create_stat_widget(self, parent_layout, icon, color, label, value):
        """Creates a single statistic widget"""
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border-radius: 8px;
            }}
        """)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"""
            font-size: 24px;
            color: {color};
            padding: 5px;
        """)
        layout.addWidget(icon_label)
        
        # Text content
        text_container = QVBoxLayout()
        text_container.setSpacing(2)
        
        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet("""
            color: #6C757D;
            font-size: 12px;
        """)
        text_container.addWidget(label_widget)
        
        # Value
        value_widget = QLabel(value)
        value_widget.setStyleSheet("""
            color: #212529;
            font-size: 16px;
            font-weight: bold;
        """)
        text_container.addWidget(value_widget)
        
        layout.addLayout(text_container)
        parent_layout.addWidget(container)
        
        return container
    
    def clear_transcript(self):
        """Czyści pole transkrypcji"""
        # Create custom styled message box
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Potwierdzenie")
        msg_box.setText("Czy na pewno chcesz wyczyścić historię transkrypcji?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Apply styling to match the main UI
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #FFFFFF;
            }
            QLabel {
                color: #212529;
                font-size: 14px;
            }
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        
        reply = msg_box.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            self.transcript_text.clear()
    
    def clear_stats(self):
        """Czyści wszystkie statystyki"""
        self.stats_manager.clear_stats()
    
    def create_settings_tab(self):
        """Creates the settings tab with improved layout"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QWidget {
                background-color: transparent;
            }
        """)
        
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Common style for all group boxes
        group_box_style = """
            QGroupBox {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E9ECEF;
                margin-top: 1em;
                padding: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #212529;
                font-weight: bold;
            }
            QLabel {
                color: #212529;
            }
            QCheckBox {
                color: #212529;
            }
            QComboBox {
                background-color: #FFFFFF;
                color: #212529;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 8px;
            }
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """
        
        # Microphone Settings Section
        mic_section = QGroupBox("Microphone Settings")
        mic_section.setStyleSheet(group_box_style)
        mic_layout = QVBoxLayout(mic_section)
        
        # Microphone Selection
        mic_label = QLabel("Select Input Device:")
        self.mic_combo = QComboBox()
        
        # Get available audio input devices
        import pyaudio
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:  # Only add input devices
                name = device_info['name']
                # Add device info to the display text
                display_text = f"{name} (Channels: {int(device_info['maxInputChannels'])})"
                self.mic_combo.addItem(display_text, device_info['index'])
        p.terminate()
        
        # Set current microphone if previously selected
        if self.selected_microphone:
            # Find the item that contains the selected microphone name
            for i in range(self.mic_combo.count()):
                if self.selected_microphone in self.mic_combo.itemText(i):
                    self.mic_combo.setCurrentIndex(i)
                    break
        
        # Create a horizontal layout for microphone selection and refresh button
        mic_selection_layout = QHBoxLayout()
        mic_selection_layout.addWidget(self.mic_combo)
        
        # Add refresh button
        refresh_mic_button = QPushButton("Refresh")
        refresh_mic_button.setToolTip("Scan for new microphones")
        refresh_mic_button.clicked.connect(self.refresh_microphone_list)
        refresh_mic_button.setFixedWidth(80)
        mic_selection_layout.addWidget(refresh_mic_button)
        
        mic_layout.addWidget(mic_label)
        mic_layout.addLayout(mic_selection_layout)
        
        # Save Microphone Button
        save_mic_button = QPushButton("Save Microphone Settings")
        save_mic_button.clicked.connect(self.save_microphone_settings)
        mic_layout.addWidget(save_mic_button)
        
        layout.addWidget(mic_section)
        
        # API Settings Section
        api_section = QGroupBox("API Settings")
        api_section.setStyleSheet(group_box_style)
        api_layout = QVBoxLayout(api_section)
        
        # API Provider Selection
        provider_layout = QHBoxLayout()
        provider_label = QLabel("API Provider:")
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenAI", "DeepInfra"])
        self.provider_combo.setCurrentText("OpenAI" if self.api_provider == "openai" else "DeepInfra")
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self.provider_combo)
        api_layout.addLayout(provider_layout)
        
        # API Key Input
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setText(self.openai_key if self.api_provider == "openai" else self.deepinfra_key)
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.api_key_input)
        api_layout.addLayout(key_layout)
        
        # Save API Settings Button
        save_api_button = QPushButton("Save API Settings")
        save_api_button.clicked.connect(self.save_api_settings)
        api_layout.addWidget(save_api_button)
        
        layout.addWidget(api_section)
        
        # Hotkey Settings Section
        hotkey_section = QGroupBox("Hotkey Settings")
        hotkey_section.setStyleSheet(group_box_style)
        hotkey_layout = QVBoxLayout(hotkey_section)
        
        # Checkboxes for modifier keys
        self.ctrl_check = QCheckBox("Ctrl")
        self.shift_check = QCheckBox("Shift")
        self.alt_check = QCheckBox("Alt")
        
        # Set initial state based on current hotkey
        self.ctrl_check.setChecked("Ctrl" in self.hotkey)
        self.shift_check.setChecked("Shift" in self.hotkey)
        self.alt_check.setChecked("Alt" in self.hotkey)
        
        hotkey_layout.addWidget(QLabel("Select at least 2 modifier keys:"))
        hotkey_layout.addWidget(self.ctrl_check)
        hotkey_layout.addWidget(self.shift_check)
        hotkey_layout.addWidget(self.alt_check)
        
        # Save Hotkey Button
        save_hotkey_button = QPushButton("Save Hotkey")
        save_hotkey_button.clicked.connect(self.save_hotkey_settings)
        hotkey_layout.addWidget(save_hotkey_button)
        
        layout.addWidget(hotkey_section)
        
        # Additional Options Section
        options_section = QGroupBox("Additional Options")
        options_section.setStyleSheet(group_box_style)
        options_layout = QVBoxLayout(options_section)
        
        # Auto-paste option
        self.auto_paste_check = QCheckBox("Enable automatic pasting")
        self.auto_paste_check.setChecked(self.auto_paste_enabled)
        options_layout.addWidget(self.auto_paste_check)
        
        # Tray notifications option
        self.tray_notif_check = QCheckBox("Enable tray notifications")
        self.tray_notif_check.setChecked(self.tray_notifications_enabled)
        options_layout.addWidget(self.tray_notif_check)
        
        # Startup option
        self.startup_check = QCheckBox("Start with system")
        self.startup_check.setChecked(self.startup_enabled)
        options_layout.addWidget(self.startup_check)
        
        # Save Options Button
        save_options_button = QPushButton("Save Options")
        save_options_button.clicked.connect(self.save_additional_options)
        options_layout.addWidget(save_options_button)
        
        layout.addWidget(options_section)
        
        # Add a spacer at the bottom
        layout.addStretch()
        
        scroll_area.setWidget(tab)
        return scroll_area
    
    def on_provider_changed(self, provider):
        """Updates the API key input when provider is changed"""
        self.api_key_input.setText(self.openai_key if provider == "OpenAI" else self.deepinfra_key)
    
    def save_api_settings(self):
        """Saves the API settings"""
        provider = self.provider_combo.currentText()
        api_key = self.api_key_input.text().strip()
        
        if not api_key:
            QMessageBox.warning(self, "API Settings", "API key cannot be empty.")
            return
        
        self.api_provider = provider.lower()
        if self.api_provider == "openai":
            self.openai_key = api_key
            self.settings.setValue("openai_key", api_key)
        else:
            self.deepinfra_key = api_key
            self.settings.setValue("deepinfra_key", api_key)
        
        self.settings.setValue("api_provider", self.api_provider)
        
        self.api_settings_changed.emit({
            "provider": self.api_provider,
            "key": api_key
        })
        
        QMessageBox.information(self, "API Settings", f"API settings for {provider} have been saved.")
    
    def save_hotkey_settings(self):
        """Saves the hotkey settings"""
        selected_keys = []
        if self.ctrl_check.isChecked():
            selected_keys.append("Ctrl")
        if self.shift_check.isChecked():
            selected_keys.append("Shift")
        if self.alt_check.isChecked():
            selected_keys.append("Alt")
        
        if len(selected_keys) < 2:
            QMessageBox.warning(self, "Hotkey Settings", "Please select at least 2 modifier keys.")
            return
        
        self.hotkey = selected_keys
        self.settings.setValue("hotkey", selected_keys)
        self.hotkey_changed.emit(selected_keys)
        
        QMessageBox.information(self, "Hotkey Settings", f"Hotkey has been changed to {' + '.join(selected_keys)}")
    
    def save_additional_options(self):
        """Saves the additional options"""
        # Update auto-paste setting
        auto_paste = self.auto_paste_check.isChecked()
        self.auto_paste_enabled = auto_paste
        self.settings.setValue("auto_paste_enabled", auto_paste)
        self.option_changed.emit("auto_paste", auto_paste)
        
        # Update tray notifications setting
        tray_notif = self.tray_notif_check.isChecked()
        self.tray_notifications_enabled = tray_notif
        self.settings.setValue("tray_notifications_enabled", tray_notif)
        self.option_changed.emit("tray_notifications", tray_notif)
        
        # Update startup setting
        startup = self.startup_check.isChecked()
        self.startup_enabled = startup
        self.settings.setValue("startup_enabled", startup)
        self.option_changed.emit("startup", startup)
        self.set_startup_registry(startup)
        
        QMessageBox.information(self, "Options", "Additional options have been saved.")

    def set_startup_registry(self, enable):
        """Sets or removes registry entry for autostart"""
        try:
            import winreg as reg
            
            # Registry key path for startup programs
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            # Open or create key
            registry_key = reg.OpenKey(reg.HKEY_CURRENT_USER, key_path, 0, reg.KEY_WRITE)
            
            app_path = sys.argv[0]
            # If launched by Python, find the proper path
            if app_path.endswith('.py'):
                app_path = f'pythonw "{app_path}"'
            elif not app_path.endswith('.exe'):
                # If not exe or py, probably a script run by Python
                app_path = f'pythonw "{app_path}"'
                
            if enable:
                # Add program to autostart
                reg.SetValueEx(registry_key, "WhisperTranscriber", 0, reg.REG_SZ, app_path)
                print(f"Added application to autostart: {app_path}")
            else:
                try:
                    # Remove program from autostart
                    reg.DeleteValue(registry_key, "WhisperTranscriber")
                    print("Removed application from autostart")
                except FileNotFoundError:
                    # Key doesn't exist, nothing to remove
                    pass
                    
            reg.CloseKey(registry_key)
            return True
        except Exception as e:
            print(f"Error configuring autostart: {e}")
            QMessageBox.warning(
                self,
                "Autostart Configuration Error",
                f"An error occurred while configuring autostart: {e}"
            )
            return False
    
    def setup_system_tray(self):
        """Configures the system tray icon"""
        # Create the tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Create a default icon if the icon file doesn't exist
        if os.path.exists("whisper_icon.png"):
            icon = QIcon("whisper_icon.png")
        else:
            # Create a simple blue icon
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#007BFF"))  # Blue color from the UI
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(8, 8, 48, 48, 10, 10)
            
            # Add a microphone icon
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.setBrush(Qt.GlobalColor.white)
            # Base of microphone
            painter.drawRoundedRect(24, 18, 16, 20, 4, 4)
            # Stand of microphone
            painter.drawLine(32, 38, 32, 44)
            painter.drawLine(24, 44, 40, 44)
            painter.end()
            
            icon = QIcon(pixmap)
        
        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)  # Set the same icon for the application window
        
        # Create context menu for the tray icon
        tray_menu = QMenu()
        
        # Show/hide action
        self.show_action = QAction("Show", self)
        self.show_action.triggered.connect(self.show_window)
        tray_menu.addAction(self.show_action)
        
        # Recording action
        self.record_action = QAction("Start Recording", self)
        self.record_action.triggered.connect(self.toggle_recording_from_tray)
        tray_menu.addAction(self.record_action)
        
        # Separator
        tray_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close_from_tray)
        tray_menu.addAction(exit_action)
        
        # Set the menu for the tray icon
        self.tray_icon.setContextMenu(tray_menu)
        
        # Handle tray icon clicks
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # Show the tray icon
        self.tray_icon.show()
        
        # Set tooltip
        self.tray_icon.setToolTip("Whisper Transcriber")
    
    def show_window(self):
        """Shows the application window"""
        self.showNormal()
        self.activateWindow()
        self.show_action.setText("Hide")
    
    def tray_icon_activated(self, reason):
        """Handles tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click
            if self.isVisible():
                self.hide()
                self.show_action.setText("Show")
            else:
                self.show_window()
    
    def closeEvent(self, event):
        """Handles window close event"""
        # Minimize to tray instead of closing
        event.ignore()
        self.hide()
        self.show_action.setText("Show")
        
        if self.tray_notifications_enabled:
            self.tray_icon.showMessage(
                "Whisper Transcriber",
                "Application is running in the background. Click the icon to show.",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
    
    def close_from_tray(self):
        """Closes the application from the system tray"""
        self.tray_icon.hide()  # Hide the icon before closing
        QApplication.quit()
    
    def copy_transcript(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.transcript_text.toPlainText())

    def update_last_recording_stats(self, duration_seconds, text):
        """Updates statistics after recording completion"""
        chars = len(text)
        
        # Update general statistics
        self.stats_manager.update_recording_stats(duration_seconds, chars)
        
        # If we're in the main view, refresh the statistics section
        if hasattr(self, 'content_layout') and self.content_layout.count() > 0:
            # Find the main content widget if it exists
            main_content = None
            for i in range(self.content_layout.count()):
                widget = self.content_layout.itemAt(i).widget()
                if widget:
                    main_content = widget
                    break
            
            if main_content and main_content.layout():
                # Remove any existing statistics section (usually the last widget)
                for i in reversed(range(main_content.layout().count())):
                    widget = main_content.layout().itemAt(i).widget()
                    if widget and widget.height() == 80:  # Stats section has fixed height of 80
                        widget.deleteLater()
                        break
                
                # Add the new statistics section
                main_content.layout().addWidget(self.create_statistics_section())
        
    def show_main_view(self):
        """Shows the main view"""
        # Update button styles
        self.main_button.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: #FFFFFF;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
        """)
        
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: #F8F9FC;
                color: #212529;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #E9ECEF;
            }
        """)
        
        # Clear existing content
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Create main content widget
        main_content = QWidget()
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setContentsMargins(20, 80, 20, 20)  # Extra top margin for nav bar
        main_content_layout.setSpacing(20)
        
        # Add sections
        main_content_layout.addWidget(self.create_recording_section())
        main_content_layout.addWidget(self.create_transcription_section())
        main_content_layout.addWidget(self.create_statistics_section())
        
        # Add to content container
        self.content_layout.addWidget(main_content)
    
    def show_settings_view(self):
        """Shows the settings view"""
        # Update button styles
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: #FFFFFF;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
        """)
        
        self.main_button.setStyleSheet("""
            QPushButton {
                background-color: #F8F9FC;
                color: #212529;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #E9ECEF;
            }
        """)
        
        # Clear existing content
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Create settings content
        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)
        settings_layout.setContentsMargins(20, 80, 20, 20)  # Extra top margin for nav bar
        settings_layout.setSpacing(20)
        
        # Add settings content
        settings_layout.addWidget(self.create_settings_tab())
        
        # Add to content container
        self.content_layout.addWidget(settings_content)
    
    def toggle_recording_from_tray(self):
        """Toggles recording from the system tray"""
        # This function will be connected to the transcriber object in whisper_app.py
        pass
    
    def on_tray_notifications_changed(self, index):
        """Handles change in tray notification settings"""
        enabled = (index == 0)
        self.tray_notifications_enabled = enabled
        self.settings.setValue("tray_notifications_enabled", enabled)
        self.option_changed.emit("tray_notifications", enabled)
    
    def on_auto_paste_changed(self, index):
        """Handles change in automatic pasting settings"""
        enabled = (index == 0)
        self.auto_paste_enabled = enabled
        self.settings.setValue("auto_paste_enabled", enabled)
        self.option_changed.emit("auto_paste", enabled)
        
    def on_startup_changed(self, index):
        """Handles change in startup settings"""
        enabled = (index == 0)
        self.startup_enabled = enabled
        self.settings.setValue("startup_enabled", enabled)
        self.option_changed.emit("startup", enabled)
        
        if enabled:
            self.set_startup_registry(True)
        else:
            self.set_startup_registry(False)

    def save_microphone_settings(self):
        """Saves the selected microphone settings"""
        if self.mic_combo.currentText() == "No microphones found":
            QMessageBox.warning(self, "No Microphone Selected", "No valid microphone is available to select.")
            return
            
        # Extract just the microphone name without the additional info
        full_text = self.mic_combo.currentText()
        mic_name = full_text.split(" (Channels:")[0]
        
        # Store the microphone name with proper encoding
        self.selected_microphone = mic_name
        self.settings.setValue("selected_microphone", mic_name)
        self.microphone_changed.emit(mic_name)
        QMessageBox.information(self, "Microphone Settings", f"Microphone has been set to: {mic_name}")

    def refresh_microphone_list(self):
        """Refreshes the list of available microphones"""
        self.mic_combo.clear()
        
        # Get available audio input devices
        import pyaudio
        p = pyaudio.PyAudio()
        found_devices = False
        
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:  # Only add input devices
                found_devices = True
                name = device_info['name']
                
                # Fix encoding of device name for display
                try:
                    name_utf8 = name.encode('latin1').decode('utf-8')
                except (UnicodeDecodeError, UnicodeEncodeError):
                    name_utf8 = name
                    
                # Add device info to the display text
                display_text = f"{name_utf8} (Channels: {int(device_info['maxInputChannels'])})"
                self.mic_combo.addItem(display_text, device_info['index'])
        p.terminate()
        
        if not found_devices:
            self.mic_combo.addItem("No microphones found")
            QMessageBox.warning(self, "No Microphones", "No microphone devices were found on your system.")
        else:
            # Set current microphone if previously selected
            if self.selected_microphone:
                # Find the item that contains the selected microphone name
                for i in range(self.mic_combo.count()):
                    if self.selected_microphone in self.mic_combo.itemText(i):
                        self.mic_combo.setCurrentIndex(i)
                        break
            
            QMessageBox.information(self, "Microphones Refreshed", f"Found {self.mic_combo.count()} microphone device(s).")

    def get_api_settings(self):
        """Returns current API settings"""
        return {
            "provider": self.api_provider,
            "key": self.get_active_api_key()
        }
    
    def get_active_api_key(self):
        """Returns active API key based on selected provider"""
        if self.api_provider == "openai":
            return self.openai_key
        elif self.api_provider == "deepinfra":
            return self.deepinfra_key
        return ""
    
    def get_selected_microphone(self):
        """Returns the currently selected microphone"""
        return self.selected_microphone

    def get_options(self):
        """Returns current application options"""
        return {
            "auto_paste_enabled": self.auto_paste_enabled,
            "sound_notifications_enabled": self.settings.value("sound_notifications_enabled", True, type=bool),
            "tray_notifications_enabled": self.tray_notifications_enabled,
            "startup_enabled": self.startup_enabled
        }

    def get_hotkey(self):
        """Returns the current hotkey combination"""
        return self.hotkey
    
    def refresh_statistics(self):
        """Refreshes the statistics section"""
        # Find the main content widget
        main_content = None
        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if widget and hasattr(widget, 'layout'):
                main_content = widget
                break
                
        if not main_content:
            return
            
        # Find and remove the statistics section if it exists
        main_layout = main_content.layout()
        if not main_layout:
            return
            
        for i in reversed(range(main_layout.count())):
            widget = main_layout.itemAt(i).widget()
            if widget and widget.height() == 80:  # Stats section has fixed height
                widget.deleteLater()
                break
                
        # Add the new statistics section
        main_layout.addWidget(self.create_statistics_section())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WhisperMainWindow()
    window.show()
    sys.exit(app.exec())
