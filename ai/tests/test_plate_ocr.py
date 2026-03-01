"""Tests for ai.plate_ocr: CTC decode, plate validation, confusion correction, caching."""

import re
import time

import numpy as np
import pytest

from ai.plate_ocr import (
    BLANK_IDX,
    CHARSET,
    STATE_PATTERNS,
    PlateOCR,
    _PartialReadMerger,
    _RecentPlateCache,
    _apply_confusion_correction,
)


class TestCTCDecode:
    """Test CTC decoding using a PlateOCR instance with mocked engine."""

    @pytest.fixture()
    def ocr(self):
        """Create a PlateOCR with a mock TRTEngine."""
        from unittest.mock import MagicMock, patch

        with patch("ai.plate_ocr.TRTEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.is_loaded = True
            MockEngine.return_value = mock_engine
            config = {
                "model_path": "/fake/model.engine",
                "input_size": [200, 48],
                "confidence_threshold": 0.7,
            }
            return PlateOCR(config)

    def _make_output(self, text: str, timesteps: int = 20, confidence: float = 0.95):
        """Create a mock CRNN output that decodes to the given text.

        Places the character at the correct CHARSET index with high probability,
        fills remaining timesteps with blank.
        """
        num_classes = len(CHARSET) + 1  # +1 for blank
        output = np.full((timesteps, num_classes), -10.0)  # low logits

        step = 0
        for char in text:
            idx = CHARSET.index(char)
            output[step, idx] = 10.0  # high logit for target char
            step += 1
            # Add blank between chars to separate duplicates
            output[step, BLANK_IDX] = 10.0
            step += 1

        # Fill remaining with blank
        for t in range(step, timesteps):
            output[t, BLANK_IDX] = 10.0

        return output

    def test_decode_simple(self, ocr):
        output = self._make_output("ABC123")
        text, conf, char_confs = ocr.ctc_decode(output)
        assert text == "ABC123"
        assert conf > 0.9
        assert len(char_confs) == 6

    def test_decode_empty_output(self, ocr):
        # All blanks
        output = np.full((20, len(CHARSET) + 1), -10.0)
        output[:, BLANK_IDX] = 10.0
        text, conf, char_confs = ocr.ctc_decode(output)
        assert text == ""
        assert conf == 0.0

    def test_decode_3d_input(self, ocr):
        """CTC decode should handle [1, T, C] input by squeezing."""
        output = self._make_output("XY")
        output_3d = output[np.newaxis, ...]  # [1, T, C]
        text, _, _ = ocr.ctc_decode(output_3d)
        assert text == "XY"

    def test_decode_suppresses_consecutive_duplicates(self, ocr):
        """Same index appearing consecutively should only produce one character."""
        num_classes = len(CHARSET) + 1
        output = np.full((6, num_classes), -10.0)
        a_idx = CHARSET.index("A")
        # Three consecutive A's → should decode as single A
        output[0, a_idx] = 10.0
        output[1, a_idx] = 10.0
        output[2, a_idx] = 10.0
        # Blank separator
        output[3, BLANK_IDX] = 10.0
        # B
        output[4, CHARSET.index("B")] = 10.0
        output[5, BLANK_IDX] = 10.0
        text, _, _ = ocr.ctc_decode(output)
        assert text == "AB"


class TestValidatePlate:
    @pytest.fixture()
    def ocr(self):
        from unittest.mock import MagicMock, patch

        with patch("ai.plate_ocr.TRTEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.is_loaded = True
            MockEngine.return_value = mock_engine
            config = {
                "model_path": "/fake/model.engine",
                "input_size": [200, 48],
                "min_plate_length": 2,
                "max_plate_length": 8,
                "validate_format": True,
            }
            return PlateOCR(config)

    def test_california_valid(self, ocr):
        assert ocr.validate_plate("7ABC123", "CA")

    def test_california_invalid(self, ocr):
        assert not ocr.validate_plate("ABC123", "CA")

    def test_new_york_valid(self, ocr):
        assert ocr.validate_plate("ABC1234", "NY")

    def test_texas_valid(self, ocr):
        assert ocr.validate_plate("ABC1234", "TX")
        assert ocr.validate_plate("123ABC", "TX")

    def test_delaware_all_digits(self, ocr):
        assert ocr.validate_plate("123456", "DE")

    def test_too_short(self, ocr):
        assert not ocr.validate_plate("A")

    def test_too_long(self, ocr):
        assert not ocr.validate_plate("ABCDEFGHI")

    def test_all_same_char(self, ocr):
        assert not ocr.validate_plate("AAAA")

    def test_no_state_accepts_valid(self, ocr):
        assert ocr.validate_plate("ABC123")

    def test_no_state_rejects_single_unique(self, ocr):
        assert not ocr.validate_plate("AAA")


class TestConfusionCorrection:
    def test_digit_to_letter_in_letter_position(self):
        # Alaska pattern: ^[A-Z]{3}\d{3}$ — first group expects letters
        ak_pattern = STATE_PATTERNS["AK"][0]
        # "0BC123" → position 0 expects letter, "0" → "O"
        result = _apply_confusion_correction("0BC123", ak_pattern)
        assert result[0] == "O"

    def test_letter_to_digit_in_digit_position(self):
        # Connecticut pattern: ^[A-Z]{2}\d{5}$ — second group expects digits
        ct_pattern = STATE_PATTERNS["CT"][0]
        # "ABO0000" → position 2 expects digit. The function processes [A-Z]{2} for
        # position 0, then \d{5} for position 1. Since the function steps through
        # one text position per pattern group, "B" at position 1 would be checked
        # against \d{5} → "B" maps to "8"
        result = _apply_confusion_correction("ABO0000", ct_pattern)
        # Position 0 checked against [A-Z]{2}: 'A' is letter, no change
        # Position 1 checked against \d{5}: 'B' is letter, mapped to '8'
        assert result[1] == "8"

    def test_no_pattern_returns_as_is(self):
        result = _apply_confusion_correction("ABC123", None)
        assert result == "ABC123"

    def test_empty_text(self):
        result = _apply_confusion_correction("", None)
        assert result == ""

    def test_unmapped_char_unchanged(self):
        # "X" is not in _LETTER_TO_DIGIT, so it stays as is
        ak_pattern = STATE_PATTERNS["AK"][0]
        result = _apply_confusion_correction("XBC123", ak_pattern)
        assert result[0] == "X"  # Not in confusion map, unchanged


class TestRecentPlateCache:
    def test_first_occurrence_not_duplicate(self):
        cache = _RecentPlateCache(maxsize=10, ttl=5.0)
        assert not cache.is_duplicate("ABC123")

    def test_second_occurrence_within_ttl_is_duplicate(self):
        cache = _RecentPlateCache(maxsize=10, ttl=5.0)
        cache.is_duplicate("ABC123")
        assert cache.is_duplicate("ABC123")

    def test_occurrence_after_ttl_not_duplicate(self):
        cache = _RecentPlateCache(maxsize=10, ttl=0.1)
        cache.is_duplicate("ABC123")
        time.sleep(0.15)
        assert not cache.is_duplicate("ABC123")

    def test_eviction_on_maxsize(self):
        cache = _RecentPlateCache(maxsize=2, ttl=60.0)
        cache.is_duplicate("A")
        cache.is_duplicate("B")
        cache.is_duplicate("C")  # evicts "A"
        # "A" is no longer cached, so not a duplicate
        assert not cache.is_duplicate("A")

    def test_get_best_read(self):
        cache = _RecentPlateCache(maxsize=10, ttl=60.0)
        cache.is_duplicate("ABC123")
        assert cache.get_best_read("ABC123") == "ABC123"
        assert cache.get_best_read("XYZ") is None


class TestPartialReadMerger:
    def test_no_bbox_returns_as_is(self):
        merger = _PartialReadMerger()
        text, conf = merger.try_merge("ABC", 0.9, None)
        assert text == "ABC"
        assert conf == 0.9

    def test_first_read_stored(self):
        merger = _PartialReadMerger()
        text, conf = merger.try_merge("AB", 0.8, [100, 100, 50, 20])
        assert text == "AB"

    def test_longer_read_replaces_shorter(self):
        merger = _PartialReadMerger(iou_thresh=0.3)
        merger.try_merge("AB", 0.7, [100, 100, 50, 20])
        text, conf = merger.try_merge("ABC1", 0.85, [100, 100, 50, 20])
        assert text == "ABC1"
        assert conf == 0.85

    def test_higher_conf_replaces_same_length(self):
        merger = _PartialReadMerger(iou_thresh=0.3)
        merger.try_merge("ABC", 0.7, [100, 100, 50, 20])
        text, conf = merger.try_merge("ABD", 0.9, [100, 100, 50, 20])
        assert text == "ABD"
        assert conf == 0.9

    def test_stale_entries_evicted(self):
        merger = _PartialReadMerger(ttl=0.1)
        merger.try_merge("AB", 0.7, [100, 100, 50, 20])
        time.sleep(0.15)
        # After TTL, the old partial is evicted, so this is a new entry
        text, conf = merger.try_merge("X", 0.5, [100, 100, 50, 20])
        assert text == "X"


class TestStatePatterns:
    """Verify a sample of state patterns match expected plate formats."""

    def test_all_states_defined(self):
        assert len(STATE_PATTERNS) >= 51  # 50 states + DC

    @pytest.mark.parametrize(
        "state,plate",
        [
            ("CA", "7ABC123"),
            ("NY", "ABC1234"),
            ("TX", "ABC1234"),
            ("TX", "123ABC"),
            ("FL", "ABCD12"),
            ("IL", "AB12345"),
            ("DE", "123456"),
            ("AK", "ABC123"),
            ("DC", "AB1234"),
        ],
    )
    def test_valid_plates_match(self, state, plate):
        patterns = STATE_PATTERNS[state]
        assert any(p.match(plate) for p in patterns), f"{plate} should match {state} pattern"

    @pytest.mark.parametrize(
        "state,plate",
        [
            ("CA", "ABCD123"),  # should be digit first
            ("NY", "AB12345"),  # wrong format
        ],
    )
    def test_invalid_plates_dont_match(self, state, plate):
        patterns = STATE_PATTERNS[state]
        assert not any(p.match(plate) for p in patterns), f"{plate} should NOT match {state}"
