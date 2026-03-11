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
import random
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 86_400  # 24 hours
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_DEFAULT_USER_AGENT = "Seen-It-First-Edge/1.0 (edge-navigation; ops@example.local)"


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
        timeout_sec: float = 10.0,
        max_retries: int = 3,
        backoff_base_sec: float = 0.75,
        user_agent: str = _DEFAULT_USER_AGENT,
    ):
        self._url = nominatim_url.rstrip("/")
        self._cache_path = Path(cache_path)
        self._rate_limit = rate_limit_delay
        self._timeout_sec = timeout_sec
        self._max_retries = max(1, max_retries)
        self._backoff_base_sec = max(0.1, backoff_base_sec)
        self._user_agent = user_agent
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
        if not self._url:
            raise GeocoderError("Geocoding disabled by navigation mode/configuration")

        self._wait_for_rate_limit()

        params = urllib.parse.urlencode({
            "q": address,
            "format": "json",
            "limit": 1,
            "addressdetails": 0,
        })
        url = f"{self._url}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})

        body = None
        for attempt in range(1, self._max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self._timeout_sec) as resp:
                    body = json.loads(resp.read().decode())
                break
            except urllib.error.HTTPError as exc:
                retryable = exc.code in {429, 500, 502, 503, 504}
                if retryable and attempt < self._max_retries:
                    self._sleep_backoff(attempt, reason=f"HTTP {exc.code}")
                    continue
                raise GeocoderError(f"Nominatim HTTP {exc.code}: {address}") from exc
            except urllib.error.URLError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt, reason=f"network error: {exc.reason}")
                    continue
                raise GeocoderError(f"Nominatim request failed: {exc}") from exc
            except TimeoutError as exc:
                if attempt < self._max_retries:
                    self._sleep_backoff(attempt, reason="timeout")
                    continue
                raise GeocoderError(f"Nominatim timeout after {self._max_retries} attempts") from exc
            except Exception as exc:
                raise GeocoderError(f"Nominatim request failed: {exc}") from exc
            finally:
                self._last_request_at = time.monotonic()

        if not body:
            raise GeocoderError(f"No results for address: '{address}'")

        hit = body[0]
        return GeocoderResult(
            lat=float(hit["lat"]),
            lon=float(hit["lon"]),
            display_name=hit.get("display_name", address),
        )

    def _sleep_backoff(self, attempt: int, reason: str):
        delay = self._backoff_base_sec * (2 ** (attempt - 1))
        jitter = random.uniform(0.0, self._backoff_base_sec * 0.25)
        wait_for = delay + jitter
        logger.warning(
            "Nominatim retry %d/%d in %.2fs (%s)",
            attempt,
            self._max_retries,
            wait_for,
            reason,
        )
        time.sleep(wait_for)

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
