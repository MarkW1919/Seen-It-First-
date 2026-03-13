"""
ONNX Runtime inference engine wrapper.

Provides the same load()/infer()/release() interface as TRTEngine so that
ONNX-backed models can be swapped in without touching the calling code.

Falls back gracefully when onnxruntime is not installed.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
    # Prefer GPU execution provider, fall back to CPU
    _PROVIDERS = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers()
        else ["CPUExecutionProvider"]
    )
    logger.debug("ONNX Runtime available — providers: %s", _PROVIDERS)
except ImportError:
    _ORT_AVAILABLE = False
    logger.warning("onnxruntime not installed. ONNX inference will not run.")


class OnnxEngine:
    """
    Wraps an ONNX model for synchronous inference.

    Matches the TRTEngine interface so callers are provider-agnostic.

    Usage::

        engine = OnnxEngine("/path/to/model.onnx")
        if engine.load():
            outputs = engine.infer(blob)   # blob: [1, C, H, W] float32 ndarray
    """

    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self._session: "ort.InferenceSession | None" = None
        self._input_name: str = ""
        self._output_names: list[str] = []
        self._loaded = False

    def load(self) -> bool:
        """Load the ONNX model and create an InferenceSession."""
        if self._loaded:
            return True  # already loaded — skip redundant session creation

        if not _ORT_AVAILABLE:
            logger.error("onnxruntime not available — cannot load %s", self.model_path)
            return False

        if not self.model_path.exists():
            logger.error("ONNX model not found: %s", self.model_path)
            return False

        try:
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.intra_op_num_threads = 2

            self._session = ort.InferenceSession(
                str(self.model_path),
                sess_options=opts,
                providers=_PROVIDERS,
            )
            self._input_name  = self._session.get_inputs()[0].name
            self._output_names = [o.name for o in self._session.get_outputs()]
            self._loaded = True

            size_mb = self.model_path.stat().st_size / (1024 * 1024)
            logger.info(
                "ONNX model loaded: %s (%.1f MB, %d output(s)) via %s",
                self.model_path.name, size_mb, len(self._output_names),
                self._session.get_providers()[0],
            )
            return True

        except Exception:
            logger.exception("Failed to load ONNX model: %s", self.model_path)
            return False

    def infer(self, input_data: np.ndarray) -> list[np.ndarray]:
        """
        Run synchronous inference.

        Args:
            input_data: Preprocessed input tensor (NCHW, float32).

        Returns:
            List of output numpy arrays, one per model output.

        Raises:
            RuntimeError: If the engine has not been loaded.
        """
        if not self._loaded or self._session is None:
            raise RuntimeError("OnnxEngine not loaded — call load() first")

        result = self._session.run(
            self._output_names,
            {self._input_name: input_data.astype(np.float32)},
        )
        return result

    def release(self):
        """Free session resources."""
        self._session = None
        self._loaded = False
        logger.debug("OnnxEngine released: %s", self.model_path.name)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def output_count(self) -> int:
        return len(self._output_names)
