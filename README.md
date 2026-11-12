# Q-RES Lifeguard Ground Station App

First-pass passive PySide6 desktop monitor for the existing WFB-ng video and MAVLink streams. No flight commands, stream-rate requests, driver changes, or WFB configuration changes are made.

## Ubuntu 22.04 setup

Install system GStreamer and Qt runtime libraries (review the package list for your machine):

```bash
sudo apt install python3-venv python3-gi gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e .
```

Use the system Python when creating the environment so the system `gi` bindings are visible. PyGObject is intentionally not a pip dependency. NumPy is included for future processing; no OpenCV or ML runtime is needed.

```bash
.venv/bin/python -m ground_station --demo
.venv/bin/python -m ground_station
```

Live defaults: RTP/H.264 UDP **5600**, MAVLink UDP **14550**. Optional `--video-port`, `--telemetry-port`, and `--system-id` overrides are available. Close other receivers bound to these ports before launching. The demo explicitly uses synthetic telemetry and an animated synthetic coastal camera preview, without binding sockets.

## Behavior and boundaries

- The video worker uses GStreamer appsink with a one-frame queue and copies RGB data into an owned QImage. A coalesced signal makes only the newest frame available to the GUI. Video keeps its original aspect ratio.
- Each frame has a monotonic timestamp. `VideoReceiver.take_frame()` is the display's single-consumer mailbox. Future inference should receive a separate bounded mailbox, never compete for this mailbox or block decoding. `VideoWidget.set_detections(timestamp, detections)` accepts normalized bounding boxes only for the currently displayed source frame; older results are discarded.
- MAVLink selects the first autopilot heartbeat's system ID (or the explicit ID), and component 1. Fields expire individually after three seconds. Zero and missing readings are distinct. Reported positive airspeed may be estimated; zero/absent airspeed displays `--` because sensor availability cannot be established from VFR_HUD alone.
- Video/telemetry indicators turn yellow after one second and red after three seconds without data. Telemetry is explicitly labeled stale after one second and blanked after three. WFB stays **UNMONITORED**; receipt of telemetry is never used as a wireless quality measurement.
- UDP receivers remain listening through signal loss. Pipeline/socket failures trigger retries. Missing receiver dependencies produce a status-bar message without crashing the interface.
- GPS includes an interactive OpenStreetMap view with zoom, pan, follow, and fullscreen controls. No aircraft controls, recording, artificial horizon, ML inference, or independent WFB status API is implemented.

## Structure and validation

`model.py` contains conversion and per-field freshness logic; `receivers.py` owns transport workers; `widgets.py` provides replaceable instruments and video overlays; `app.py` composes the window. Resize the vertical and horizontal splitters to adjust panel proportions.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Live aircraft video and telemetry require validation on the actual WFB-ng laptop. If video is missing, check `gst-inspect-1.0 avdec_h264` and confirm the supplied pipeline works with other UDP receivers closed. Diagnostic errors appear in the status bar. Exit closes receiver threads and releases sockets/pipelines.

Additional integration checks:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/smoke_gui.py
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/smoke_streams.py
```

The stream check requires local UDP access and the GStreamer `openh264enc` test encoder (from plugins-bad). It uses ports 15601 and 15551, sends synthetic packets, and shuts down automatically.

PySide6 is pinned to 6.8.3: the 6.12.0 bindings lose references to `None` on Python 3.10 during repeated Qt updates, causing a fatal native crash. After pulling dependency changes, run `.venv/bin/python -m pip install -e .` to apply the pin.

The GPS HUD includes a colored GPS status derived from GPS_RAW_INT fix type (no GPS, searching, 2D, 3D, or enhanced fix). Missing/expired reports show “No recent GPS data”; this is independent of the overall MAVLink connection indicator.

Demo mode renders an offline animated aerial shoreline and rescue boat at approximately 30 fps, with a permanent synthetic-video label. It does not use GStreamer or bind the aircraft UDP ports. Telemetry still refreshes at 10 Hz.

## Aircraft map

The GPS panel feeds valid, fresh aircraft coordinates into a native Qt OpenStreetMap view. Use +/− or the scroll wheel to zoom, drag to pan, and “Follow aircraft” to recenter and resume tracking. “Fullscreen / return” expands the map; press it again or Esc to return. Missing/stale GPS retains the last valid marker in amber with a LAST KNOWN POSITION label until a fresh fix returns. The last position is retained for the current application session; before the first fix the map waits for a valid position. A valid position at 0°, 0° is supported.

Internet is needed for uncached map tiles; telemetry and video continue independently if maps cannot load. Only visible tiles are fetched, with a seven-day local disk cache and application User-Agent. Attribution links to OpenStreetMap. Tile requests reveal the viewed area to the provider. Public tiles are best-effort, with no bulk/offline download feature. See https://operations.osmfoundation.org/policies/tiles/ . For another compatible provider, set `LIFEGUARD_TILE_URL` to an HTTPS tile template containing `{z}`, `{x}`, and `{y}`; update attribution for that provider before distributing.

Before the first GPS fix, the map shows a world overview; the first valid position zooms to the aircraft. Qt network errors appear on the map (hover for the full message). When launched from Snap VS Code, the application removes inherited Snap GTK/GIO module paths from its own process before Qt loads; no system libraries or editor settings are modified.

Reported nonzero coordinates now center the map even while GPS fix status is searching or unavailable. These positions may be autopilot estimates or retained readings, so they appear amber with “REPORTED POSITION — GPS fix unconfirmed.” The all-zero placeholder without a fix is ignored. Dragging disables follow; use “Follow aircraft” to resume.
