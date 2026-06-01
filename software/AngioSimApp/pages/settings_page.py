import os
import yaml
import cv2
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QSlider, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from core.image_processor import ImageProcessor

# ==================== THREAD UNTUK AMBIL FEED KAMERA ====================
class CameraThread(QThread):
    change_pixmap_signal = pyqtSignal(object) 

    def __init__(self):
        super().__init__()
        self._run_flag = True

    def run(self):
        # PERBAIKAN: Diarahkan ke indeks 1 agar membaca kamera alat eksternal
        self.cap = cv2.VideoCapture(1, cv2.CAP_DSHOW) 
        
        while self._run_flag:
            ret, cv_img = self.cap.read()
            if ret:
                self.change_pixmap_signal.emit(cv_img)
                
        self.cap.release()

    def stop(self):
        self._run_flag = False
        # PERBAIKAN: Putus koneksi hardware cv2 secara paksa sebelum wait() agar tidak hang
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        self.wait()


# ==================== MAIN SETTINGS PAGE CLASS ====================
class SettingsPage(QWidget):
    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.sliders = {} 
        self.default_values = {}
        
        self.settings_data = self.load_settings_yaml()
        self.init_ui()
        
        self.thread = CameraThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        # PERBAIKAN: Di-komentar agar thread tidak otomatis berjalan mencuri port di background saat awal start app
        # self.thread.start() 

    def load_settings_yaml(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            yaml_path = os.path.join(base_dir, "settings.yaml")
            with open(yaml_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"Error loading settings YAML: {e}")
            return {"image_processing": [], "pump_control": []}

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
        isi_container.setContentsMargins(40, 30, 40, 30)

        # --- TOMBOL BACK ---
        btn_back = QPushButton("← BACK TO MENU")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.setStyleSheet("""
            QPushButton {
                color: #1B5E20; font-weight: bold; border: none; 
                text-align: left; font-size: 14px; background: transparent;
            }
            QPushButton:hover { color: #1FAE75; }
        """)
        btn_back.clicked.connect(lambda: self.parent_window.go_to_home() if self.parent_window else None)
        isi_container.addWidget(btn_back)

        isi_container.addSpacing(10)
        
        # --- JUDUL HALAMAN ---
        title = QLabel("DEVICE CALIBRATION & SETTINGS")
        title.setStyleSheet("font-size: 32px; font-weight: 800; color: #1B5E20;")
        isi_container.addWidget(title)

        # ==================== PAPAN PUTIH UTAMA ====================
        papan_settings = QFrame()
        papan_settings.setStyleSheet("""
            QFrame {
                background-color: white; 
                border-radius: 25px; 
                border: 1px solid #E1E6EF;
            }
            QLabel { border: none; background: transparent; }
        """)
        
        layout_split = QHBoxLayout(papan_settings)
        layout_split.setContentsMargins(30, 30, 30, 30)
        layout_split.setSpacing(40)

        # ---------------- KOLOM KIRI: CAMERA PREVIEW ----------------
        kolom_kiri = QVBoxLayout()
        kolom_kiri.setAlignment(Qt.AlignmentFlag.AlignTop)

        lbl_cam_title = QLabel("Fluoroscopy Live Preview")
        lbl_cam_title.setStyleSheet("font-weight: bold; color: #2F3A45; font-size: 18px;")
        kolom_kiri.addWidget(lbl_cam_title)
        kolom_kiri.addSpacing(10)

        self.camera_feed = QLabel()
        self.camera_feed.setFixedSize(480, 320)
        self.camera_feed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_feed.setText("[ Menghubungkan ke Kamera... ]")
        self.camera_feed.setStyleSheet("""
            QLabel {
                background-color: #2D3748; 
                color: #A0AEC0; 
                border-radius: 15px;
                font-size: 14px;
            }
        """)
        kolom_kiri.addWidget(self.camera_feed)
        
        layout_split.addLayout(kolom_kiri, stretch=4)

        # ---------------- KOLOM KANAN: TUNING CONTROL ----------------
        kolom_kanan = QVBoxLayout()
        kolom_kanan.setSpacing(20)
        kolom_kanan.setAlignment(Qt.AlignmentFlag.AlignTop)

        group_style = """
            QGroupBox {
                font-weight: bold; font-size: 15px; color: #1FAE75;
                border: 1px solid #E2E8F0; border-radius: 12px; margin-top: 15px;
                padding-top: 15px; padding-left: 10px; padding-right: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; }
        """

        group_img = QGroupBox("Image Processing Tuning")
        group_img.setStyleSheet(group_style)
        layout_img = QVBoxLayout(group_img)
        layout_img.setSpacing(15)
        
        for item in self.settings_data.get('image_processing', []):
            self.build_slider_from_yaml(layout_img, item)
            
        kolom_kanan.addWidget(group_img)

        group_pump = QGroupBox("Pump PWM Control (Fluid Dynamics)")
        group_pump.setStyleSheet(group_style)
        layout_pump = QVBoxLayout(group_pump)
        layout_pump.setSpacing(15)
        
        for item in self.settings_data.get('pump_control', []):
            self.build_slider_from_yaml(layout_pump, item)
            
        kolom_kanan.addWidget(group_pump)
        
        layout_tombol = QHBoxLayout()
        layout_tombol.addStretch()

        btn_save = QPushButton("Save Parameters")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #1FAE75; color: white; font-weight: bold;
                border: none; border-radius: 8px; padding: 8px 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #1B5E20; }
        """)
        btn_save.clicked.connect(self.save_parameters)
        layout_tombol.addWidget(btn_save)
        
        btn_reset = QPushButton("Reset Default")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #EDF2F7; color: #4A5568; font-weight: bold;
                border: 1px solid #CBD5E0; border-radius: 8px; padding: 8px 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #E2E8F0; }
        """)
        btn_reset.clicked.connect(self.reset_to_default)
        layout_tombol.addWidget(btn_reset)
        
        kolom_kanan.addLayout(layout_tombol)
        layout_split.addLayout(kolom_kanan, stretch=5)
        
        isi_container.addWidget(papan_settings)
        isi_container.addSpacing(20)

    def build_slider_from_yaml(self, parent_layout, item_dict):
        s_id = item_dict.get('id', 'unknown')
        label_text = item_dict.get('label', 'Param:')
        min_val = item_dict.get('min', 0)
        max_val = item_dict.get('max', 100)
        default_val = item_dict.get('default', 50)

        self.default_values[s_id] = default_val

        row_layout = QHBoxLayout()
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #4A5568; font-weight: 500; font-size: 13px;")
        lbl.setFixedWidth(140)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default_val)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #E2E8F0; height: 6px; background: #EDF2F7; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #1FAE75; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px;
            }
            QSlider::handle:horizontal:hover { background: #1B5E20; }
        """)
        
        lbl_value = QLabel(str(default_val))
        lbl_value.setStyleSheet("color: #718096; font-weight: bold; font-size: 13px;")
        lbl_value.setFixedWidth(30)
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        slider.valueChanged.connect(lambda v: lbl_value.setText(str(v)))
        
        row_layout.addWidget(lbl)
        row_layout.addWidget(slider)
        row_layout.addWidget(lbl_value)
        parent_layout.addLayout(row_layout)
        
        self.sliders[s_id] = slider

    def start_camera(self):
        """Menyalakan kamera settings dengan thread baru yang fresh."""
        if self.thread is not None and self.thread.isRunning():
            return

        self.thread = CameraThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.start()

    def update_image(self, cv_img):
        b_val = self.sliders['brightness'].value()
        c_val = self.sliders['contrast'].value()
        t_val = self.sliders['threshold'].value()

        # Murni memanggil backend ImageProcessor
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
        self.camera_feed.setPixmap(scaled_pixmap)

    def reset_to_default(self):
        # 1. Kembalikan semua slider di layar ke nilai pabrikan awal
        for s_id, slider in self.sliders.items():
            if s_id in self.default_values:
                slider.setValue(self.default_values[s_id])
        
        # 2. LANGSUNG OTOMATIS SIMPAN KE FILE YAML
        # Panggil fungsi save_parameters yang sudah kita buat tadi
        self.save_parameters()
        print("[PyQt] Reset Default sukses dan otomatis disimpan ke YAML!")

    def save_parameters(self):
        """Menyimpan nilai slider saat ini ke file YAML."""
        current_data = self.settings_data
        
        # Update nilai default di dalam data YAML sesuai posisi slider sekarang
        for section in ['image_processing', 'pump_control']:
            for item in current_data.get(section, []):
                s_id = item['id']
                if s_id in self.sliders:
                    item['default'] = self.sliders[s_id].value()
        
        # Tulis ulang file settings.yaml
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            yaml_path = os.path.join(base_dir, "settings.yaml")
            with open(yaml_path, 'w', encoding='utf-8') as file:
                yaml.dump(current_data, file, default_flow_style=False)
            print("[PyQt] Settings berhasil disimpan ke settings.yaml!")
        except Exception as e:
            print(f"[PyQt] Gagal menyimpan settings: {e}")

    def closeEvent(self, event):
        if self.thread:
            self.thread.stop()
            self.thread = None
        event.accept()