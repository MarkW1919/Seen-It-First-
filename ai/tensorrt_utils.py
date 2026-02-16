"""TensorRT engine utilities for Jetson Orin Nano Super."""
import logging
import os

import numpy as np

logger = logging.getLogger(__name__)


class TRTEngine:
    """Wrapper for TensorRT engine inference.

    On Jetson with TensorRT available, loads .engine files directly.
    Falls back to ONNX Runtime when TensorRT is not available.
    """

    def __init__(self, engine_path: str, onnx_path: str | None = None):
        self.engine_path = engine_path
        self.onnx_path = onnx_path
        self._session = None
        self._trt_engine = None
        self._trt_context = None
        self._backend = None

        self._load()

    def _load(self):
        # Try TensorRT first (Jetson)
        if os.path.exists(self.engine_path):
            try:
                import tensorrt as trt
                import pycuda.driver as cuda
                import pycuda.autoinit  # noqa: F401

                trt_logger = trt.Logger(trt.Logger.WARNING)
                with open(self.engine_path, "rb") as f:
                    runtime = trt.Runtime(trt_logger)
                    self._trt_engine = runtime.deserialize_cuda_engine(f.read())
                    self._trt_context = self._trt_engine.create_execution_context()
                    self._backend = "tensorrt"
                    logger.info(f"Loaded TensorRT engine: {self.engine_path}")
                    return
            except ImportError:
                logger.warning("TensorRT not available, falling back to ONNX Runtime")

        # Fallback to ONNX Runtime
        onnx_path = self.onnx_path or self.engine_path.replace(".engine", ".onnx")
        if os.path.exists(onnx_path):
            try:
                import onnxruntime as ort

                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                self._session = ort.InferenceSession(onnx_path, providers=providers)
                self._backend = "onnxrt"
                logger.info(f"Loaded ONNX model: {onnx_path}")
                return
            except Exception as e:
                logger.error(f"Failed to load ONNX model: {e}")

        logger.warning(f"No model found at {self.engine_path} or {onnx_path}")
        self._backend = None

    @property
    def is_loaded(self) -> bool:
        return self._backend is not None

    def infer(self, input_data: np.ndarray) -> list[np.ndarray]:
        """Run inference on input data.

        Args:
            input_data: Preprocessed input tensor (NCHW format)

        Returns:
            List of output arrays
        """
        if self._backend == "tensorrt":
            return self._infer_trt(input_data)
        elif self._backend == "onnxrt":
            return self._infer_onnx(input_data)
        else:
            raise RuntimeError("No model loaded")

    def _infer_trt(self, input_data: np.ndarray) -> list[np.ndarray]:
        import pycuda.driver as cuda

        # Allocate buffers
        bindings = []
        outputs = []
        stream = cuda.Stream()

        for i in range(self._trt_engine.num_io_tensors):
            name = self._trt_engine.get_tensor_name(i)
            shape = self._trt_engine.get_tensor_shape(name)
            dtype = np.float32

            if self._trt_engine.get_tensor_mode(name).name == "INPUT":
                buf = cuda.mem_alloc(input_data.nbytes)
                cuda.memcpy_htod_async(buf, input_data.astype(dtype), stream)
                bindings.append(int(buf))
                self._trt_context.set_tensor_address(name, int(buf))
            else:
                out = np.empty(shape, dtype=dtype)
                buf = cuda.mem_alloc(out.nbytes)
                bindings.append(int(buf))
                outputs.append((out, buf))
                self._trt_context.set_tensor_address(name, int(buf))

        self._trt_context.execute_async_v3(stream.handle)
        stream.synchronize()

        results = []
        for out, buf in outputs:
            cuda.memcpy_dtoh(out, buf)
            results.append(out)

        return results

    def _infer_onnx(self, input_data: np.ndarray) -> list[np.ndarray]:
        input_name = self._session.get_inputs()[0].name
        results = self._session.run(None, {input_name: input_data.astype(np.float32)})
        return results


def convert_onnx_to_tensorrt(
    onnx_path: str,
    engine_path: str,
    fp16: bool = True,
    max_batch_size: int = 1,
    workspace_gb: float = 2.0,
):
    """Convert ONNX model to TensorRT engine (run on Jetson)."""
    try:
        import tensorrt as trt

        logger_trt = trt.Logger(trt.Logger.INFO)
        builder = trt.Builder(logger_trt)
        network = builder.create_network(
            1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        )
        parser = trt.OnnxParser(network, logger_trt)

        with open(onnx_path, "rb") as f:
            if not parser.parse(f.read()):
                for i in range(parser.num_errors):
                    logger.error(f"ONNX parse error: {parser.get_error(i)}")
                raise RuntimeError("Failed to parse ONNX model")

        config = builder.create_builder_config()
        config.set_memory_pool_limit(
            trt.MemoryPoolType.WORKSPACE, int(workspace_gb * (1 << 30))
        )

        if fp16 and builder.platform_has_fast_fp16:
            config.set_flag(trt.BuilderFlag.FP16)
            logger.info("FP16 mode enabled")

        engine = builder.build_serialized_network(network, config)
        with open(engine_path, "wb") as f:
            f.write(engine)

        logger.info(f"TensorRT engine saved: {engine_path}")

    except ImportError:
        logger.error("TensorRT not available - must run on Jetson device")
