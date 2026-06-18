import os
import cv2
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

# ==================== CAMERA THREAD FOR READY PAGE ====================
class ReadyCameraThread(QThread):
    change_pixmap_signal = pyqtSignal(object)

    # PERBAIKAN: Mengubah default index ke 1 agar mengarah ke kamera alat
    def __init__(self, camera_index=1):
        super().__init__()
        self.camera_index = camera_index
        self._run_flag = True

    def run(self):
        # Membuka kamera dengan backend DirectShow agar lebih cepat di Windows
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        while self._run_flag:
            ret, cv_img = self.cap.read()
            if ret:
                self.change_pixmap_signal.emit(cv_img)
        self.cap.release()

    def stop(self):
        self._run_flag = False
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        self.wait()

class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
# ==================== MAIN READY PAGE CLASS ====================
class ReadyPage(QWidget):
    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.camera_thread = None
        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        # ==================== MAIN CONTAINER ====================
        container = QFrame()
        container.setObjectName("MainContainer")
        container.setStyleSheet("""
            #MainContainer {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, 
                                  stop:0 #E8F5E9, stop:1 #DCEAF5); 
                border-radius: 30px;
            }
        """)
        outer_layout.addWidget(container)

        isi_container = QVBoxLayout(container)
        isi_container.setContentsMargins(40, 25, 40, 25)

        # --- TOMBOL BACK TO MENU ---
        btn_back = QPushButton("← BACK TO MENU")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.setStyleSheet("""
            QPushButton {
                color: #1B5E20; font-weight: bold; border: none; 
                text-align: left; font-size: 14px; background: transparent;
            }
            QPushButton:hover { color: #1FAE75; }
        """)
        btn_back.clicked.connect(self.handle_back)
        isi_container.addWidget(btn_back)
        
        # --- JUDUL UTAMA ---
        title = QLabel("CARDIAC PHANTOM SIMULATION")
        title.setStyleSheet("font-size: 32px; font-weight: 800; color: #1B5E20;")
        isi_container.addWidget(title)
        isi_container.addSpacing(10)

        # ==================== GRID SPLIT LAYOUT ====================
        main_grid = QGridLayout()
        main_grid.setHorizontalSpacing(30)

        # ------------------- SISI KIRI: CONTROL PANEL -------------------
        papan_kiri = QFrame()
        papan_kiri.setStyleSheet("background-color: white; border-radius: 20px; border: 1px solid #E1E6EF;")
        layout_kiri = QVBoxLayout(papan_kiri)
        layout_kiri.setContentsMargins(25, 20, 25, 20)
        layout_kiri.setSpacing(20)

        # 1. POSISI ATAS: SYSTEM INITIALIZATION STATUS BOX
        status_box = QFrame()
        status_box.setStyleSheet("background-color: #F8FAFC; border-radius: 12px; border: 1px solid #E2E8F0;")
        layout_status = QVBoxLayout(status_box)
        layout_status.setContentsMargins(20, 15, 20, 15)
        
        lbl_status_title = QLabel("SYSTEM INITIALIZATION STATUS")
        lbl_status_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #64748B; border: none;")
        layout_status.addWidget(lbl_status_title)
        layout_status.addSpacing(5)

        # Baris 1: CARDIAC MOTION
        row1 = QFrame()
        row1_layout = QHBoxLayout(row1)
        lbl_name1 = QLabel("CARDIAC MOTION")
        lbl_name1.setStyleSheet("font-size: 13px; color: #475569; font-weight: 500;")
        self.lbl_status_cardiac = ClickableLabel("WAITING...")
        self.lbl_status_cardiac.setStyleSheet("font-size: 13px; color: #D97706; font-weight: bold;")
        self.lbl_status_cardiac.setAlignment(Qt.AlignmentFlag.AlignRight)
        row1_layout.addWidget(lbl_name1)
        row1_layout.addWidget(self.lbl_status_cardiac)
        layout_status.addWidget(row1)

        # Baris 2: BLOOD CIRCULATION
        row2 = QFrame()
        row2_layout = QHBoxLayout(row2)
        lbl_name2 = QLabel("BLOOD CIRCULATION")
        lbl_name2.setStyleSheet("font-size: 13px; color: #475569; font-weight: 500;")
        self.lbl_status_blood = ClickableLabel("WAITING...")
        self.lbl_status_blood.setStyleSheet("font-size: 13px; color: #D97706; font-weight: bold;")
        self.lbl_status_blood.setAlignment(Qt.AlignmentFlag.AlignRight)
        row2_layout.addWidget(lbl_name2)
        row2_layout.addWidget(self.lbl_status_blood)
        layout_status.addWidget(row2)

        # Baris 3: VISUALIZATION
        row3 = QFrame()
        row3_layout = QHBoxLayout(row3)
        lbl_name3 = QLabel("VISUALIZATION")
        lbl_name3.setStyleSheet("font-size: 13px; color: #475569; font-weight: 500;")
        self.lbl_status_visualization = ClickableLabel("WAITING...")
        self.lbl_status_visualization.setStyleSheet("font-size: 13px; color: #D97706; font-weight: bold;")
        self.lbl_status_visualization.setAlignment(Qt.AlignmentFlag.AlignRight)
        row3_layout.addWidget(lbl_name3)
        row3_layout.addWidget(self.lbl_status_visualization)
        layout_status.addWidget(row3)
        
        self.lbl_status_cardiac.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_status_blood.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_status_visualization.setCursor(Qt.CursorShape.PointingHandCursor)

        self.lbl_status_cardiac.clicked.connect(
            lambda: self.update_hardware_status("CARDIAC MOTION", True)
        )
        self.lbl_status_blood.clicked.connect(
            lambda: self.update_hardware_status("BLOOD CIRCULATION", True)
        )
        self.lbl_status_visualization.clicked.connect(
            lambda: self.update_hardware_status("VISUALIZATION", True)
        )

        layout_kiri.addWidget(status_box)

        # 2. POSISI BAWAH: LIVE MONITORING PARAMETERS BOX
        data_box = QFrame()
        data_box.setStyleSheet("background-color: #F8FAFC; border-radius: 12px; border: 1px solid #E2E8F0;")
        layout_data = QVBoxLayout(data_box)
        layout_data.setContentsMargins(20, 15, 20, 15)
        
        lbl_data_title = QLabel("LIVE MONITORING PARAMETERS")
        lbl_data_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #64748B; border: none;")
        layout_data.addWidget(lbl_data_title)
        
        layout_angka_monitoring = QHBoxLayout()
        layout_angka_monitoring.setSpacing(20)

        # Sub-container Heart Rate (BPM)
        bpm_container = QVBoxLayout()
        lbl_bpm_header = QLabel("HEART RATE")
        lbl_bpm_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #94A3B8; border: none;")
        lbl_bpm_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_bpm_value = QLabel("-- BPM")
        self.lbl_bpm_value.setStyleSheet("font-size: 38px; font-weight: 800; color: #1E293B; border: none;")
        self.lbl_bpm_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bpm_container.addWidget(lbl_bpm_header)
        bpm_container.addWidget(self.lbl_bpm_value)

        # Sub-container Power Consumption (Watt)
        watt_container = QVBoxLayout()
        lbl_watt_header = QLabel("POWER CONSUMPTION")
        lbl_watt_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #94A3B8; border: none;")
        lbl_watt_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_watt_value = QLabel("-- W")
        self.lbl_watt_value.setStyleSheet("font-size: 38px; font-weight: 800; color: #0284C7; border: none;")
        self.lbl_watt_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        watt_container.addWidget(lbl_watt_header)
        watt_container.addWidget(self.lbl_watt_value)

        layout_angka_monitoring.addLayout(bpm_container)
        layout_angka_monitoring.addLayout(watt_container)
        layout_data.addLayout(layout_angka_monitoring)
        
        layout_kiri.addWidget(data_box)
        
        # 3. TOMBOL AKSI (START & STOP)
        layout_action_btn = QHBoxLayout()
        self.btn_start_sim = QPushButton("START SIMULATION")
        self.btn_start_sim.setEnabled(False)  
        self.btn_start_sim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_sim.setStyleSheet("""
            QPushButton {
                background-color: #E2E8F0; color: #94A3B8; border: 1px solid #CBD5E0;
                font-weight: bold; border-radius: 10px; padding: 12px; font-size: 13px;
            }
        """)
        self.btn_start_sim.clicked.connect(lambda: self.parent_window.go_to_simulation() if self.parent_window else None)
        
        self.btn_stop_device = QPushButton("🛑 STOP DEVICE")
        self.btn_stop_device.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_device.setStyleSheet("""
            QPushButton {
                background-color: #EF4444; color: white; border: none; 
                font-weight: bold; border-radius: 10px; padding: 12px; font-size: 13px;
            }
            QPushButton:hover { background-color: #DC2626; }
        """)
        
        layout_action_btn.addWidget(self.btn_start_sim)
        layout_action_btn.addWidget(self.btn_stop_device)
        layout_kiri.addLayout(layout_action_btn)

        main_grid.addWidget(papan_kiri, 0, 0)

        # ------------------- SISI KANAN: MONITOR (FLUOROSCOPY) -------------------
        papan_kanan = QFrame()
        papan_kanan.setStyleSheet("background-color: white; border-radius: 20px; border: 1px solid #E1E6EF;")
        layout_kanan = QVBoxLayout(papan_kanan)
        layout_kanan.setContentsMargins(25, 25, 25, 25)
        layout_kanan.setAlignment(Qt.AlignmentFlag.AlignTop)

        lbl_monitor_title = QLabel("Fluoroscopy Monitor View")
        lbl_monitor_title.setStyleSheet("font-weight: bold; color: #2F3A45; font-size: 18px; border: none;")
        layout_kanan.addWidget(lbl_monitor_title)
        layout_kanan.addSpacing(10)

        self.fluoro_monitor = QLabel()
        self.fluoro_monitor.setFixedSize(480, 320)
        self.fluoro_monitor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fluoro_monitor.setText("[ Feed Kamera Siap ]")
        self.fluoro_monitor.setStyleSheet("""
            QLabel {
                background-color: #1E293B; color: #94A3B8; 
                border-radius: 15px; font-size: 14px; border: none;
            }
        """)
        layout_kanan.addWidget(self.fluoro_monitor)

        main_grid.addWidget(papan_kanan, 0, 1)

        main_grid.setColumnStretch(0, 4)
        main_grid.setColumnStretch(1, 5)

        isi_container.addLayout(main_grid)
        isi_container.addStretch(1)

        # PERBAIKAN: Hubungkan tombol stop device bawaanmu ke fungsi handle_back agar berjalan
        self.btn_stop_device.clicked.connect(self.handle_stop_device)

    # ==================== LOGIKA TRIGER & HANDSHAKE ====================
    def trigger_system_activation(self):
        print("[PyQt] Mengirim sinyal inisialisasi ke hardware...")
        
        self.lbl_status_cardiac.setText("WAITING...")
        self.lbl_status_cardiac.setStyleSheet("font-size: 13px; color: #D97706; font-weight: bold;")
        self.lbl_status_blood.setText("WAITING...")
        self.lbl_status_blood.setStyleSheet("font-size: 13px; color: #D97706; font-weight: bold;")
        self.lbl_status_visualization.setText("WAITING...")
        self.lbl_status_visualization.setStyleSheet("font-size: 13px; color: #D97706; font-weight: bold;")
        
        self.lbl_bpm_value.setText("-- BPM")
        self.lbl_watt_value.setText("-- W")
        
        self.btn_start_sim.setEnabled(False)
        self.btn_start_sim.setStyleSheet("background-color: #E2E8F0; color: #94A3B8; border: 1px solid #CBD5E0; font-weight: bold; border-radius: 10px; padding: 12px; font-size: 13px;")

        self.start_camera()

    def update_hardware_status(self, component_name, is_ready):
        if is_ready:
            if component_name == "CARDIAC MOTION":
                self.lbl_status_cardiac.setText("READY ✔")
                self.lbl_status_cardiac.setStyleSheet("font-size: 13px; color: #10B981; font-weight: bold;")
            elif component_name == "BLOOD CIRCULATION":
                self.lbl_status_blood.setText("READY ✔")
                self.lbl_status_blood.setStyleSheet("font-size: 13px; color: #10B981; font-weight: bold;")
            elif component_name == "VISUALIZATION":
                self.lbl_status_visualization.setText("READY ✔")
                self.lbl_status_visualization.setStyleSheet("font-size: 13px; color: #10B981; font-weight: bold;")
        
        self.check_overall_readiness()

    def check_overall_readiness(self):
        cond1 = "READY" in self.lbl_status_cardiac.text()
        cond2 = "READY" in self.lbl_status_blood.text()
        cond3 = "READY" in self.lbl_status_visualization.text()
        
        if cond1 and cond2 and cond3:
            self.btn_start_sim.setEnabled(True)
            self.btn_start_sim.setStyleSheet("""
                QPushButton {
                    background-color: #10B981; color: white; border: none;
                    font-weight: bold; border-radius: 10px; padding: 12px; font-size: 13px;
                }
                QPushButton:hover { background-color: #059669; }
            """)
            self.lbl_bpm_value.setText("60 BPM")
            self.lbl_watt_value.setText("12.5 W")

    # ==================== LIVE CAMERA IMAGE PROCESSING ====================
    def start_camera(self):
        if self.camera_thread is None:
            # PERBAIKAN: Set indeks kamera eksternal ke 1
            self.camera_thread = ReadyCameraThread(camera_index=1)
            self.camera_thread.change_pixmap_signal.connect(self.process_and_update_image)
            self.camera_thread.start()

    def process_and_update_image(self, cv_img):
        try:
            settings_pg = self.parent_window.settings_page
            b_val = settings_pg.sliders['brightness'].value()
            c_val = settings_pg.sliders['contrast'].value()
            t_val = settings_pg.sliders['threshold'].value()
        except AttributeError:
            b_val, c_val, t_val = 50, 50, 30

        # Murni delegasikan pemrosesan citra penuh ke backend core tanpa merusak GUI
        from core.image_processor import ImageProcessor
        rgb_image = ImageProcessor.process_fluoroscopy(cv_img, brightness_raw=b_val, contrast_raw=c_val, threshold_val=t_val)

        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_format)
        scaled_pixmap = pixmap.scaled(
            480, 320, 
            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.fluoro_monitor.setPixmap(scaled_pixmap)

    def handle_back(self):
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
        if self.parent_window:
            self.parent_window.go_to_home()

    def handle_stop_device(self):
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None

        if self.parent_window and hasattr(self.parent_window, "comm"):
            self.parent_window.comm.stop_device()
        else:
            self.handle_back()