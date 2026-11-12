"""Local synthetic RTP/MAVLink integration check; uses non-production ports."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gi
gi.require_version('Gst','1.0')
from gi.repository import Gst
from PySide6.QtCore import QCoreApplication, QTimer
from pymavlink import mavutil
from ground_station.receivers import VideoReceiver, MavlinkReceiver
Gst.init(None)
app = QCoreApplication([])
video = VideoReceiver(15601)
mav = MavlinkReceiver(15551)
received = {'video':False,'mav':False}
errors = []
video.status.connect(errors.append)
mav.status.connect(errors.append)
def frame():
    item = video.take_frame()
    if item:
        received['video'] = item.image.width() == 320 and item.image.height() == 240

def telemetry(data, timestamp):
    if data.mode is not None and data.roll is not None:
        received['mav'] = True
video.frame_available.connect(frame)
mav.telemetry.connect(telemetry)
sender = mavutil.mavlink_connection('udpout:127.0.0.1:15551',source_system=1,source_component=1)
pipeline = Gst.parse_launch('videotestsrc is-live=true ! video/x-raw,width=320,height=240 ! openh264enc ! rtph264pay pt=96 config-interval=1 ! udpsink host=127.0.0.1 port=15601 sync=false')
video.start()
mav.start()
pipeline.set_state(Gst.State.PLAYING)
timer = QTimer()
def send():
    sender.mav.heartbeat_send(2,3,128,0,4)
    sender.mav.attitude_send(0,0.1,0.2,0.3,0,0,0)
timer.timeout.connect(send)
timer.start(100)
QTimer.singleShot(3500,app.quit)
try:
    app.exec()
finally:
    timer.stop()
    pipeline.set_state(Gst.State.NULL)
    sender.close()
    for worker in (video,mav):
        worker.requestInterruption()
    for worker in (video,mav):
        worker.wait()
assert all(received.values()), (received, errors)
print('PASS: local RTP decode and MAVLink reception',received)
