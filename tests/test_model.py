import math
import unittest
from types import SimpleNamespace
from ground_station.model import TelemetryStore


def message(kind, **values):
    return SimpleNamespace(get_type=lambda: kind, **values)

class TelemetryTests(unittest.TestCase):
    def test_units_and_zero(self):
        store = TelemetryStore()
        store.update(message('ATTITUDE', roll=math.pi/2, pitch=0, yaw=-math.pi/2), now=10)
        store.update(message('GLOBAL_POSITION_INT', lat=442312000, lon=-764860000,
                             relative_alt=35200, vx=300, vy=400, hdg=24700), now=10)
        data = store.snapshot(10)
        self.assertAlmostEqual(data.roll,90)
        self.assertEqual(data.pitch,0)
        self.assertEqual(data.yaw,270)
        self.assertAlmostEqual(data.longitude,-76.486)
        self.assertEqual(data.altitude,35.2)
        self.assertEqual(data.groundspeed,5)
        self.assertEqual(data.heading,247)

    def test_unknowns_and_expiry(self):
        store = TelemetryStore()
        store.update(message('SYS_STATUS',voltage_battery=65535,current_battery=-1,battery_remaining=-1),now=10)
        self.assertIsNone(store.snapshot(10).current)
        self.assertIsNone(store.snapshot(10).voltage)
        store.update(message('SYS_STATUS',voltage_battery=24200,current_battery=0,battery_remaining=0),now=11)
        self.assertEqual(store.snapshot(11).current,0)
        self.assertEqual(store.snapshot(11).remaining,0)
        store.update(message('ATTITUDE',roll=0,pitch=0,yaw=0),now=14)
        self.assertIsNone(store.snapshot(14).voltage)
        self.assertEqual(store.snapshot(14).roll,0)

    def test_gps_status_transitions_and_expiry(self):
        store = TelemetryStore()
        self.assertIsNone(store.snapshot(10).gps_status)
        for fix, expected in [(0, 'No GPS detected'), (1, 'Searching for fix'),
                              (2, '2D position only'), (3, '3D fix acquired'),
                              (6, 'RTK fixed'), (99, 'Unknown fix status')]:
            store.update(message('GPS_RAW_INT', satellites_visible=10, fix_type=fix), now=10)
            self.assertEqual(store.snapshot(10).gps_status, expected)
        self.assertIsNone(store.snapshot(13).gps_status)

    def test_gps_and_heartbeat(self):
        store = TelemetryStore()
        store.update(message('GPS_RAW_INT',satellites_visible=255,fix_type=3),now=10)
        store.update(message('HEARTBEAT',base_mode=128),mode='QLOITER',now=10)
        self.assertIsNone(store.snapshot(10).satellites)
        self.assertEqual(store.snapshot(10).fix,'3D')
        self.assertEqual(store.snapshot(10).armed,'ARMED')
        self.assertEqual(store.snapshot(10).mode,'QLOITER')

if __name__ == '__main__':
    unittest.main()
