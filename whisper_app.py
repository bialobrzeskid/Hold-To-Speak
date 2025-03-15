import sys
import os
import pyaudio
import wave
import requests
import time
import asyncio
import aiohttp
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMessageBox
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRunnable, QThreadPool, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from pynput import keyboard
import pyperclip
import winsound

# Importuj nasze moduły UI
from whisper_ui import WhisperMainWindow
from recording_popup import RecordingPopup

# Parametry nagrywania
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000
CHUNK = 4096
WAVE_OUTPUT_FILENAME = "output.mp3"

class KeyboardHandler(QObject):
    start_recording_signal = pyqtSignal()
    stop_recording_signal = pyqtSignal()
    
    def __init__(self, hotkeys=None):
        super().__init__()
        # Słownik przechowujący informacje o wciśniętych klawiszach
        self.pressed_keys = {}
        self.recording = False
        self.hotkeys = hotkeys or ["Ctrl", "Shift"]
        self.setup_listener()
    
    def setup_listener(self):
        def on_press(key):
            try:
                # Próba konwersji nazwy klawisza
                key_name = self._convert_key_to_name(key)
                self.pressed_keys[key_name] = True
                
                # Sprawdź czy wszystkie hotkeys są wciśnięte
                if self.check_hotkey_combination() and not self.recording:
                    self.recording = True
                    self.start_recording_signal.emit()
            except Exception as e:
                print(f"Błąd podczas przetwarzania wciśnięcia klawisza: {str(e)}")
        
        def on_release(key):
            try:
                # Próba konwersji nazwy klawisza
                key_name = self._convert_key_to_name(key)
                if key_name in self.pressed_keys:
                    self.pressed_keys[key_name] = False
                
                # Jeśli nagrywamy i któryś z klawiszy hotkey został puszczony, zatrzymaj nagrywanie
                if self.recording and not self.check_hotkey_combination():
                    self.recording = False
                    self.stop_recording_signal.emit()
            except Exception as e:
                print(f"Błąd podczas przetwarzania puszczenia klawisza: {str(e)}")
        
        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.start()
    
    def _convert_key_to_name(self, key):
        """Konwertuje obiekt klawisza na ustandaryzowaną nazwę"""
        # Obsługa specjalnych klawiszy - uproszczona do tylko używanych klawiszy
        special_keys = {
            keyboard.Key.alt: "Alt",
            keyboard.Key.alt_l: "Alt",
            keyboard.Key.alt_r: "Alt",
            keyboard.Key.ctrl: "Ctrl",
            keyboard.Key.ctrl_l: "Ctrl",
            keyboard.Key.ctrl_r: "Ctrl",
            keyboard.Key.shift: "Shift",
            keyboard.Key.shift_l: "Shift",
            keyboard.Key.shift_r: "Shift",
        }
        
        if key in special_keys:
            return special_keys[key]
        
        # Obsługa zwykłych klawiszy znakowych
        try:
            # Jeśli to klawisz alfanumeryczny, zwróć jego reprezentację
            return key.char.upper()
        except AttributeError:
            # Jeśli nie udało się uzyskać znaku, zwróć reprezentację string klawisza
            return str(key).replace("'", "")
    
    def check_hotkey_combination(self):
        """Sprawdza czy wszystkie klawisze hotkey są aktualnie wciśnięte"""
        for key in self.hotkeys:
            if key not in self.pressed_keys or not self.pressed_keys[key]:
                return False
        return True
    
    def update_hotkeys(self, new_hotkeys):
        """Aktualizuje skróty klawiszowe"""
        self.hotkeys = new_hotkeys
        # Czyścimy słownik wciśniętych klawiszy, aby uniknąć konfliktów
        self.pressed_keys = {}
        print(f"Zaktualizowano skróty klawiszowe: {self.hotkeys}")

