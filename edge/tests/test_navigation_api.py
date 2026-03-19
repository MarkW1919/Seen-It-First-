import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from edge.api.navigation import (
    OperatorProfile,
    StartNavRequest,
    get_operator_profile,
    get_recent_events,
    get_runtime_status,
    start_navigation,
    stop_navigation,
    update_operator_profile,
)


class NavigationApiTests(unittest.TestCase):
    def setUp(self):
        self.nav = SimpleNamespace(
            arrival_detector=Mock(),
            scheduler=SimpleNamespace(
                activate=Mock(),
                deactivate=Mock(),
                camera_manager=None,
                is_active=True,
            ),
            gps_state=Mock(),
            ws_manager=SimpleNamespace(client_count=2),
            current_pos={"lat": 35.5, "lon": -97.5},
            event_publisher=Mock(),
            is_navigating=False,
            destination=None,
            current_route={"dummy": True},
        )
        self.nav.arrival_detector.has_arrived = False
        self.nav.arrival_detector.last_distance_m = None
        self.request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(nav=self.nav)))

    def test_start_navigation_rejects_radius_out_of_bounds(self):
        for bad_radius in (0.5, 1320.1):
            with self.assertRaises(ValidationError):
                StartNavRequest(dest_lat=1.0, dest_lon=2.0, display_name="x", radius_ft=bad_radius)

        self.nav.arrival_detector.set_radius.assert_not_called()
        self.nav.scheduler.deactivate.assert_not_called()

    def test_start_navigation_updates_state_and_stops_pipeline(self):
        response = start_navigation(
            StartNavRequest(dest_lat=42.0, dest_lon=-71.0, display_name="HQ", radius_ft=300.0),
            self.request,
        )

        self.nav.arrival_detector.set_radius.assert_called_once()
        self.nav.arrival_detector.set_destination.assert_called_once_with(42.0, -71.0)
        self.nav.scheduler.deactivate.assert_called_once()
        self.assertTrue(self.nav.is_navigating)
        self.assertEqual(self.nav.destination["display_name"], "HQ")
        self.assertEqual(response["status"], "navigating")

    def test_stop_navigation_clears_state_and_starts_pipeline(self):
        self.nav.is_navigating = True
        self.nav.destination = {"lat": 1.0, "lon": 2.0}
        self.nav.current_route = {"polyline": []}

        response = stop_navigation(self.request)

        self.nav.arrival_detector.clear.assert_called_once()
        self.nav.scheduler.activate.assert_called_once()
        self.assertFalse(self.nav.is_navigating)
        self.assertIsNone(self.nav.destination)
        self.assertIsNone(self.nav.current_route)
        self.assertEqual(response["status"], "stopped")

    def test_get_recent_events_uses_event_publisher_history(self):
        self.nav.event_publisher.recent_events.return_value = [{"event": "ALERT", "plate": "ABC123"}]

        response = get_recent_events(self.request, event_type="alert", limit=10)

        self.nav.event_publisher.recent_events.assert_called_once_with("ALERT", 10)
        self.assertEqual(response.total, 1)
        self.assertEqual(response.events[0]["plate"], "ABC123")

    def test_get_runtime_status_summarizes_camera_state(self):
        capture = SimpleNamespace(
            config=SimpleNamespace(name="Front Left"),
            stats={"measured_fps": 29.7, "queue_depth": 3, "last_frame_time": 90.0},
            is_running=True,
        )
        self.nav.scheduler.camera_manager = SimpleNamespace(cameras={"cam-front-left": capture})

        with patch("edge.api.navigation.time.monotonic", return_value=100.0):
            response = get_runtime_status(self.request)

        self.assertTrue(response.pipeline_active)
        self.assertEqual(response.ws_clients, 2)
        self.assertEqual(response.operator_gps, {"lat": 35.5, "lon": -97.5})
        self.assertEqual(len(response.cameras), 1)
        self.assertEqual(response.cameras[0].name, "Front Left")
        self.assertEqual(response.cameras[0].status, "Online")
        self.assertEqual(response.cameras[0].queue_depth, 3)
        self.assertEqual(response.cameras[0].last_frame_age_s, 10.0)

    def test_operator_profile_round_trip_uses_persisted_file(self):
        profile = OperatorProfile(
            hotlist_refresh_sec=30,
            arrival_distance_ft=500,
            show_traffic_overlays=True,
            ocr_confidence_threshold=0.85,
            max_tracked_vehicles=15,
            auto_checkin_on_arrival=True,
            silent_shift_mode=False,
            low_storage_warning=True,
        )

        with TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "operator_profile.json"
            with patch("edge.api.navigation.OPERATOR_PROFILE_PATH", profile_path):
                saved = update_operator_profile(profile)
                loaded = get_operator_profile()

        self.assertEqual(saved.arrival_distance_ft, 500)
        self.assertEqual(loaded.hotlist_refresh_sec, 30)
        self.assertEqual(loaded.max_tracked_vehicles, 15)


if __name__ == "__main__":
    unittest.main()
