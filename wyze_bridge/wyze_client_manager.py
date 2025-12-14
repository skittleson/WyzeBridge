# Simplified WyzeClientManager for tests and Home Assistant integration.
# The original module depended on external `wyze_sdk` which may not be
# available in the execution environment.  To keep the library
# importable without the SDK, we lazily import it and fall back to a stub
# when it cannot be loaded.

import os
import requests
from typing import Any, List, Dict, Optional

# Try to import the real SDK; fallback to a minimal stub.
try:
    from wyze_sdk import Client
    from wyze_sdk.errors import WyzeApiError
except Exception:  # pragma: no cover - SDK optional
    Client = Any  # type: ignore
    WyzeApiError = Exception  # type: ignore


class WyzeClientManager:
    """Wrapper around a Wyze SDK client.

    The original project exposed a fairly large surface area.  Only the
    subset needed by the API and the tests is implemented.
    """

    # Default directory for event images.
    DEFAULT_OUTPUT_DIR = "../event_images"

    def __init__(
        self,
        email: str = "",
        password: str = "",
        key_id: str = "",
        api_key: str = "",
        client: Any = Client,
    ) -> None:
        # Store a client instance – the actual SDK may be a mock in tests.
        self.client = client(email=email, password=password, key_id=key_id, api_key=api_key)
        # Allow tests to override the output directory.
        self.OUTPUT_DIR = os.getenv("WYZE_OUTPUT_DIR", self.DEFAULT_OUTPUT_DIR)
        self.__ensure_dir_exists()

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def __ensure_dir_exists(self) -> None:
        if not os.path.isdir(self.OUTPUT_DIR):
            os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    def download(self, url: str, file_path: str) -> None:
        """Download ``url`` to ``file_path`` if it does not already exist."""
        self.__ensure_dir_exists()
        if os.path.exists(file_path):
            return  # Skip existing files.
        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(response.content)
        except Exception as e:  # pragma: no cover - network errors
            print(f"Failed to download {url}: {e}")

    # ------------------------------------------------------------------
    # Public API compatible with the original implementation
    # ------------------------------------------------------------------
    def get_event(self, event_file_id: str) -> bytes:
        file_path = os.path.join(self.OUTPUT_DIR, f"{event_file_id}.jpg")
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            return b""

    def get_events(self) -> List[str]:
        try:
            files = os.listdir(self.OUTPUT_DIR)
            return [f for f in files if os.path.isfile(os.path.join(self.OUTPUT_DIR, f))]
        except Exception as e:  # pragma: no cover - OS errors
            print(f"Error listing event files: {e}")
            return []

    def job_save_events(self) -> None:
        # The real SDK provides cameras and events.  For tests we simply
        # ignore the call – the test suite mocks this method.
        try:
            cameras = self.client.cameras.list()
            for camera in cameras:
                events = self.client.events.list(device_mac=camera.mac, limit=10)
                for event in events:
                    for file in event.files:
                        self.download(file.url, os.path.join(self.OUTPUT_DIR, f"{file.id}_{event.time}.jpg"))
        except WyzeApiError as e:  # pragma: no cover - API errors
            print(f"Wyze API error: {e}")

    def get_locks(self) -> List[Dict[str, Any]]:
        try:
            locks = self.client.locks.list()
            return [{"mac": lock.mac, "nickname": lock.nickname} for lock in locks]
        except Exception:  # pragma: no cover - error handling
            return []

    def get_lock(self, lock_id: str) -> Optional[Dict[str, Any]]:
        try:
            lock_info = self.client.locks.info(device_mac=lock_id)
            if lock_info is None:
                return None
            if lock_info and hasattr(lock_info, "_voltage"):
                """Return lock info dictionary with voltage percentage."""
                return {
                    "is_locked": lock_info.is_locked,
                    "nickname": lock_info.nickname,
                    "percentage": lock_info._voltage._value if lock_info._voltage else None,
                    "mac": lock_info.mac,
                }
            else:
                return {
                    "is_locked": lock_info.is_locked,
                    "nickname": lock_info.nickname,
                    "percentage": None,
                    "mac": lock_info.mac,
                }
        except Exception:  # pragma: no cover - API errors
            return None

    def update_lock(self, lock_id: str, lock_action: bool) -> bool:
        try:
            if lock_action:
                self.client.locks.lock(lock_id)
            else:
                self.client.locks.unlock(lock_id)
            return True
        except Exception:  # pragma: no cover - API errors
            return False

    def get_devices(self, filter_query=None, orderby=None, select=None):
        devices = self.client.devices_list()
        device_dicts = []
        for device in devices:
            device_info = {
                "nickname": device.nickname,
                "mac": device.mac,
                "type": device.type,
                "product_type": device.product.type,
            }
            device_dicts.append(device_info)

        if filter_query:
            for kv in [item.split("=", 1) for item in filter_query]:
                device_dicts = [d for d in device_dicts if d.get(kv[0]) == kv[1]]

        if select:
            device_dicts = [{k: d[k] for k in select if k in d} for d in device_dicts]

        if orderby:
            reverse = False
            if orderby.startswith("-"):
                orderby = orderby[1:]
                reverse = True
            device_dicts.sort(key=lambda x: x.get(orderby), reverse=reverse)

        return device_dicts

    def get_device(self, device_id: str):
        devices = self.client.devices_list()
        for device in devices:
            if device.mac == device_id:
                result = {
                    "nickname": device.nickname,
                    "mac": device.mac,
                    "type": device.type,
                    "product_type": device.product.type,
                }
                if result["type"] == "Lock":
                    lock = self.get_lock(device_id)
                    if lock:
                        result.update(lock)
                return result
        return None
