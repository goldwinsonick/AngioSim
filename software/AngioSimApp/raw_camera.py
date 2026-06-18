import cv2
import time
import os


# ============================================================
# USER PARAMETERS
# ============================================================
WIDTH = 1920
HEIGHT = 1080
FPS = 60

OUTPUT_PATH = "led_blinking.mp4"
VIDEO_SOURCE = 1   # try 0, 1, or 2


# ============================================================
# OPEN CAMERA
# ============================================================
def open_camera(source):
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(source, backend)

        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, FPS)

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = cap.get(cv2.CAP_PROP_FPS)

            print("Camera opened successfully.")
            print(f"Requested : {WIDTH} x {HEIGHT} @ {FPS} FPS")
            print(f"Actual    : {actual_w} x {actual_h} @ {actual_fps:.2f} FPS")

            return cap

        cap.release()

    return None


# ============================================================
# CREATE VIDEO WRITER
# ============================================================
def create_writer(output_path):
    output_dir = os.path.dirname(output_path)

    if output_dir != "":
        os.makedirs(output_dir, exist_ok=True)

    codec_list = ["avc1", "mp4v"]

    for codec in codec_list:
        fourcc = cv2.VideoWriter_fourcc(*codec)

        writer = cv2.VideoWriter(
            output_path,
            fourcc,
            FPS,
            (WIDTH, HEIGHT)
        )

        if writer.isOpened():
            print(f"Video writer opened with codec: {codec}")
            return writer

        writer.release()

    return None


# ============================================================
# MAIN
# ============================================================
def main():
    cap = open_camera(VIDEO_SOURCE)

    if cap is None:
        print("ERROR: Cannot open camera.")
        print("Try changing VIDEO_SOURCE to 0, 1, or 2.")
        return

    writer = create_writer(OUTPUT_PATH)

    if writer is None:
        print("ERROR: Cannot create video writer.")
        cap.release()
        return

    cv2.namedWindow("Recording Preview", cv2.WINDOW_NORMAL)

    print("")
    print("Recording started.")
    print("Press Q or ESC to stop safely.")
    print("Do not stop using the VS Code stop button.")
    print("")

    start_time = time.time()
    last_report_time = start_time

    captured_frames = 0
    written_frames = 0
    fps_counter = 0

    try:
        while True:
            ret, frame = cap.read()

            if not ret or frame is None:
                print("No frame received.")
                break

            captured_frames += 1
            fps_counter += 1

            h, w = frame.shape[:2]

            if w != WIDTH or h != HEIGHT:
                frame = cv2.resize(frame, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)

            now = time.time()
            elapsed = now - start_time

            # ====================================================
            # IMPORTANT PART:
            # Keep video duration matched to real time.
            # If camera is slower than 60 FPS, duplicate frames.
            # ====================================================
            target_written_frames = int(elapsed * FPS)

            while written_frames < target_written_frames:
                writer.write(frame)
                written_frames += 1

            cv2.imshow("Recording Preview", frame)

            if now - last_report_time >= 1.0:
                measured_capture_fps = fps_counter / (now - last_report_time)
                video_duration = written_frames / FPS

                print(
                    f"Capture FPS: {measured_capture_fps:.2f} | "
                    f"Written frames: {written_frames} | "
                    f"Video duration: {video_duration:.2f}s | "
                    f"Real elapsed: {elapsed:.2f}s"
                )

                fps_counter = 0
                last_report_time = now

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                print("Stopping safely...")
                break

    finally:
        # Write a few final frames to align final duration
        final_elapsed = time.time() - start_time
        final_target_frames = int(final_elapsed * FPS)

        while written_frames < final_target_frames:
            writer.write(frame)
            written_frames += 1

        cap.release()
        writer.release()
        cv2.destroyAllWindows()

        duration = time.time() - start_time

        print("")
        print("Recording finished.")
        print(f"Output          : {OUTPUT_PATH}")
        print(f"Captured frames : {captured_frames}")
        print(f"Written frames  : {written_frames}")
        print(f"Real duration   : {duration:.2f} seconds")
        print(f"Video duration  : {written_frames / FPS:.2f} seconds")

        if os.path.exists(OUTPUT_PATH):
            file_size = os.path.getsize(OUTPUT_PATH)
            print(f"File size       : {file_size / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()