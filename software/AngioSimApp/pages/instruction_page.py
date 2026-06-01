import os
import yaml
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

class InstructionPage(QWidget):
    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.init_ui()

    def load_instructions(self):
        """Membaca data instruksi dari file YAML."""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            yaml_path = os.path.join(base_dir, "instruction.yaml")
            with open(yaml_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                return data.get('instructions', [])
        except Exception as e:
            print(f"Error loading YAML: {e}")
            return []

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
        btn_back.clicked.connect(lambda: self.parent_window.stacked_widget.setCurrentIndex(0))
        isi_container.addWidget(btn_back)

        isi_container.addSpacing(10)
        
        # --- JUDUL HALAMAN ---
        title = QLabel("USER INSTRUCTIONS")
        title.setStyleSheet("font-size: 32px; font-weight: 800; color: #1B5E20;")
        isi_container.addWidget(title)

        # ==================== SCROLL AREA ====================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        
        # PAPAN PUTIH BESAR UTAMA
        papan_instruksi = QFrame()
        papan_instruksi.setStyleSheet("""
            QFrame {
                background-color: white; 
                border-radius: 25px; 
                border: 1px solid #E1E6EF;
            }
        """)
        
        grid_layout = QGridLayout(papan_instruksi)
        grid_layout.setContentsMargins(35, 35, 35, 35)
        grid_layout.setHorizontalSpacing(60)  
        grid_layout.setVerticalSpacing(40)    

        # Load data dari YAML
        data_instruksi = self.load_instructions()
        base_dir = os.path.dirname(os.path.abspath(__file__))

        MAX_COLUMNS = 2 

        for index, item in enumerate(data_instruksi):
            t = item.get('title', 'No Title')
            d = item.get('desc', 'No Description')
            img_name = item.get('image', '')
            
            row = index // MAX_COLUMNS
            col = index % MAX_COLUMNS

            item_box = QWidget()
            item_box.setStyleSheet("background: transparent; border: none;")
            
            item_vbox = QVBoxLayout(item_box)
            item_vbox.setContentsMargins(0, 0, 0, 0)
            item_vbox.setSpacing(12)
            item_vbox.setAlignment(Qt.AlignmentFlag.AlignTop) 

            # 1. Bagian Gambar (Menggunakan teknik pembungkus horizontal agar presisi)
            if img_name:
                project_dir = os.path.dirname(base_dir)
                img_path = os.path.join(project_dir, "assets", "instructions", img_name)
                pixmap = QPixmap(img_path)
                
                if not pixmap.isNull():
                    # Skalakan pixmap ke lebar 460px
                    scaled_pixmap = pixmap.scaledToWidth(460, Qt.TransformationMode.SmoothTransformation)
                    
                    img_lbl = QLabel()
                    img_lbl.setPixmap(scaled_pixmap)
                    # Mengunci ukuran fisik label agar pas mengikuti ukuran gambar hasil skala
                    img_lbl.setFixedSize(scaled_pixmap.size())
                    img_lbl.setStyleSheet("border-radius: 12px; border: 1px solid #E1E6EF; background: transparent;")
                    
                    # Trik: Dibungkus QHBoxLayout dengan AlignLeft agar ukurannya tidak dipaksa melar oleh grid
                    img_container = QWidget()
                    img_container_layout = QHBoxLayout(img_container)
                    img_container_layout.setContentsMargins(0, 0, 0, 0)
                    img_container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                    img_container_layout.addWidget(img_lbl)
                    
                    item_vbox.addWidget(img_container)
                else:
                    # Placeholder minimalis jika file gambar tidak ditemukan
                    img_lbl = QLabel()
                    img_lbl.setText("[ Panduan Gambar Belum Tersedia ]")
                    img_lbl.setFixedSize(460, 240)
                    img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    img_lbl.setStyleSheet("background: #F5F7FA; border-radius: 12px; color: #A0AEC0; border: 1px dashed #CBD5E0;")
                    item_vbox.addWidget(img_lbl)

            # 2. Judul Langkah
            lbl_title = QLabel(t)
            lbl_title.setStyleSheet("font-weight: bold; color: #1FAE75; font-size: 18px; border: none; background: transparent;")
            lbl_title.setWordWrap(True)
            item_vbox.addWidget(lbl_title)
            
            # 3. Deskripsi Langkah
            lbl_desc = QLabel(d)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #2F3A45; font-size: 14px; border: none; background: transparent; line-height: 140%;")
            item_vbox.addWidget(lbl_desc)

            grid_layout.addWidget(item_box, row, col)

        main_scroll_layout = QVBoxLayout(scroll_content)
        main_scroll_layout.addWidget(papan_instruksi)
        main_scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        isi_container.addWidget(scroll)

        # Scrollbar styling
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none; background: transparent; width: 8px; margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #D1D9E6; min-height: 30px; border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)