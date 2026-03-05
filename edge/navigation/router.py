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
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_OSRM_PUBLIC = "https://router.project-osrm.org"


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

    def __init__(self, osrm_url: str = _OSRM_PUBLIC):
        self._url = osrm_url.rstrip("/")

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
        coords = f"{start_lon},{start_lat};{dest_lon},{dest_lat}"
        url = (
            f"{self._url}/route/v1/driving/{coords}"
            "?overview=full&geometries=polyline&steps=false"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Seen-It-First-Edge/1.0"},
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise RouterError(f"OSRM HTTP {exc.code}") from exc
        except Exception as exc:
            raise RouterError(f"OSRM request failed: {exc}") from exc

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
