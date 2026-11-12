"""Run with QT_QPA_PLATFORM=offscreen .venv/bin/python tests/smoke_gui.py."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from ground_station.app import MainWindow, STYLE

app = QApplication([])
app.setStyleSheet(STYLE)
window = MainWindow(argparse.Namespace(demo=True))
window.show()

def verify():
    assert window.video.frame is not None
    assert window.data.latitude == 44.2312
    window.resize(1000,700)
    app.processEvents()
    window.grab().save('/tmp/lifeguard-demo.png')
    window.close()
    live = MainWindow(argparse.Namespace(demo=False, video_port=15600, telemetry_port=15550, system_id=None))
    live.show()
    QTimer.singleShot(1500, lambda: finish(live))

def finish(live):
    live.close()
    print('PASS: demo render, resize, live receiver startup, and clean shutdown')
    app.quit()

app.setQuitOnLastWindowClosed(False)
QTimer.singleShot(500,verify)
app.exec()
