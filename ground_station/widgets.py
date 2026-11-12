"""Reusable Qt instruments and aspect-preserving camera surface."""
from dataclasses import dataclass
from .map_widget import MapWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QPushButton

@dataclass(frozen=True)
class Detection:
    # Normalized source-image coordinates, associated with a VideoFrame timestamp.
    x: float
    y: float
    width: float
    height: float
    label: str

class VideoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.frame = None
        self.detections = []
        self.setMinimumSize(320, 180)

    def set_frame(self, frame):
        self.frame = frame
        self.detections = []
        self.update()

    def set_detections(self, timestamp, detections):
        if self.frame and timestamp == self.frame.timestamp:
            self.detections = detections
            self.update()

    def clear(self):
        if self.frame:
            self.frame = None
            self.detections = []
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#030608'))
        if not self.frame:
            painter.setPen(QColor('#8797a5'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'NO VIDEO SIGNAL')
            return
        image = self.frame.image
        size = image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRectF((self.width()-size.width())/2, (self.height()-size.height())/2, size.width(), size.height())
        painter.drawImage(target, image)
        painter.setPen(QPen(QColor('#58e1b5'), 2))
        for box in self.detections:
            rect = QRectF(target.x()+box.x*target.width(), target.y()+box.y*target.height(), box.width*target.width(), box.height*target.height())
            painter.drawRect(rect)
            painter.drawText(rect.topLeft(), box.label)


def formatted(value, unit='', precision=1):
    if value is None:
        return '--'
    return f'{value:.{precision}f}{(" " + unit) if unit else ""}' if isinstance(value, (int, float)) else str(value)

class TelemetryWidget(QFrame):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel('FLIGHT TELEMETRY')
        title.setObjectName('section')
        layout.addWidget(title)
        grid = QGridLayout()
        layout.addLayout(grid)
        self.values = {}
        groups = [
            [('roll','Roll','°'),('pitch','Pitch','°'),('yaw','Yaw','°'),('mode','Mode',''),('fix','GPS fix','')],
            [('altitude','Relative alt','m'),('groundspeed','Ground speed','m/s'),('airspeed','Reported airspeed*','m/s'),('vertical_speed','Climb','m/s'),('heading','Heading','°')],
            [('voltage','Battery','V'),('current','Current','A'),('remaining','Remaining','%'),('armed','Vehicle','')]]
        for column, group in enumerate(groups):
            for row, (key, label, unit) in enumerate(group):
                grid.addWidget(QLabel(label), row, column*2)
                value = QLabel('--')
                value.setObjectName('value')
                grid.addWidget(value, row, column*2+1)
                self.values[key] = (value, unit)
        note = QLabel('* Reported airspeed may be estimated; availability is not sensor verification.')
        note.setObjectName('muted')
        note.setWordWrap(True)
        layout.addWidget(note)

    def set_telemetry(self, data):
        for key, (label, unit) in self.values.items():
            label.setText(formatted(getattr(data, key), unit))

class GPSWidget(QFrame):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel('GPS / LOCATION')
        title.setObjectName('section')
        layout.addWidget(title)
        self.position_label = QLabel('Position: --')
        self.position_label.setWordWrap(True)
        layout.addWidget(self.position_label)
        self.summary_status = QLabel('No recent GPS data')
        layout.addWidget(self.summary_status)
        toggle = QPushButton('GPS details')
        toggle.setCheckable(True)
        layout.addWidget(toggle)
        details = QWidget()
        grid = QGridLayout(details)
        layout.addWidget(details)
        details.hide()
        toggle.toggled.connect(details.setVisible)
        self.values = {}
        for row, (key, name, unit, precision) in enumerate([
            ('latitude','Latitude','°',6),('longitude','Longitude','°',6),('altitude','Relative altitude','m',1),
            ('gps_status','GPS status','',0),('fix','GPS fix','',0),('satellites','Satellites','',0),('heading','Heading','°',1)]):
            grid.addWidget(QLabel(name),row,0)
            value = QLabel('--')
            value.setObjectName('value')
            grid.addWidget(value,row,1)
            self.values[key] = (value,unit,precision)
        self.map_view = MapWidget()
        self.map_view.home_layout = layout
        layout.addWidget(self.map_view, 1)

    def set_telemetry(self, data):
        for key, (label,unit,precision) in self.values.items():
            label.setText(formatted(getattr(data,key),unit,precision))
        self.map_view.set_telemetry(data)
        self.position_label.setText(f"Lat {formatted(data.latitude, '°', 6)}   Lon {formatted(data.longitude, '°', 6)}")
        status = self.values['gps_status'][0]
        if data.gps_status is None:
            status.setText('No recent GPS data')
        color = '#ef7c80' if data.gps_status == 'No GPS detected' else (
            '#65dcad' if data.fix in ('3D', 'DGPS', 'RTK float', 'RTK fixed', 'PPP')
            and data.gps_status is not None else '#efc66a')
        status.setStyleSheet(f'color: {color}')
        self.summary_status.setText(status.text())
        self.summary_status.setStyleSheet(f'color: {color}')
