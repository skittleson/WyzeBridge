import unittest
from unittest.mock import patch, MagicMock
import os
import shutil

from wyze_sdk.errors import WyzeApiError

from wyze_bridge.wyze_client_manager import WyzeClientManager  # Import the class from your module

class TestWyzeClientManager(unittest.TestCase):


    @patch('wyze_bridge.wyze_client_manager.WyzeClientManager.__init__')
    def setUp(self, mock_init):
        # Initialize the mock to avoid actual initialization
        mock_init.return_value = None
        self.manager = WyzeClientManager(
            email="test@example.com",
            password="password",
            key_id="key_id",
            api_key="api_key",
            client=MagicMock()
        )
        self.manager.client = MagicMock()
        # Set OUTPUT_DIR attribute for testing purposes
        self.manager.OUTPUT_DIR = 'test_output_dir'
        if os.path.exists(self.manager.OUTPUT_DIR):
            shutil.rmtree(self.manager.OUTPUT_DIR)

    @patch('requests.get')
    def test_download_image_success(self, mock_get):
        # Mock a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'test content'
        mock_get.return_value = mock_response

        file_path = os.path.join(self.manager.OUTPUT_DIR, 'test_image.jpg')
        self.manager.download('http://example.com/image.jpg', file_path)

        # Check that the file was created and contains the expected data
        with open(file_path, 'rb') as f:
            content = f.read()
        self.assertEqual(content, b'test content')

    @patch('requests.get')
    def test_download_image_failure(self, mock_get):
        # Mock a failed response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        file_path = os.path.join(self.manager.OUTPUT_DIR, 'test_image.jpg')
        self.manager.download('http://example.com/image.jpg', file_path)

        # Check that the file was not created
        self.assertFalse(os.path.exists(file_path))

    def test_get_event_file_not_found(self):
        event_id = 'non_existent_event'
        event_data = self.manager.get_event(event_id)
        self.assertEqual(event_data, b'')

    def test_update_lock_success(self):
        lock_id = "12345"
        lock_action = True
        result = self.manager.update_lock(lock_id, lock_action)
        self.assertTrue(result)
        self.manager.client.locks.lock.assert_called_once_with(lock_id)

    def test_update_lock_unlock_success(self):
        lock_id = "67890"
        lock_action = False
        result = self.manager.update_lock(lock_id, lock_action)
        self.assertTrue(result)
        self.manager.client.locks.unlock.assert_called_once_with(lock_id)

if __name__ == '__main__':
    unittest.main()