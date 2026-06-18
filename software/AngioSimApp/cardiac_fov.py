import cv2
import numpy as np
import json
import os


# ============================================================
# CAMERA SETTINGS
# ============================================================
CAMERA_INDEX = 1          # ganti ke 0 / 2 kalau kamera tidak kebuka
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# ============================================================
# LOCKED UNDISTORT SETTINGS
# ============================================================
UNDISTORT_K1 = -0.09
UNDISTORT_K2 = 0.00
UNDISTORT_ZOOM = 1.00

# ============================================================
# FOV OUTPUT SETTINGS
# ============================================================
WARP_OUTPUT_SIZE = 720
POINT_FILE = "fov_points.json"

POINT_RADIUS = 8
SELECT_RADIUS = 30

# ============================================================
# GLOBAL STATE
# ============================================================
raw_points = []
selected_point = -1
dragging = False


# ============================================================
# CAMERA
# ============================================================
def open_camera(index):
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(index, backend)

        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            print(f"Kamera berhasil dibuka: index {index}")
            return cap

        cap.release()

    print(f"Kamera index {index} tidak bisa dibuka.")
    return None


# ============================================================
# LOCKED UNDISTORT
# ============================================================
def undistort_radial_manual(frame, k1=-0.09, k2=0.00, zoom=1.00):
    """
    Manual undistortion untuk kamera wide-angle.
    Di sini parameternya sudah di-lock.
    """

    h, w = frame.shape[:2]

    cx = w / 2.0
    cy = h / 2.0

    x = (np.arange(w, dtype=np.float32) - cx) / (w / 2.0)
    y = (np.arange(h, dtype=np.float32) - cy) / (h / 2.0)
    xv, yv = np.meshgrid(x, y)

    zoom = max(1.0, zoom)

    xu = xv / zoom
    yu = yv / zoom

    r2 = xu * xu + yu * yu
    factor = 1.0 + k1 * r2 + k2 * r2 * r2

    xd = xu * factor
    yd = yu * factor

    map_x = (xd * (w / 2.0) + cx).astype(np.float32)
    map_y = (yd * (h / 2.0) + cy).astype(np.float32)

    undistorted = cv2.remap(
        frame,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    return undistorted


# ============================================================
# POINT UTILITIES
# ============================================================
def init_default_points(frame):
    """
    Titik default FOV di frame yang SUDAH di-undistort.
    Nanti bisa kamu drag manual.
    """
    h, w = frame.shape[:2]

    return [
        [int(0.10 * w), int(0.18 * h)],  # TL
        [int(0.90 * w), int(0.18 * h)],  # TR
        [int(0.90 * w), int(0.88 * h)],  # BR
        [int(0.10 * w), int(0.88 * h)]   # BL
    ]


def order_points(pts):
    """
    Urutkan 4 titik menjadi:
    TL, TR, BR, BL
    """
    pts = np.array(pts, dtype=np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # TL
    rect[2] = pts[np.argmax(s)]  # BR

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # TR
    rect[3] = pts[np.argmax(diff)]  # BL

    return rect


def distance(p1, p2):
    p1 = np.array(p1, dtype=np.float32)
    p2 = np.array(p2, dtype=np.float32)
    return np.linalg.norm(p1 - p2)


def save_points(points):
    with open(POINT_FILE, "w") as f:
        json.dump(points, f, indent=4)
    print(f"Titik FOV disimpan ke {POINT_FILE}")


def load_points():
    if not os.path.exists(POINT_FILE):
        print("Belum ada file titik FOV.")
        return []

    with open(POINT_FILE, "r") as f:
        points = json.load(f)

    print(f"Titik FOV dimuat dari {POINT_FILE}")
    return points


# ============================================================
# MOUSE CALLBACK
# ============================================================
def mouse_callback(event, x, y, flags, param):
    global raw_points, selected_point, dragging

    if len(raw_points) != 4:
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        selected_point = -1

        for i, p in enumerate(raw_points):
            px, py = p
            dist = np.sqrt((x - px) ** 2 + (y - py) ** 2)
            if dist < SELECT_RADIUS:
                selected_point = i
                dragging = True
                break

    elif event == cv2.EVENT_MOUSEMOVE:
        if dragging and selected_point != -1:
            raw_points[selected_point] = [x, y]

    elif event == cv2.EVENT_LBUTTONUP:
        dragging = False
        selected_point = -1


# ============================================================
# DRAWING
# ============================================================
def draw_overlay(frame, points):
    display = frame.copy()

    cv2.rectangle(display, (0, 0), (1180, 55), (0, 0, 0), -1)
    cv2.putText(
        display,
        "Drag red dots | R reset | P save points | L load points | S save image | Q quit",
        (15, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.78,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    if len(points) == 4:
        ordered = order_points(points)
        ordered_int = ordered.astype(np.int32)

        cv2.polylines(
            display,
            [ordered_int],
            isClosed=True,
            color=(255, 0, 0),
            thickness=3
        )

        labels = ["TL", "TR", "BR", "BL"]

        for i, (x, y) in enumerate(ordered_int):
            cv2.circle(display, (x, y), POINT_RADIUS, (0, 0, 255), -1)
            cv2.putText(
                display,
                labels[i],
                (x + 8, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
                cv2.LINE_AA
            )

    return display


def apply_flip(img, flip_mode):
    """
    0 = no flip
    1 = horizontal
    2 = vertical
    3 = both
    """
    if flip_mode == 1:
        return cv2.flip(img, 1)
    elif flip_mode == 2:
        return cv2.flip(img, 0)
    elif flip_mode == 3:
        return cv2.flip(img, -1)
    return img


# ============================================================
# FOV TRANSFORM
# ============================================================
def transform_fov_no_crop_no_gepeng(frame, points, margin_percent=0, flip_output=1):
    """
    Transform FOV:
    - Input frame sudah di-undistort
    - 4 titik dipakai untuk perspective transform
    - Output 720x720
    - Tidak crop manual
    - Tidak gepeng (aspect ratio dijaga)
    """

    out_size = WARP_OUTPUT_SIZE

    if len(points) != 4:
        blank = np.ones((out_size, out_size, 3), dtype=np.uint8) * 255
        cv2.putText(
            blank,
            "Set 4 FOV points first",
            (40, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 255),
            3,
            cv2.LINE_AA
        )
        return blank

    src = order_points(points)
    tl, tr, br, bl = src

    width_top = distance(tl, tr)
    width_bottom = distance(bl, br)
    height_left = distance(tl, bl)
    height_right = distance(tr, br)

    avg_width = (width_top + width_bottom) / 2.0
    avg_height = (height_left + height_right) / 2.0

    if avg_width < 1 or avg_height < 1:
        return np.ones((out_size, out_size, 3), dtype=np.uint8) * 255

    margin = int((margin_percent / 100.0) * out_size)
    usable_size = out_size - 2 * margin

    scale = min(usable_size / avg_width, usable_size / avg_height)

    rect_w = int(avg_width * scale)
    rect_h = int(avg_height * scale)

    x0 = (out_size - rect_w) // 2
    y0 = (out_size - rect_h) // 2
    x1 = x0 + rect_w
    y1 = y0 + rect_h

    dst = np.float32([
        [x0, y0],  # TL
        [x1, y0],  # TR
        [x1, y1],  # BR
        [x0, y1]   # BL
    ])

    matrix = cv2.getPerspectiveTransform(src, dst)

    warped = cv2.warpPerspective(
        frame,
        matrix,
        (out_size, out_size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    warped = apply_flip(warped, flip_output)

    cv2.rectangle(warped, (0, 0), (260, 42), (0, 0, 0), -1)
    cv2.putText(
        warped,
        "Warped FOV",
        (15, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    return warped


# ============================================================
# TRACKBAR
# ============================================================
def nothing(x):
    pass


# ============================================================
# MAIN
# ============================================================
def main():
    global raw_points

    cap = open_camera(CAMERA_INDEX)

    if cap is None:
        print("Coba ganti CAMERA_INDEX ke 0, 1, atau 2.")
        return

    cv2.namedWindow("Original - Undistorted + FOV Points", cv2.WINDOW_AUTOSIZE)
    cv2.namedWindow("Warped FOV", cv2.WINDOW_AUTOSIZE)
    cv2.namedWindow("FOV Transform Control", cv2.WINDOW_NORMAL)

    cv2.resizeWindow("FOV Transform Control", 420, 140)

    cv2.setMouseCallback("Original - Undistorted + FOV Points", mouse_callback)

    cv2.createTrackbar("Margin", "FOV Transform Control", 0, 30, nothing)
    cv2.createTrackbar("Flip Output", "FOV Transform Control", 1, 3, nothing)

    print("Program berjalan.")
    print("Undistort sudah di-lock:")
    print(f"  K1   = {UNDISTORT_K1}")
    print(f"  K2   = {UNDISTORT_K2}")
    print(f"  Zoom = {UNDISTORT_ZOOM}")
    print("")
    print("Urutan proses:")
    print("kamera -> undistort -> pilih 4 titik FOV -> transform FOV")
    print("")
    print("Keyboard:")
    print("R = reset titik")
    print("P = save points")
    print("L = load points")
    print("S = save warped image")
    print("Q = keluar")
    print("")
    print("Catatan:")
    print("- Output Warped FOV = 720x720")
    print("- No crop")
    print("- No gepeng")
    print("- Boleh ada padding putih, itu normal")

    save_count = 0

    while True:
        ret, frame = cap.read()

        if not ret or frame is None:
            print("Frame kamera tidak terbaca.")
            break

        # 1. UNDISTORT DULU (LOCKED)
        undistorted = undistort_radial_manual(
            frame,
            k1=UNDISTORT_K1,
            k2=UNDISTORT_K2,
            zoom=UNDISTORT_ZOOM
        )

        # 2. INIT POINT kalau belum ada
        if len(raw_points) != 4:
            raw_points = init_default_points(undistorted)

        # 3. AMBIL CONTROL TRANSFORM
        margin = cv2.getTrackbarPos("Margin", "FOV Transform Control")
        flip_output = cv2.getTrackbarPos("Flip Output", "FOV Transform Control")

        # 4. TRANSFORM FOV
        overlay = draw_overlay(undistorted, raw_points)

        warped = transform_fov_no_crop_no_gepeng(
            undistorted,
            raw_points,
            margin_percent=margin,
            flip_output=flip_output
        )

        cv2.imshow("Original - Undistorted + FOV Points", overlay)
        cv2.imshow("Warped FOV", warped)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord("r"):
            raw_points = init_default_points(undistorted)
            print("Titik FOV di-reset.")

        elif key == ord("p"):
            save_points(raw_points)

        elif key == ord("l"):
            loaded = load_points()
            if len(loaded) == 4:
                raw_points = loaded
                print("Titik FOV berhasil di-load.")
            else:
                print("File titik tidak valid atau belum ada.")

        elif key == ord("s"):
            filename = f"warped_fov_{save_count}.png"
            cv2.imwrite(filename, warped)
            print(f"Saved image: {filename}")
            save_count += 1

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()