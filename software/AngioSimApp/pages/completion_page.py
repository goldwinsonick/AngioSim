from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt

class CompletionPage(QWidget):
    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.total_seconds = 0
        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QFrame()
        container.setObjectName("CompContainer")
        container.setStyleSheet("""
            #CompContainer {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, 
                                  stop:0 #E8F5E9, stop:1 #DCEAF5); 
                border-radius: 30px;
            }
        """)
        outer_layout.addWidget(container)

        # Layout vertikal utama container
        isi_container = QVBoxLayout(container)
        isi_container.setContentsMargins(40, 40, 40, 40)

        # Spacer atas: mendorong semua elemen agar berada tepat di tengah secara vertikal
        isi_container.addStretch(1)

        # --- 1. JUDUL UTAMA HALAMAN (Paling Atas, Di Tengah) ---
        row_title = QHBoxLayout()
        title = QLabel("SIMULATION COMPLETED")
        title.setStyleSheet("""
            font-size: 32px; 
            font-weight: 800; 
            color: #102A43; 
            letter-spacing: 1px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_title.addWidget(title)
        isi_container.addLayout(row_title)
        
        # Jarak dari judul ke box timer
        isi_container.addSpacing(50)

        # --- 2. BOX PANEL TIMER (TOTAL DURASI - DI TENGAH JUDUL) ---
        row_timer = QHBoxLayout()
        
        timer_box = QFrame()
        timer_box.setFixedWidth(380) # Mengunci lebar box timer
        timer_box.setStyleSheet("""
            QFrame {
                background-color: white; 
                border-radius: 20px; 
                border: 1px solid #BCCCDC;
            }
        """)
        
        layout_timer_box = QVBoxLayout(timer_box)
        layout_timer_box.setContentsMargins(30, 25, 30, 25)
        layout_timer_box.setSpacing(12)
        
        lbl_timer_header = QLabel("TOTAL ELAPSED TIME")
        lbl_timer_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #627D98; border: none;")
        lbl_timer_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_timer_value = QLabel("00 : 00 : 00")
        self.lbl_timer_value.setStyleSheet("""
            QLabel {
                font-size: 34px; 
                font-weight: 800; 
                color: #102A43; 
                font-family: 'Courier New'; 
                border: none;
            }
        """)
        self.lbl_timer_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout_timer_box.addWidget(lbl_timer_header)
        layout_timer_box.addWidget(self.lbl_timer_value)
        
        # Bungkus box timer dengan layout horizontal agar posisinya presisi di tengah
        row_timer.addStretch(1)
        row_timer.addWidget(timer_box)
        row_timer.addStretch(1)
        
        isi_container.addLayout(row_timer)
        
        # Jarak dari box timer ke tombol
        isi_container.addSpacing(40)

        # --- 3. TOMBOL END SIMULATION (DI TENGAH BOX TIMER) ---
        row_btn = QHBoxLayout()
        
        self.btn_end_sim = QPushButton("END SIMULATION")
        self.btn_end_sim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_end_sim.setFixedSize(240, 55) # Dimensi: Tidak terlalu lebar, tebal ke bawah
        
        self.btn_end_sim.setStyleSheet("""
            QPushButton {
                background-color: white; 
                color: #102A43; 
                border: 2px solid #BCCCDC; 
                font-weight: bold; 
                border-radius: 15px; 
                font-size: 13px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover { 
                background-color: #F8FAFC; 
                border-color: #627D98;
                color: #000000;
            }
            QPushButton:pressed {
                background-color: #E2E8F0;
            }
        """)
        self.btn_end_sim.clicked.connect(self.handle_end_simulation)
        
        # Bungkus tombol dengan layout horizontal agar sejajar lurus di tengah box timer
        row_btn.addStretch(1)
        row_btn.addWidget(self.btn_end_sim)
        row_btn.addStretch(1)
        
        isi_container.addLayout(row_btn)

        # Spacer bawah: menjaga keseimbangan vertikal agar tetap di tengah halaman
        isi_container.addStretch(1)

    # ==================== SIKLUS HIDUP & LOGIKA NAVIGASI ====================
    def set_final_time(self, seconds):
        """Menerima lemparan data detik dari halaman simulasi."""
        self.total_seconds = seconds
        hours = self.total_seconds // 3600
        minutes = (self.total_seconds % 3600) // 60
        secs = self.total_seconds % 60
        self.lbl_timer_value.setText(f"{hours:02d} : {minutes:02d} : {secs:02d}")

    def handle_end_simulation(self):
        print("[PyQt] Sesi simulasi selesai total. Kembali ke halaman utama (Ready Page).")
        self.parent_window.stacked_widget.setCurrentWidget(self.parent_window.ready_page)