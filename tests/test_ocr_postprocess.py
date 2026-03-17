import unittest

from edge.inference.ocr import PlateOCR


class TestPlateOCRPostprocess(unittest.TestCase):
    def setUp(self):
        self.ocr = PlateOCR({"model_path": "models/ocr/ocr.engine"})

    def test_ambiguity_correction_defaults_disabled_without_config(self):
        self.assertFalse(self.ocr.enable_ambiguity_correction)

    def test_ambiguity_correction_can_be_enabled_from_config(self):
        ocr = PlateOCR(
            {
                "model_path": "models/ocr/ocr.engine",
                "enable_ambiguity_correction": True,
            }
        )
        self.assertTrue(ocr.enable_ambiguity_correction)

    def test_postprocess_strips_non_alnum_and_uppercases(self):
        cleaned = self.ocr._postprocess_text(" ab-12 c* ")
        self.assertEqual(cleaned, "AB12C")

    def test_postprocess_truncates_to_max_chars(self):
        cleaned = self.ocr._postprocess_text("ABCDEFGHIJK")
        self.assertEqual(cleaned, "ABCDEFGH")

    def test_resolve_ambiguities_prefers_digits_in_digit_context(self):
        corrected = self.ocr._resolve_ambiguities("12O45")
        self.assertEqual(corrected, "12045")

    def test_resolve_ambiguities_prefers_letters_in_alpha_context(self):
        corrected = self.ocr._resolve_ambiguities("AB0DE")
        self.assertEqual(corrected, "ABODE")

    def test_resolve_ambiguities_uses_original_neighbor_context(self):
        corrected = self.ocr._resolve_ambiguities("1S3")
        self.assertEqual(corrected, "153")

    def test_resolve_ambiguities_avoids_edge_digit_to_alpha_flip(self):
        corrected = self.ocr._resolve_ambiguities("3S1")
        self.assertEqual(corrected, "351")

    def test_resolve_ambiguities_converts_leading_ambiguous_in_digit_context(self):
        corrected = self.ocr._resolve_ambiguities("O12")
        self.assertEqual(corrected, "012")


if __name__ == "__main__":
    unittest.main()
