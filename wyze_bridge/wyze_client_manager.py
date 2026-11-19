# Simplified WyzeClientManager for tests and Home Assistant integration.
# The original module depended on external `wyze_sdk` which may not be
# available in the execution environment.  To keep the library
# importable without the SDK, we lazily import it and fall back to a stub
# when it cannot be loaded.

import datetime
import os
import time
from collections.abc import Callable
from typing import Any, ClassVar, Dict, List, Optional

import requests

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

    # Wyze rate-limits aggressively, so polling clients share one recent answer.
    LOCK_CACHE_SECONDS = float(os.getenv("WYZE_LOCK_CACHE_SECONDS", "20"))
    GATEWAY_CACHE_SECONDS = 300.0
    HISTORY_DAYS = 30

    LOCK_STATES: ClassVar[dict[int, str]] = {1: "locked", 2: "locking", 3: "unlocked", 4: "unlocking"}
    JAM_EVENTS: ClassVar[set[str]] = {"JAMMED", "TOTALLY_JAMMED"}

    def __init__(
        self,
        email: str = "",
        password: str = "",
        key_id: str = "",
        api_key: str = "",
        client: Any = Client,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # Store a client instance – the actual SDK may be a mock in tests.
        self.client = client(email=email, password=password, key_id=key_id, api_key=api_key)
        self._clock = clock
        self._cache: dict[str, Any] = {}
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
        except Exception as e:  # pragma: no cover - API errors
            print(f"Failed to {'lock' if lock_action else 'unlock'} {lock_id}: {e}")
            return False
        finally:
            self.clear_cache()

    # ------------------------------------------------------------------
    # Full lock status for Home Assistant
    # ------------------------------------------------------------------
    def clear_cache(self) -> None:
        self._cache = {}

    def _cached(self, key: str, ttl: float, fetch: Callable[[], Any]) -> Any:
        now = self._clock()
        hit = self._cache.get(key)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]
        value = fetch()
        self._cache[key] = (now, value)
        return value

    @staticmethod
    def _value(prop: Any) -> Any:
        return getattr(prop, "value", prop)

    @staticmethod
    def _event_to_dict(record: Any) -> dict[str, Any]:
        event_time = record.time
        if isinstance(event_time, datetime.datetime):
            if event_time.tzinfo is None:
                event_time = event_time.astimezone()
            event_time = event_time.isoformat()
        source = getattr(getattr(record, "details", None), "source", None)
        return {
            "type": record.type.name.lower() if hasattr(record.type, "name") else str(record.type),
            "description": getattr(record.type, "description", None),
            "time": event_time,
            "source": getattr(source, "description", None),
        }

    def _fetch_records(self, lock_id: str, limit: int) -> list[Any]:
        return list(
            self.client.locks.get_records(
                device_mac=lock_id,
                since=datetime.datetime.now() - datetime.timedelta(days=self.HISTORY_DAYS),
                limit=limit,
            )
        )

    def get_lock_events(self, lock_id: str, limit: int = 20) -> list[dict[str, Any]]:
        records = self._cached(
            f"events:{lock_id}:{limit}", self.LOCK_CACHE_SECONDS, lambda: self._fetch_records(lock_id, limit)
        )
        return [self._event_to_dict(r) for r in records]

    def _gateway_rssi(self) -> int | None:
        def fetch() -> int | None:
            try:
                gateways = [d for d in self.client.devices_list() if d.type == "GateWay"]
            except Exception as e:
                print(f"Could not list devices: {e}")
                return None
            if not gateways:
                return None
            try:
                return self._value(self.client.locks.gateways.info(device_mac=gateways[0].mac).rssi)
            except Exception as e:  # SDK gateway info is unreliable; the device list may carry rssi
                print(f"Could not read lock gateway: {e}")
                return self._value(getattr(gateways[0], "rssi", None))

        return self._cached("gateway_rssi", self.GATEWAY_CACHE_SECONDS, fetch)

    def get_lock_status(self, lock_id: str) -> dict[str, Any] | None:
        info = self._cached(
            f"info:{lock_id}", self.LOCK_CACHE_SECONDS, lambda: self.client.locks.info(device_mac=lock_id)
        )
        if info is None:
            return None
        try:
            events = self.get_lock_events(lock_id, limit=1)
        except Exception as e:  # history is optional, the lock state is not
            print(f"Could not read lock history: {e}")
            events = []
        last_event = events[0] if events else None

        state = self.LOCK_STATES.get(self._value(info.lock_state), "unknown")
        if last_event and last_event["type"].upper() in self.JAM_EVENTS:
            state = "jammed"

        return {
            "mac": info.mac,
            "nickname": info.nickname,
            "is_locked": info.is_locked,
            "state": state,
            "door_open": bool(info.is_open) if getattr(info, "door_sensor", True) else None,
            "online": bool(info.is_online),
            "battery": self._value(info.voltage),
            "firmware": info.firmware_version,
            "gateway_rssi": self._gateway_rssi(),
            "last_event": last_event,
        }

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
