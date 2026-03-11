import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from edge.navigation.geocoder import Geocoder, GeocoderError, GeocoderResult


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class GeocoderTests(unittest.TestCase):
    def test_geocode_cache_hit_and_miss(self):
        with tempfile.TemporaryDirectory() as td:
            cache_path = Path(td) / "cache.json"
            geocoder = Geocoder(cache_path=cache_path)

            with patch.object(geocoder, "_nominatim_request", return_value=GeocoderResult(1.0, 2.0, "A")) as req:
                first = geocoder.geocode("Address A")
                second = geocoder.geocode("Address A")

            self.assertEqual(first, second)
            self.assertEqual(req.call_count, 1, "Expected one miss followed by one cache hit")

    def test_rate_limit_wait_uses_monotonic_and_sleep(self):
        with tempfile.TemporaryDirectory() as td:
            geocoder = Geocoder(cache_path=Path(td) / "cache.json", rate_limit_delay=1.1)
            geocoder._last_request_at = 100.0

            with patch("edge.navigation.geocoder.time.monotonic", return_value=100.3), patch(
                "edge.navigation.geocoder.time.sleep"
            ) as sleep_mock:
                geocoder._wait_for_rate_limit()

            sleep_mock.assert_called_once()
            self.assertAlmostEqual(sleep_mock.call_args.args[0], 0.8, places=3)

    def test_nominatim_http_error_maps_to_geocoder_error(self):
        with tempfile.TemporaryDirectory() as td:
            geocoder = Geocoder(cache_path=Path(td) / "cache.json")

            import urllib.error

            http_error = urllib.error.HTTPError(
                url="https://example",
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=None,
            )

            with patch("edge.navigation.geocoder.urllib.request.urlopen", side_effect=http_error):
                with self.assertRaises(GeocoderError) as ctx:
                    geocoder._nominatim_request("Address B")

            self.assertIn("Nominatim HTTP 429", str(ctx.exception))

    def test_nominatim_empty_body_maps_to_geocoder_error(self):
        with tempfile.TemporaryDirectory() as td:
            geocoder = Geocoder(cache_path=Path(td) / "cache.json")

            with patch(
                "edge.navigation.geocoder.urllib.request.urlopen",
                return_value=_FakeResponse([]),
            ):
                with self.assertRaises(GeocoderError) as ctx:
                    geocoder._nominatim_request("Nowhere")

            self.assertIn("No results for address", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
