import os
import unittest
from unittest.mock import patch
from ground_station.runtime import configure_desktop_environment


class RuntimeTests(unittest.TestCase):
    def test_snap_editor_paths_removed_and_host_paths_retained(self):
        with patch.dict(os.environ, {'SNAP_NAME': 'code',
            'GIO_MODULE_DIR': '/home/user/snap/code/common/.cache/gio-modules',
            'GTK_PATH': '/snap/code/current/gtk', 'GTK_MODULES': 'gail:atk-bridge:other',
            'LD_LIBRARY_PATH': '/opt/ros/lib:/snap/core20/current/lib'}, clear=True):
            configure_desktop_environment()
            self.assertNotIn('GIO_MODULE_DIR', os.environ)
            self.assertNotIn('GTK_PATH', os.environ)
            self.assertEqual(os.environ['GTK_MODULES'], 'other')
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/opt/ros/lib')

    def test_normal_environment_unchanged(self):
        with patch.dict(os.environ, {'GIO_MODULE_DIR': '/custom/modules'}, clear=True):
            configure_desktop_environment()
            self.assertEqual(dict(os.environ), {'GIO_MODULE_DIR': '/custom/modules'})
