"""
Data models for the vehicle ranking engine.
"""

from dataclasses import dataclass


@dataclass
class RankedVehicle:
    """A detected vehicle with a computed likelihood score."""
    vehicle_id:   str
    plate_text:   str | None
    vehicle_type: str
    make:         str
    model:        str
    color:        str
    year_range:   str
    confidence:   float
    distance_ft:  float
    hotlist_match: bool
    score:        float
    latitude:     float
    longitude:    float
    timestamp:    float
    camera_id:    str
    fingerprint:  str = ""

    def to_dict(self) -> dict:
        return {
            "vehicle_id":   self.vehicle_id,
            "vehicle_type": self.vehicle_type,
            "make":         self.make,
            "model":        self.model,
            "color":        self.color,
            "year_range":   self.year_range,
            "plate":        self.plate_text,
            "confidence":   round(self.confidence, 4),
            "distance_ft":  round(self.distance_ft, 1),
            "hotlist_match": self.hotlist_match,
            "score":        round(self.score, 2),
            "latitude":     self.latitude,
            "longitude":    self.longitude,
            "timestamp":    self.timestamp,
            "camera_id":    self.camera_id,
            "fingerprint":  self.fingerprint,
        }
