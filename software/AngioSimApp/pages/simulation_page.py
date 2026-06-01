# pages/simulation_page.py
import cv2
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap

# Hubungkan ke backend pengolah gambar
from core.image_processor import ImageProcessor

# ==================== CAMERA THREAD FOR SIMULATION PAGE ====================
class SimCameraThread(QThread):
    change_pixmap_signal = pyqtSignal(object)

    def __init__(self, camera_index=1):
        super().__init__()
        self.camera_index = camera_index
        self._run_flag = True
        self._is_paused = False

    def run(self):
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        while self._run_flag:
            if not self._is_paused:
                ret, cv_img = self.cap.read()
                if ret:
                    self.change_pixmap_signal.emit(cv_img)
            else:
                self.msleep(30) # Istirahatkan thread sejenak saat dipause agar CPU dingin
        self.cap.release()

    def set_paused(self, state: bool):
        self._is_paused = state

    def stop(self):
        self._run_flag = False
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        self.wait()


# ==================== MAIN SIMULATION PAGE CLASS ====================
class SimulationPage(QWidget):
    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.camera_thread = None
        
        # State Management untuk simulasi
        self.is_paused = False
        self.total_seconds = 0
        
        # Timer internal untuk pencatat waktu simulasi (Stopwatch)
        self.stopwatch = QTimer(self)
        self.stopwatch.timeout.connect(self.update_stopwatch)
        
        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        # ==================== MAIN CONTAINER ====================
        container = QFrame()
        container.setObjectName("SimContainer")
        container.setStyleSheet("""
            #SimContainer {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, 
                                  stop:0 #E8F5E9, stop:1 #DCEAF5); 
                border-radius: 30px;
            }
        """)
        outer_layout.addWidget(container)

        isi_container = QVBoxLayout(container)
        isi_container.setContentsMargins(40, 25, 40, 25)

        # --- JUDUL UTAMA HALAMAN ---
        title_layout = QHBoxLayout()
        title = QLabel("LIVE FLUOROSCOPY")
        title.setStyleSheet("font-size: 26px; font-weight: 800; color: #102A43;")
        title_layout.addWidget(title)
        title_layout.addStretch(1)
        isi_container.addLayout(title_layout)
        isi_container.addSpacing(15)

        # ==================== GRID LAYOUT UTAMA ====================
        main_grid = QGridLayout()
        main_grid.setHorizontalSpacing(30)

        # ------------------- SISI KIRI: DISPLAY MONITOR UTAMA (DIPERBESAR) -------------------
        papan_kiri = QFrame()
        papan_kiri.setStyleSheet("background-color: white; border-radius: 20px; border: 1px solid #BCCCDC;")
        layout_kiri = QVBoxLayout(papan_kiri)
        layout_kiri.setContentsMargins(15, 15, 15, 15)

        # Layar hitam preview video fluoroscopy diperbesar ke 800x500
        self.live_monitor = QLabel()
        self.live_monitor.setFixedSize(800, 500)  
        self.live_monitor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_monitor.setText("[ Kamera Memuat Umpan Gambar... ]")
        self.live_monitor.setStyleSheet("""
            QLabel {
                background-color: #0B132B; color: #627D98; 
                border-radius: 15px; font-size: 16px; border: none;
            }
        """)
        layout_kiri.addWidget(self.live_monitor)
        main_grid.addWidget(papan_kiri, 0, 0)

        # ------------------- SISI KANAN: INSTRUMEN & CONTROL PANEL -------------------
        papan_kanan = QFrame()
        papan_kanan.setStyleSheet("background-color: white; border-radius: 20px; border: 1px solid #BCCCDC;")
        layout_kanan = QVBoxLayout(papan_kanan)
        layout_kanan.setContentsMargins(25, 25, 25, 25)
        layout_kanan.setSpacing(25)

        # 1. BOX PANEL TIMER (STOPWATCH SIMULASI)
        timer_box = QFrame()
        timer_box.setStyleSheet("background-color: #F0F4F8; border-radius: 12px; border: 1px solid #D9E2EC;")
        layout_timer_box = QVBoxLayout(timer_box)
        layout_timer_box.setContentsMargins(15, 15, 15, 15)
        
        lbl_timer_header = QLabel("ELAPSED TIME")
        lbl_timer_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #627D98; border: none;")
        lbl_timer_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_timer_value = QLabel("00 : 00 : 00")
        self.lbl_timer_value.setStyleSheet("font-size: 34px; font-weight: 800; color: #102A43; font-family: 'Courier New'; border: none;")
        self.lbl_timer_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout_timer_box.addWidget(lbl_timer_header)
        layout_timer_box.addWidget(self.lbl_timer_value)
        layout_kanan.addWidget(timer_box)

        # 2. PANEL TOMBOL UTAMA PAUSE / RESUME
        self.btn_pause_resume = QPushButton("⏸ PAUSE SIMULATION")
        self.btn_pause_resume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause_resume.setStyleSheet("""
            QPushButton {
                background-color: #D97706; color: white; border: none;
                font-weight: bold; border-radius: 12px; padding: 15px; font-size: 14px;
            }
            QPushButton:hover { background-color: #B45309; }
        """)
        self.btn_pause_resume.clicked.connect(self.toggle_pause_resume)
        layout_kanan.addWidget(self.btn_pause_resume)

        # LABEL CATATAN PENTING
        self.lbl_note = QLabel(
            "ℹ️ Catatan: Fungsi di atas hanya akan menjeda visualisasi kamera "
            "dan perhitungan waktu di monitor. Sistem mekanis pompa tetap aktif berjalan."
        )
        self.lbl_note.setWordWrap(True)
        self.lbl_note.setStyleSheet("font-size: 11px; color: #627D98; line-height: 15px; border: none;")
        layout_kanan.addWidget(self.lbl_note)
        
        layout_kanan.addStretch(1)

        # 3. BARIS BOTTOM NAVIGATION BUTTONS (STOP DEVICE & NEXT)
        layout_nav_bawah = QHBoxLayout()
        
        # Tombol Stop
        self.btn_stop_sim = QPushButton("🛑 STOP SIMULATION")
        self.btn_stop_sim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_sim.setStyleSheet("""
            QPushButton {
                background-color: #EF4444; color: white; border: none;
                font-weight: bold; border-radius: 10px; padding: 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #DC2626; }
        """)
        self.btn_stop_sim.clicked.connect(self.handle_stop_simulation)
        
        # Tombol Next Page
        self.btn_next_page = QPushButton("NEXT PAGE →")
        self.btn_next_page.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next_page.setStyleSheet("""
            QPushButton {
                background-color: #10B981; color: white; border: none;
                font-weight: bold; border-radius: 10px; padding: 12px 20px; font-size: 12px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_next_page.clicked.connect(self.handle_next_page)
        
        layout_nav_bawah.addWidget(self.btn_stop_sim)
        layout_nav_bawah.addStretch(1)
        layout_nav_bawah.addWidget(self.btn_next_page)
        
        layout_kanan.addLayout(layout_nav_bawah)

        # Satukan layout sisi kiri dan sisi kanan ke grid utama
        main_grid.addWidget(papan_kanan, 0, 1)
        main_grid.setColumnStretch(0, 7)
        main_grid.setColumnStretch(1, 3)

        isi_container.addLayout(main_grid)

    # ==================== LOGIKA HALAMAN & SIKLUS HIDUP ====================
    def trigger_page_start(self):
        print("[PyQt] Memulai halaman Live Fluoroscopy...")
        self.is_paused = False
        self.total_seconds = 0
        self.lbl_timer_value.setText("00 : 00 : 00")
        
        self.btn_pause_resume.setText("⏸ PAUSE SIMULATION")
        self.btn_pause_resume.setStyleSheet("""
            QPushButton { background-color: #D97706; color: white; border: none; font-weight: bold; border-radius: 12px; padding: 15px; font-size: 14px; }
            QPushButton:hover { background-color: #B45309; }
        """)

        self.stopwatch.start(1000)
        self.start_camera()

    def update_stopwatch(self):
        self.total_seconds += 1
        hours = self.total_seconds // 3600
        minutes = (self.total_seconds % 3600) // 60
        seconds = self.total_seconds % 60
        self.lbl_timer_value.setText(f"{hours:02d} : {minutes:02d} : {seconds:02d}")

    def toggle_pause_resume(self):
        if not self.is_paused:
            self.is_paused = True
            self.stopwatch.stop() 
            if self.camera_thread:
                self.camera_thread.set_paused(True) 
            
            self.btn_pause_resume.setText("▶ RESUME SIMULATION")
            self.btn_pause_resume.setStyleSheet("""
                QPushButton { background-color: #10B981; color: white; border: none; font-weight: bold; border-radius: 12px; padding: 15px; font-size: 14px; }
                QPushButton:hover { background-color: #059669; }
            """)
            print("[PyQt] Umpan visualisasi simulasi dijeda sementara.")
        else:
            self.is_paused = False
            self.stopwatch.start(1000) 
            if self.camera_thread:
                self.camera_thread.set_paused(False) 
            
            self.btn_pause_resume.setText("⏸ PAUSE SIMULATION")
            self.btn_pause_resume.setStyleSheet("""
                QPushButton { background-color: #D97706; color: white; border: none; font-weight: bold; border-radius: 12px; padding: 15px; font-size: 14px; }
                QPushButton:hover { background-color: #B45309; }
            """)
            print("[PyQt] Umpan visualisasi simulasi dilanjutkan kembali.")

    def handle_stop_simulation(self):
        print("[PyQt] Menghentikan simulasi, kembali ke menu setup.")
        self.clean_up_resources()
        self.parent_window.stacked_widget.setCurrentWidget(self.parent_window.ready_page) 

    def handle_next_page(self):
        # PERBAIKAN: Menambahkan fungsi pemindah halaman aktif dan melempar parameter data waktu
        print("[PyQt] Melompat ke halaman berikutnya...")
        waktu_akhir = self.total_seconds
        self.clean_up_resources()
        
        if self.parent_window and hasattr(self.parent_window, 'stacked_widget'):
            # Jika ada halaman completion page, set dulu datanya sebelum pindah
            if hasattr(self.parent_window, 'completion_page'):
                self.parent_window.completion_page.set_final_time(waktu_akhir)
                self.parent_window.stacked_widget.setCurrentWidget(self.parent_window.completion_page)
            else:
                # Jika tidak ada objek khusus, kamu bisa pakai setCurrentIndex halaman berikutnya
                # Contoh: self.parent_window.stacked_widget.setCurrentIndex(3)
                pass

    def clean_up_resources(self):
        self.stopwatch.stop()
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None

    # ==================== PEMROSESAN GAMBAR DENGAN BACKEND CORE ====================
    def start_camera(self):
        if self.camera_thread is None:
            self.camera_thread = SimCameraThread(camera_index=1)
            self.camera_thread.change_pixmap_signal.connect(self.process_and_render)
            self.camera_thread.start()

    def process_and_render(self, cv_img):
        try:
            settings_pg = self.parent_window.settings_page
            b_val = settings_pg.sliders['brightness'].value()
            c_val = settings_pg.sliders['contrast'].value()
            t_val = settings_pg.sliders['threshold'].value()
        except AttributeError:
            b_val, c_val, t_val = 50, 50, 30

        rgb_image = ImageProcessor.process_fluoroscopy(cv_img, brightness_raw=b_val, contrast_raw=c_val, threshold_val=t_val)

        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_format)
        
        scaled_pixmap = pixmap.scaled(
            800, 500, 
            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
            Qt.TransformationMode.SmoothTransformation
        )
        # PERBAIKAN: Memastikan kurung penutup setPixmap tidak hilang
        self.live_monitor.setPixmap(scaled_pixmap)