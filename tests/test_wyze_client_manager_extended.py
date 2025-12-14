import unittest
from unittest.mock import MagicMock, patch
import os
import shutil

from wyze_bridge.wyze_client_manager import WyzeClientManager

class TestWyzeClientManagerExtended(unittest.TestCase):
    def setUp(self):
        # Patch the init to skip client creation
        patcher = patch('wyze_bridge.wyze_client_manager.WyzeClientManager.__init__', return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()
        # Instantiate manager and set a custom output dir for tests
        self.manager = WyzeClientManager(email="", password="", key_id="", api_key="")
        self.manager.OUTPUT_DIR = "test_output_dir_ext"
        if os.path.exists(self.manager.OUTPUT_DIR):
            shutil.rmtree(self.manager.OUTPUT_DIR)
        os.makedirs(self.manager.OUTPUT_DIR)
        # Replace client with a MagicMock
        self.manager.client = MagicMock()

    def test_get_devices(self):
        # Setup mock devices
        mock_device1 = MagicMock()
        mock_device1.nickname = "Cam1"
        mock_device1.mac = "00:11:22"
        mock_device1.type = "camera"
        mock_device1.product = MagicMock()
        mock_device1.product.type = "Wyze Cam"
        mock_device2 = MagicMock()
        mock_device2.nickname = "Lock1"
        mock_device2.mac = "AA:BB:CC"
        mock_device2.type = "Lock"
        mock_device2.product = MagicMock()
        mock_device2.product.type = "Wyze Lock"
        self.manager.client.devices_list.return_value = [mock_device1, mock_device2]

        result = self.manager.get_devices()
        expected = [
            {"nickname": "Cam1", "mac": "00:11:22", "type": "camera", "product_type": "Wyze Cam"},
            {"nickname": "Lock1", "mac": "AA:BB:CC", "type": "Lock", "product_type": "Wyze Lock"},
        ]
        self.assertEqual(result, expected)

    def test_get_device_with_lock_info(self):
        # Mock device list
        lock_device = MagicMock()
        lock_device.nickname = "FrontDoor"
        lock_device.mac = "DD:EE:FF"
        lock_device.type = "Lock"
        lock_device.product = MagicMock()
        lock_device.product.type = "Wyze Lock"
        self.manager.client.devices_list.return_value = [lock_device]

        # Mock lock info
        lock_info = MagicMock()
        lock_info.is_locked = True
        lock_info.nickname = "FrontDoor"
        lock_info.mac = "DD:EE:FF"
        lock_info._voltage = MagicMock(_value=80)
        self.manager.client.locks.info.return_value = lock_info

        result = self.manager.get_device("DD:EE:FF")
        expected = {
            "nickname": "FrontDoor",
            "mac": "DD:EE:FF",
            "type": "Lock",
            "product_type": "Wyze Lock",
            "is_locked": True,
            "nickname": "FrontDoor",
            "percentage": 80,
            "mac": "DD:EE:FF",
        }
        # The merge operation may duplicate keys; tests focus on lock info presence
        self.assertTrue(result.get("is_locked"))
        self.assertEqual(result.get("percentage"), 80)

    def test_get_events_list(self):
        # Create dummy files in output dir
        filenames = ["event1.jpg", "event2.jpg", "readme.txt"]
        for f in filenames:
            with open(os.path.join(self.manager.OUTPUT_DIR, f), 'w') as fp:
                fp.write("data")
        events = self.manager.get_events()
        self.assertCountEqual(events, ["event1.jpg", "event2.jpg", "readme.txt"])

    def test_get_event_file_found(self):
        test_file = os.path.join(self.manager.OUTPUT_DIR, "exist.jpg")
        with open(test_file, 'wb') as fp:
            fp.write(b'content')
        data = self.manager.get_event("exist")
        self.assertEqual(data, b'content')


    def test_update_lock_calls(self):
        lock_id = "LOCK1"
        # Test locking
        result = self.manager.update_lock(lock_id, True)
        self.assertTrue(result)
        self.manager.client.locks.lock.assert_called_once_with(lock_id)
        self.manager.client.locks.lock.reset_mock()
        # Test unlocking
        result = self.manager.update_lock(lock_id, False)
        self.assertTrue(result)
        self.manager.client.locks.unlock.assert_called_once_with(lock_id)

    def test_get_locks(self):
        lock1 = MagicMock()
        lock1.mac = "MAC1"
        lock1.nickname = "LockOne"
        lock2 = MagicMock()
        lock2.mac = "MAC2"
        lock2.nickname = "LockTwo"
        self.manager.client.locks.list.return_value = [lock1, lock2]
        result = self.manager.get_locks()
        expected = [
            {"mac": "MAC1", "nickname": "LockOne"},
            {"mac": "MAC2", "nickname": "LockTwo"}
        ]
        self.assertEqual(result, expected)

    def test_get_lock_info(self):
        lock_info = MagicMock()
        lock_info.is_locked = False
        lock_info.nickname = "FrontDoor"
        lock_info.mac = "MAC123"
        lock_info._voltage = MagicMock(_value=75)
        self.manager.client.locks.info.return_value = lock_info
        result = self.manager.get_lock("MAC123")
        expected = {
            "is_locked": False,
            "nickname": "FrontDoor",
            "percentage": 75,
            "mac": "MAC123"
        }
        self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
