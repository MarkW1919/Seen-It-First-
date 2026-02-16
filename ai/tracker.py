"""DeepSORT-based multi-object tracker for vehicles."""
import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)


@dataclass
class KalmanState:
    """Simple 2D Kalman filter state for bounding box tracking."""

    mean: np.ndarray  # [cx, cy, aspect_ratio, height, vx, vy, va, vh]
    covariance: np.ndarray

    @staticmethod
    def init_from_bbox(bbox: list[int]) -> "KalmanState":
        x, y, w, h = bbox
        cx = x + w / 2
        cy = y + h / 2
        aspect = w / max(h, 1)
        mean = np.array([cx, cy, aspect, h, 0, 0, 0, 0], dtype=np.float64)
        covariance = np.diag([100, 100, 1, 100, 250, 250, 1e-2, 250]) ** 2
        return KalmanState(mean=mean, covariance=covariance)

    @property
    def bbox(self) -> list[int]:
        cx, cy, a, h = self.mean[:4]
        w = a * h
        return [int(cx - w / 2), int(cy - h / 2), int(w), int(h)]

    def predict(self):
        F = np.eye(8)
        F[:4, 4:] = np.eye(4)
        Q = np.eye(8) * 10
        self.mean = F @ self.mean
        self.covariance = F @ self.covariance @ F.T + Q

    def update(self, bbox: list[int]):
        x, y, w, h = bbox
        cx = x + w / 2
        cy = y + h / 2
        aspect = w / max(h, 1)
        z = np.array([cx, cy, aspect, h])
        H = np.eye(4, 8)
        R = np.diag([10, 10, 0.1, 10]) ** 2
        S = H @ self.covariance @ H.T + R
        K = self.covariance @ H.T @ np.linalg.inv(S)
        self.mean = self.mean + K @ (z - H @ self.mean)
        self.covariance = (np.eye(8) - K @ H) @ self.covariance


@dataclass
class Track:
    track_id: int
    state: KalmanState
    hits: int = 1
    age: int = 0
    time_since_update: int = 0
    detections: list[dict] = field(default_factory=list)

    @property
    def is_confirmed(self) -> bool:
        return self.hits >= 3

    @property
    def bbox(self) -> list[int]:
        return self.state.bbox


class MultiObjectTracker:
    """Simplified DeepSORT tracker using IoU + Kalman filtering."""

    def __init__(self, config: dict):
        self.max_age = config.get("max_age", 30)
        self.min_hits = config.get("min_hits", 3)
        self.iou_threshold = config.get("iou_threshold", 0.3)
        self._next_id = 1
        self.tracks: list[Track] = []

    def update(self, detections: list[dict]) -> list[Track]:
        """Update tracker with new detections.

        Args:
            detections: List of detection dicts with 'bbox' key

        Returns:
            List of confirmed tracks
        """
        # Predict all existing tracks
        for track in self.tracks:
            track.state.predict()
            track.age += 1
            track.time_since_update += 1

        # Match detections to tracks using IoU
        if self.tracks and detections:
            track_bboxes = [t.state.bbox for t in self.tracks]
            det_bboxes = [d["bbox"] for d in detections]
            cost_matrix = self._iou_cost(track_bboxes, det_bboxes)

            row_indices, col_indices = linear_sum_assignment(cost_matrix)

            matched_tracks = set()
            matched_dets = set()

            for r, c in zip(row_indices, col_indices):
                if cost_matrix[r, c] < (1 - self.iou_threshold):
                    self.tracks[r].state.update(detections[c]["bbox"])
                    self.tracks[r].hits += 1
                    self.tracks[r].time_since_update = 0
                    self.tracks[r].detections.append(detections[c])
                    matched_tracks.add(r)
                    matched_dets.add(c)

            # Create new tracks for unmatched detections
            for i, det in enumerate(detections):
                if i not in matched_dets:
                    state = KalmanState.init_from_bbox(det["bbox"])
                    track = Track(
                        track_id=self._next_id,
                        state=state,
                        detections=[det],
                    )
                    self._next_id += 1
                    self.tracks.append(track)
        elif detections:
            # No existing tracks
            for det in detections:
                state = KalmanState.init_from_bbox(det["bbox"])
                track = Track(
                    track_id=self._next_id,
                    state=state,
                    detections=[det],
                )
                self._next_id += 1
                self.tracks.append(track)

        # Remove dead tracks
        self.tracks = [
            t for t in self.tracks if t.time_since_update < self.max_age
        ]

        # Return confirmed tracks
        return [t for t in self.tracks if t.is_confirmed]

    def _iou_cost(
        self, track_bboxes: list[list[int]], det_bboxes: list[list[int]]
    ) -> np.ndarray:
        """Compute IoU cost matrix."""
        n, m = len(track_bboxes), len(det_bboxes)
        cost = np.ones((n, m))

        for i, tb in enumerate(track_bboxes):
            for j, db in enumerate(det_bboxes):
                cost[i, j] = 1 - self._iou(tb, db)

        return cost

    @staticmethod
    def _iou(a: list[int], b: list[int]) -> float:
        ax1, ay1, aw, ah = a
        bx1, by1, bw, bh = b
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = aw * ah + bw * bh - inter

        return inter / max(union, 1e-6)

    def reset(self):
        self.tracks.clear()
        self._next_id = 1
