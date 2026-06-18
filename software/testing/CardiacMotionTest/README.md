# AngioSim — Cardiac Motion Test

Tools for driving the AngioSim cardiac-simulator actuator, recording video of the
resulting motion, and analyzing that footage to produce displacement graphs for
the thesis.

The project has two independent PyQt6 apps plus a notebook:

| Path | What it is |
|---|---|
| [app/](app/) | **Recording app** — live camera preview, ESP32 PWM control, and synchronized video + session recording |
| [analysis/](analysis/) | **Analysis app** — lens undistortion (top camera) and marking each point's REST position, saved to a setup file |
| [analysis/notebooks/compare_results.ipynb](analysis/notebooks/compare_results.ipynb) | Aggregates every video's exported results into the comparison graphs used in the paper |
| [firmware/angiosim_firmware/](firmware/angiosim_firmware/) | ESP32 Arduino sketch that drives the 4-channel 12 V PWM board over serial |
| [data/](data/) | Recorded experiment footage (`top_recording/`, `side_recording/`) |

---

## 1. Setup

### 1.1 Python environment

From `software/testing/CardiacMotionTest/`:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

This installs PyQt6, OpenCV, pyqtgraph, pyserial, numpy/scipy, matplotlib, and
(for the comparison notebook) pandas + ipykernel.

To run the notebook in VS Code / Jupyter, select the **`.venv`** kernel
("Python 3 (.venv)") so `pandas`/`ipykernel` and the `analysis/core` imports
resolve correctly.

### 1.2 Firmware

Flash [firmware/angiosim_firmware/angiosim_firmware.ino](firmware/angiosim_firmware/angiosim_firmware.ino)
to the ESP32 with the Arduino IDE / `arduino-cli`. It exposes a simple
line-delimited ASCII protocol at **115200 baud**:

```
PC  -> ESP32   SET_PWM:<ch>:<val>      ch = 1-4, val = 0-255
               SET_FREQ:<ch>:<hz>      ch = 1-4, hz  = 100-40000
               BOARD_ENABLE:<0|1>
               PING
ESP32 -> PC    ACK:...   /   ERR:<msg>
```

Channels 1-4 map to GPIO 25/26/27/14, each driving one 12 V PWM output (8-bit
duty resolution) for the actuator/accumulator solenoids.

### 1.3 Cameras

- **Top camera**: Yahboom OV2710 USB camera (significant lens/barrel
  distortion — this is why the analysis app has a lens-calibration step,
  see §3.3).
- **Side camera**: phone camera (negligible distortion), used as a secondary
  reference angle.

---

## 2. Recording system (`app/`)

```powershell
python app/main.py
```

This opens **"AngioSim — Recording"**: a live camera preview on the left and
session/PWM controls on the right.

### 2.1 Camera

- **Cam / resolution**: pick the camera index and capture resolution
  (640×480 / 1280×720 / 1920×1080), then **Switch**.
- **Scan**: probes camera indices 0-7 and lists the ones that respond
  (temporarily stops the live feed — DirectShow can't share a camera handle).

### 2.2 ESP32 connection

- **Port**: select the ESP32's COM port (use **Refresh** to rescan), then
  **Connect**. A 5-second ping keeps the link alive; the status bar shows
  `ESP32: ACK:...` on success.

### 2.3 PWM control

- **Enable Control Board** arms all 4 channels (sends `BOARD_ENABLE:1` and
  starts each channel's duty-cycle timer; disabling forces duty back to 0).
- Each of the 4 channels has an independent **mode**:
  - **Always On** — constant duty (0-255).
  - **Systole/Diastole** — alternates between a systole and diastole duty at a
    given **BPM** and **systole fraction** (the fraction of each beat period
    spent at the systole duty).
  - **Interval** — simple ON/OFF duty cycling with configurable ON/OFF times
    in ms and an ON duty.
- **Freq (Hz)** sets the channel's PWM carrier frequency (100 Hz – 40 kHz;
  20 kHz default keeps the actuator silent).

All camera/serial/PWM settings persist to [app/app_settings.json](app/app_settings.json)
on close and are restored on the next launch.

### 2.4 Recording a session

1. Fill in **Name** (used as the folder suffix, spaces → underscores) and
   optional **Notes**.
2. Press **● Start Recording**. A new folder is created at
   `app/recordings/<timestamp>_<name>/` containing:
   - `footage.mp4` — the captured video (frame size/FPS match the live camera)
   - `session.json` — metadata: label, notes, start time, fps, frame size,
     total frame count, and the **PWM settings active for each of the 4
     channels** (`{"<channel>": {"freq_hz": ..., "duty": ...}}`)
3. Press **■ Stop Recording** to finalize both files. The status bar reports
   the number of frames saved.

> Recordings used for analysis are moved/copied into [data/top_recording/](data/top_recording/)
> (folder + `footage.mp4` + `session.json`) or [data/side_recording/](data/side_recording/)
> (flat `.mp4` files from the phone, no `session.json`).
>
> **Naming convention** the analysis notebook expects to parse conditions from:
> `..._with_accumulator_pwm_<duty>` / `..._no_accumulator_pwm_<duty>`
> (a legacy form without `pwm_`, e.g. `..._with_accumulator_170`, is also
> recognized).

---

## 3. Analysis system (`analysis/`)

```powershell
python analysis/main.py
```

This opens **"AngioSim — Motion Analyzer"**.

The app's job is deliberately narrow: **undistort the footage where needed,
and let you mark each tracked point's REST position** (the frame and pixel
location that everything else gets measured relative to), saved to a setup
file. **Tracking, px↔mm calibration, and displacement math are *not* done
here** — they all happen in the comparison notebook, where you have full
visibility and control over the (non-trivial — see the note in §3.2)
calibration involved.

