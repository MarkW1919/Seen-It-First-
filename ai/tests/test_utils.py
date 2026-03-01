"""Tests for ai.utils: softmax, IoU, TTLCache, LetterboxPreprocessor."""

import time
from unittest.mock import patch

import numpy as np
import pytest

from ai.utils import TTLCache, compute_iou, softmax


class TestSoftmax:
    def test_uniform_input(self):
        x = np.array([1.0, 1.0, 1.0])
        result = softmax(x)
        np.testing.assert_allclose(result, [1 / 3, 1 / 3, 1 / 3], atol=1e-6)

    def test_sums_to_one(self):
        x = np.array([1.0, 2.0, 3.0, 4.0])
        result = softmax(x)
        assert abs(result.sum() - 1.0) < 1e-6

    def test_max_element_has_highest_probability(self):
        x = np.array([1.0, 5.0, 2.0])
        result = softmax(x)
        assert np.argmax(result) == 1

    def test_numerical_stability_large_values(self):
        x = np.array([1000.0, 1001.0, 1002.0])
        result = softmax(x)
        assert not np.any(np.isnan(result))
        assert not np.any(np.isinf(result))
        assert abs(result.sum() - 1.0) < 1e-6

    def test_single_element(self):
        x = np.array([42.0])
        result = softmax(x)
        np.testing.assert_allclose(result, [1.0])

    def test_negative_values(self):
        x = np.array([-1.0, -2.0, -3.0])
        result = softmax(x)
        assert abs(result.sum() - 1.0) < 1e-6
        assert np.argmax(result) == 0


class TestComputeIoU:
    def test_identical_boxes(self):
        box = [10, 10, 50, 50]
        assert abs(compute_iou(box, box) - 1.0) < 1e-6

    def test_no_overlap(self):
        a = [0, 0, 10, 10]
        b = [20, 20, 10, 10]
        assert compute_iou(a, b) == 0.0

    def test_partial_overlap(self):
        a = [0, 0, 10, 10]
        b = [5, 5, 10, 10]
        # Intersection: 5x5=25, union: 100+100-25=175
        expected = 25 / 175
        assert abs(compute_iou(a, b) - expected) < 1e-6

    def test_one_inside_other(self):
        big = [0, 0, 100, 100]
        small = [25, 25, 50, 50]
        # Intersection = 50*50=2500, union = 10000+2500-2500=10000
        expected = 2500 / 10000
        assert abs(compute_iou(big, small) - expected) < 1e-6

    def test_touching_edges(self):
        a = [0, 0, 10, 10]
        b = [10, 0, 10, 10]
        assert compute_iou(a, b) == 0.0

    def test_zero_area_box(self):
        a = [0, 0, 0, 0]
        b = [0, 0, 10, 10]
        assert compute_iou(a, b) == 0.0


class TestTTLCache:
    def test_put_and_get(self):
        cache = TTLCache(maxsize=10, ttl=60.0)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_missing_key_returns_none(self):
        cache = TTLCache(maxsize=10, ttl=60.0)
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = TTLCache(maxsize=10, ttl=0.5)
        cache.put("key1", "value1")
        time.sleep(0.6)
        assert cache.get("key1") is None

    def test_contains_active(self):
        cache = TTLCache(maxsize=10, ttl=60.0)
        cache.put("key1", "value1")
        assert "key1" in cache
        assert cache.contains("key1")

    def test_contains_expired(self):
        cache = TTLCache(maxsize=10, ttl=0.1)
        cache.put("key1", "value1")
        time.sleep(0.2)
        assert "key1" not in cache

    def test_eviction_on_maxsize(self):
        cache = TTLCache(maxsize=3, ttl=60.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("d") == 4

    def test_lru_order_on_access(self):
        cache = TTLCache(maxsize=3, ttl=60.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Access "a" to move it to end
        cache.get("a")
        # Insert new key, should evict "b" (oldest unused)
        cache.put("d", 4)
        assert cache.get("b") is None
        assert cache.get("a") == 1

    def test_overwrite_value(self):
        cache = TTLCache(maxsize=10, ttl=60.0)
        cache.put("key", "old")
        cache.put("key", "new")
        assert cache.get("key") == "new"
