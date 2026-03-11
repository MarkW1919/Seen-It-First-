"""
Model loader: ONNX → TensorRT engine builder and cache manager.

Responsibilities:
- Check engine cache (models/*.engine); skip build if present
- Build FP16/INT8 TensorRT engines from ONNX sources
- Verify GPU compatibility before build
- Report build status per model

Phase 1: All models are pretrained. No training code here.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import tensorrt as trt
    TRT_AVAILABLE = True
except ImportError:
    TRT_AVAILABLE = False
    logger.warning("TensorRT not available. Engine building disabled.")


class ModelLoader:
    """
    Loads or builds TensorRT engines from ONNX models.

    Engine files are cached on disk. Subsequent calls with the same
    engine_path skip the build step entirely.

    Usage:
        loader = ModelLoader()
        gpu_info = loader.verify_gpu()
        ok = loader.load_or_build(
            onnx_path="models/raw/yolov8n.onnx",
            engine_path="models/vehicle/vehicle.engine",
            precision="fp16",
        )
    """

    def __init__(self, workspace_gb: float = 2.0):
        """
        Args:
            workspace_gb: TensorRT builder workspace limit in GB.
                          2 GB is safe for Jetson Orin Nano Super.
        """
        self.workspace_gb = workspace_gb
        self._trt_logger = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_gpu(self) -> dict:
        """
        Check GPU availability and return capability info.

        Returns:
            Dict with keys: trt_available, trt_version, cuda_available,
            device_name, total_memory_mb, fp16_supported, int8_supported.
        """
        info: dict = {
            "trt_available": TRT_AVAILABLE,
            "trt_version": None,
            "cuda_available": False,
            "device_name": "unknown",
            "total_memory_mb": 0,
            "fp16_supported": False,
            "int8_supported": False,
        }

        if not TRT_AVAILABLE:
            return info

        info["trt_version"] = trt.__version__

        try:
            import pycuda.driver as cuda
            import pycuda.autoinit  # noqa: F401

            device = cuda.Device(0)
            info["cuda_available"] = True
            info["device_name"] = device.name()
            info["total_memory_mb"] = device.total_memory() // (1024 * 1024)
        except Exception as exc:
            logger.warning("PyCUDA device query failed: %s", exc)
            return info

        # Check precision support via a throw-away builder
        try:
            builder = trt.Builder(self._get_trt_logger())
            info["fp16_supported"] = builder.platform_has_fast_fp16
            info["int8_supported"] = builder.platform_has_fast_int8
        except Exception as exc:
            logger.warning("TRT builder precision check failed: %s", exc)

        return info

    def load_or_build(
        self,
        onnx_path: str | Path,
        engine_path: str | Path,
        precision: str = "fp16",
        input_shape: tuple | None = None,
    ) -> bool:
        """
        Return True when the engine is ready (cached or freshly built).

        If engine_path exists on disk, returns True immediately (cache hit).
        Otherwise deserializes onnx_path and builds the TensorRT engine.

        Args:
            onnx_path: Source ONNX model path.
            engine_path: Destination .engine file path.
            precision: "fp32", "fp16", or "int8".
            input_shape: Optional fixed input shape (N, C, H, W).
                         Required when the ONNX model has dynamic axes.

        Returns:
            True on success, False on any error.
        """
        engine_path = Path(engine_path)
        onnx_path = Path(onnx_path)

        if engine_path.exists():
            size_mb = engine_path.stat().st_size / (1024 * 1024)
            logger.info(
                "Engine cache hit: %s (%.1f MB)", engine_path.name, size_mb
            )
            return True

        if not onnx_path.exists():
            logger.error("ONNX source not found: %s", onnx_path)
            return False

        if not TRT_AVAILABLE:
            logger.error(
                "TensorRT unavailable — cannot build %s", engine_path.name
            )
            return False

        logger.info(
            "Building %s engine: %s → %s",
            precision.upper(), onnx_path.name, engine_path.name,
        )
        return self._build_engine(onnx_path, engine_path, precision, input_shape)

    def build_all(self, model_specs: list[dict]) -> dict[str, bool]:
        """
        Build multiple engines from a spec list.

        Each spec dict:
            onnx        (str)   : path to ONNX file
            engine      (str)   : path for output .engine
            precision   (str)   : "fp16" | "fp32" | "int8"  (default "fp16")
            input_shape (tuple) : optional fixed shape

        Returns:
            {engine_stem: success_bool}
        """
        results: dict[str, bool] = {}
        for spec in model_specs:
            stem = Path(spec["engine"]).stem
            results[stem] = self.load_or_build(
                onnx_path=spec["onnx"],
                engine_path=spec["engine"],
                precision=spec.get("precision", "fp16"),
                input_shape=spec.get("input_shape"),
            )
            status = "OK" if results[stem] else "FAILED"
            logger.info("  %-20s %s", stem, status)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_trt_logger(self) -> "trt.Logger":
        if self._trt_logger is None:
            self._trt_logger = trt.Logger(trt.Logger.WARNING)
        return self._trt_logger

    def _build_engine(
        self,
        onnx_path: Path,
        engine_path: Path,
        precision: str,
        input_shape: tuple | None,
    ) -> bool:
        trt_logger = self._get_trt_logger()
        builder = trt.Builder(trt_logger)

        network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        network = builder.create_network(network_flags)
        parser = trt.OnnxParser(network, trt_logger)

        with open(onnx_path, "rb") as f:
            if not parser.parse(f.read()):
                for i in range(parser.num_errors):
                    logger.error("ONNX parse error [%d]: %s", i, parser.get_error(i))
                return False

        config = builder.create_builder_config()
        config.set_memory_pool_limit(
            trt.MemoryPoolType.WORKSPACE,
            int(self.workspace_gb * 1024 ** 3),
        )

        # Precision flags
        if precision == "fp16":
            if builder.platform_has_fast_fp16:
                config.set_flag(trt.BuilderFlag.FP16)
            else:
                logger.warning("FP16 not supported on this platform; using FP32")
        elif precision == "int8":
            if builder.platform_has_fast_int8:
                config.set_flag(trt.BuilderFlag.INT8)
                logger.warning(
                    "INT8 enabled without calibration — accuracy may degrade"
                )
            else:
                logger.warning("INT8 not supported; falling back to FP16/FP32")
                if builder.platform_has_fast_fp16:
                    config.set_flag(trt.BuilderFlag.FP16)

        # Static shape optimization profile (required for dynamic-axis ONNX)
        if input_shape is not None:
            profile = builder.create_optimization_profile()
            input_name = network.get_input(0).name
            profile.set_shape(input_name, input_shape, input_shape, input_shape)
            config.add_optimization_profile(profile)

        engine_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = builder.build_serialized_network(network, config)
        if serialized is None:
            logger.error("TRT engine build returned None for %s", onnx_path.name)
            return False

        with open(engine_path, "wb") as f:
            f.write(serialized)

        size_mb = engine_path.stat().st_size / (1024 * 1024)
        logger.info("Engine saved: %s (%.1f MB)", engine_path, size_mb)
        return True
