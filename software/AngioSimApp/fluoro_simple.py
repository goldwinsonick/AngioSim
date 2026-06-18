import cv2
import numpy as np


# ============================================================
# INPUT CONFIG
# ============================================================

INPUT_MODE = "image"   # "image", "video", atau "camera"

IMAGE_PATH = "fov_base.png"
VIDEO_PATH = "raw_video.mp4"
CAMERA_INDEX = 0

DISPLAY_W = 720
DISPLAY_H = 520

WINDOW_NAME = "Fluoro Tuning - Safe Full Frame"


# ============================================================
# DEFAULT SLIDER
# ============================================================

DEFAULT_BG_GRAY = 88
DEFAULT_HEART_GRAY = 125
DEFAULT_CONTRAST = 18      # 0..100
DEFAULT_SOFTNESS = 35      # 0..100
DEFAULT_DETAIL = 8         # 0..100
DEFAULT_NOISE = 2          # 0..20
DEFAULT_HOLE_FIX = 100     # 0..100, hapus lubang background


# ============================================================
# UTILITIES
# ============================================================

def nothing(x):
    pass


def resize_fit(img, width, height):
    h, w = img.shape[:2]
    scale = min(width / w, height / h)

    nw = int(w * scale)
    nh = int(h * scale)

    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

    if len(img.shape) == 2:
        canvas = np.zeros((height, width), dtype=np.uint8)
    else:
        canvas = np.zeros((height, width, 3), dtype=np.uint8)

    y = (height - nh) // 2
    x = (width - nw) // 2

    canvas[y:y + nh, x:x + nw] = resized
    return canvas