### 3.1 Load a video

**Load Video…** opens a `footage.mp4` (or any `.mp4`). If a
`<video_stem>_setup.json` exists next to it (see §3.4), it's loaded silently —
markers, rest frame, and sync offset all restore automatically.

Use the **seek slider**, **▶ Play/Pause**, and the **±1 / ±10** step buttons to
scrub through the footage. The frame counter shows `Frame: n / total`.

### 3.2 Lens calibration (top camera only, once per camera)

Every frame — for display, marker placement/clicking, and the saved rest
reference — is passed through `cv2.undistort()` immediately after it's read,
so there is exactly **one** consistent coordinate space throughout the app.

Of the two recordings:
- the **top camera** (Yahboom OV2710 USB) has significant barrel distortion
  and needs this step;
- the **side camera** (phone) has negligible distortion and is used as-is — no
  `side_lens.json` is ever created, so those frames simply pass through
  untouched.

Click **Lens Calibration…** to open a tuner: drag the **k1**/**k2** (radial
distortion) and **focal scale** sliders while watching a live preview of the
current frame (toggle **Overlay reference grid** to help) until straight
physical references — frame edges, rows of screws — actually look straight.
Click **Save**.

This is saved as a *shared* file keyed by source
(`analysis/calibration/<top|side>_lens.json`, auto-detected from the
`top_recording`/`side_recording` folder name) — **not** per video. Every
subsequent video from that camera loads and applies it automatically (the
**Lens: …** label shows the active label and coefficients), so you only ever
tune it once per camera/lens combination. If a video's resolution doesn't
match the saved calibration's, it's skipped with a warning rather than
mis-applied.

> **Why tracking and px↔mm conversion are done in the notebook instead:**
> a scale derived from a ruler is only valid for points lying on the *same
> physical plane* as the ruler — lens undistortion corrects *radial*
> distortion only, it cannot fix the perspective/depth foreshortening that
> makes a ruler's px-per-mm invalid for markers sitting at a different depth.
> Getting this right needs a plane-aware (or per-marker-depth) calibration
> approach that's much easier to reason about — and iterate on — in the
> notebook, where the tracking and the calibration math live side by side and
> can be re-run cheaply against the same exported rest references.

### 3.3 Place markers and set the rest frame

1. Scrub to the frame you consider the **rest** (baseline/resting) position of
   the heart surface — this frame and these pixel locations are what the
   notebook will track from, in both directions.
2. Click **+ Add Marker**, then click on the marker's location in the video.
   Repeat for each marker (2-5 recommended; each gets a numbered, colored dot).
3. The frame you were on when you placed the *last* marker becomes the
   **rest frame** — shown in the **"Rest frame: N"** label. Re-placing markers
   on a different frame moves the rest reference.
4. **Clear All** removes every marker and resets the rest frame.

### 3.4 Save / load setup

- **Save Setup** writes `<video_stem>_setup.json` — markers (rest-frame pixel
  positions), rest frame index, and sync offset (see
  [analysis/core/setup.py](analysis/core/setup.py) for the full schema). Lens
  calibration is *not* part of this file — it's the shared per-camera file
  from §3.2, loaded independently of any one video's setup. **This setup file
  is the only thing the notebook needs from the app** — it opens the video
  itself, applies the same shared lens calibration, and tracks from the saved
  rest reference.
- **Load Setup** restores it manually; it's also auto-loaded (silently) when
  you open a video that has one — so re-opening a video for review brings
  everything back exactly as you left it.

---

## 4. Comparison notebook (`analysis/notebooks/compare_results.ipynb`)

Once you've gone through the Analysis app for the videos you care about (each
producing a `<video_stem>_setup.json` with its rest reference), open the
notebook with the `.venv` kernel selected. This is where tracking, calibration,
and all the measurement math now live — using the same `core.marker_tracker`
and `core.lens_calibration` building blocks the app uses, so the coordinate
space matches exactly:

1. Locates the project root and adds `analysis/` to `sys.path`.
2. **Discovers** every `footage.mp4` under `data/top_recording/*/` and every
   `.mp4` under `data/side_recording/`, and parses each one's
   `accumulator` (bool), `pwm_duty` (int), and `source` (`top`/`side`) from
   the folder/file name (cross-checked against `session.json` for top
   recordings).
3. **Loads** each video's `_setup.json` (rest frame + marker positions), opens
   the video, applies the matching `<source>_lens.json` if one exists (top
   only — side passes through untouched), and runs `MarkerTracker`
   bidirectionally from the rest frame to extract each marker's raw `(x, y)`
   pixel trajectory.
4. **Calibrates and measures**: derives px↔mm scale and per-marker
   displacement-from-rest using whatever plane/depth-aware approach is
   appropriate (see the note in §3.2 — this is the step that needs care),
   applies each video's `sync_offset_s` to align `time_s_synced`, and
   concatenates everything into one tagged `combined` DataFrame.
5. **Plots**:
   - per-marker displacement-from-rest overlaid by PWM duty, split into
     "with accumulator" / "no accumulator" panels
   - peak-to-peak displacement amplitude vs. PWM duty (one line per
     marker/accumulator condition)
   - optional top-vs-side overlay for conditions recorded from both cameras
   All figures are saved as PNGs to `analysis/notebooks/figures/`.
6. **Exports** `combined_results.csv` and `summary_results.csv` to
   `analysis/notebooks/` for the thesis appendix / raw-data reference.

If a video is missing its `_setup.json`, the discovery cell reports it by
label so you know which ones still need rest markers placed in the Analysis app.
