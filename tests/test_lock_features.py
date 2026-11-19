import datetime
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from wyze_bridge.wyze_client_manager import WyzeClientManager

LOCK_MAC = "YD.LO1.abc"
GATEWAY_MAC = "YD.GW1.def"


def make_lock_info(state_code=1, door_open=False, online=True, door_sensor=True):
    return SimpleNamespace(
        is_locked=state_code == 1,
        nickname="Front Door",
        mac=LOCK_MAC,
        lock_state=SimpleNamespace(value=state_code),
        is_open=door_open,
        is_online=online,
        door_sensor=door_sensor,
        firmware_version="1.0.0",
        voltage=SimpleNamespace(value=93),
        _voltage=SimpleNamespace(_value=93),
    )


def make_record(event_name, source_name, minutes_ago=1):
    when = datetime.datetime(
        2026, 11, 19, 9, 0, tzinfo=datetime.timezone.utc
    ) - datetime.timedelta(minutes=minutes_ago)
    return SimpleNamespace(
        type=SimpleNamespace(
            name=event_name, description=event_name.replace("_", " ").capitalize()
        ),
        time=when,
        details=SimpleNamespace(source=SimpleNamespace(description=source_name)),
    )


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class LockFeatureTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["WYZE_OUTPUT_DIR"] = self.tmp.name
        self.client = MagicMock()
        self.client.locks.info.return_value = make_lock_info()
        self.client.locks.get_records.return_value = [make_record("LOCKED", "App")]
        gateway = SimpleNamespace(mac=GATEWAY_MAC, type="GateWay")
        self.client.devices_list.return_value = [gateway]
        self.client.locks.gateways.info.return_value = SimpleNamespace(
            rssi=-61, is_online=True
        )
        self.clock = FakeClock()
        self.manager = WyzeClientManager(
            client=lambda **_: self.client, clock=self.clock
        )


class TestLockStatus(LockFeatureTestBase):
    def test_reports_live_state_names(self):
        for code, expected in [
            (1, "locked"),
            (2, "locking"),
            (3, "unlocked"),
            (4, "unlocking"),
        ]:
            self.client.locks.info.return_value = make_lock_info(state_code=code)
            self.manager.clear_cache()
            self.assertEqual(self.manager.get_lock_status(LOCK_MAC)["state"], expected)

    def test_jammed_when_latest_event_is_a_jam(self):
        self.client.locks.info.return_value = make_lock_info(state_code=3)
        self.client.locks.get_records.return_value = [make_record("JAMMED", "Auto")]
        self.assertEqual(self.manager.get_lock_status(LOCK_MAC)["state"], "jammed")

    def test_door_online_battery_firmware(self):
        self.client.locks.info.return_value = make_lock_info(
            door_open=True, online=False
        )
        status = self.manager.get_lock_status(LOCK_MAC)
        self.assertTrue(status["door_open"])
        self.assertFalse(status["online"])
        self.assertEqual(status["battery"], 93)
        self.assertEqual(status["firmware"], "1.0.0")

    def test_door_unknown_when_door_sensor_disabled(self):
        self.client.locks.info.return_value = make_lock_info(
            door_open=False, door_sensor=False
        )
        self.assertIsNone(self.manager.get_lock_status(LOCK_MAC)["door_open"])

    def test_last_event_has_type_time_and_source(self):
        status = self.manager.get_lock_status(LOCK_MAC)
        self.assertEqual(status["last_event"]["type"], "locked")
        self.assertEqual(status["last_event"]["source"], "App")
        self.assertEqual(status["last_event"]["time"], "2026-11-19T08:59:00+00:00")

    def test_gateway_signal_strength(self):
        status = self.manager.get_lock_status(LOCK_MAC)
        self.assertEqual(status["gateway_rssi"], -61)

    def test_gateway_failure_does_not_break_status(self):
        self.client.locks.gateways.info.side_effect = RuntimeError("sdk bug")
        status = self.manager.get_lock_status(LOCK_MAC)
        self.assertIsNone(status["gateway_rssi"])
        self.assertEqual(status["state"], "locked")

    def test_gateway_rssi_falls_back_to_device_list(self):
        self.client.locks.gateways.info.side_effect = RuntimeError("sdk bug")
        self.client.devices_list.return_value = [SimpleNamespace(mac=GATEWAY_MAC, type="GateWay", rssi=-70)]
        self.assertEqual(self.manager.get_lock_status(LOCK_MAC)["gateway_rssi"], -70)


