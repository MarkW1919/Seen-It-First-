import unittest

import numpy as np

from edge.inference.classifier import VehicleClassifier
from edge.inference.vehicle_classifier import VehicleClassifierModel


class ClassifierFallbackTests(unittest.TestCase):
    def test_vehicle_classifier_model_returns_unknown_when_not_loaded(self):
        model = VehicleClassifierModel({"model_path": "missing.onnx"})

        crop = np.full((32, 32, 3), 127, dtype=np.uint8)
        result = model.classify(crop)

        self.assertEqual(result.make, "unknown")
        self.assertEqual(result.model, "unknown")
        self.assertEqual(result.year_range, "unknown")
        self.assertEqual(result.vehicle_type, "vehicle")
        self.assertEqual(result.confidence, 0.0)

    def test_vehicle_classifier_pipeline_no_models_no_crash(self):
        classifier = VehicleClassifier(config={})

        crop = np.zeros((48, 48, 3), dtype=np.uint8)
        result = classifier.classify(crop)

        self.assertIsNotNone(result)
        self.assertEqual(result.make, "unknown")
        self.assertEqual(result.model, "unknown")
        self.assertEqual(result.year_range, "unknown")
        self.assertEqual(result.color, "black")
        self.assertEqual(result.vehicle_type, "vehicle")
        self.assertEqual(result.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
