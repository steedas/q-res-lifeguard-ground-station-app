"""Independent receivers. No transport configuration or flight commands are sent."""
import threading
import time
from dataclasses import dataclass
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from .model import TelemetryStore

@dataclass(frozen=True)
class VideoFrame:
    image: QImage
    timestamp: float

class VideoReceiver(QThread):
    status = Signal(str)
    frame_available = Signal()  # Notification only: a single newest frame is retained.

    def __init__(self, port=5600, parent=None):
        super().__init__(parent)
        self.port = port
        self._lock = threading.Lock()
        self._latest = None
        self._notified = False

    def take_frame(self):
        with self._lock:
            frame, self._latest = self._latest, None
            self._notified = False
            return frame

    def run(self):
        try:
            import gi
            gi.require_version("Gst", "1.0")
            gi.require_version("GstVideo", "1.0")
            from gi.repository import Gst, GstVideo
            Gst.init(None)
        except Exception as exc:
            self.status.emit(f"Video unavailable: {exc}")
            return
        while not self.isInterruptionRequested():
            pipeline = None
            try:
                pipeline = Gst.parse_launch(
                    f'udpsrc port={self.port} caps="application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000" '
                    '! rtpjitterbuffer latency=50 drop-on-latency=true ! rtph264depay ! h264parse '
                    '! avdec_h264 ! videoconvert ! video/x-raw,format=RGB '
                    '! appsink name=frames sync=false max-buffers=1 drop=true')
                sink = pipeline.get_by_name("frames")
                if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                    raise RuntimeError("GStreamer could not start")
                bus = pipeline.get_bus()
                while not self.isInterruptionRequested():
                    error = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
                    if error:
                        raise RuntimeError(error.parse_error()[0] if error.type == Gst.MessageType.ERROR else "Stream ended")
                    sample = sink.emit("try-pull-sample", 100 * Gst.MSECOND)
                    if sample is None:
                        continue
                    info = GstVideo.VideoInfo.new_from_caps(sample.get_caps())
                    buffer = sample.get_buffer()
                    ok, mapped = buffer.map(Gst.MapFlags.READ)
                    if not ok:
                        continue
                    try:
                        image = QImage(mapped.data, info.width, info.height, info.stride[0], QImage.Format.Format_RGB888).copy()
                    finally:
                        buffer.unmap(mapped)
                    with self._lock:
                        self._latest = VideoFrame(image, time.monotonic())
                        notify = not self._notified
                        self._notified = True
                    if notify:
                        self.frame_available.emit()
            except Exception as exc:
                self.status.emit(f"Video retrying: {exc}")
            finally:
                if pipeline is not None:
                    pipeline.set_state(Gst.State.NULL)
            for _ in range(20):
                if self.isInterruptionRequested():
                    break
                self.msleep(100)

class MavlinkReceiver(QThread):
    telemetry = Signal(object, float)
    status = Signal(str)

    def __init__(self, port=14550, system_id=None, parent=None):
        super().__init__(parent)
        self.port, self.system_id = port, system_id

    def run(self):
        try:
            from pymavlink import mavutil
        except ImportError as exc:
            self.status.emit(str(exc))
            return
        while not self.isInterruptionRequested():
            master = None
            try:
                master = mavutil.mavlink_connection(f"udpin:0.0.0.0:{self.port}")
                store = TelemetryStore()
                last_rx = 0.0
                last_emit = 0.0
                selected = self.system_id
                while not self.isInterruptionRequested():
                    msg = master.recv_match(blocking=True, timeout=0.1)
                    now = time.monotonic()
                    if msg is not None and msg.get_type() != "BAD_DATA":
                        if selected is None and msg.get_type() == "HEARTBEAT" and msg.autopilot != mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                            selected = msg.get_srcSystem()
                        if selected is not None and msg.get_srcSystem() == selected and msg.get_srcComponent() == 1:
                            last_rx = now
                            store.update(msg, mavutil.mode_string_v10(msg) if msg.get_type() == "HEARTBEAT" else None, now)
                    if now - last_emit >= 0.1:
                        self.telemetry.emit(store.snapshot(now), last_rx)
                        last_emit = now
            except Exception as exc:
                self.status.emit(f"Telemetry retrying: {exc}")
            finally:
                if master is not None:
                    master.close()
            for _ in range(20):
                if self.isInterruptionRequested():
                    break
                self.msleep(100)
