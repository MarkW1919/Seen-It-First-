"""
Geocoder: address string → latitude / longitude.

Offline-first design — no network calls.

Two resolution strategies (in order):
  1. Coordinate string:  "37.7749,-122.4194" or "37.7749, -122.4194"
     → parsed directly; no cache lookup needed.
  2. Disk cache hit:     addresses previously geocoded and stored locally.
     → returns the cached result (TTL: 24 hours).

If neither strategy resolves the input a GeocoderError is raised with
a message explaining how to supply coordinates directly.

Cache format:
    {
        "<address>": {
            "lat": 37.7749,
            "lon": -122.4194,
            "display_name": "San Francisco, CA, USA",
            "cached_at": 1700000000.0
        }
    }
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 86_400  # 24 hours

# Matches "lat,lon" or "lat, lon" with optional leading/trailing whitespace.
# Accepts optional sign and decimal point for each component.
_COORD_RE = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$"
)


@dataclass
class GeocoderResult:
    lat: float
    lon: float
    display_name: str


class GeocoderError(Exception):
    """Raised when geocoding fails."""


class Geocoder:
    """
    Offline geocoder — resolves addresses without any network calls.

    Args:
        cache_path: Path to JSON cache file (pre-populated entries are served
                    directly; no Nominatim or other external API is called).
        nominatim_url: Accepted for API compatibility but ignored in offline mode.
        rate_limit_delay: Accepted for API compatibility but ignored.
    """

    def __init__(
        self,
        nominatim_url: str = "",        # ignored — kept for API compatibility
        cache_path: str | Path = "data/geocode_cache.json",
        rate_limit_delay: float = 0.0,  # ignored — no network calls
    ):
        self._cache_path = Path(cache_path)
        self._cache: dict[str, dict] = {}
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def geocode(self, address: str) -> GeocoderResult:
        """
        Resolve an address string to lat/lon without network access.

        Accepts:
          • Coordinate pair:  "37.7749,-122.4194"  →  parsed directly.
          • Cached address:   any address previously stored in the disk cache.

        Raises:
            GeocoderError: When the address is not a coordinate pair and is
                           not present in the local cache.  The error message
                           instructs the caller to supply coordinates directly
                           (e.g. "37.7749,-122.4194") or use
                           POST /navigation/start with dest_lat / dest_lon.
        """
        # ── Strategy 1: coordinate string ──────────────────────────────
        coord = _COORD_RE.match(address)
        if coord:
            lat = float(coord.group(1))
            lon = float(coord.group(2))
            if not (-90.0 <= lat <= 90.0):
                raise GeocoderError(
                    f"Latitude {lat} out of range [-90, 90].  "
                    "Provide coordinates as 'latitude,longitude'."
                )
            if not (-180.0 <= lon <= 180.0):
                raise GeocoderError(
                    f"Longitude {lon} out of range [-180, 180].  "
                    "Provide coordinates as 'latitude,longitude'."
                )
            logger.debug("Geocode from coordinate string: %.6f, %.6f", lat, lon)
            return GeocoderResult(lat=lat, lon=lon, display_name=address.strip())

        # ── Strategy 2: disk cache ──────────────────────────────────────
        key = address.strip().lower()
        cached = self._cache.get(key)
        if cached:
            age = time.time() - cached.get("cached_at", 0)
            if age < _CACHE_TTL_SEC:
                logger.debug("Geocode cache hit: %s", address)
                return GeocoderResult(
                    lat=cached["lat"],
                    lon=cached["lon"],
                    display_name=cached["display_name"],
                )

        # ── No resolution available ─────────────────────────────────────
        raise GeocoderError(
            f"Cannot resolve '{address}' in offline mode.  "
            "Supply coordinates directly as 'latitude,longitude' "
            "(e.g. '37.7749,-122.4194'), or use POST /navigation/start "
            "with dest_lat and dest_lon fields."
        )

    def add_to_cache(self, address: str, lat: float, lon: float, display_name: str = "") -> None:
        """
        Manually add an address → coordinate mapping to the disk cache.

        Useful for pre-populating common destinations before deployment.
        """
        key = address.strip().lower()
        self._cache[key] = {
            "lat": lat,
            "lon": lon,
            "display_name": display_name or address.strip(),
            "cached_at": time.time(),
        }
        self._save_cache()
        logger.info("Geocode cache updated: %s → (%.6f, %.6f)", address, lat, lon)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_cache(self):
        if self._cache_path.exists():
            try:
                with open(self._cache_path) as f:
                    self._cache = json.load(f)
                logger.debug("Geocode cache loaded (%d entries)", len(self._cache))
            except Exception as exc:
                logger.warning("Could not load geocode cache: %s", exc)
                self._cache = {}

    def _save_cache(self):
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._cache_path, "w") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as exc:
            logger.warning("Could not save geocode cache: %s", exc)
