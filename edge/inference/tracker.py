"""
Lightweight DeepSORT tracker for multi-object tracking.

Tracks vehicles across frames using IoU + appearance embedding.
Runs at 12-15 FPS per camera.
"""

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """A tracked object."""
    track_id: int
    bbox: np.ndarray  # [x1, y1, x2, y2]
    embedding: np.ndarray | None = None
    hits: int = 1
    age: int = 0
    time_since_update: int = 0
    confirmed: bool = False
    classified: bool = False
    plate_text: str = ""
    plate_confidence: float = 0.0
    class_name: str = ""
    confidence: float = 0.0   # detection confidence from the originating YOLO box
    metadata: dict = field(default_factory=dict)


class Tracker:
    """
    Lightweight DeepSORT-style multi-object tracker.

    Uses IoU-based assignment with optional cosine distance
    on appearance embeddings for re-identification.

    Config:
        max_age: Frames before deleting a lost track.
        min_hits: Detections before a track is confirmed.
        iou_threshold: Minimum IoU for assignment.
        max_cosine_distance: Max cosine distance for embedding match.
    """

    def __init__(self, config: dict):
        self.max_age = config.get("max_age", 30)
        self.min_hits = config.get("min_hits", 3)
        self.iou_threshold = config.get("iou_threshold", 0.3)
        self.max_cosine_distance = config.get("max_cosine_distance", 0.4)
        self._next_id = 1
        self.tracks: list[Track] = []

    def update(
        self,
        detections: list[np.ndarray],
        embeddings: list[np.ndarray] | None = None,
    ) -> list[Track]:
        """
        Update tracks with new detections.

        Args:
            detections: List of [x1, y1, x2, y2, confidence] arrays.
            embeddings: Optional appearance embeddings per detection.

        Returns:
            List of currently active (confirmed) tracks.
        """
        # Predict: age all tracks
        for track in self.tracks:
            track.age += 1
            track.time_since_update += 1

        if len(detections) == 0:
            self._prune_tracks()
            return self.confirmed_tracks

        det_boxes = np.array([d[:4] for d in detections])
        det_confs = [float(d[4]) if len(d) > 4 else 0.0 for d in detections]
        det_embeddings = embeddings if embeddings else [None] * len(detections)

        # Build cost matrix using IoU
        if len(self.tracks) > 0:
            track_boxes = np.array([t.bbox for t in self.tracks])
            iou_matrix = self._iou_batch(track_boxes, det_boxes)

            # If we have embeddings, blend with cosine distance
            if embeddings is not None and any(
                t.embedding is not None for t in self.tracks
            ):
                cost_matrix = self._blended_cost(iou_matrix, det_embeddings)
            else:
                cost_matrix = 1.0 - iou_matrix

            # Hungarian assignment
            matched, unmatched_tracks, unmatched_dets = self._assign(
                cost_matrix, iou_matrix
            )
        else:
            matched = []
            unmatched_tracks = []
            unmatched_dets = list(range(len(detections)))

        # Update matched tracks
        for track_idx, det_idx in matched:
            track = self.tracks[track_idx]
            track.bbox = det_boxes[det_idx]
            track.confidence = det_confs[det_idx]
            track.hits += 1
            track.time_since_update = 0
            if det_embeddings[det_idx] is not None:
                track.embedding = det_embeddings[det_idx]
            if track.hits >= self.min_hits:
                track.confirmed = True

        # Create new tracks for unmatched detections
        for det_idx in unmatched_dets:
            new_track = Track(
                track_id=self._next_id,
                bbox=det_boxes[det_idx],
                confidence=det_confs[det_idx],
                embedding=det_embeddings[det_idx],
            )
            self._next_id += 1
            self.tracks.append(new_track)

        self._prune_tracks()
        return self.confirmed_tracks

    def _assign(
        self, cost_matrix: np.ndarray, iou_matrix: np.ndarray
    ) -> tuple[list, list, list]:
        """Hungarian assignment with IoU threshold gating."""
        if cost_matrix.size == 0:
            return [], list(range(cost_matrix.shape[0])), list(range(cost_matrix.shape[1]))

        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        matched = []
        unmatched_tracks = set(range(cost_matrix.shape[0]))
        unmatched_dets = set(range(cost_matrix.shape[1]))

        for r, c in zip(row_indices, col_indices):
            if iou_matrix[r, c] < self.iou_threshold:
                continue
            matched.append((r, c))
            unmatched_tracks.discard(r)
            unmatched_dets.discard(c)

        return matched, list(unmatched_tracks), list(unmatched_dets)

    def _blended_cost(
        self, iou_matrix: np.ndarray, det_embeddings: list
    ) -> np.ndarray:
        """Blend IoU cost with cosine embedding distance."""
        iou_cost = 1.0 - iou_matrix
        cos_cost = np.ones_like(iou_cost)

        for t_idx, track in enumerate(self.tracks):
            if track.embedding is None:
                continue
            for d_idx, det_emb in enumerate(det_embeddings):
                if det_emb is None:
                    continue
                cos_dist = 1.0 - np.dot(track.embedding, det_emb) / (
                    np.linalg.norm(track.embedding) * np.linalg.norm(det_emb) + 1e-6
                )
                cos_cost[t_idx, d_idx] = cos_dist

        # Weighted blend: 60% IoU, 40% appearance
        return 0.6 * iou_cost + 0.4 * cos_cost

    def _prune_tracks(self):
        """Remove tracks that exceed max_age without updates."""
        self.tracks = [
            t for t in self.tracks
            if t.time_since_update <= self.max_age
        ]

    @staticmethod
    def _iou_batch(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
        """Compute IoU between two sets of boxes. Returns [M, N] matrix."""
        x1 = np.maximum(boxes_a[:, 0:1], boxes_b[:, 0].T)
        y1 = np.maximum(boxes_a[:, 1:2], boxes_b[:, 1].T)
        x2 = np.minimum(boxes_a[:, 2:3], boxes_b[:, 2].T)
        y2 = np.minimum(boxes_a[:, 3:4], boxes_b[:, 3].T)

        inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)

        area_a = (boxes_a[:, 2] - boxes_a[:, 0]) * (boxes_a[:, 3] - boxes_a[:, 1])
        area_b = (boxes_b[:, 2] - boxes_b[:, 0]) * (boxes_b[:, 3] - boxes_b[:, 1])

        union = area_a[:, np.newaxis] + area_b[np.newaxis, :] - inter
        return inter / (union + 1e-6)

    @property
    def confirmed_tracks(self) -> list[Track]:
        return [t for t in self.tracks if t.confirmed]

    def get_track(self, track_id: int) -> Track | None:
        for t in self.tracks:
            if t.track_id == track_id:
                return t
        return None

    def reset(self):
        self.tracks.clear()
        self._next_id = 1
