import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from edge.navigation.geocoder import Geocoder, GeocoderResult


class TestGeocoder(unittest.TestCase):
    def test_cache_hit_skips_network(self):
        with tempfile.TemporaryDirectory() as td:
            cache_path = Path(td) / "geocode_cache.json"
            key = "1600 amphitheatre parkway"
            cache_path.write_text(
                json.dumps(
                    {
                        key: {
                            "lat": 37.422,
                            "lon": -122.084,
                            "display_name": "Googleplex",
                            "cached_at": 9999999999.0,
                        }
                    }
                )
            )
            g = Geocoder(cache_path=cache_path)

            with patch.object(g, "_nominatim_request") as req:
                result = g.geocode("1600 Amphitheatre Parkway")

            self.assertEqual(result.display_name, "Googleplex")
            req.assert_not_called()

    def test_rate_limit_uses_monotonic_clock_after_request(self):
        with tempfile.TemporaryDirectory() as td:
            cache_path = Path(td) / "geocode_cache.json"
            g = Geocoder(cache_path=cache_path, rate_limit_delay=1.1)

            response = MagicMock()
            response.read.return_value = b'[{"lat":"1.0","lon":"2.0","display_name":"A"}]'
            cm = MagicMock()
            cm.__enter__.return_value = response
            cm.__exit__.return_value = False

            mono_values = iter([100.0, 100.2, 100.3, 100.3, 100.4])
            sleeps = []

            def fake_monotonic():
                return next(mono_values)

            def fake_sleep(v):
                sleeps.append(v)

            with patch("urllib.request.urlopen", return_value=cm):
                with patch("edge.navigation.geocoder.time.monotonic", side_effect=fake_monotonic):
                    with patch("edge.navigation.geocoder.time.sleep", side_effect=fake_sleep):
                        r1 = g.geocode("Address A")
                        self.assertIsInstance(r1, GeocoderResult)
                        r2 = g.geocode("Address B")
                        self.assertIsInstance(r2, GeocoderResult)

            self.assertEqual(len(sleeps), 1)
            self.assertLessEqual(sleeps[0], 1.1)
            self.assertGreaterEqual(sleeps[0], 0.0)


if __name__ == "__main__":
    unittest.main()
