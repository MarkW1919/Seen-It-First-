"""
Seen-It-First-Edge: Main entry point.

Single-process edge service that orchestrates:
1. Camera ingestion (GStreamer/NVDEC)
2. Inference pipeline (vehicle → plate → OCR → classifier → tracker)
3. Hotlist matching
4. Local SQLite storage
5. Console + audio alerts
6. Thermal monitoring + adaptive throttling
7. Navigation API server (FastAPI/uvicorn, port 8080)
"""

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

import uvicorn
import yaml

from edge.camera.manager import CameraManager
from edge.inference.vehicle_detector import VehicleDetector
from edge.inference.plate_detector import PlateDetector
from edge.inference.ocr import PlateOCR
from edge.inference.classifier import VehicleClassifier
from edge.inference.vehicle_classifier import VehicleClassifierModel
from edge.inference.vehicle_color import VehicleColorDetector
from edge.inference.vehicle_reid import VehicleReID
from edge.inference.vehicle_fingerprint import VehicleFingerprintGenerator
from edge.inference.scheduler import InferenceScheduler
from edge.inference.events import EventPublisher
from edge.inference.fusion import DetectionFusionEngine
from edge.hotlist.loader import HotlistLoader
from edge.hotlist.matcher import HotlistMatcher
from edge.storage.database import Database
from edge.storage.repository import DetectionRepository
from edge.system.thermal import ThermalMonitor
from edge.system.monitoring import SystemMonitor
from edge.system.alerts import AlertManager
from edge.evidence.capture import SnapshotCapture
from edge.evidence.storage import EvidenceStorage
from edge.evidence.cleanup import MediaRetentionManager
from edge.ranking.engine import RankingEngine
from edge.api.state import GpsState

logger = logging.getLogger("seen-it-first")

# Base directory (repo root)
BASE_DIR = Path(__file__).resolve().parent.parent


def load_config(config_path: str | None = None) -> dict:
    """Load system configuration from YAML."""
    if config_path is None:
        config_path = str(BASE_DIR / "edge" / "config" / "system.yaml")

    path = Path(config_path)
    if not path.exists():
        logger.error("Config file not found: %s", path)
        sys.exit(1)

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    logger.info("Configuration loaded from %s", path)
    return config


