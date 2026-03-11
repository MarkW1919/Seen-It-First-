"""
Vehicle likelihood scoring for the ranking engine.

Computes a weighted score (0–100) representing the probability that a
detected vehicle is the target.

Weights
-------
Plate readability:   0.30
Detection confidence: 0.25
Distance to dest:    0.20
Hotlist match:       0.20
Recent activity:     0.05

Bonus modifiers (applied after weighting, total capped at 100)
--------------
Hotlist match:           +50
Readable plate:          +20
Within 50 ft of dest:    +15
Active within 10 s:      +5
"""


class VehicleScorer:
    """Compute a 0–100 likelihood score for a candidate vehicle."""

    WEIGHT_PLATE    = 0.30
    WEIGHT_CONF     = 0.25
    WEIGHT_DISTANCE = 0.20
    WEIGHT_HOTLIST  = 0.20
    WEIGHT_RECENT   = 0.05

    def score(
        self,
        vehicle_conf:  float,
        plate_text:    str | None,
        distance_ft:   float,
        hotlist_match: bool,
        age_s:         float,
    ) -> float:
        """
        Compute a 0–100 score.

        Args:
            vehicle_conf:  Detection confidence (0–1).
            plate_text:    Confirmed plate text, or None/empty if unread.
            distance_ft:   Distance from detection point to destination (ft).
            hotlist_match: Whether the plate is on the alert hotlist.
            age_s:         Seconds since this detection was last seen.

        Returns:
            Float score in [0, 100].
        """
        has_plate = bool(plate_text)

        # Component scores (each 0–100)
        plate_score = 100.0 if has_plate else 0.0
        conf_score  = max(0.0, min(vehicle_conf, 1.0)) * 100.0

        distance_ft = max(0.0, distance_ft)

        if distance_ft <= 50:
            dist_score = 100.0
        elif distance_ft < 500:
            dist_score = (500.0 - distance_ft) / 450.0 * 100.0
        else:
            dist_score = 0.0

        hotlist_score = 100.0 if hotlist_match else 0.0
        recent_score  = 100.0 if age_s <= 10.0 else 0.0

        # Weighted base (max = 100.0)
        base = (
            plate_score    * self.WEIGHT_PLATE    +
            conf_score     * self.WEIGHT_CONF     +
            dist_score     * self.WEIGHT_DISTANCE +
            hotlist_score  * self.WEIGHT_HOTLIST  +
            recent_score   * self.WEIGHT_RECENT
        )

        # Bonus modifiers
        bonus = 0.0
        if hotlist_match:
            bonus += 50.0
        if has_plate:
            bonus += 20.0
        if distance_ft <= 50:
            bonus += 15.0
        if age_s <= 10.0:
            bonus += 5.0

        return min(100.0, base + bonus)
