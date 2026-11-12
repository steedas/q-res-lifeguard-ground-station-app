"""Native Qt slippy map. Only visible OSM tiles are requested asynchronously."""
import math
import hashlib
import os
import time
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QUrl, QStandardPaths, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDialog


def world_pixel(latitude, longitude, zoom):
    latitude = max(-85.05112878, min(85.05112878, latitude))
    size = 256 * 2 ** zoom
    return ((longitude + 180) / 360 * size,
            (1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * size)


class MapCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(200, 150)
        self.zoom = 2
        self.center = (20.0, 0.0)
        self.position = None
        self.position_current = False
        self.position_reported = False
        self.follow = True
        self.drag = None
        self.tiles = {}
        self.pending = set()
        self.failed = {}
        self.network = QNetworkAccessManager(self)
        self.cache = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)) / 'map-tiles'
        self.template = os.environ.get('LIFEGUARD_TILE_URL', 'https://tile.openstreetmap.org/{z}/{x}/{y}.png')
        self.cache = self.cache / hashlib.sha256(self.template.encode()).hexdigest()[:12]
        self.offline = False
        self.network_error = ""
        self.tile_timer = QTimer(self)
        self.tile_timer.setSingleShot(True)
        self.tile_timer.timeout.connect(self.load_visible)

    def set_position(self, latitude, longitude, valid, reported=False):
        self.position_current = valid
        self.position_reported = reported
        if valid or reported:
            if self.position is None and self.zoom == 2:
                self.zoom = 15
            self.position = (latitude, longitude)
        if self.position and (self.follow or self.center is None):
            self.center = self.position
        self.update()
        self.tile_timer.start(150) if not self.tile_timer.isActive() else None

    def change_zoom(self, step):
        self.zoom = max(2, min(19, self.zoom + step))
        self.update()
        self.tile_timer.start(150)

    def visible(self):
        if self.center is None:
            return []
        cx, cy = world_pixel(*self.center, self.zoom)
        left, top = cx - self.width()/2, cy - self.height()/2
        count = 2 ** self.zoom
        return [((self.zoom, x % count, y), x*256-left, y*256-top)
                for x in range(math.floor(left/256), math.floor((left+self.width())/256)+1)
                for y in range(max(0, math.floor(top/256)), min(count-1, math.floor((top+self.height())/256))+1)]

    def load_visible(self):
        if not self.isVisible():
            return
        for key, _, _ in self.visible():
            if key in self.tiles or key in self.pending or time.monotonic()-self.failed.get(key, -math.inf) < 30:
                continue
            path = self.cache / ('%s_%s_%s.png' % key)
            # Seven-day local retention satisfies the tile provider's minimum cache policy.
            try:
                if time.time() - path.stat().st_mtime < 7*86400:
                    pixmap = QPixmap(str(path))
                    if not pixmap.isNull():
                        self.tiles[key] = pixmap
                        continue
            except OSError:
                pass
            if len(self.pending) >= 6:
                break
            request = QNetworkRequest(QUrl(self.template.format(z=key[0], x=key[1], y=key[2])))
            request.setRawHeader(b'User-Agent', b'LifeguardVTOLGroundStation/0.1')
            request.setTransferTimeout(10000)
            reply = self.network.get(request)
            self.pending.add(key)
            reply.finished.connect(lambda k=key, p=path, r=reply: self.tile_received(k,p,r))
        self.update()

    def tile_received(self, key, path, reply):
        self.pending.discard(key)
        pixmap = QPixmap()
        data = reply.readAll()
        if reply.error() == reply.NetworkError.NoError and pixmap.loadFromData(data):
            self.tiles[key] = pixmap
            self.offline = False
            self.network_error = ""
            try:
                self.cache.mkdir(parents=True, exist_ok=True)
                path.write_bytes(bytes(data))
            except OSError:
                pass
        else:
            self.failed[key] = time.monotonic()
            self.offline = True
            self.network_error = reply.errorString() if reply.error() != reply.NetworkError.NoError else "Invalid map tile response"
            self.setToolTip(self.network_error)
        reply.deleteLater()
        # Bound image memory; the disk cache preserves previously viewed tiles.
        visible = {k for k, _, _ in self.visible()}
        if len(self.tiles) > 128:
            self.tiles = {k:v for k,v in self.tiles.items() if k in visible}
        self.update()
        self.tile_timer.start(150)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#16232e'))
        for key, x, y in self.visible():
            if key in self.tiles:
                painter.drawPixmap(QPointF(x,y),self.tiles[key])
            else:
                painter.setPen(QPen(QColor('#263c4d'),1))
                painter.drawRect(int(x),int(y),256,256)
        if self.center and self.position:
            cx, cy = world_pixel(*self.center,self.zoom)
            px, py = world_pixel(*self.position,self.zoom)
            span = 256 * 2**self.zoom
            dx = (px-cx+span/2) % span-span/2
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor('#ffffff'),3))
            painter.setBrush(QColor('#e34e46' if self.position_current else '#efc66a'))
            painter.drawEllipse(QPointF(self.width()/2+dx,self.height()/2+py-cy),8,8)
        messages = []
        if not self.position:
            messages.append('Waiting for valid GPS position')
        elif not self.position_current:
            messages.append('REPORTED POSITION — GPS fix unconfirmed' if self.position_reported
                            else 'LAST KNOWN POSITION — GPS fix unavailable')
        if self.offline:
            messages.append('Map unavailable — ' + self.network_error)
        if messages:
            painter.fillRect(0, 0, self.width(), 26 * len(messages), QColor('#10171f'))
            painter.setPen(QColor('#efc66a'))
            for row, message in enumerate(messages):
                painter.drawText(8, 19 + row * 26, message)

    def resizeEvent(self,event):
        self.tile_timer.start(150)

    def showEvent(self,event):
        self.tile_timer.start(150)

    def wheelEvent(self,event):
        self.change_zoom(1 if event.angleDelta().y() > 0 else -1)
        event.accept()

    def mousePressEvent(self,event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag = event.position()

    def mouseMoveEvent(self,event):
        if self.drag is not None and self.center:
            self.follow = False
            x,y = world_pixel(*self.center,self.zoom)
            delta = event.position()-self.drag
            self.drag = event.position()
            size = 256 * 2**self.zoom
            x, y = (x-delta.x()) % size, max(0,min(size,y-delta.y()))
            self.center = (math.degrees(math.atan(math.sinh(math.pi*(1-2*y/size)))), x/size*360-180)
            self.update()
            self.tile_timer.start(150)

    def mouseReleaseEvent(self,event):
        self.drag = None


class MapWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.map = MapCanvas()
        self.dialog = None
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(0,0,0,0)
        controls = QHBoxLayout()
        for text,callback in [('+',lambda:self.map.change_zoom(1)),('−',lambda:self.map.change_zoom(-1)),
                              ('Follow aircraft',self.recenter),('Fullscreen / return',self.fullscreen)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            controls.addWidget(button)
            if text == 'Follow aircraft':
                self.follow_button = button
        self.layout_box.addLayout(controls)
        self.layout_box.addWidget(self.map,1)
        attribution = QLabel('<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>')
        attribution.setStyleSheet('color: #aebdca')
        attribution.setOpenExternalLinks(True)
        self.layout_box.addWidget(attribution)
        self.hint = QLabel('Drag to pan · Scroll or +/− to zoom')
        self.hint.setObjectName('muted')
        self.layout_box.addWidget(self.hint)

    def recenter(self):
        self.map.follow = True
        if self.map.position:
            self.map.center = self.map.position
            self.map.update()
            self.map.tile_timer.start(150)

    def fullscreen(self):
        if self.dialog:
            self.dialog.reject()
            return
        self.dialog = QDialog(self.window())
        self.dialog.setWindowTitle('Aircraft map — Esc to return')
        layout = QVBoxLayout(self.dialog)
        layout.addWidget(self)
        self.dialog.finished.connect(self.restore)
        self.dialog.showFullScreen()

    def restore(self, result=0):
        dialog, self.dialog = self.dialog, None
        self.home_layout.addWidget(self)
        if dialog:
            dialog.deleteLater()

    def set_telemetry(self,data):
        lat,lon = data.latitude,data.longitude
        coordinates_available = (lat is not None and lon is not None
                                 and math.isfinite(lat) and math.isfinite(lon)
                                 and -90 <= lat <= 90 and -180 <= lon <= 180)
        valid = coordinates_available and data.fix in ('2D','3D','DGPS','RTK float','RTK fixed','Static','PPP')
        # GLOBAL_POSITION_INT may contain an autopilot estimate/retained position
        # before GPS_RAW_INT reports a fix. Show it, clearly marked unconfirmed.
        # The all-zero no-fix placeholder must not move the map to Null Island.
        reported = coordinates_available and not valid and (lat != 0 or lon != 0)
        self.map.set_position(lat,lon,valid,reported)
        self.follow_button.setText('Following aircraft' if self.map.follow else 'Follow aircraft')
