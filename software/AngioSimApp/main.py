import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from pages.home_page import HomePage
from pages.instruction_page import InstructionPage
from pages.settings_page import SettingsPage
from pages.ready_page import ReadyPage
from pages.simulation_page import SimulationPage
from pages.completion_page import CompletionPage
from core.communication.comm_controller import CommController

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardiac Phantom Simulator")
        self.setMinimumSize(1000, 600)
        self.resize(1280, 720)

        # ==================== COMMUNICATION CONTROLLER ====================
        self.comm = CommController("config/device_config.yaml")
        self.comm.device_started.connect(self.handle_device_started)
        self.comm.device_stopped.connect(self.handle_device_stopped)
        self.comm.parameters_saved.connect(self.handle_parameters_saved)
        self.comm.parameters_reset.connect(self.handle_parameters_reset)
        self.comm.error_message.connect(self.handle_device_error)
        self.comm.log_message.connect(print)
        self.comm.start()

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Memuat seluruh halaman UI bawaan kamu
        self.home_page = HomePage(self)    
        self.instruction_page = InstructionPage(self)  
        self.settings_page = SettingsPage(self)
        self.ready_page = ReadyPage(self)
        self.simulation_page = SimulationPage(self)
        self.completion_page = CompletionPage(self)

        self.stacked_widget.addWidget(self.home_page)         # index 0
        self.stacked_widget.addWidget(self.instruction_page)  # index 1
        self.stacked_widget.addWidget(self.settings_page)     # index 2
        self.stacked_widget.addWidget(self.ready_page)        # index 3
        self.stacked_widget.addWidget(self.simulation_page)   # index 4
        self.stacked_widget.addWidget(self.completion_page)   # index 5
        
        # Koneksi navigasi tombol menu utama
        self.home_page.card_start.clicked.connect(self.go_to_ready)
        self.home_page.card_instr.clicked.connect(self.go_to_instruction)
        self.home_page.card_settings.clicked.connect(self.go_to_settings)

        self.stacked_widget.setCurrentIndex(0)

    # ==================== MANAJEMEN NAVIGASI & KAMERA TERINTEGRASI ====================

    def stop_all_cameras(self):
        print("[PyQt] Mematikan semua resource kamera...")

        if hasattr(self, 'settings_page') and self.settings_page:
            if hasattr(self.settings_page, 'thread') and self.settings_page.thread:
                if self.settings_page.thread.isRunning():
                    self.settings_page.thread.stop()
                self.settings_page.thread = None

        if hasattr(self, 'ready_page') and self.ready_page:
            if hasattr(self.ready_page, 'camera_thread') and self.ready_page.camera_thread:
                if self.ready_page.camera_thread.isRunning():
                    self.ready_page.camera_thread.stop()
                self.ready_page.camera_thread = None

        if hasattr(self, 'simulation_page') and self.simulation_page:
            if hasattr(self.simulation_page, 'camera_thread') and self.simulation_page.camera_thread:
                if self.simulation_page.camera_thread.isRunning():
                    self.simulation_page.camera_thread.stop()
                self.simulation_page.camera_thread = None

    def go_to_home(self):
        self.stop_all_cameras()
        self.stacked_widget.setCurrentIndex(0)

    def go_to_instruction(self):
        self.stop_all_cameras()
        self.stacked_widget.setCurrentIndex(1)

    def go_to_settings(self):
        self.stop_all_cameras()
        self.stacked_widget.setCurrentIndex(2) # Masuk ke SettingsPage
        
        # Panggil fungsi penyala kamera yang ditaruh di dalam settings_page
        if hasattr(self, 'settings_page') and self.settings_page:
            if hasattr(self.settings_page, 'start_camera'):
                self.settings_page.start_camera()

    def go_to_ready(self):
        self.comm.start_device()

    def go_to_simulation(self):
        self.stop_all_cameras() 
        self.stacked_widget.setCurrentIndex(4) # Pindah ke SimulationPage
        if hasattr(self, 'simulation_page') and self.simulation_page:
            self.simulation_page.trigger_page_start()

    def go_to_completion(self):
        self.stop_all_cameras()
        self.stacked_widget.setCurrentIndex(5)

    # ==================== HANDLER DATA UART SERIAL ====================

    def handle_device_started(self):
        print("[GUI] Device started.")
        self.stop_all_cameras()
        self.stacked_widget.setCurrentIndex(3)
        self.ready_page.trigger_system_activation()

    def handle_device_stopped(self):
        print("[GUI] Device stopped.")
        self.stop_all_cameras()
        self.stacked_widget.setCurrentIndex(0)

    def handle_parameters_saved(self, params):
        print("[GUI] Parameters saved:", params)

    def handle_parameters_reset(self, params):
        print("[GUI] Parameters reset:", params)

    def handle_device_error(self, message):
        print("[GUI] Device error:", message)
        QMessageBox.warning(self, "Device Error", message)

    def closeEvent(self, event):
        """Memastikan port serial dan thread kamera dilepas saat aplikasi ditutup (X)."""
        self.stop_all_cameras()
        if hasattr(self, "comm"):
            self.comm.shutdown()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())