def setup_logging(config: dict):
    """Configure logging to console and file."""
    log_level = config.get("system", {}).get("log_level", "INFO")
    log_dir = BASE_DIR / config.get("system", {}).get("log_dir", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "edge.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler(str(log_file), mode="a")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.addHandler(console)
    root.addHandler(file_handler)


class EdgeService:
    """
    Main edge service orchestrator.

    Lifecycle:
    1. Load config
    2. Initialize database
    3. Load models
    4. Start cameras
    5. Run processing loop
    6. Clean shutdown on SIGTERM/SIGINT
    """

    def __init__(self, config: dict):
        self.config = config
        self._running = False

        # Components
        self.camera_manager: CameraManager | None = None
        self.scheduler: InferenceScheduler | None = None
        self.hotlist_loader: HotlistLoader | None = None
        self.hotlist_matcher: HotlistMatcher | None = None
        self.event_publisher: EventPublisher | None = None
        self.fusion_engine: DetectionFusionEngine | None = None
        self.snapshot_capture: SnapshotCapture | None = None
        self.evidence_storage: EvidenceStorage | None = None
        self.retention_manager: MediaRetentionManager | None = None
        self.ranking_engine: RankingEngine | None = None
        self.gps_state: GpsState | None = None
        self.db: Database | None = None
        self.repo: DetectionRepository | None = None
        self.thermal: ThermalMonitor | None = None
        self.monitor: SystemMonitor | None = None
        self.alert_manager: AlertManager | None = None

        # Stats
        self._loop_count = 0
        self._last_stats_time = 0.0
        self._stats_interval = 30.0  # log stats every 30s

    def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("Initializing Seen-It-First Edge Service")

        # Database
        db_path = str(BASE_DIR / self.config["system"]["database_path"])
        self.db = Database(db_path)
        if not self.db.initialize():
            logger.error("Database initialization failed")
            return False
        self.repo = DetectionRepository(self.db)

        # Thermal monitor
        self.thermal = ThermalMonitor(self.config.get("thermal", {}))

        # System monitor
        self.monitor = SystemMonitor()

        # Camera manager
        cam_config_path = str(BASE_DIR / "edge" / "camera" / "config.yaml")
        queue_size = self.config.get("cameras", {}).get("queue_size", 8)
        self.camera_manager = CameraManager(cam_config_path, queue_size)

        # Inference models
        inf_config = self.config.get("inference", {})

        vehicle_det = VehicleDetector(inf_config.get("vehicle_detection", {}))
        plate_det   = PlateDetector(inf_config.get("plate_detection", {}))
        ocr_cfg = dict(inf_config.get("ocr", {}))
        ocr_cfg.update(self.config.get("night_vision", {}))
        ocr         = PlateOCR(ocr_cfg)

        # Vehicle intelligence sub-models (all ONNX-based, graceful fallback)
        models_dir      = str(BASE_DIR / "edge" / "models")
        clf_cfg         = inf_config.get("classifier", {})
        clf_model_cfg   = inf_config.get("vehicle_classifier", {
            "model_path": f"{models_dir}/vehicle_make_model_classifier.onnx",
        })
        color_cfg       = inf_config.get("vehicle_color", {
            "model_path": f"{models_dir}/vehicle_color_model.onnx",
        })
        reid_cfg        = inf_config.get("vehicle_reid", {
            "model_path": f"{models_dir}/vehicle_embedding_model.onnx",
        })

        clf_model   = VehicleClassifierModel(clf_model_cfg)
        color_det   = VehicleColorDetector(color_cfg)
        reid_model  = VehicleReID(reid_cfg)
        fp_gen      = VehicleFingerprintGenerator()

        classifier = VehicleClassifier(
            config=clf_cfg,
            classifier_model=clf_model,
            color_detector=color_det,
            reid_model=reid_model,
            fingerprint_gen=fp_gen,
        )

        # Load models (non-fatal if models not present yet)
        models_loaded = True
        for name, model in [
            ("vehicle_detector", vehicle_det),
            ("plate_detector", plate_det),
            ("ocr", ocr),
            ("classifier", classifier),
        ]:
            if not model.load():
                logger.warning("Model not loaded: %s (engine file missing?)", name)
                models_loaded = False

        if not models_loaded:
            logger.warning(
                "Some models failed to load. Pipeline will run with available models."
            )

        # Hotlist (created before scheduler so fusion can use it)
        hotlist_config = self.config.get("hotlist", {})
        hotlist_path = str(BASE_DIR / hotlist_config.get("file_path", "data/hotlist.csv"))
        self.hotlist_loader = HotlistLoader(hotlist_path)
        self.hotlist_loader.load()  # non-fatal if file missing
        self.hotlist_matcher = HotlistMatcher(
            self.hotlist_loader,
            cooldown_sec=hotlist_config.get("cooldown_sec", 60),
        )

        # GPS state (written by API thread, read by inference thread)
        self.gps_state = GpsState()

        # Ranking engine (written by inference thread, read by API thread)
        self.ranking_engine = RankingEngine(hotlist_matcher=self.hotlist_matcher)

        # Event publisher (ws_manager set later in _start_api_server)
        self.event_publisher = EventPublisher()

        # Evidence capture and storage
        evidence_cfg = self.config.get("evidence", {})
        evidence_root = str(BASE_DIR / evidence_cfg.get("root", "data/evidence"))
        self.snapshot_capture = SnapshotCapture(
            evidence_root=evidence_root,
            jpeg_quality=evidence_cfg.get("jpeg_quality", 85),
        )
        self.evidence_storage = EvidenceStorage(self.repo)

        # Detection fusion engine
        self.fusion_engine = DetectionFusionEngine(
            event_publisher=self.event_publisher,
            hotlist_matcher=self.hotlist_matcher,
            snapshot_capture=self.snapshot_capture,
            evidence_storage=self.evidence_storage,
            ranking_engine=self.ranking_engine,
        )

        # Scheduler
        sched_config = dict(self.config.get("scheduling", {}))
        sched_config["brightness_threshold"] = self.config.get("night_vision", {}).get("brightness_threshold", 60)
        self.scheduler = InferenceScheduler(sched_config)
        self.scheduler.set_camera_manager(self.camera_manager)
        self.scheduler.set_models(
            vehicle_detector=vehicle_det,
            plate_detector=plate_det,
            ocr=ocr,
            classifier=classifier,
            tracker_config=inf_config.get("tracker", {}),
            fusion_engine=self.fusion_engine,
            event_publisher=self.event_publisher,
        )

        # Wire GPS state into the pipeline so detections carry operator position
        if hasattr(self.scheduler, "pipeline") and self.scheduler.pipeline is not None:
            self.scheduler.pipeline.set_gps_state(self.gps_state)

        # Alert manager
        self.alert_manager = AlertManager(hotlist_config)

        # Media retention manager (background cleanup thread)
        self.retention_manager = MediaRetentionManager(
            evidence_root=evidence_root,
            retention_days=evidence_cfg.get("retention_days", 30),
        )

        # Navigation API server (FastAPI + uvicorn, daemon thread)
        # Also wires ws_manager into event_publisher
        self._start_api_server()

        logger.info("CameraManager started")

        logger.info("Initialization complete")
        return True

    def _start_api_server(self):
        """Start the FastAPI navigation server in a daemon thread."""
        from edge.api.app import create_app, ConnectionManager
        nav_cfg = self.config.get("navigation", {})
        api_cfg = self.config.get("api", {})

        # Create shared ConnectionManager so event_publisher can broadcast
        # to WebSocket clients from the inference thread.
        ws_manager = ConnectionManager()
        if self.event_publisher is not None:
            self.event_publisher.set_ws_manager(ws_manager)

        api_app = create_app(
            scheduler=self.scheduler,
            config=nav_cfg,
            api_config=api_cfg,
            ws_manager=ws_manager,
            event_publisher=self.event_publisher,
            ranking_engine=self.ranking_engine,
            gps_state=self.gps_state,
            repository=self.repo,
        )

        host = api_cfg.get("host", "0.0.0.0")
        port = api_cfg.get("port", 8080)

        api_thread = threading.Thread(
            target=uvicorn.run,
            args=(api_app,),
            kwargs={"host": host, "port": port, "log_level": "warning"},
            daemon=True,
            name="nav-api-server",
        )
        api_thread.start()
        logger.info("Navigation API server started on %s:%d", host, port)

    def start(self):
        """Start cameras and begin processing."""
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Start media retention background thread
        if self.retention_manager:
            self.retention_manager.start()

        # Start cameras
        results = self.camera_manager.start_all()
        for cam_id, success in results.items():
            if success:
                logger.info("Camera %s started", cam_id)
            else:
                logger.error("Camera %s failed to start", cam_id)

        active = self.camera_manager.active_camera_ids
        if not active:
            logger.error("No cameras started. Exiting.")
            return

        logger.info(
            "Edge service running with %d camera(s): %s",
            len(active), ", ".join(active),
        )

        self._running = True
        self._run_loop()

    def _run_loop(self):
        """Main processing loop."""
        normal_fps = self.config.get("scheduling", {}).get("vehicle_detection_fps", 15)

        while self._running:
            self._loop_count += 1

            # Thermal check
            throttle_level, gpu_temp = self.thermal.check()
            target_fps = self.thermal.get_target_fps(normal_fps)
            self.scheduler.set_detection_fps(target_fps)

            # Classifier suspend/resume based on thermal
            if self.thermal.should_suspend_classifier:
                self.scheduler.classifier.suspend()
            else:
                self.scheduler.classifier.resume()

            # Log thermal events to DB
            if throttle_level > 0 and self._loop_count % 100 == 0:
                self.repo.save_thermal_event(
                    gpu_temp, throttle_level,
                    f"throttle_level_{throttle_level}_fps_{target_fps}",
                )

            # Process frames from all cameras
            frames = self.camera_manager.get_latest_frames()
            for cam_id, packet in frames.items():
                if packet is None:
                    continue

                result = self.scheduler.process_frame(packet)
                if result is None:
                    continue  # frame skipped (rate limiting)

            # Periodic hotlist reload check
            if self._loop_count % 500 == 0:
                self.hotlist_loader.check_reload()

            # Periodic stats logging
            now = time.monotonic()
            if (now - self._last_stats_time) >= self._stats_interval:
                self._log_stats(gpu_temp)
                self._last_stats_time = now

            # Small sleep to prevent busy-waiting when no frames available
            if not any(f is not None for f in frames.values()):
                time.sleep(0.001)

    def _log_stats(self, gpu_temp: float):
        """Log periodic system statistics."""
        stats = self.monitor.get_stats(gpu_temp)
        sched_stats = self.scheduler.stats
        cam_stats = self.camera_manager.stats

        active_tracks = sum(
            len(t.confirmed_tracks)
            for t in self.scheduler.trackers.values()
        )

        logger.info(
            "Stats: GPU=%.1f°C util=%.0f%% mem=%.0f/%.0fMB "
            "det_fps=%d cams=%d tracks=%d alerts=%d detections=%d",
            stats["gpu_temp_c"],
            stats["gpu_util_pct"],
            stats["mem_used_mb"],
            stats["mem_total_mb"],
            sched_stats["current_det_fps"],
            len(self.camera_manager.active_camera_ids),
            active_tracks,
            self.alert_manager.alert_count,
            self.repo.get_detection_count(),
        )

        # Save to DB
        self.repo.save_system_stats(
            gpu_temp=stats["gpu_temp_c"],
            gpu_util=stats["gpu_util_pct"],
            mem_used_mb=stats["mem_used_mb"],
            mem_total_mb=stats["mem_total_mb"],
            det_fps=sched_stats["current_det_fps"],
            cameras_active=len(self.camera_manager.active_camera_ids),
            tracks_active=active_tracks,
        )

    def _signal_handler(self, signum, frame):
        """Handle SIGTERM/SIGINT for clean shutdown."""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, shutting down...", sig_name)
        self._running = False

    def shutdown(self):
        """Clean shutdown of all components."""
        logger.info("Shutting down edge service")
        self._running = False

        if self.camera_manager:
            self.camera_manager.stop_all()

        if self.scheduler:
            if self.scheduler.vehicle_detector:
                self.scheduler.vehicle_detector.release()
            if self.scheduler.plate_detector:
                self.scheduler.plate_detector.release()
            if self.scheduler.ocr:
                self.scheduler.ocr.release()
            if self.scheduler.classifier:
                self.scheduler.classifier.release()

        if self.snapshot_capture:
            self.snapshot_capture.shutdown(wait=True)

        if self.retention_manager:
            self.retention_manager.stop()

        if self.db:
            self.db.close()

        logger.info("Edge service stopped")


def main():
    """Entry point."""
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)
    setup_logging(config)

    service = EdgeService(config)

    if not service.initialize():
        logger.error("Initialization failed. Exiting.")
        sys.exit(1)

    try:
        service.start()
    except KeyboardInterrupt:
        pass
    finally:
        service.shutdown()


if __name__ == "__main__":
    main()