def to_bgr(img):
    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def add_label(img, text):
    out = img.copy()
    cv2.putText(
        out,
        text,
        (18, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )
    return out


def add_noise(gray, sigma):
    if sigma <= 0:
        return gray

    noise = np.random.normal(0, sigma, gray.shape).astype(np.float32)
    out = gray.astype(np.float32) + noise

    return np.clip(out, 0, 255).astype(np.uint8)


def remove_background_holes(frame_bgr, proc_gray, fill_gray, strength=100):
    """
    Menghapus lubang hitam pada background pegboard.
    V2:
    - hole TIDAK diisi dengan gray konstan
    - hole di-inpaint dari area sekitarnya supaya warnanya mengikuti background lokal
    """
    if strength <= 0:
        return proc_gray

    raw_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    # Deteksi lubang gelap pada pegboard
    dark = (raw_gray < 45).astype(np.uint8) * 255

    kernel = np.ones((3, 3), np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel, iterations=1)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    hole_mask = np.zeros_like(raw_gray, dtype=np.uint8)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 15 or area > 2500:
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter <= 0:
            continue

        circularity = 4.0 * np.pi * area / (perimeter * perimeter)

        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / max(1, h)

        # Ambil lubang kecil / bulat, hindari shadow atau struktur phantom
        if circularity < 0.25:
            continue
        if aspect < 0.45 or aspect > 2.2:
            continue

        cv2.drawContours(hole_mask, [cnt], -1, 255, thickness=-1)

    if not np.any(hole_mask > 0):
        return proc_gray

    # Sedikit dilate supaya tepi hole ikut ketutup
    hole_mask = cv2.dilate(hole_mask, np.ones((5, 5), np.uint8), iterations=1)

    # Inpaint pakai nilai sekitar, jadi tidak jadi putih / abu flat
    inpainted = cv2.inpaint(proc_gray, hole_mask, 5, cv2.INPAINT_TELEA)

    # Alpha blur supaya transisi halus
    alpha = cv2.GaussianBlur(hole_mask.astype(np.float32) / 255.0, (17, 17), 0)
    alpha = np.clip(alpha * (strength / 100.0), 0.0, 1.0)

    out = proc_gray.astype(np.float32) * (1.0 - alpha) + inpainted.astype(np.float32) * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def get_values():
    bg_gray = cv2.getTrackbarPos("BG_GRAY", WINDOW_NAME)
    heart_gray = cv2.getTrackbarPos("HEART_GRAY", WINDOW_NAME)
    contrast = cv2.getTrackbarPos("CONTRAST", WINDOW_NAME) / 100.0
    softness = cv2.getTrackbarPos("SOFTNESS", WINDOW_NAME) / 100.0
    detail = cv2.getTrackbarPos("DETAIL", WINDOW_NAME) / 100.0
    noise = cv2.getTrackbarPos("NOISE", WINDOW_NAME)
    hole_fix = cv2.getTrackbarPos("HOLE_FIX", WINDOW_NAME)

    return bg_gray, heart_gray, contrast, softness, detail, noise, hole_fix


# ============================================================
# MAIN FLUORO PROCESSING
# ============================================================

def process_fluoro(frame_bgr):
    bg_gray, heart_gray, contrast, softness, detail, noise, hole_fix = get_values()

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # Blur besar untuk bikin tampilan soft seperti fluoro
    blur_sigma = 1.0 + softness * 5.0
    gray_soft = cv2.GaussianBlur(gray, (0, 0), blur_sigma)

    # Normalisasi berdasarkan range gambar saat ini
    p_low = np.percentile(gray_soft, 5)
    p_high = np.percentile(gray_soft, 95)

    norm = (gray_soft - p_low) / max(1.0, p_high - p_low)
    norm = np.clip(norm, 0.0, 1.0)

    # Compress ke range abu-abu yang sempit
    out = bg_gray + norm * (heart_gray - bg_gray)

    # Contrast kecil saja, jangan agresif
    out = (out - 128.0) * (1.0 + contrast) + 128.0

    # Detail halus, bukan CLAHE kuat
    low = cv2.GaussianBlur(gray_soft, (0, 0), 8.0)
    high = gray_soft - low

    out = out + high * detail * 0.35

    # Final soft blur kecil supaya tidak tajam
    out = cv2.GaussianBlur(out, (0, 0), 0.8)

    out = np.clip(out, 0, 255).astype(np.uint8)

    # Hapus lubang background pegboard supaya tidak muncul sebagai dot hitam.
    out = remove_background_holes(frame_bgr, out, fill_gray=bg_gray, strength=hole_fix)

    # Grain tipis
    out = add_noise(out, noise)

    return out


# ============================================================
# VIEW
# ============================================================

def make_view(frame_bgr, proc_gray):
    raw_show = resize_fit(frame_bgr, DISPLAY_W, DISPLAY_H)
    proc_show = resize_fit(to_bgr(proc_gray), DISPLAY_W, DISPLAY_H)

    raw_show = add_label(raw_show, "RAW")
    proc_show = add_label(proc_show, "PROCESSED FLUORO")

    combined = np.hstack([raw_show, proc_show])

    help_text = "s=save | p=print values | q=quit"
    cv2.putText(
        combined,
        help_text,
        (16, combined.shape[0] - 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (230, 230, 230),
        1,
        cv2.LINE_AA
    )

    return combined


def print_values():
    bg_gray, heart_gray, contrast, softness, detail, noise, hole_fix = get_values()

    print("\n========== CURRENT VALUES ==========")
    print(f"BG_GRAY    : {bg_gray}")
    print(f"HEART_GRAY : {heart_gray}")
    print(f"CONTRAST   : {contrast:.2f}")
    print(f"SOFTNESS   : {softness:.2f}")
    print(f"DETAIL     : {detail:.2f}")
    print(f"NOISE      : {noise}")
    print(f"HOLE_FIX   : {hole_fix}")
    print("====================================\n")


# ============================================================
# MAIN LOOP
# ============================================================

def run_image_mode(frame):
    while True:
        proc = process_fluoro(frame)
        view = make_view(frame, proc)

        cv2.imshow(WINDOW_NAME, view)

        key = cv2.waitKey(30) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("s"):
            cv2.imwrite("fluoro_result.png", proc)
            print("Saved: fluoro_result.png")
        elif key == ord("p"):
            print_values()

    cv2.destroyAllWindows()


def run_stream_mode(cap):
    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps is None or fps <= 1:
        fps = 30

    delay = int(1000 / fps)

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Video selesai / frame tidak terbaca.")
            break

        proc = process_fluoro(frame)
        view = make_view(frame, proc)

        cv2.imshow(WINDOW_NAME, view)

        key = cv2.waitKey(delay) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("s"):
            cv2.imwrite("fluoro_result.png", proc)
            print("Saved: fluoro_result.png")
        elif key == ord("p"):
            print_values()

    cap.release()
    cv2.destroyAllWindows()


def main():
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, DISPLAY_W * 2, DISPLAY_H + 260)

    cv2.createTrackbar("BG_GRAY", WINDOW_NAME, DEFAULT_BG_GRAY, 160, nothing)
    cv2.createTrackbar("HEART_GRAY", WINDOW_NAME, DEFAULT_HEART_GRAY, 220, nothing)
    cv2.createTrackbar("CONTRAST", WINDOW_NAME, DEFAULT_CONTRAST, 100, nothing)
    cv2.createTrackbar("SOFTNESS", WINDOW_NAME, DEFAULT_SOFTNESS, 100, nothing)
    cv2.createTrackbar("DETAIL", WINDOW_NAME, DEFAULT_DETAIL, 100, nothing)
    cv2.createTrackbar("NOISE", WINDOW_NAME, DEFAULT_NOISE, 20, nothing)
    cv2.createTrackbar("HOLE_FIX", WINDOW_NAME, DEFAULT_HOLE_FIX, 100, nothing)

    print("\n=== FLUORO TUNING SAFE FULL FRAME ===")
    print("Tidak pakai object mask otomatis, jadi aorta tidak akan kepotong.")
    print("Ada HOLE_FIX untuk menyamarkan lubang pegboard/background.")
    print("Keys:")
    print("  s = save")
    print("  p = print values")
    print("  q = quit\n")

    if INPUT_MODE == "image":
        frame = cv2.imread(IMAGE_PATH)

        if frame is None:
            raise FileNotFoundError(f"Gambar tidak ditemukan: {IMAGE_PATH}")

        run_image_mode(frame)

    elif INPUT_MODE == "video":
        cap = cv2.VideoCapture(VIDEO_PATH)

        if not cap.isOpened():
            raise RuntimeError(f"Video tidak bisa dibuka: {VIDEO_PATH}")

        run_stream_mode(cap)

    elif INPUT_MODE == "camera":
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

        if not cap.isOpened():
            raise RuntimeError(f"Kamera index {CAMERA_INDEX} tidak bisa dibuka.")

        run_stream_mode(cap)

    else:
        raise ValueError("INPUT_MODE harus 'image', 'video', atau 'camera'.")


if __name__ == "__main__":
    main()