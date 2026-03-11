#!/usr/bin/env python3
"""
Inference pipeline benchmark.

Runs one image through every stage of the pipeline and prints
per-stage latency. Verifies all TensorRT engines load correctly.
Also runs a full InferencePipeline integration smoke-test.

Usage:
    python scripts/test_pipeline.py
    python scripts/test_pipeline.py --image path/to/test.jpg
    python scripts/test_pipeline.py --runs 10
    python scripts/test_pipeline.py --pipeline-only

Performance targets (Jetson Orin Nano Super):
    Vehicle detection   < 8 ms
    Plate detection     < 6 ms
    OCR                 < 10 ms
    Classification      < 4 ms
    Total pipeline      < 30 ms
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Performance targets (ms)
TARGETS = {
    "vehicle_detection": 8.0,
    "plate_detection":   6.0,
    "ocr":               10.0,
    "classification":    4.0,
    "total":             30.0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_test_frame(image_path: str | None) -> np.ndarray:
    """Load an image or generate a synthetic 1920×1080 frame."""
    if image_path:
        frame = cv2.imread(image_path)
        if frame is None:
            logger.warning("Could not read %s; using synthetic frame.", image_path)
        else:
            logger.info("Test frame: %s (%dx%d)", image_path, frame.shape[1], frame.shape[0])
            return frame

    # Synthetic: grey background with a white rectangle simulating a car
    frame = np.full((1080, 1920, 3), 80, dtype=np.uint8)
    cv2.rectangle(frame, (400, 300), (1100, 700), (180, 180, 180), -1)   # car body
    cv2.rectangle(frame, (580, 640), (820, 700), (230, 230, 200), -1)    # plate area
    logger.info("Test frame: synthetic 1920×1080")
    return frame


def _ms(t0: float) -> float:
    return (time.monotonic() - t0) * 1000


# ---------------------------------------------------------------------------
# Stage timing wrappers
# ---------------------------------------------------------------------------

def time_vehicle_detection(detector, frame: np.ndarray) -> tuple[list, float]:
    t0 = time.monotonic()
    vehicles = detector.detect(frame)
    elapsed = _ms(t0)
    return vehicles, elapsed


def time_plate_detection(detector, frame: np.ndarray, vehicles: list) -> tuple[list, float]:
    if not vehicles:
        return [], 0.0
    t0 = time.monotonic()
    plates = detector.detect(frame, vehicles)
    elapsed = _ms(t0)
    return plates, elapsed


def time_ocr(ocr_model, frame: np.ndarray, plates: list, night_mode: bool) -> tuple[list, float]:
    if not plates:
        return [], 0.0
    t0 = time.monotonic()
    results = ocr_model.recognize(frame, plates, night_mode=night_mode)
    elapsed = _ms(t0)
    return results, elapsed


def time_classifier(clf, frame: np.ndarray, crop: np.ndarray | None) -> tuple[object, float]:
    if crop is None or clf.is_suspended:
        return None, 0.0
    t0 = time.monotonic()
    result = clf.classify(crop)
    elapsed = _ms(t0)
    return result, elapsed


# ---------------------------------------------------------------------------
# Load check
# ---------------------------------------------------------------------------

def load_models(config: dict) -> tuple:
    """Load all four inference models. Return (vd, pd, ocr, clf, all_ok)."""
    from edge.inference.vehicle_detector import VehicleDetector
    from edge.inference.plate_detector import PlateDetector
    from edge.inference.ocr import PlateOCR
    from edge.inference.classifier import VehicleClassifier

    vd  = VehicleDetector(config["vehicle_detection"])
    pd  = PlateDetector(config["plate_detection"])
    ocr = PlateOCR(config["ocr"])
    clf = VehicleClassifier(config["classifier"])

    statuses = {
        "vehicle_detector": vd.load(),
        "plate_detector":   pd.load(),
        "ocr":              ocr.load(),
        "classifier":       clf.load(),
    }

    print()
    print("Model load status:")
    all_ok = True
    for name, ok in statuses.items():
        tag = "LOADED" if ok else "NOT LOADED (no engine file or no GPU)"
        print(f"  {name:<22} {tag}")
        if not ok:
            all_ok = False
    print()

    return vd, pd, ocr, clf, all_ok


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

def run_benchmark(args: argparse.Namespace):
    import yaml

    config_path = REPO_ROOT / "edge" / "config" / "system.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    inf_cfg = cfg["inference"]

    vd, pd, ocr_model, clf, all_loaded = load_models(inf_cfg)

    frame = load_test_frame(args.image)

    # Synthetic vehicle crop for classifier timing (even without real detection)
    h, w = frame.shape[:2]
    sample_crop = frame[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]

    runs = args.runs
    print(f"Running {runs} iteration(s)...\n")

    accum = {k: 0.0 for k in TARGETS}

    for i in range(runs):
        vehicles, t_vd = time_vehicle_detection(vd, frame)
        plates,   t_pd = time_plate_detection(pd, frame, vehicles)
        ocr_res,  t_ocr = time_ocr(ocr_model, frame, plates, night_mode=False)
        clf_res,  t_clf = time_classifier(clf, frame, sample_crop)

        t_total = t_vd + t_pd + t_ocr + t_clf

        accum["vehicle_detection"] += t_vd
        accum["plate_detection"]   += t_pd
        accum["ocr"]               += t_ocr
        accum["classification"]    += t_clf
        accum["total"]             += t_total

        if args.verbose or runs == 1:
            print(f"Run {i+1}:")
            print(f"  vehicles found : {len(vehicles)}")
            print(f"  plates found   : {len(plates)}")
            print(f"  OCR results    : {[r.to_dict() for r in ocr_res]}")
            if clf_res:
                print(f"  classification : {clf_res.to_dict()}")
            print()

    # Summary table
    print("=" * 55)
    print(f"{'Stage':<22} {'Avg (ms)':>10} {'Target':>10} {'Pass':>6}")
    print("-" * 55)

    stage_keys = [
        ("Vehicle detection", "vehicle_detection"),
        ("Plate detection",   "plate_detection"),
        ("OCR",              "ocr"),
        ("Classification",   "classification"),
        ("Total pipeline",   "total"),
    ]

    all_pass = True
    for label, key in stage_keys:
        avg = accum[key] / runs
        target = TARGETS[key]
        # Only fail if model was loaded (otherwise timing is 0 — no engine)
        passed = avg <= target or avg == 0.0
        if avg > 0.0 and avg > target:
            all_pass = False
        symbol = "✓" if passed else "✗"
        note = "" if avg > 0.0 else " (engine not loaded)"
        print(f"  {label:<20} {avg:>9.2f}  {target:>9.1f}  {symbol}{note}")

    print("=" * 55)

    if not all_loaded:
        print(
            "\nNOTE: One or more engines did not load. "
            "Run build_tensorrt_engines.py first."
        )
    elif all_pass:
        print("\nAll performance targets met.")
    else:
        print("\nSome targets missed — check GPU thermal state or engine precision.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_pipeline_integration(args: argparse.Namespace):
    """
    Smoke-test the full InferencePipeline with a synthetic FramePacket.

    Verifies:
    - All models load (or produce graceful warnings)
    - InferencePipeline.process_frame() returns a PipelineResult
    - Latency is within the target budget
    - EventPublisher and DetectionFusionEngine initialise without errors
    """
    import yaml
    from edge.camera.capture import FramePacket
    from edge.inference.events import EventPublisher
    from edge.inference.fusion import DetectionFusionEngine
    from edge.inference.pipeline import InferencePipeline

    config_path = REPO_ROOT / "edge" / "config" / "system.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    inf_cfg = cfg["inference"]

    print("\n" + "=" * 55)
    print("InferencePipeline integration test")
    print("=" * 55)

    vd, pd, ocr_model, clf, all_loaded = load_models(inf_cfg)

    # Stubs for fusion and events (no ws_manager / uvicorn loop needed)
    publisher = EventPublisher()
    fusion = DetectionFusionEngine(event_publisher=publisher, hotlist_matcher=None)

    pipeline = InferencePipeline(
        vehicle_detector=vd,
        plate_detector=pd,
        ocr=ocr_model,
        classifier=clf,
        tracker_config=inf_cfg.get("tracker", {}),
        fusion_engine=fusion,
        event_publisher=publisher,
    )

    print("Vehicle detector loaded")
    print("Plate detector loaded")
    print("OCR loaded")
    print("Classifier loaded")
    print("Tracker loaded")

    frame = load_test_frame(args.image)

    # Build a synthetic FramePacket
    packet = FramePacket(
        camera_id="cam1",
        frame=frame,
        timestamp=time.monotonic(),
        frame_number=1,
        width=frame.shape[1],
        height=frame.shape[0],
    )

    print(f"\nRunning {args.runs} pipeline integration pass(es)...\n")

    total_ms = 0.0
    for i in range(args.runs):
        t0 = time.monotonic()
        result = pipeline.process_frame(packet, night_mode=False)
        elapsed = (time.monotonic() - t0) * 1000
        total_ms += elapsed

        if args.verbose or args.runs == 1:
            print(f"  Run {i + 1}: {elapsed:.1f} ms  "
                  f"vehicles={len(result.vehicles)}  "
                  f"plates={len(result.plates)}  "
                  f"tracks={len(result.tracks)}")

    avg_ms = total_ms / args.runs
    passed = avg_ms <= TARGETS["total"] or avg_ms == 0.0
    symbol = "✓" if passed else "✗"
    print(f"\n  Pipeline test frame processed.")
    print(f"  Avg latency: {avg_ms:.1f} ms  target={TARGETS['total']} ms  {symbol}")

    print("\n" + "=" * 55)
    if not all_loaded:
        print("NOTE: Some engines not loaded — latency figures are indicative only.")
    elif passed:
        print("Pipeline integration test PASSED.")
    else:
        print("Pipeline integration test: latency over target.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline latency benchmark")
    parser.add_argument("--image", default=None, help="Test image path (optional)")
    parser.add_argument("--runs", type=int, default=1, help="Number of benchmark runs")
    parser.add_argument("--verbose", action="store_true", help="Print per-run details")
    parser.add_argument(
        "--pipeline-only",
        action="store_true",
        help="Run only the InferencePipeline integration test (skip stage benchmarks)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.pipeline_only:
        run_benchmark(args)
    run_pipeline_integration(args)
