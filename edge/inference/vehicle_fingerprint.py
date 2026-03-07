"""
Vehicle fingerprinting and deduplication.

VehicleFingerprintGenerator
----------------------------
Combines make/model/color/year text attributes with a hash of the ReID
embedding vector to produce a short, human-readable fingerprint string:

    "{type}-{make}-{model}-{year}-{color}-{hash}"

Example:
    "pickup-chevrolet-silverado-2019-2022-black-9A72F1"

When no embedding is available, the hash is derived from the text fields
alone so the fingerprint is still stable across frames.

FingerprintDeduplicator
-----------------------
Suppresses duplicate detection events when the same fingerprint is seen
more than once within WINDOW_S seconds at a GPS distance < DISTANCE_FT.

Two cameras seeing the same vehicle at the same moment would normally
produce two separate detection events.  The deduplicator collapses these
into a single event and returns True from is_duplicate() to signal that
the caller should skip further processing for this detection.

Thread-safety: designed for single-threaded use inside the fusion engine.
"""

import hashlib
import logging
import re
import time

import numpy as np

logger = logging.getLogger(__name__)

# Deduplication thresholds
_DEDUP_WINDOW_S  = 5.0    # suppress same fingerprint within this window
_DEDUP_DIST_FT   = 10.0   # and within this GPS distance (feet)


class VehicleFingerprintGenerator:
    """
    Generates a compact fingerprint string for a detected vehicle.

    The fingerprint encodes:
      • Coarse vehicle attributes (type / make / model / year / color)
      • A 6-character hex hash of the ReID embedding (or text fallback)

    The hash component reduces false collisions when two different vehicles
    share the same make/model/color — their embeddings will differ.

    Usage::

        gen = VehicleFingerprintGenerator()
        fp = gen.generate(
            vehicle_type="pickup",
            make="Chevrolet",
            model="Silverado",
            year_range="2019-2022",
            color="black",
            embedding=np.array(...),   # optional
        )
        # → "pickup-chevrolet-silverado-2019-2022-black-9A72F1"
    """

    def generate(
        self,
        vehicle_type: str,
        make:         str,
        model:        str,
        year_range:   str,
        color:        str,
        embedding:    "np.ndarray | None" = None,
    ) -> str:
        """
        Build and return a fingerprint string.

        Args:
            vehicle_type: Coarse vehicle category (car, pickup, suv, …).
            make:         Manufacturer name or "unknown".
            model:        Model name or "unknown".
            year_range:   Year bucket string ("2019-2022") or "unknown".
            color:        Dominant color name or "unknown".
            embedding:    Optional 128-dim float32 ReID embedding.

        Returns:
            Fingerprint string like "pickup-chevrolet-silverado-2019-2022-black-9A72F1".
        """
        parts = [
            _slug(vehicle_type),
            _slug(make),
            _slug(model),
            _slug(year_range),
            _slug(color),
        ]
        base_str = "-".join(parts)
        hash_suffix = self._hash(embedding, base_str)
        return f"{base_str}-{hash_suffix}"

    @staticmethod
    def _hash(embedding: "np.ndarray | None", fallback_str: str) -> str:
        """
        Compute a 6-character uppercase hex hash.

        Uses the ReID embedding when available (quantised to int16 to reduce
        frame-to-frame noise sensitivity).  Falls back to SHA-256 of the
        text fields when no embedding is provided.
        """
        if embedding is not None and embedding.size > 0:
            # Quantise: multiply by 1000, round to int16 → stable across frames
            quantised = np.clip(embedding * 1000, -32768, 32767).astype(np.int16)
            data = quantised.tobytes()
        else:
            data = fallback_str.encode("utf-8")

        digest = hashlib.sha256(data).hexdigest()
        return digest[:6].upper()


class FingerprintDeduplicator:
    """
    Suppresses repeated detections of the same vehicle fingerprint.

    When the same fingerprint is presented within WINDOW_S seconds and
    the GPS position has not moved more than DISTANCE_FT from the first
    sighting, is_duplicate() returns True and the caller should skip
    further processing (evidence capture, DB insert, event broadcast).

    The internal state is evicted periodically to prevent unbounded growth.
    """

    def __init__(
        self,
        window_s:   float = _DEDUP_WINDOW_S,
        distance_ft: float = _DEDUP_DIST_FT,
    ):
        self._window_s   = window_s
        self._dist_ft    = distance_ft
        # fingerprint → (last_seen_time, lat, lon)
        self._seen: dict[str, tuple[float, float, float]] = {}
        self._last_eviction = time.monotonic()

    def is_duplicate(
        self,
        fingerprint: str,
        timestamp:   float,
        lat:         float,
        lon:         float,
    ) -> bool:
        """
        Check whether this fingerprint/position/time combination is a duplicate.

        Side-effect: updates the stored timestamp for this fingerprint.

        Args:
            fingerprint: Fingerprint string produced by VehicleFingerprintGenerator.
            timestamp:   Unix timestamp of this detection.
            lat:         Operator GPS latitude at detection time.
            lon:         Operator GPS longitude at detection time.

        Returns:
            True if this detection should be suppressed as a duplicate.
        """
        if not fingerprint:
            return False

        now = time.monotonic()
        self._maybe_evict(now)

        existing = self._seen.get(fingerprint)
        if existing is None:
            self._seen[fingerprint] = (timestamp, lat, lon)
            return False

        prev_ts, prev_lat, prev_lon = existing

        # Outside time window → treat as new detection
        if (timestamp - prev_ts) > self._window_s:
            self._seen[fingerprint] = (timestamp, lat, lon)
            return False

        # Within time window — check GPS proximity
        dist_ft = _approx_distance_ft(lat, lon, prev_lat, prev_lon)
        if dist_ft < self._dist_ft:
            # Update timestamp so the window slides forward
            self._seen[fingerprint] = (timestamp, lat, lon)
            logger.debug(
                "Fingerprint dedup: %s suppressed (age=%.1fs dist=%.1fft)",
                fingerprint, timestamp - prev_ts, dist_ft,
            )
            return True

        # Same fingerprint but vehicle moved more than threshold → new sighting
        self._seen[fingerprint] = (timestamp, lat, lon)
        return False

    def _maybe_evict(self, now: float):
        """Periodically remove entries older than 2× the window."""
        if (now - self._last_eviction) < self._window_s * 2:
            return
        cutoff = time.time() - self._window_s * 2
        stale = [fp for fp, (ts, _, __) in self._seen.items() if ts < cutoff]
        for fp in stale:
            del self._seen[fp]
        self._last_eviction = now


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    """Lowercase alphanumeric slug; hyphens preserved in year ranges."""
    if not text or text.lower() == "unknown":
        return "unknown"
    # Allow hyphens (year ranges like "2019-2022") and digits
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s or "unknown"


def _approx_distance_ft(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Fast planar approximation of distance in feet.

    Accurate to within ~1 % for distances up to ~1 mile.
    """
    if lat1 == 0.0 and lon1 == 0.0:
        return 0.0
    # 1 degree latitude ≈ 364 000 ft; 1 degree longitude depends on latitude
    import math
    lat_ft = (lat2 - lat1) * 364_000.0
    lon_ft = (lon2 - lon1) * 364_000.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(lat_ft, lon_ft)
