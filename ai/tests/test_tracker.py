"""Tests for ai.tracker: KalmanState, Track, MultiObjectTracker."""

import numpy as np
import pytest

from ai.tracker import KalmanState, MultiObjectTracker, Track


class TestKalmanState:
    def test_init_from_bbox(self):
        bbox = [100, 200, 50, 80]
        ks = KalmanState.init_from_bbox(bbox)
        # Center should be (125, 240)
        assert abs(ks.mean[0] - 125.0) < 1e-6
        assert abs(ks.mean[1] - 240.0) < 1e-6
        # Aspect = 50/80 = 0.625
        assert abs(ks.mean[2] - 0.625) < 1e-6
        # Height
        assert abs(ks.mean[3] - 80.0) < 1e-6
        # Velocities start at 0
        np.testing.assert_array_equal(ks.mean[4:], [0, 0, 0, 0])

    def test_bbox_roundtrip(self):
        bbox = [100, 200, 50, 80]
        ks = KalmanState.init_from_bbox(bbox)
        recovered = ks.bbox
        # Should be close to original (integer rounding)
        assert abs(recovered[0] - bbox[0]) <= 1
        assert abs(recovered[1] - bbox[1]) <= 1
        assert abs(recovered[2] - bbox[2]) <= 1
        assert abs(recovered[3] - bbox[3]) <= 1

    def test_predict_moves_state(self):
        ks = KalmanState.init_from_bbox([100, 100, 50, 50])
        original_mean = ks.mean.copy()
        ks.predict()
        # predict() updates the state (adds velocity to position)
        # Since velocities are 0, mean changes minimally; covariance grows
        assert ks.covariance is not None
        assert np.any(ks.covariance != KalmanState.init_from_bbox([100, 100, 50, 50]).covariance)

    def test_update_refines_state(self):
        ks = KalmanState.init_from_bbox([100, 100, 50, 50])
        ks.predict()
        original = ks.mean.copy()
        ks.update([110, 110, 50, 50])
        # After update with new measurement, state should shift toward measurement
        assert ks.mean[0] != original[0] or ks.mean[1] != original[1]

    def test_zero_height_bbox(self):
        # Should not crash, aspect = w / max(h, 1)
        ks = KalmanState.init_from_bbox([10, 10, 20, 0])
        assert ks.mean[2] == 20.0  # w / max(0, 1) = 20


class TestTrack:
    def test_is_confirmed_after_3_hits(self):
        ks = KalmanState.init_from_bbox([0, 0, 10, 10])
        track = Track(track_id=1, state=ks, hits=1)
        assert not track.is_confirmed

        track.hits = 3
        assert track.is_confirmed

    def test_add_detection_capped(self):
        ks = KalmanState.init_from_bbox([0, 0, 10, 10])
        track = Track(track_id=1, state=ks)
        for i in range(15):
            track.add_detection({"id": i, "bbox": [i, i, 10, 10]})
        # Capped at MAX_TRACK_DETECTIONS (10)
        assert len(track.detections) == 10
        # Oldest evicted, newest present
        assert track.detections[-1]["id"] == 14

    def test_bbox_property(self):
        ks = KalmanState.init_from_bbox([100, 200, 50, 80])
        track = Track(track_id=1, state=ks)
        bbox = track.bbox
        assert len(bbox) == 4


class TestMultiObjectTracker:
    def make_tracker(self, **kwargs):
        config = {"max_age": 5, "min_hits": 3, "iou_threshold": 0.3}
        config.update(kwargs)
        return MultiObjectTracker(config)

    def test_create_tracks_from_detections(self):
        tracker = self.make_tracker()
        dets = [{"bbox": [100, 100, 50, 50]}, {"bbox": [300, 300, 60, 60]}]
        tracker.update(dets)
        assert len(tracker.tracks) == 2

    def test_no_detections_ages_tracks(self):
        tracker = self.make_tracker()
        tracker.update([{"bbox": [100, 100, 50, 50]}])
        assert tracker.tracks[0].time_since_update == 0
        tracker.update([])
        assert tracker.tracks[0].time_since_update == 1

    def test_dead_tracks_removed(self):
        tracker = self.make_tracker(max_age=2)
        tracker.update([{"bbox": [100, 100, 50, 50]}])
        tracker.update([])  # time_since_update = 1
        tracker.update([])  # time_since_update = 2 >= max_age, removed
        assert len(tracker.tracks) == 0

    def test_confirmed_tracks_require_min_hits(self):
        tracker = self.make_tracker(min_hits=3)
        det = [{"bbox": [100, 100, 50, 50]}]
        confirmed = tracker.update(det)
        assert len(confirmed) == 0  # Only 1 hit

        confirmed = tracker.update(det)
        assert len(confirmed) == 0  # 2 hits

        confirmed = tracker.update(det)
        assert len(confirmed) == 1  # 3 hits = confirmed

    def test_matching_updates_existing_tracks(self):
        tracker = self.make_tracker()
        det1 = [{"bbox": [100, 100, 50, 50]}]
        tracker.update(det1)
        initial_id = tracker.tracks[0].track_id

        # Same detection region — should match, not create new
        det2 = [{"bbox": [102, 102, 50, 50]}]
        tracker.update(det2)
        assert len(tracker.tracks) == 1
        assert tracker.tracks[0].track_id == initial_id
        assert tracker.tracks[0].hits == 2

    def test_reset_clears_state(self):
        tracker = self.make_tracker()
        tracker.update([{"bbox": [100, 100, 50, 50]}])
        tracker.reset()
        assert len(tracker.tracks) == 0
        assert tracker._next_id == 1

    def test_iou_cost_vectorized_identical_boxes(self):
        cost = MultiObjectTracker._iou_cost_vectorized(
            [[10, 10, 50, 50]], [[10, 10, 50, 50]]
        )
        assert cost.shape == (1, 1)
        assert abs(cost[0, 0]) < 1e-4  # IoU=1.0, cost=0.0

    def test_iou_cost_vectorized_no_overlap(self):
        cost = MultiObjectTracker._iou_cost_vectorized(
            [[0, 0, 10, 10]], [[100, 100, 10, 10]]
        )
        assert abs(cost[0, 0] - 1.0) < 1e-4  # IoU=0.0, cost=1.0

    def test_iou_cost_vectorized_multiple(self):
        tracks = [[0, 0, 10, 10], [50, 50, 10, 10]]
        dets = [[1, 1, 10, 10], [100, 100, 10, 10]]
        cost = MultiObjectTracker._iou_cost_vectorized(tracks, dets)
        assert cost.shape == (2, 2)
        # First track should match first detection (high IoU, low cost)
        assert cost[0, 0] < cost[0, 1]