class WorkerSignals(QObject):
    """Sygnały używane przez Worker do komunikacji z głównym wątkiem"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

class Worker(QRunnable):
    """Klasa Worker do wykonywania zadań w osobnym wątku"""
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

class WhisperTranscriber(QObject):
    """Klasa obsługująca nagrywanie i transkrypcję"""
    
    transcription_complete = pyqtSignal(str, float)  # Tekst, czas nagrywania
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.recording = False
        self.frames = []
        self.stream = None
        self.recording_start_time = None
        self.api_provider = "openai"  # Domyślnie OpenAI
        self.api_key = ""
        self.selected_mic_index = None
        
        # Opcje
        self.auto_paste_enabled = True
        self.sound_notifications_enabled = False
        self.tray_notifications_enabled = True
        
        # Inicjalizacja PyAudio przy starcie - będzie używana przez całą aplikację
        self.audio = pyaudio.PyAudio()
        print("PyAudio zainicjalizowany")
        
        # Połącz sygnały UI z metodami
        self.main_window.record_button.clicked.connect(self.toggle_recording)
        self.main_window.api_settings_changed.connect(self.update_api_settings)
        self.main_window.hotkey_changed.connect(self.update_hotkeys)
        self.main_window.option_changed.connect(self.update_option)
        self.main_window.microphone_changed.connect(self.update_microphone)
        
        # Połącz akcję nagrywania z zasobnika systemowego
        self.main_window.record_action.triggered.connect(self.toggle_recording)
        
        # Pobierz aktualne ustawienia API
        api_settings = self.main_window.get_api_settings()
        self.update_api_settings(api_settings)
        
        # Pobierz aktualne ustawienia opcji
        options = self.main_window.get_options()
        self.auto_paste_enabled = options.get("auto_paste_enabled", True)
        self.sound_notifications_enabled = options.get("sound_notifications_enabled", True)
        self.tray_notifications_enabled = options.get("tray_notifications_enabled", True)
        
        # Get initial microphone selection
        self.update_microphone(self.main_window.get_selected_microphone())
        
        # Utwórz obsługę klawiatury
        self.keyboard_handler = KeyboardHandler(self.main_window.get_hotkey())
        self.keyboard_handler.start_recording_signal.connect(self.start_recording)
        self.keyboard_handler.stop_recording_signal.connect(self.stop_recording)
        
        # Create recording popup
        self.popup = RecordingPopup()
        
        # Timer dla licznika nagrywania
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_recording_timer)
        self.recording_time_seconds = 0
        
        # Timer do zbierania audio
        self.audio_timer = QTimer()
        self.audio_timer.timeout.connect(self.collect_audio)
        
        # Inicjalizuj ThreadPool do obsługi zadań asynchronicznych
        self.threadpool = QThreadPool()
        print(f"Dostępnych wątków: {self.threadpool.maxThreadCount()}")
        
        # Check if any microphones are available and show a message if not
        self.check_microphone_availability()
    
    def __del__(self):
        """Destruktor - upewnij się, że PyAudio jest poprawnie zamykany"""
        if hasattr(self, 'audio') and self.audio:
            try:
                self.audio.terminate()
                print("PyAudio zamknięty")
            except:
                pass
    
    def play_notification(self, start=True):
        """Odtwarza dźwięk powiadomienia o rozpoczęciu lub zakończeniu nagrywania"""
        if not self.sound_notifications_enabled:
            return
            
        if not start:
            # Dźwięk rozpoczęcia nagrywania (wyższy ton)
            winsound.Beep(200, 200)  # 1000 Hz przez 200 ms
    
    def update_recording_timer(self):
        """Aktualizuje wyświetlany czas nagrywania"""
        self.recording_time_seconds += 1
        self.popup.update_timer(self.recording_time_seconds)
    
    def toggle_recording(self):
        """Przełącznik nagrywania dla przycisku UI i zasobnika systemowego"""
        if not self.recording:
            self.start_recording()
            # Aktualizacja akcji nagrywania w zasobniku i ikony przycisku
            self.main_window.record_action.setText("Zatrzymaj nagrywanie")
            self.main_window.toggle_recording_icon(True)
        else:
            self.stop_recording()
            # Aktualizacja akcji nagrywania w zasobniku i ikony przycisku
            self.main_window.record_action.setText("Rozpocznij nagrywanie")
            self.main_window.toggle_recording_icon(False)
    
    def start_recording(self):
        """Rozpoczyna nagrywanie"""
        if self.recording:  # Zabezpieczenie przed podwójnym startem
            return
            
        # Natychmiast ustaw flagę nagrywania - to powinno być na początku
        self.recording = True
        self.recording_start_time = time.time()
        self.recording_time_seconds = 0
        
        # Show recording popup
        self.popup.show_recording()
        
        # Aktualizacja UI i uruchomienie timerów - tylko niezbędne operacje
        self.main_window.toggle_recording_icon(True)
        self.recording_timer.start(1000)  # Aktualizuj timer co sekundę
        
        # Przygotuj nagrywanie audio - używamy istniejącej instancji PyAudio
        self.frames = []
        
        # Try to use the selected microphone or find a default one
        input_device = self.selected_mic_index
        valid_input_device = False
        
        # If no specific device is selected, try to find any valid input device
        if input_device is None:
            try:
                default_device_info = self.audio.get_default_input_device_info()
                if default_device_info and default_device_info['maxInputChannels'] > 0:
                    input_device = default_device_info['index']
                    valid_input_device = True
                    print(f"Using default input device: {default_device_info['name']} (index: {input_device})")
                else:
                    valid_input_device = False
            except Exception as e:
                print(f"Error getting default input device: {str(e)}")
                valid_input_device = False
                
            # If no default device works, try finding any input device
            if not valid_input_device:
                for i in range(self.audio.get_device_count()):
                    device_info = self.audio.get_device_info_by_index(i)
                    if device_info['maxInputChannels'] > 0:
                        input_device = i
                        valid_input_device = True
                        print(f"Using input device: {device_info['name']} (index: {i})")
                        break
        else:
            # Check if the selected device is valid
            try:
                device_info = self.audio.get_device_info_by_index(input_device)
                if device_info['maxInputChannels'] > 0:
                    valid_input_device = True
            except Exception as e:
                print(f"Error checking selected input device: {str(e)}")
                valid_input_device = False
        
        if not valid_input_device:
            error_msg = "Nie znaleziono żadnego urządzenia wejściowego audio (mikrofonu)."
            print(error_msg)
            self.main_window.transcript_text.append(f"Błąd: {error_msg}\n\n")
            self.stop_recording()
            return
            
        try:
            # Utwórz nowy strumień audio używając istniejącej instancji PyAudio
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=input_device,
                frames_per_buffer=CHUNK
            )
            
            # Uruchom timer do zbierania audio
            self.audio_timer.start(20)  # Zbieraj dane co 20ms
            
        except Exception as e:
            print(f"Błąd podczas inicjalizacji strumienia audio: {e}")
            self.main_window.transcript_text.append(f"Błąd podczas inicjalizacji strumienia audio: {str(e)}\n\n")
            self.stop_recording()
            return
        
        # Powiadomienie dźwiękowe na końcu (może być opóźnione)
        if self.sound_notifications_enabled:
            QTimer.singleShot(50, lambda: self.play_notification(start=True))
    
    def collect_audio(self):
        """Zbiera dane audio"""
        if self.recording:
            try:
                data = self.stream.read(CHUNK)
                self.frames.append(data)
            except Exception as e:
                print(f"Błąd podczas nagrywania: {str(e)}")
                self.stop_recording()
    
    def stop_recording(self):
        """Zatrzymuje nagrywanie"""
        if not self.recording:
            return
        
        # Zatrzymaj timer nagrywania
        self.recording_timer.stop()
        
        # Show processing state in popup
        self.popup.show_processing()
        
        # Usuń sprawdzanie minimalnego czasu nagrywania
        # Natychmiast przejdź do finalizacji
        self.finalize_recording()
    
    def finalize_recording(self):
        """Finalizuje nagrywanie i wysyła do API"""
        self.recording = False
        recording_duration = time.time() - self.recording_start_time
        
        # Zatrzymaj nagrywanie - najważniejsze operacje najpierw
        if self.audio_timer.isActive():
            self.audio_timer.stop()
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            except Exception as e:
                print(f"Błąd podczas zatrzymywania strumienia: {str(e)}")
        
        # Aktualizacja UI może poczekać
        self.main_window.record_action.setText("Rozpocznij nagrywanie")
        self.main_window.toggle_recording_icon(False)
        
        # Powiadomienie dźwiękowe
        if self.sound_notifications_enabled:
            winsound.Beep(200, 100)  # Krótszy dźwięk (100ms zamiast 200ms)
        
        if len(self.frames) > 0:
            # Zapisz plik audio - użyj bardziej wydajnej metody
            try:
                with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wave_file:
                    wave_file.setnchannels(CHANNELS)
                    wave_file.setsampwidth(self.audio.get_sample_size(FORMAT))
                    wave_file.setframerate(RATE)
                    wave_file.writeframes(b''.join(self.frames))
                
                # Wyślij do API - przeprowadzamy równoczesne operacje
                QApplication.processEvents()  # Odśwież UI podczas oczekiwania
                self.send_audio_to_whisper(WAVE_OUTPUT_FILENAME, recording_duration)
            except Exception as e:
                error_text = f"Błąd podczas zapisu audio: {str(e)}\n\n"
                self.main_window.transcript_text.append(error_text)
                
                # Ukryj popup w przypadku błędu
                self.popup.hide_popup()
        else:
            self.main_window.transcript_text.append("Błąd: Nie zarejestrowano żadnego dźwięku\n\n")
            self.main_window.transcript_text.append(f"Gotowy do nagrywania ({' + '.join(self.main_window.get_hotkey())})")
            # Ukryj popup
            self.popup.hide_popup()
    
    def send_audio_to_whisper(self, file_path, duration):
        """Wysyła audio do wybranego API asynchronicznie"""
        api_settings = self.main_window.get_api_settings()
        api_provider = api_settings["provider"]
        api_key = api_settings["key"]
        
        if not api_key:
            self.main_window.transcript_text.append(f"Błąd: Brak klucza API {api_provider.upper()}. Ustaw klucz w zakładce Ustawienia.\n\n")
            
            # Ukryj popup
            self.popup.hide_popup()
            return
        
        # Wybór API w zależności od dostawcy - uruchamiamy asynchronicznie
        if api_provider == "openai":
            worker = Worker(self.send_to_openai_async, file_path, api_key, duration)
            worker.signals.finished.connect(self.on_transcription_result)
            worker.signals.error.connect(self.on_transcription_error)
            self.threadpool.start(worker)
        elif api_provider == "deepinfra":
            worker = Worker(self.send_to_deepinfra_async, file_path, api_key, duration)
            worker.signals.finished.connect(self.on_transcription_result)
            worker.signals.error.connect(self.on_transcription_error)
            self.threadpool.start(worker)
        else:
            self.main_window.transcript_text.append(f"Błąd: Nieznany dostawca API: {api_provider}\n\n")
            
            # Ukryj popup
            self.popup.hide_popup()
    
    def send_to_openai_async(self, file_path, api_key, duration):
        """Wysyła audio do API OpenAI - wersja asynchroniczna"""
        url = "https://api.openai.com/v1/audio/transcriptions"
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            with open(file_path, 'rb') as audio_file:
                files = {
                    'file': (file_path, audio_file, 'audio/wav'),
                    'model': (None, 'whisper-1')
                }
                response = requests.post(url, headers=headers, files=files)
            
            if response.status_code == 200:
                result = response.json()
                transcribed_text = result['text']
                return {
                    "text": transcribed_text,
                    "duration": duration,
                    "success": True
                }
            else:
                return {
                    "error": f"Błąd OpenAI API: {response.status_code}\n{response.text}",
                    "success": False
                }
        except Exception as e:
            return {
                "error": f"Błąd podczas przetwarzania: {str(e)}",
                "success": False
            }
    
    def send_to_deepinfra_async(self, file_path, api_key, duration):
        """Wysyła audio do API DeepInfra - wersja asynchroniczna"""
        url = "https://api.deepinfra.com/v1/inference/openai/whisper-large-v3-turbo"
        
        try:
            headers = {
                "Authorization": f"bearer {api_key}"
            }
            
            with open(file_path, 'rb') as audio_file:
                files = {
                    'audio': (file_path, audio_file, 'audio/wav'),
                }
                response = requests.post(url, headers=headers, files=files)
            
            if response.status_code == 200:
                result = response.json()
                
                # DeepInfra może zwrócić tekst na kilka sposobów
                if "text" in result and result["text"]:
                    transcribed_text = result["text"]
                elif "segments" in result and result["segments"]:
                    # Łączymy segmenty tekstu
                    segments = [seg["text"] for seg in result["segments"] if "text" in seg]
                    transcribed_text = " ".join(segments)
                else:
                    transcribed_text = "Brak tekstu w odpowiedzi API."
                
                return {
                    "text": transcribed_text,
                    "duration": duration,
                    "success": True
                }
            else:
                return {
                    "error": f"Błąd DeepInfra API: {response.status_code}\n{response.text}",
                    "success": False
                }
        except Exception as e:
            return {
                "error": f"Błąd podczas przetwarzania DeepInfra API: {str(e)}",
                "success": False
            }
    
    def on_transcription_result(self, result):
        """Obsługuje wynik transkrypcji z wątku roboczego"""
        if result["success"]:
            transcribed_text = result["text"]
            duration = result["duration"]
            
            # Dodaj tekst do interfejsu
            self.main_window.transcript_text.append(transcribed_text + "\n\n")
            
            # Kopiuj tekst do schowka i symuluj wklejenie
            if self.auto_paste_enabled:
                self.paste_text_to_clipboard(transcribed_text)
            else:
                pyperclip.copy(transcribed_text)
            
            # Aktualizuj statystyki - bezpieczna wersja
            try:
                # Update statistics in the stats_manager
                self.main_window.stats_manager.update_recording_stats(duration, len(transcribed_text))
                
                # Force refresh of the main view if it's currently visible
                if self.main_window.isVisible() and hasattr(self.main_window, 'main_button'):
                    if self.main_window.main_button.styleSheet().find("background-color: #007BFF") >= 0:
                        # We're in main view, refresh statistics
                        QTimer.singleShot(100, self.main_window.refresh_statistics)
            except Exception as e:
                print(f"Error updating statistics: {str(e)}")
            
            # Emituj sygnał o zakończeniu transkrypcji
            self.transcription_complete.emit(transcribed_text, duration)
        else:
            # W przypadku błędu
            error_text = result["error"] + "\n\n"
            self.main_window.transcript_text.append(error_text)
        
        # Ukryj popup
        self.popup.hide_popup()

    def on_transcription_error(self, error_message):
        """Handles errors during transcription"""
        error_text = f"Błąd transkrypcji: {error_message}\n\n"
        self.main_window.transcript_text.append(error_text)
        
        # Hide processing popup
        if hasattr(self, 'popup'):
            self.popup.hide_popup()
    
    def paste_text_to_clipboard(self, text):
        """Copies text to clipboard and simulates pasting if auto-paste is enabled"""
        # Copy to clipboard
        pyperclip.copy(text)
        
        # Simulate Ctrl+V keypress if auto-paste is enabled
        if self.auto_paste_enabled:
            try:
                # Small delay to ensure clipboard is updated
                time.sleep(0.1)
                keyboard_controller = keyboard.Controller()
                keyboard_controller.press(keyboard.Key.ctrl)
                keyboard_controller.press('v')
                keyboard_controller.release('v')
                keyboard_controller.release(keyboard.Key.ctrl)
            except Exception as e:
                print(f"Error simulating paste: {str(e)}")

    def update_api_settings(self, settings):
        """Aktualizuje ustawienia API"""
        self.api_provider = settings.get("provider", "openai")
        self.api_key = settings.get("key", "")
        print(f"Zaktualizowano ustawienia API: {self.api_provider}")

    def update_hotkeys(self, new_hotkeys):
        """Updates hotkey settings in keyboard handler"""
        if hasattr(self, 'keyboard_handler'):
            self.keyboard_handler.update_hotkeys(new_hotkeys)
            print(f"Hotkeys updated to: {new_hotkeys}")

    def update_option(self, option_name, value):
        """Updates application options"""
        if option_name == "auto_paste":
            self.auto_paste_enabled = value
            print(f"Auto paste option set to: {value}")
        elif option_name == "tray_notifications":
            self.tray_notifications_enabled = value
            print(f"Tray notifications option set to: {value}")
        elif option_name == "sound_notifications":
            self.sound_notifications_enabled = value
            print(f"Sound notifications option set to: {value}")
        elif option_name == "startup":
            # This is handled by the UI directly
            print(f"Startup option set to: {value}")
        else:
            print(f"Unknown option: {option_name}")

    def update_microphone(self, mic_name):
        """Updates the selected microphone"""
        # If no microphone name is provided, use the default device
        if not mic_name:
            try:
                default_device_info = self.audio.get_default_input_device_info()
                if default_device_info and default_device_info['maxInputChannels'] > 0:
                    self.selected_mic_index = default_device_info['index']
                    device_name = default_device_info['name']
                    # Ensure proper encoding for display
                    try:
                        # Try to properly encode device name for display if it contains non-ASCII characters
                        device_name = device_name.encode('latin1').decode('utf-8')
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        pass  # Keep original if encoding conversion fails
                    print(f"Using default microphone: {device_name} (index: {self.selected_mic_index})")
                else:
                    self.selected_mic_index = None
                    print("No valid default input device found")
            except Exception as e:
                print(f"Could not get default input device: {str(e)}")
                self.selected_mic_index = None
            return
        
        # If a microphone name is provided, try to find it
        found = False
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:  # Only consider input devices
                name = device_info['name']
                # Try to properly encode device name for comparison
                try:
                    name_utf8 = name.encode('latin1').decode('utf-8')
                except (UnicodeDecodeError, UnicodeEncodeError):
                    name_utf8 = name  # Keep original if encoding conversion fails
                
                if name == mic_name or name_utf8 == mic_name:
                    self.selected_mic_index = i
                    print(f"Selected microphone: {name_utf8} (index: {i})")
                    found = True
                    break
        
        if not found:
            print(f"Warning: Could not find microphone: {mic_name}")
            # Try to find any microphone that contains the name (partial match)
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    name = device_info['name']
                    # Try to properly encode device name for comparison
                    try:
                        name_utf8 = name.encode('latin1').decode('utf-8')
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        name_utf8 = name
                    
                    if mic_name in name or mic_name in name_utf8:
                        self.selected_mic_index = i
                        print(f"Found similar microphone: {name_utf8} (index: {i})")
                        found = True
                        break
            
            # If still not found, use the default input device
            if not found:
                try:
                    default_device_info = self.audio.get_default_input_device_info()
                    if default_device_info and default_device_info['maxInputChannels'] > 0:
                        self.selected_mic_index = default_device_info['index']
                        device_name = default_device_info['name']
                        # Ensure proper encoding for display
                        try:
                            device_name = device_name.encode('latin1').decode('utf-8')
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            pass
                        print(f"Using default microphone: {device_name} (index: {self.selected_mic_index})")
                    else:
                        self.selected_mic_index = None
                        print("No valid default input device found")
                except Exception as e:
                    print(f"Could not get default input device: {str(e)}")
                    self.selected_mic_index = None

    def check_microphone_availability(self):
        """Checks if any microphones are available and shows a message if not"""
        has_microphone = False
        
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                has_microphone = True
                print(f"Available microphone: {device_info['name']} (index: {i})")
                break
        
        if not has_microphone:
            error_msg = "Brak wykrytych mikrofonów w systemie. Proszę podłączyć mikrofon i zrestartować aplikację lub przejść do Ustawień, aby odświeżyć listę mikrofonów."
            print(error_msg)
            
            # Show a message box with instructions
            QTimer.singleShot(500, lambda: QMessageBox.warning(
                self.main_window, 
                "Nie wykryto mikrofonów", 
                error_msg + "\n\nAby aplikacja działała prawidłowo, wymagany jest mikrofon."
            ))

def main():
    app = QApplication(sys.argv)
    
    # Ustaw możliwości zasobnika systemowego
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray nie jest dostępny w tym systemie.")
    else:
        QApplication.setQuitOnLastWindowClosed(False)  # Nie zamykaj aplikacji po zamknięciu ostatniego okna
    
    main_window = WhisperMainWindow()
    transcriber = WhisperTranscriber(main_window)
    
    # Upewnij się, że PyAudio zostanie poprawnie zamknięty przy zamykaniu aplikacji
    app.aboutToQuit.connect(lambda: transcriber.audio.terminate() if hasattr(transcriber, 'audio') else None)
    
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()