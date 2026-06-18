import os
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

# --- CLASS BARU: Kotak yang bisa diklik ---
class ClickableCard(QFrame):
    clicked = pyqtSignal() # Signal custom supaya bisa di-connect seperti button

    def __init__(self, icon, title_text):
        super().__init__()
        self.setFixedWidth(280)
        self.setMinimumHeight(320) # Sedikit lebih pendek karena tombol hijau hilang
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Style saat normal dan saat di-hover (biar user tau ini bisa diklik)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 25px;
                border: 1px solid #E1E6EF;
            }
            QFrame:hover {
                background-color: #F9FBFF;
                border: 2px solid #1FAE75;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 40, 20, 40)
        layout.setSpacing(15)

        # 1. Ikon
        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 90px; color: #1FAE75; border: none; background: transparent;")
        
        # 2. Judul
        title_lbl = QLabel(title_text)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #2F3A45; border: none; background: transparent;")

        layout.addStretch(1)
        layout.addWidget(icon_lbl)
        layout.addSpacing(20)
        layout.addWidget(title_lbl)
        layout.addStretch(1)

    # Fungsi deteksi klik mouse
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class HomePage(QWidget):
    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

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
        isi_container.setContentsMargins(0, 40, 0, 40)
        isi_container.setSpacing(0)

        # 1. LOGO
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "assets", "angiosim_logo.png")
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(500, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        isi_container.addWidget(logo)

        isi_container.addSpacing(30)

        # 2. JUDUL
        title = QLabel("ANGIOPLASTY TRAINING SIMULATOR")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #2F3A45; letter-spacing: 1px;")
        isi_container.addWidget(title)
        
        isi_container.addSpacing(50)

        # 3. MENU CARDS (Horizontal)
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(50)
        menu_layout.addStretch(1)

        # Buat Card menggunakan class ClickableCard
        self.card_start = ClickableCard("▶", "START DEVICE")
        self.card_settings = ClickableCard("⚙", "SETTINGS")
        self.card_instr = ClickableCard("📋", "INSTRUCTIONS")

        menu_layout.addWidget(self.card_start)
        menu_layout.addSpacing(25)
        menu_layout.addWidget(self.card_settings)
        menu_layout.addSpacing(25)
        menu_layout.addWidget(self.card_instr)

        menu_layout.addStretch(1)
        isi_container.addLayout(menu_layout)
        isi_container.addStretch(1)