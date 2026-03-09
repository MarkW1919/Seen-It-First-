import unittest

from edge.inference.ocr import PlateOCR


class TestPlateOCRPostprocess(unittest.TestCase):
    def setUp(self):
        self.ocr = PlateOCR({"model_path": "models/ocr/ocr.engine"})

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


if __name__ == "__main__":
    unittest.main()
