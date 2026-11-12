"""Detect None reference corruption, then stress the actual dashboard updates.
Run: QT_QPA_PLATFORM=offscreen .venv/bin/python tests/check_qt_runtime.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6 import __version__
from PySide6.QtWidgets import QApplication, QLabel
from ground_station.model import Telemetry
from ground_station.widgets import GPSWidget, TelemetryWidget

app = QApplication([])
label = QLabel('warmup')
for _ in range(20):
    label.setText('warmup')
before = sys.getrefcount(None)
for _ in range(100):
    label.setText('probe')
delta = sys.getrefcount(None) - before
assert delta > -10, f'Unsafe Qt binding: None refcount changed by {delta} in 100 calls'
gps, telemetry = GPSWidget(), TelemetryWidget()
data = Telemetry()
for i in range(10000):
    data.latitude = 44.2312 if i % 2 else None
    gps.set_telemetry(data)
    telemetry.set_telemetry(data)
    if i % 100 == 0:
        app.processEvents()
print(f'PASS: PySide6 {__version__}, None refcount delta {delta}; 10,000 dashboard updates')
