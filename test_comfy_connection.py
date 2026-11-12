import unittest
from unittest.mock import Mock, patch

import requests
from comfyui_art_v9 import check_connection, base_url


class ComfyConnectionTests(unittest.TestCase):
    def test_server_online(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {"system": {"comfyui_version": "1"}, "devices": [{"name": "GPU"}]}
        response.raise_for_status.return_value = None
        session.get.return_value = response
        with patch.dict("os.environ", {"COMFYUI_URL": "http://127.0.0.1:8188"}):
            result = check_connection(session=session)
        self.assertEqual(len(result["devices"]), 1)
        session.get.assert_called_once_with("http://127.0.0.1:8188/system_stats", timeout=5)

    def test_connection_refused_shows_actionable_message(self):
        session = Mock()
        session.get.side_effect = requests.ConnectionError("Connection refused")
        with patch.dict("os.environ", {"COMFYUI_URL": "http://127.0.0.1:8188"}):
            with self.assertRaisesRegex(RuntimeError, "COMFYUI_OFFLINE.*Termux"):
                check_connection(session=session)

    def test_external_comfyui_url_rejected(self):
        with patch.dict("os.environ", {"COMFYUI_URL": "http://0.0.0.0:8188"}):
            with self.assertRaises(ValueError):
                base_url()


if __name__ == "__main__":
    unittest.main()
