"""Offline map behavior checks; never requests public map tiles."""
import argparse
import math
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from ground_station.map_widget import MapCanvas, world_pixel
from ground_station.model import Telemetry
from ground_station.app import MainWindow

app = QApplication([])
assert world_pixel(0,0,2) == (512,512)
assert all(math.isfinite(x) for x in world_pixel(90,180,19))
with patch.object(MapCanvas,'load_visible'):
    window = MainWindow(argparse.Namespace(demo=True))
    window.show()
    view = window.gps.map_view
    # Discard the initial synthetic demo fix to check a session before its first fix.
    view.map.position = None
    view.map.center = (20.0,0.0)
    view.map.zoom = 2
    view.set_telemetry(Telemetry(latitude=0,longitude=0,fix='No fix'))
    assert view.map.position is None
    assert view.map.visible()  # World map is available before the first fix.
    view.set_telemetry(Telemetry(latitude=44.2312,longitude=-76.486,fix='No fix'))
    assert view.map.position == (44.2312,-76.486)
    assert view.map.center == (44.2312,-76.486)
    assert view.map.zoom == 15
    assert not view.map.position_current
    assert view.map.position_reported
    view.set_telemetry(Telemetry(latitude=0,longitude=0,fix='3D'))
    assert view.map.position == (0,0)
    assert view.map.position_current
    view.map.change_zoom(1)
    assert view.map.zoom == 16
    for _ in range(30):
        view.map.change_zoom(1)
    assert view.map.zoom == 19
    view.map.follow = False
    view.set_telemetry(Telemetry(latitude=44,longitude=-76,fix='3D'))
    assert view.map.center == (0,0)
    view.recenter()
    assert view.map.center == (44,-76)
    view.set_telemetry(Telemetry(latitude=0,longitude=0,fix='No fix'))
    assert view.map.position == (44,-76)
    assert not view.map.position_current
    assert view.map.center == (44,-76)
    view.set_telemetry(Telemetry())
    assert view.map.position == (44,-76)
    assert not view.map.position_current
    view.set_telemetry(Telemetry(latitude=45,longitude=-77,fix='3D'))
    assert view.map.position == (45,-77)
    assert view.map.position_current
    view.fullscreen()
    app.processEvents()
    assert view.dialog is not None
    view.fullscreen()
    app.processEvents()
    assert view.dialog is None
    assert view.home_layout.indexOf(view) >= 0
    view.fullscreen()
    window.close()
    assert view.dialog is None
print('PASS: projection, zero coordinates, fix gating, zoom limits, follow, fullscreen and shutdown')
