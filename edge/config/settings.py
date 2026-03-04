"""
SEEN IT FIRST - Configuration Loader

Reads YAML configuration files and provides typed access via dataclasses.
Supports environment variable overrides with SIF_* prefix.

Usage:
    from edge.config.settings import get_settings
    settings = get_settings()
    print(settings.system.database.path)
    print(settings.cameras[0].id)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve the base directory for config files.  The YAML files live alongside
# this Python module at  edge/config/*.yaml.
# ---------------------------------------------------------------------------
_CONFIG_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CONFIG_DIR.parent.parent  # two levels up from edge/config/


# ===== Camera dataclasses =================================================

@dataclass(frozen=True)
class CameraConfig:
    """Configuration for a single camera."""
    id: str
    housing: str
    sensor: str
    source_type: str          # csi | rtsp | usb
    source: str               # device index or RTSP URL
    width: int
    height: int
    fps: int
    role: str                 # lpr | wide
    ir_led_gpio_pin: int
    ir_cut_gpio_pin: int


# ===== Inference dataclasses ==============================================

@dataclass(frozen=True)
class VehicleDetectorConfig:
    architecture: str
    engine_path: str
    onnx_path: str
    input_width: int
    input_height: int
    precision: str
    confidence_threshold: float
    nms_iou_threshold: float
    target_classes: List[int]
    class_names: Dict[int, str]


@dataclass(frozen=True)
class PlateDetectorConfig:
    architecture: str
    engine_path: str
    onnx_path: str
    input_width: int
    input_height: int
    precision: str
    confidence_threshold: float
    nms_iou_threshold: float


@dataclass(frozen=True)
class OCRConfig:
    architecture: str
    engine_path: str
    onnx_path: str
    input_width: int
    input_height: int
    precision: str
    min_plate_length: int
    max_plate_length: int
    charset: str


@dataclass(frozen=True)
class VehicleClassifierConfig:
    architecture: str
    engine_path: str
    onnx_path: str
    input_width: int
    input_height: int
    precision: str
    calibration_cache: str


@dataclass(frozen=True)
class TrackerConfig:
    algorithm: str
    max_age: int
    n_init: int
    max_cosine_distance: float
    nn_budget: int
    embedding_dim: int
    embedding_engine_path: str
    embedding_onnx_path: str


@dataclass(frozen=True)
class SchedulingConfig:
    skip_frames: int
    max_concurrent_engines: int
    backpressure_threshold_ms: int
    engine_warmup_iterations: int


@dataclass(frozen=True)
class ModelsConfig:
    vehicle_detector: VehicleDetectorConfig
    plate_detector: PlateDetectorConfig
    ocr: OCRConfig
    vehicle_classifier: VehicleClassifierConfig
    tracker: TrackerConfig


@dataclass(frozen=True)
class InferenceConfig:
    models: ModelsConfig
    scheduling: SchedulingConfig


# ===== System dataclasses =================================================

@dataclass(frozen=True)
class DatabaseConfig:
    path: str
    wal_mode: bool
    busy_timeout_ms: int


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    format: str
    file: str
    max_bytes: int
    backup_count: int


@dataclass(frozen=True)
class ThermalThresholds:
    warning: int
    high: int
    critical: int
    emergency: int


@dataclass(frozen=True)
class ThermalConfig:
    check_interval_sec: int
    thresholds: ThermalThresholds
    recovery_hysteresis: int


@dataclass(frozen=True)
class HotlistConfig:
    cooldown_seconds: int
    alert_confidence_threshold: float


@dataclass(frozen=True)
class NightModeConfig:
    brightness_activate: int
    brightness_deactivate: int


@dataclass(frozen=True)
class APIConfig:
    host: str
    port: int
    cors_origins: List[str]


@dataclass(frozen=True)
class SystemConfig:
    database: DatabaseConfig
    logging: LoggingConfig
    thermal: ThermalConfig
    hotlist: HotlistConfig
    night_mode: NightModeConfig
    api: APIConfig
    data_dir: str
    capture_dir: str
    clip_dir: str


# ===== Top-level settings =================================================

@dataclass(frozen=True)
class Settings:
    """Top-level configuration container holding all subsystems."""
    cameras: List[CameraConfig]
    inference: InferenceConfig
    system: SystemConfig
    project_root: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    logger.info("Loaded configuration file", extra={"path": str(path)})
    return data


def _env_override(data: Dict[str, Any], prefix: str = "SIF") -> Dict[str, Any]:
    """
    Apply environment variable overrides.

    Environment variables follow the convention:
        SIF_<SECTION>_<KEY>=<value>
    Nested keys use double underscores:
        SIF_DATABASE__PATH=/custom/path.db
        SIF_THERMAL__THRESHOLDS__WARNING=70

    Only existing keys are overridden -- new keys are not injected.
    """
    result = dict(data)
    env_prefix = f"{prefix}_"

    for env_key, env_val in os.environ.items():
        if not env_key.startswith(env_prefix):
            continue

        # Strip prefix and split on double-underscore for nesting
        key_trail = env_key[len(env_prefix):].lower().split("__")

        # Walk into the dict
        target = result
        for part in key_trail[:-1]:
            if isinstance(target, dict) and part in target:
                # We need a mutable copy when first touching a subtree
                if not isinstance(target[part], dict):
                    break
                target[part] = dict(target[part])
                target = target[part]
            else:
                break
        else:
            final_key = key_trail[-1]
            if isinstance(target, dict) and final_key in target:
                original = target[final_key]
                target[final_key] = _coerce(env_val, type(original))
                logger.info(
                    "Environment override applied",
                    extra={"env_var": env_key, "key": ".".join(key_trail)},
                )

    return result


def _coerce(value: str, target_type: type) -> Any:
    """Coerce a string environment variable value to *target_type*."""
    if target_type is bool:
        return value.lower() in ("true", "1", "yes")
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    if target_type is list:
        # Simple comma-separated list
        return [v.strip() for v in value.split(",")]
    return value


# ---------------------------------------------------------------------------
# Dataclass builders
# ---------------------------------------------------------------------------

def _build_cameras(raw: Dict[str, Any]) -> List[CameraConfig]:
    """Build a list of CameraConfig from raw YAML data."""
    cameras: List[CameraConfig] = []
    for cam in raw.get("cameras", []):
        cameras.append(CameraConfig(
            id=str(cam["id"]),
            housing=str(cam["housing"]),
            sensor=str(cam["sensor"]),
            source_type=str(cam["source_type"]),
            source=str(cam["source"]),
            width=int(cam["width"]),
            height=int(cam["height"]),
            fps=int(cam["fps"]),
            role=str(cam["role"]),
            ir_led_gpio_pin=int(cam["ir_led_gpio_pin"]),
            ir_cut_gpio_pin=int(cam["ir_cut_gpio_pin"]),
        ))
    return cameras


def _build_inference(raw: Dict[str, Any]) -> InferenceConfig:
    """Build InferenceConfig from raw YAML data."""
    models_raw = raw.get("models", {})

    vd = models_raw.get("vehicle_detector", {})
    # class_names keys come in as ints from YAML; ensure they stay ints
    class_names_raw = vd.get("class_names", {})
    class_names = {int(k): str(v) for k, v in class_names_raw.items()}

    vehicle_detector = VehicleDetectorConfig(
        architecture=str(vd["architecture"]),
        engine_path=str(vd["engine_path"]),
        onnx_path=str(vd["onnx_path"]),
        input_width=int(vd["input_width"]),
        input_height=int(vd["input_height"]),
        precision=str(vd["precision"]),
        confidence_threshold=float(vd["confidence_threshold"]),
        nms_iou_threshold=float(vd["nms_iou_threshold"]),
        target_classes=[int(c) for c in vd["target_classes"]],
        class_names=class_names,
    )

    pd = models_raw.get("plate_detector", {})
    plate_detector = PlateDetectorConfig(
        architecture=str(pd["architecture"]),
        engine_path=str(pd["engine_path"]),
        onnx_path=str(pd["onnx_path"]),
        input_width=int(pd["input_width"]),
        input_height=int(pd["input_height"]),
        precision=str(pd["precision"]),
        confidence_threshold=float(pd["confidence_threshold"]),
        nms_iou_threshold=float(pd["nms_iou_threshold"]),
    )

    ocr_raw = models_raw.get("ocr", {})
    ocr = OCRConfig(
        architecture=str(ocr_raw["architecture"]),
        engine_path=str(ocr_raw["engine_path"]),
        onnx_path=str(ocr_raw["onnx_path"]),
        input_width=int(ocr_raw["input_width"]),
        input_height=int(ocr_raw["input_height"]),
        precision=str(ocr_raw["precision"]),
        min_plate_length=int(ocr_raw["min_plate_length"]),
        max_plate_length=int(ocr_raw["max_plate_length"]),
        charset=str(ocr_raw["charset"]),
    )

    vc_raw = models_raw.get("vehicle_classifier", {})
    vehicle_classifier = VehicleClassifierConfig(
        architecture=str(vc_raw["architecture"]),
        engine_path=str(vc_raw["engine_path"]),
        onnx_path=str(vc_raw["onnx_path"]),
        input_width=int(vc_raw["input_width"]),
        input_height=int(vc_raw["input_height"]),
        precision=str(vc_raw["precision"]),
        calibration_cache=str(vc_raw["calibration_cache"]),
    )

    tr = models_raw.get("tracker", {})
    tracker = TrackerConfig(
        algorithm=str(tr["algorithm"]),
        max_age=int(tr["max_age"]),
        n_init=int(tr["n_init"]),
        max_cosine_distance=float(tr["max_cosine_distance"]),
        nn_budget=int(tr["nn_budget"]),
        embedding_dim=int(tr["embedding_dim"]),
        embedding_engine_path=str(tr["embedding_engine_path"]),
        embedding_onnx_path=str(tr["embedding_onnx_path"]),
    )

    models = ModelsConfig(
        vehicle_detector=vehicle_detector,
        plate_detector=plate_detector,
        ocr=ocr,
        vehicle_classifier=vehicle_classifier,
        tracker=tracker,
    )

    sc = raw.get("scheduling", {})
    scheduling = SchedulingConfig(
        skip_frames=int(sc["skip_frames"]),
        max_concurrent_engines=int(sc["max_concurrent_engines"]),
        backpressure_threshold_ms=int(sc["backpressure_threshold_ms"]),
        engine_warmup_iterations=int(sc["engine_warmup_iterations"]),
    )

    return InferenceConfig(models=models, scheduling=scheduling)


def _build_system(raw: Dict[str, Any]) -> SystemConfig:
    """Build SystemConfig from raw YAML data."""
    db = raw.get("database", {})
    database = DatabaseConfig(
        path=str(db["path"]),
        wal_mode=bool(db["wal_mode"]),
        busy_timeout_ms=int(db["busy_timeout_ms"]),
    )

    lg = raw.get("logging", {})
    logging_cfg = LoggingConfig(
        level=str(lg["level"]),
        format=str(lg["format"]),
        file=str(lg["file"]),
        max_bytes=int(lg["max_bytes"]),
        backup_count=int(lg["backup_count"]),
    )

    th = raw.get("thermal", {})
    thresholds_raw = th.get("thresholds", {})
    thermal = ThermalConfig(
        check_interval_sec=int(th["check_interval_sec"]),
        thresholds=ThermalThresholds(
            warning=int(thresholds_raw["warning"]),
            high=int(thresholds_raw["high"]),
            critical=int(thresholds_raw["critical"]),
            emergency=int(thresholds_raw["emergency"]),
        ),
        recovery_hysteresis=int(th["recovery_hysteresis"]),
    )

    hl = raw.get("hotlist", {})
    hotlist = HotlistConfig(
        cooldown_seconds=int(hl["cooldown_seconds"]),
        alert_confidence_threshold=float(hl["alert_confidence_threshold"]),
    )

    nm = raw.get("night_mode", {})
    night_mode = NightModeConfig(
        brightness_activate=int(nm["brightness_activate"]),
        brightness_deactivate=int(nm["brightness_deactivate"]),
    )

    api_raw = raw.get("api", {})
    api = APIConfig(
        host=str(api_raw["host"]),
        port=int(api_raw["port"]),
        cors_origins=[str(o) for o in api_raw.get("cors_origins", [])],
    )

    return SystemConfig(
        database=database,
        logging=logging_cfg,
        thermal=thermal,
        hotlist=hotlist,
        night_mode=night_mode,
        api=api,
        data_dir=str(raw.get("data_dir", "data/")),
        capture_dir=str(raw.get("capture_dir", "data/captures/")),
        clip_dir=str(raw.get("clip_dir", "data/clips/")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_settings_singleton: Optional[Settings] = None


def load_settings(
    config_dir: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> Settings:
    """
    Load all configuration files, apply environment overrides, and return a
    fully-typed ``Settings`` instance.

    Parameters
    ----------
    config_dir : Path, optional
        Directory containing the YAML files.  Defaults to the directory where
        this module lives (``edge/config/``).
    project_root : Path, optional
        Project root used to resolve relative paths in the config files.
        Defaults to two directories above *config_dir*.

    Returns
    -------
    Settings
    """
    global _settings_singleton

    if config_dir is None:
        config_dir = _CONFIG_DIR
    if project_root is None:
        project_root = _PROJECT_ROOT

    cameras_path = config_dir / "cameras.yaml"
    inference_path = config_dir / "inference.yaml"
    system_path = config_dir / "system.yaml"

    # Load raw YAML ---------------------------------------------------------
    cameras_raw = _load_yaml(cameras_path)
    inference_raw = _load_yaml(inference_path)
    system_raw = _load_yaml(system_path)

    # Apply environment overrides -------------------------------------------
    cameras_raw = _env_override(cameras_raw, prefix="SIF_CAMERAS")
    inference_raw = _env_override(inference_raw, prefix="SIF_INFERENCE")
    system_raw = _env_override(system_raw, prefix="SIF")

    # Build typed dataclasses -----------------------------------------------
    cameras = _build_cameras(cameras_raw)
    inference = _build_inference(inference_raw)
    system = _build_system(system_raw)

    _settings_singleton = Settings(
        cameras=cameras,
        inference=inference,
        system=system,
        project_root=str(project_root),
    )

    logger.info(
        "Configuration loaded successfully",
        extra={
            "camera_count": len(cameras),
            "project_root": str(project_root),
        },
    )
    return _settings_singleton


def get_settings() -> Settings:
    """
    Return the cached ``Settings`` singleton.

    Calls ``load_settings()`` automatically on first access.
    """
    global _settings_singleton
    if _settings_singleton is None:
        _settings_singleton = load_settings()
    return _settings_singleton


def reload_settings() -> Settings:
    """Force-reload all configuration from disk and environment."""
    global _settings_singleton
    _settings_singleton = None
    return load_settings()


def resolve_path(relative: str) -> Path:
    """
    Resolve a path that is relative to the project root.

    Example::

        db_path = resolve_path(settings.system.database.path)
        # -> /absolute/project/root/data/seen_it_first.db
    """
    settings = get_settings()
    return Path(settings.project_root) / relative
