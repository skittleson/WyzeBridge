import datetime
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from wyze_bridge.wyze_client_manager import WyzeClientManager

CAM_MAC = "D03F279F990F"


def make_event(event_id="e1", minutes_ago=2, tags=("PERSON",)):
    when = datetime.datetime(2026, 11, 19, 15, 0, tzinfo=datetime.timezone.utc) - datetime.timedelta(
        minutes=minutes_ago
    )
    return SimpleNamespace(
        id=event_id,
        mac=CAM_MAC,
        time=when,
        alarm_type=SimpleNamespace(name="MOTION", description="Motion"),
        tags=[SimpleNamespace(name=t, description=t.capitalize()) for t in tags],
    )


def make_camera(mac=CAM_MAC, online=True):
    return SimpleNamespace(
        type="Camera",
        mac=mac,
        nickname="Gate Cam",
        product=SimpleNamespace(model="WYZE_CAKP2JFUS"),
        is_online=online,
        firmware_version="4.36.11.8391",
        ip="192.168.4.50",
        rssi=-55,
        ssid="home",
        voltage=None,
    )


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class CameraTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["WYZE_OUTPUT_DIR"] = self.tmp.name
        self.client = MagicMock()
        plug = SimpleNamespace(type="Plug", mac="PLUG")
        self.client.devices_list.return_value = [make_camera(), plug]
        self.client.events.list.return_value = [make_event()]
        self.clock = FakeClock()
        self.manager = WyzeClientManager(client=lambda **_: self.client, clock=self.clock)


class TestCameraDetails(CameraTestBase):
    def test_lists_basic_details(self):
        cam = self.manager.get_cameras()[0]
        self.assertEqual(cam["mac"], CAM_MAC)
        self.assertEqual(cam["nickname"], "Gate Cam")
        self.assertEqual(cam["model"], "WYZE_CAKP2JFUS")
        self.assertTrue(cam["online"])
        self.assertEqual(cam["firmware"], "4.36.11.8391")
        self.assertEqual(cam["ip"], "192.168.4.50")
        self.assertEqual(cam["rssi"], -55)

    def test_includes_latest_event(self):
        event = self.manager.get_cameras()[0]["last_event"]
        self.assertEqual(event["id"], "e1")
        self.assertEqual(event["type"], "Motion")
        self.assertEqual(event["tags"], ["Person"])
        self.assertEqual(event["time"], "2026-11-19T14:58:00+00:00")

    def test_only_cameras_are_listed(self):
        self.assertEqual([c["mac"] for c in self.manager.get_cameras()], [CAM_MAC])

    def test_newest_event_wins(self):
        self.client.events.list.return_value = [make_event("new", minutes_ago=1), make_event("old", minutes_ago=30)]
        self.assertEqual(self.manager.get_cameras()[0]["last_event"]["id"], "new")

    def test_last_event_survives_when_it_leaves_the_recent_batch(self):
        self.manager.get_cameras()
        self.client.events.list.return_value = []
        self.clock.now += 120
        self.assertEqual(self.manager.get_cameras()[0]["last_event"]["id"], "e1")

    def test_quiet_camera_is_seeded_with_its_own_lookup(self):
        quiet = make_camera(mac="QUIET")
        self.client.devices_list.return_value = [make_camera(), quiet]
        seeded = make_event("q1", minutes_ago=600)
        seeded.mac = "QUIET"

        def events(**kwargs):
            return [seeded] if kwargs.get("device_ids") == ["QUIET"] else [make_event()]

        self.client.events.list.side_effect = events
        cams = {c["mac"]: c for c in self.manager.get_cameras()}
        self.assertEqual(cams["QUIET"]["last_event"]["id"], "q1")

    def test_at_most_one_seed_lookup_per_refresh(self):
        self.client.devices_list.return_value = [make_camera(mac=f"C{i}") for i in range(5)]
        self.client.events.list.return_value = []
        self.manager.get_cameras()
        self.assertEqual(self.client.events.list.call_count, 2)  # recent batch + one seed

    def test_epoch_millisecond_times_become_iso(self):
        event = make_event()
        event.time = 1795128746581
        self.client.events.list.return_value = [event]
        self.assertEqual(self.manager.get_cameras()[0]["last_event"]["time"], "2026-11-19T22:52:26.581000+00:00")

    def test_camera_without_events(self):
        self.client.events.list.return_value = []
        self.assertIsNone(self.manager.get_cameras()[0]["last_event"])

    def test_get_single_camera(self):
        self.assertEqual(self.manager.get_camera(CAM_MAC)["nickname"], "Gate Cam")
        self.assertIsNone(self.manager.get_camera("nope"))

    def test_camera_list_is_cached(self):
        self.manager.get_cameras()
        self.clock.now += 10
        self.manager.get_cameras()
        self.assertEqual(self.client.events.list.call_count, 1)
        self.clock.now += 120
        self.manager.get_cameras()
        self.assertEqual(self.client.events.list.call_count, 2)


class TestCameraEvents(CameraTestBase):
    def test_lists_events_for_one_camera(self):
        self.client.events.list.return_value = [make_event("a"), make_event("b", minutes_ago=9, tags=())]
        events = self.manager.get_camera_events(CAM_MAC, limit=5)
        self.assertEqual([e["id"] for e in events], ["a", "b"])
        self.assertEqual(events[1]["tags"], [])
        kwargs = self.client.events.list.call_args.kwargs
        self.assertEqual(kwargs["device_ids"], [CAM_MAC])
        self.assertEqual(kwargs["limit"], 5)

    def test_event_limit_capped_at_wyze_maximum(self):
        self.client.events.list.return_value = []
        self.manager.get_camera_events(CAM_MAC, limit=50)
        self.assertEqual(self.client.events.list.call_args.kwargs["limit"], 20)


class TestCameraApi(unittest.TestCase):
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

    def test_cameras_keyed_by_mac(self):
        self.manager.get_cameras.return_value = [{"mac": CAM_MAC, "last_event": None}]
        self.assertIn(CAM_MAC, self.http.get("/cameras").json()["by_mac"])

    def test_single_camera_404(self):
        self.manager.get_camera.return_value = None
        self.assertEqual(self.http.get("/cameras/nope").status_code, 404)

    def test_camera_events(self):
        self.manager.get_camera_events.return_value = [{"id": "a"}]
        self.assertEqual(self.http.get(f"/cameras/{CAM_MAC}/events?limit=3").json(), {"events": [{"id": "a"}]})
        self.manager.get_camera_events.assert_called_once_with(CAM_MAC, limit=3)


if __name__ == "__main__":
    unittest.main()
