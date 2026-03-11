"""
Geocoder: address string → latitude / longitude.

Uses OpenStreetMap Nominatim API (free, no key required).
Results are cached to a local JSON file to honour Nominatim's
1-request/second rate limit and avoid redundant lookups.

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
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 86_400  # 24 hours
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "Seen-It-First-Edge/1.0 (edge-navigation)"


@dataclass
class GeocoderResult:
    lat: float
    lon: float
    display_name: str


class GeocoderError(Exception):
    """Raised when geocoding fails."""


class Geocoder:
    """
    Nominatim geocoder with local disk cache.

    Args:
        nominatim_url: Base URL for Nominatim (override for self-hosted).
        cache_path: Path to JSON cache file.
        rate_limit_delay: Minimum seconds between API calls (Nominatim policy ≥ 1 s).
    """

    def __init__(
        self,
        nominatim_url: str = _NOMINATIM_URL,
        cache_path: str | Path = "data/geocode_cache.json",
        rate_limit_delay: float = 1.1,
    ):
        self._url = nominatim_url.rstrip("/")
        self._cache_path = Path(cache_path)
        self._rate_limit = rate_limit_delay
        # Monotonic timestamp of last API call (used only for rate limiting).
        self._last_request_at: float = 0.0
        self._cache: dict[str, dict] = {}
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def geocode(self, address: str) -> GeocoderResult:
        """
        Convert an address string to lat/lon.

        Checks disk cache first; calls Nominatim only on cache miss.

        Args:
            address: Human-readable address or place name.

        Returns:
            GeocoderResult with lat, lon, display_name.

        Raises:
            GeocoderError: If the address cannot be resolved.
        """
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

        result = self._nominatim_request(address)
        self._cache[key] = {
            "lat": result.lat,
            "lon": result.lon,
            "display_name": result.display_name,
            "cached_at": time.time(),
        }
        self._save_cache()
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _nominatim_request(self, address: str) -> GeocoderResult:
        """Call Nominatim, honouring the rate limit."""
        self._wait_for_rate_limit()

        params = urllib.parse.urlencode({
            "q": address,
            "format": "json",
            "limit": 1,
            "addressdetails": 0,
        })
        url = f"{self._url}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise GeocoderError(f"Nominatim HTTP {exc.code}: {address}") from exc
        except Exception as exc:
            raise GeocoderError(f"Nominatim request failed: {exc}") from exc
        finally:
            # Keep rate-limit timing on the monotonic clock to avoid
            # wall-clock jumps and mixed-clock math bugs.
            self._last_request_at = time.monotonic()

        if not body:
            raise GeocoderError(f"No results for address: '{address}'")

        hit = body[0]
        return GeocoderResult(
            lat=float(hit["lat"]),
            lon=float(hit["lon"]),
            display_name=hit.get("display_name", address),
        )

    def _wait_for_rate_limit(self):
        """Block until at least `_rate_limit` seconds since last call."""
        wait = self._rate_limit - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)

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
