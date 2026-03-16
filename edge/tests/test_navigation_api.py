import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from edge.api.navigation import StartNavRequest, start_navigation, stop_navigation


class NavigationApiTests(unittest.TestCase):
    def setUp(self):
        self.nav = SimpleNamespace(
            arrival_detector=Mock(),
            scheduler=Mock(),
            gps_state=Mock(),
            is_navigating=False,
            destination=None,
            current_route={"dummy": True},
        )
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


if __name__ == "__main__":
    unittest.main()
