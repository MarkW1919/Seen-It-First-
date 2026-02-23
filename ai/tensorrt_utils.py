"""TensorRT engine utilities for Jetson Orin Nano Super.

Optimized for sustained 25-30 FPS with:
- Pre-allocated persistent CUDA buffers (zero per-frame allocation)
- Persistent CUDA stream reuse
- Automatic ONNX-to-TensorRT engine caching
- Proper GPU memory lifecycle management
"""
import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class TRTEngine:
    """High-performance TensorRT engine wrapper with persistent GPU buffers.

    On Jetson with TensorRT available, loads .engine files directly.
    Auto-converts from ONNX if engine file is missing.
    Falls back to ONNX Runtime when TensorRT is not available.
    """

    def __init__(
        self,
        engine_path: str,
        onnx_path: str | None = None,
        fp16: bool = True,
        int8: bool = False,
        workspace_gb: float = 2.0,
    ):
        self.engine_path = engine_path
        self.onnx_path = onnx_path or engine_path.replace(".engine", ".onnx")
        self.fp16 = fp16
        self.int8 = int8
        self.workspace_gb = workspace_gb

        self._session = None
        self._trt_engine = None
        self._trt_context = None
        self._backend = None

        # Persistent CUDA resources (allocated once, reused every frame)
        self._cuda_stream = None
        self._input_buf_device = None
        self._output_bufs_device: list = []
        self._output_bufs_host: list[np.ndarray] = []
        self._input_nbytes = 0
        self._buffers_allocated = False

        self._load()

    def _load(self):
        engine_exists = os.path.exists(self.engine_path)
        onnx_exists = os.path.exists(self.onnx_path)

        # Try TensorRT first (Jetson)
        if engine_exists:
            if self._load_trt_engine():
                return
        elif onnx_exists:
            # Auto-convert ONNX to TensorRT engine
            if self._try_auto_convert():
                return

        # Fallback to ONNX Runtime
        if onnx_exists:
            self._load_onnx()
            return

        logger.warning(f"No model found at {self.engine_path} or {self.onnx_path}")
        self._backend = None

    def _load_trt_engine(self) -> bool:
        """Load a pre-built TensorRT engine file."""
        try:
            import tensorrt as trt
            import pycuda.driver as cuda
            import pycuda.autoinit  # noqa: F401

            trt_logger = trt.Logger(trt.Logger.WARNING)
            with open(self.engine_path, "rb") as f:
                runtime = trt.Runtime(trt_logger)
                self._trt_engine = runtime.deserialize_cuda_engine(f.read())

            if self._trt_engine is None:
                logger.error(f"Failed to deserialize engine: {self.engine_path}")
                return False

            self._trt_context = self._trt_engine.create_execution_context()
            self._cuda_stream = cuda.Stream()

            self._backend = "tensorrt"
            logger.info(f"Loaded TensorRT engine: {self.engine_path}")
            return True

        except ImportError:
            logger.warning("TensorRT not available, falling back to ONNX Runtime")
            return False
        except Exception as e:
            logger.error(f"Failed to load TensorRT engine: {e}")
            return False

    def _try_auto_convert(self) -> bool:
        """Auto-convert ONNX to TensorRT if TensorRT is available."""
        try:
            import tensorrt  # noqa: F401

            logger.info(
                f"TensorRT engine not found at {self.engine_path}, "
                f"auto-converting from {self.onnx_path}..."
            )
            convert_onnx_to_tensorrt(
                onnx_path=self.onnx_path,
                engine_path=self.engine_path,
                fp16=self.fp16,
                int8=self.int8,
                workspace_gb=self.workspace_gb,
            )
            if os.path.exists(self.engine_path):
                return self._load_trt_engine()
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Auto-conversion failed: {e}")
        return False

    def _load_onnx(self):
        """Load model via ONNX Runtime as fallback."""
        try:
            import onnxruntime as ort

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self._session = ort.InferenceSession(
                self.onnx_path, providers=providers
            )
            self._backend = "onnxrt"
            logger.info(f"Loaded ONNX model: {self.onnx_path}")
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            self._backend = None

    def _allocate_buffers(self, input_data: np.ndarray):
        """Allocate persistent GPU buffers on first inference call.

        Buffers are reused for every subsequent frame, eliminating the
        per-frame allocation overhead (~2ms+) and GPU memory leaks.
        """
        import pycuda.driver as cuda

        self._free_buffers()

        self._output_bufs_device = []
        self._output_bufs_host = []
        dtype = np.float32

        for i in range(self._trt_engine.num_io_tensors):
            name = self._trt_engine.get_tensor_name(i)
            mode = self._trt_engine.get_tensor_mode(name).name

            if mode == "INPUT":
                self._input_nbytes = input_data.nbytes
                self._input_buf_device = cuda.mem_alloc(input_data.nbytes)
                self._trt_context.set_tensor_address(
                    name, int(self._input_buf_device)
                )
            else:
                shape = self._trt_engine.get_tensor_shape(name)
                host_buf = np.empty(shape, dtype=dtype)
                device_buf = cuda.mem_alloc(host_buf.nbytes)
                self._output_bufs_host.append(host_buf)
                self._output_bufs_device.append(device_buf)
                self._trt_context.set_tensor_address(name, int(device_buf))

        self._buffers_allocated = True
        logger.debug(
            f"Allocated persistent CUDA buffers: "
            f"input={input_data.nbytes}B, "
            f"outputs={len(self._output_bufs_device)}"
        )

    def _free_buffers(self):
        """Explicitly free all GPU memory."""
        try:
            import pycuda.driver as cuda  # noqa: F811
        except ImportError:
            return

        if self._input_buf_device is not None:
            self._input_buf_device.free()
            self._input_buf_device = None

        for buf in self._output_bufs_device:
            buf.free()
        self._output_bufs_device = []
        self._output_bufs_host = []
        self._buffers_allocated = False

    @property
    def is_loaded(self) -> bool:
        return self._backend is not None

    def infer(self, input_data: np.ndarray) -> list[np.ndarray]:
        """Run inference on input data.

        Args:
            input_data: Preprocessed input tensor (NCHW format, float32)

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
        """TensorRT inference with pre-allocated persistent buffers.

        Returns the pre-allocated host buffers directly (no copy).
        These are overwritten on the next infer() call, so callers
        that need persistence must copy the arrays they need.
        This eliminates ~0.5ms of per-frame numpy allocation + memcpy.
        """
        import pycuda.driver as cuda

        input_data = np.ascontiguousarray(input_data, dtype=np.float32)

        # Allocate buffers once on first call (or if input shape changed)
        if not self._buffers_allocated or input_data.nbytes != self._input_nbytes:
            self._allocate_buffers(input_data)

        # Copy input to GPU (async)
        cuda.memcpy_htod_async(
            self._input_buf_device, input_data, self._cuda_stream
        )

        # Execute inference (async)
        self._trt_context.execute_async_v3(self._cuda_stream.handle)

        # Copy outputs from GPU into pre-allocated host buffers (async)
        for host_buf, device_buf in zip(
            self._output_bufs_host, self._output_bufs_device
        ):
            cuda.memcpy_dtoh_async(host_buf, device_buf, self._cuda_stream)

        # Single synchronize after all async operations
        self._cuda_stream.synchronize()

        return self._output_bufs_host

    def _infer_onnx(self, input_data: np.ndarray) -> list[np.ndarray]:
        """ONNX Runtime inference fallback."""
        input_name = self._session.get_inputs()[0].name
        results = self._session.run(
            None, {input_name: input_data.astype(np.float32)}
        )
        return results

    def close(self):
        """Release all GPU resources."""
        self._free_buffers()
        self._cuda_stream = None
        self._trt_context = None
        self._trt_engine = None
        self._session = None
        self._backend = None

    def __del__(self):
        self.close()


def convert_onnx_to_tensorrt(
    onnx_path: str,
    engine_path: str,
    fp16: bool = True,
    int8: bool = False,
    workspace_gb: float = 2.0,
    max_batch_size: int = 1,
):
    """Convert ONNX model to TensorRT engine.

    Supports FP16 and INT8 precision modes. Engine files are cached
    on disk for instant loading on subsequent runs.
    """
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

        if int8 and builder.platform_has_fast_int8:
            config.set_flag(trt.BuilderFlag.INT8)
            logger.info("INT8 mode enabled (requires calibration data)")

        # Enable DLA if available (Jetson Xavier/Orin)
        if builder.num_DLA_cores > 0:
            config.default_device_type = trt.DeviceType.DLA
            config.DLA_core = 0
            config.set_flag(trt.BuilderFlag.GPU_FALLBACK)
            logger.info(f"DLA enabled with {builder.num_DLA_cores} cores")

        logger.info(f"Building TensorRT engine from {onnx_path}...")
        engine = builder.build_serialized_network(network, config)

        if engine is None:
            raise RuntimeError("TensorRT engine build failed")

        Path(engine_path).parent.mkdir(parents=True, exist_ok=True)

        with open(engine_path, "wb") as f:
            f.write(engine)

        logger.info(f"TensorRT engine saved: {engine_path}")

    except ImportError:
        logger.error("TensorRT not available - must run on Jetson device")
        raise
