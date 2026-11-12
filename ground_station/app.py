"""Application composition and connection freshness policy."""
import argparse
import math
import sys
import time
from .runtime import configure_desktop_environment

configure_desktop_environment()

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSplitter, QFrame
from .demo import demo_frame
from .model import Telemetry
from .receivers import VideoReceiver, MavlinkReceiver
from .widgets import VideoWidget, TelemetryWidget, GPSWidget, formatted

STYLE = '''
QWidget { background: #10171f; color: #aebdca; font-family: sans-serif; font-size: 13px; }
QMainWindow { background: #0b1118; }
QFrame { border: 1px solid #263442; border-radius: 6px; }
QLabel { border: none; background: transparent; }
QLabel#brand { color: #f0f5f7; font-size: 21px; font-weight: 700; }
QLabel#section { color: #63d6c2; font-weight: 700; padding-bottom: 8px; }
QLabel#value { color: #eef5f8; font-weight: 600; }
QLabel#muted { color: #748898; font-size: 11px; }
QLabel#map { color: #667c8c; background: #0b1219; padding: 12px; }
QSplitter::handle { background: #0b1118; }
'''

class MainWindow(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.demo = args.demo
        self.setWindowTitle('LIFEGUARD VTOL — Ground Station' + (' [DEMO]' if self.demo else ''))
        self.resize(1600, 950)
        self.last_video = self.last_telemetry = 0.0
        self.data = Telemetry()
        self.workers = []
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 14)
        header = QHBoxLayout()
        brand = QLabel('LIFEGUARD  /  VTOL')
        brand.setObjectName('brand')
        header.addWidget(brand)
        header.addStretch()
        self.indicators = {}
        for name in ('VIDEO','TELEMETRY','WFB'):
            label = QLabel()
            header.addWidget(label)
            self.indicators[name] = label
        self.clock = QLabel()
        header.addWidget(self.clock)
        layout.addLayout(header)
        self.notice = QLabel('DEMO — SYNTHETIC DATA / RECEIVERS DISABLED' if self.demo else 'PASSIVE MONITOR  •  Waiting for aircraft streams')
        self.notice.setObjectName('section')
        layout.addWidget(self.notice)
        split = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(split, 1)
        video_panel = QWidget()
        video_layout = QVBoxLayout(video_panel)
        video_layout.setContentsMargins(0,0,0,0)
        self.video = VideoWidget()
        video_layout.addWidget(self.video,1)
        metrics = QHBoxLayout()
        self.metrics = {}
        for key,title,unit in [('altitude','ALT','m'),('groundspeed','GND SPD','m/s'),('airspeed','AIR SPD*','m/s'),('heading','HEADING','°')]:
            label = QLabel()
            label.setObjectName('value')
            metrics.addWidget(label)
            self.metrics[key] = (label,title,unit)
        video_layout.addLayout(metrics)
        split.addWidget(video_panel)
        bottom = QSplitter(Qt.Orientation.Horizontal)
        self.telemetry = TelemetryWidget()
        self.gps = GPSWidget()
        bottom.addWidget(self.telemetry)
        bottom.addWidget(self.gps)
        bottom.setSizes([1050,450])
        split.addWidget(bottom)
        split.setSizes([700,250])
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        self.statusBar().showMessage('WFB link unmonitored — no independent link-status provider configured')
        if not self.demo:
            video = VideoReceiver(args.video_port, self)
            video.frame_available.connect(self.receive_frame)
            video.status.connect(self.receiver_error)
            self.video_receiver = video
            mav = MavlinkReceiver(args.telemetry_port, args.system_id, self)
            mav.telemetry.connect(self.receive_telemetry)
            mav.status.connect(self.receiver_error)
            self.workers = [video,mav]
            for worker in self.workers:
                worker.start()
        self.demo_timer = QTimer(self)
        if self.demo:
            self.demo_timer.timeout.connect(self.refresh_demo_video)
            self.demo_timer.start(33)
            self.refresh_demo_video()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(100)
        self.refresh()

    def receiver_error(self, message):
        self.statusBar().showMessage(message)

    def receive_frame(self):
        frame = self.video_receiver.take_frame()
        if frame:
            self.last_video = frame.timestamp
            self.video.set_frame(frame)

    def receive_telemetry(self, data, timestamp):
        self.data, self.last_telemetry = data, timestamp

    def indicator(self, name, text, color):
        self.indicators[name].setText(f'● {name}  {text}   ')
        self.indicators[name].setStyleSheet(f'color: {color}')

    def refresh_demo_video(self):
        self.last_video = time.monotonic()
        self.video.set_frame(demo_frame(self.last_video))

    def refresh(self):
        now = time.monotonic()
        if self.demo:
            self.data = Telemetry(roll=2.4*math.sin(now/3),pitch=-1.3,yaw=247,latitude=44.2312,longitude=-76.486,
                                  altitude=35.2,groundspeed=12.3,vertical_speed=0.2,heading=247,voltage=24.2,current=23.1,
                                  remaining=75,satellites=14,fix='3D',gps_status='3D fix acquired',mode='QLOITER',armed='ARMED')
            self.last_telemetry = now
        for name, timestamp in [('VIDEO',self.last_video),('TELEMETRY',self.last_telemetry)]:
            age = now-timestamp if timestamp else float('inf')
            state,color = ('ACTIVE','#65dcad') if age < 1 else (('STALE','#efc66a') if age < 3 else ('DISCONNECTED','#ef7c80'))
            self.indicator(name,state,color)
        self.indicator('WFB','UNMONITORED','#efc66a')
        if now-self.last_video >= 3:
            self.video.clear()
        stale = now-self.last_telemetry >= 1
        data = Telemetry() if now-self.last_telemetry >= 3 else self.data
        self.telemetry.set_telemetry(data)
        self.gps.set_telemetry(data)
        for key,(label,title,unit) in self.metrics.items():
            label.setText(f'{title}   {formatted(getattr(data,key),unit)}')
        if not self.demo:
            self.notice.setText('TELEMETRY STALE — values expire after 3 seconds' if stale else 'LIVE MONITOR  •  Airspeed may be estimated')
        self.clock.setText(time.strftime('%H:%M:%S'))

    def closeEvent(self, event):
        if self.gps.map_view.dialog:
            self.gps.map_view.dialog.reject()
        self.timer.stop()
        self.demo_timer.stop()
        for worker in self.workers:
            worker.requestInterruption()
        for worker in self.workers:
            worker.wait()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description='Lifeguard VTOL passive ground station')
    parser.add_argument('--demo',action='store_true',help='Synthetic preview; does not open UDP ports')
    parser.add_argument('--video-port',type=int,default=5600)
    parser.add_argument('--telemetry-port',type=int,default=14550)
    parser.add_argument('--system-id',type=int,help='Aircraft MAVLink system ID (default: select first autopilot heartbeat)')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = MainWindow(args)
    window.show()
    sys.exit(app.exec())