class TestLockEvents(LockFeatureTestBase):
    def test_lists_recent_events(self):
        self.client.locks.get_records.return_value = [
            make_record("UNLOCKED", "Keypad", 1),
            make_record("OPEN_TOO_LONG", "Auto", 5),
        ]
        events = self.manager.get_lock_events(LOCK_MAC, limit=2)
        self.assertEqual([e["type"] for e in events], ["unlocked", "open_too_long"])
        self.assertEqual(events[0]["source"], "Keypad")
        self.assertEqual(self.client.locks.get_records.call_args.kwargs["limit"], 2)

    def test_history_window_starts_in_the_past(self):
        # Wyze's `begin` (the SDK's `since`) is the oldest time returned, not the newest.
        self.manager.get_lock_events(LOCK_MAC, limit=1)
        since = self.client.locks.get_records.call_args.kwargs["since"]
        self.assertLess(since, datetime.datetime.now() - datetime.timedelta(days=1))


class TestLockCache(LockFeatureTestBase):
    def test_repeat_reads_within_ttl_reuse_wyze_answer(self):
        self.manager.get_lock_status(LOCK_MAC)
        self.clock.now += 5
        self.manager.get_lock_status(LOCK_MAC)
        self.assertEqual(self.client.locks.info.call_count, 1)

    def test_reads_after_ttl_ask_wyze_again(self):
        self.manager.get_lock_status(LOCK_MAC)
        self.clock.now += 60
        self.manager.get_lock_status(LOCK_MAC)
        self.assertEqual(self.client.locks.info.call_count, 2)

    def test_lock_command_clears_cache(self):
        self.manager.get_lock_status(LOCK_MAC)
        self.manager.update_lock(LOCK_MAC, True)
        self.manager.get_lock_status(LOCK_MAC)
        self.assertEqual(self.client.locks.info.call_count, 2)


class TestLockApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ["WYZE_EMAIL", "WYZE_PASSWORD", "WYZE_KEY_ID", "WYZE_API_KEY"]:
            os.environ[name] = "test"
        os.environ["WYZE_OUTPUT_DIR"] = tempfile.mkdtemp()
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "wyze_bridge"))
        import api

        cls.api = api

    def setUp(self):
        self.manager = MagicMock()
        self.api.manager = self.manager
        self.http = TestClient(self.api.app)

    def test_get_lock_status(self):
        self.manager.get_lock_status.return_value = {"state": "locked"}
        response = self.http.get(f"/locks/{LOCK_MAC}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"state": "locked"})

    def test_get_lock_status_unknown_lock(self):
        self.manager.get_lock_status.return_value = None
        self.assertEqual(self.http.get(f"/locks/{LOCK_MAC}").status_code, 404)

    def test_get_lock_events(self):
        self.manager.get_lock_events.return_value = [{"type": "locked"}]
        response = self.http.get(f"/locks/{LOCK_MAC}/events?limit=3")
        self.assertEqual(response.json(), {"events": [{"type": "locked"}]})
        self.manager.get_lock_events.assert_called_once_with(LOCK_MAC, limit=3)

    def test_failed_lock_command_is_an_error(self):
        self.manager.update_lock.return_value = False
        response = self.http.put(f"/locks/{LOCK_MAC}?lock_action=true")
        self.assertEqual(response.status_code, 502)

    def test_lock_action_in_json_body(self):
        self.manager.update_lock.return_value = True
        response = self.http.put(f"/locks/{LOCK_MAC}", json={"lock_action": False})
        self.assertEqual(response.status_code, 200)
        self.manager.update_lock.assert_called_once_with(LOCK_MAC, False)

    def test_lock_action_query_param_still_works(self):
        self.manager.update_lock.return_value = True
        self.http.put(f"/locks/{LOCK_MAC}?lock_action=false")
        self.manager.update_lock.assert_called_once_with(LOCK_MAC, False)


if __name__ == "__main__":
    unittest.main()
