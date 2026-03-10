import tempfile
import unittest
from pathlib import Path

from scripts.validate_config import validate_camera_config, validate_system_config


class ValidateConfigTests(unittest.TestCase):
    def test_repo_configs_are_valid(self):
        system = Path("edge/config/system.yaml")
        camera = Path("edge/camera/config.yaml")
        issues = validate_system_config(system) + validate_camera_config(camera)
        errors = [i for i in issues if i.level == "ERROR"]
        self.assertEqual([], errors, msg=f"Config errors: {[e.message for e in errors]}")

    def test_invalid_port_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "system.yaml"
            p.write_text(
                """
system: {database_path: data/db.sqlite}
inference:
  vehicle_detection: {model_path: models/vehicle.engine}
  plate_detection: {model_path: models/plate.engine}
  ocr: {model_path: models/ocr.engine}
  classifier: {model_path: models/classifier.engine}
api: {host: 0.0.0.0, port: 70000}
hotlist: {file_path: data/hotlist.csv}
navigation:
  nominatim_url: https://example.com
  osrm_url: https://example.com
thermal: {threshold_1: 80, threshold_2: 90}
""",
                encoding="utf-8",
            )
            issues = validate_system_config(p)
            self.assertTrue(any("api.port" in i.message for i in issues))


if __name__ == "__main__":
    unittest.main()
