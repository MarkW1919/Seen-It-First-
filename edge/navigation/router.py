"""
OSRM routing: (start_lat, start_lon, dest_lat, dest_lon) → route.

Uses the public OSRM demo server by default.  For production, point
osrm_url at a self-hosted OSRM instance.

Decodes OSRM's Encoded Polyline Algorithm (precision 5) into a list
of [lat, lon] coordinate pairs suitable for Leaflet.

OSRM route endpoint:
    GET /route/v1/driving/{lon},{lat};{lon},{lat}
         ?overview=full&geometries=polyline&steps=false
"""

import json
import logging
import math
import urllib.error
import urllib.request
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_OSRM_PUBLIC = "https://router.project-osrm.org"
_DEFAULT_USER_AGENT = "Seen-It-First-Edge/1.0 (edge-navigation; ops@example.local)"


@dataclass
class RouteResult:
    """Driving route between two points."""
    polyline: list[list[float]]   # [[lat, lon], ...]
    distance_m: float
    duration_s: float
    eta_iso: str                   # ISO-8601 arrival time


class RouterError(Exception):
    """Raised when routing fails."""


class Router:
    """
    OSRM driving route calculator.

    Args:
        osrm_url: Base URL of OSRM instance.
    """

    def __init__(
        self,
        osrm_url: str = _OSRM_PUBLIC,
        timeout_sec: float = 10.0,
        max_retries: int = 3,
        backoff_base_sec: float = 0.75,
        user_agent: str = _DEFAULT_USER_AGENT,
        min_request_interval_sec: float = 1.0,
    ):
        self._url = osrm_url.rstrip("/")
        self._timeout_sec = timeout_sec
        self._max_retries = max(1, max_retries)
        self._backoff_base_sec = max(0.1, backoff_base_sec)
        self._user_agent = user_agent
        self._min_request_interval_sec = max(0.0, min_request_interval_sec)
        self._last_request_at: float = 0.0

    def get_route(
        self,
        start_lat: float, start_lon: float,
        dest_lat: float,  dest_lon: float,
    ) -> RouteResult:
        """
        Compute a driving route between two GPS points.

        Args:
            start_lat / start_lon: Current position.
            dest_lat  / dest_lon : Destination position.

        Returns:
            RouteResult with polyline (Leaflet-ready), distance, duration, ETA.

        Raises:
            RouterError: On OSRM errors or no route found.
        """
        if not self._url:
            raise RouterError("Routing disabled by navigation mode/configuration")

        coords = f"{start_lon},{start_lat};{dest_lon},{dest_lat}"
        url = (
            f"{self._url}/route/v1/driving/{coords}"
            "?overview=full&geometries=polyline&steps=false"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self._user_agent},
        )

        data = None
        for attempt in range(1, self._max_retries + 1):
            self._wait_for_rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=self._timeout_sec) as resp:
                    data = json.loads(resp.read().decode())
                break
            except urllib.error.HTTPError as exc:
                retryable = exc.code in {429, 500, 502, 503, 504}
                if retryable and attempt < self._max_retries:
                    self._sleep_backoff(attempt, reason=f"HTTP {exc.code}")
                    continue
                raise RouterError(f"OSRM HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt, reason=f"network error: {exc.reason}")
                    continue
                raise RouterError(f"OSRM request failed: {exc}") from exc
            except TimeoutError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt, reason="timeout")
                    continue
                raise RouterError(f"OSRM timeout after {self._max_retries} attempts") from exc
            except Exception as exc:
                raise RouterError(f"OSRM request failed: {exc}") from exc
            finally:
                self._last_request_at = time.monotonic()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise RouterError(f"OSRM returned: {data.get('code', 'unknown')}")

        route = data["routes"][0]
        distance_m = float(route["distance"])
        duration_s = float(route["duration"])
        eta = (
            datetime.now(tz=timezone.utc) + timedelta(seconds=duration_s)
        ).isoformat()

        polyline = self._decode_polyline(route["geometry"])

        return RouteResult(
            polyline=polyline,
            distance_m=distance_m,
            duration_s=duration_s,
            eta_iso=eta,
        )



    def _sleep_backoff(self, attempt: int, reason: str):
        delay = self._backoff_base_sec * (2 ** (attempt - 1))
        jitter = random.uniform(0.0, self._backoff_base_sec * 0.25)
        wait_for = delay + jitter
        logger.warning(
            "OSRM retry %d/%d in %.2fs (%s)",
            attempt,
            self._max_retries,
            wait_for,
            reason,
        )
        time.sleep(wait_for)

    def _wait_for_rate_limit(self):
        wait = self._min_request_interval_sec - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)

    # ------------------------------------------------------------------
    # Polyline decoder (Google / OSRM Encoded Polyline Algorithm)
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_polyline(encoded: str) -> list[list[float]]:
        """
        Decode an encoded polyline string (precision 5) to [[lat, lon], ...].

        Reference: https://developers.google.com/maps/documentation/utilities/polylinealgorithm
        """
        points: list[list[float]] = []
        index = lat = lng = 0

        while index < len(encoded):
            # Decode latitude delta
            result, shift = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = -(result >> 1) if result & 1 else result >> 1
            lat += dlat

            # Decode longitude delta
            result, shift = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            dlng = -(result >> 1) if result & 1 else result >> 1
            lng += dlng

            points.append([lat / 1e5, lng / 1e5])

        return points
