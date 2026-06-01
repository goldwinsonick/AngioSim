# core/image_processor.py
import cv2
import numpy as np

class ImageProcessor:
    @staticmethod
    def process_fluoroscopy(cv_img, brightness_raw, contrast_raw, threshold_val):
        """
        Memproses raw frame dari kamera menjadi citra simulasi fluoroskopi (X-Ray).
        
        Parameters:
        - cv_img: Frame asli dalam format BGR (OpenCV)
        - brightness_raw: Nilai dari slider (0 - 100, default 50)
        - contrast_raw: Nilai dari slider (0 - 100, default 50)
        - threshold_val: Nilai batas biner untuk penonjolan kontras (0 - 255)
        
        Returns:
        - rgb_image: Frame matang siap pakai format RGB untuk PyQt6
        """
        # 1. Konversi ke Grayscale (karena citra X-Ray murni monokrom)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

        # 2. Perhitungan Koreksi Brightness & Contrast
        # Slider 50 -> Faktor 1.0 (Normal). Slider > 50 -> Lebih terang/kontras naik.
        alpha = contrast_raw / 50.0      # Faktor pengali Kontras
        beta = (brightness_raw - 50) * 2 # Faktor pergeseran Brightness
        
        # Terapkan rumus linear: Y = alpha * X + beta
        adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)

        # 3. Terapkan Efek Threshold (Opsional/Sesuai Kebutuhan)
        # Berguna jika ingin membuat batas tegas antara anatomi jantung/kateter dengan background
        if threshold_val > 0:
            # Menggunakan Adaptive atau Binary Threshold biasa agar pembuluh darah terlihat kontras
            _, adjusted = cv2.threshold(adjusted, threshold_val, 255, cv2.THRESH_BINARY)

        # 4. Inversi Citra (Opsional, Khas Cath Lab)
        # Di beberapa mesin, area padat berwarna gelap, area kosong berwarna putih (atau sebaliknya).
        # Jika simulasi fluoroskopi kamu ingin background-nya terang dan kateter/jantungnya gelap:
        # adjusted = cv2.bitwise_not(adjusted)

        # 5. Konversi kembali ke format RGB (Wajib untuk QImage PyQt6 Format_RGB888)
        rgb_image = cv2.cvtColor(adjusted, cv2.COLOR_GRAY2RGB)
        
        return rgb_image