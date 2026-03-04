"""
TensorRT engine loading and inference utilities.

Handles engine deserialization, CUDA memory allocation, and synchronous
inference for all models in the pipeline.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import tensorrt as trt
    import pycuda.driver as cuda
    import pycuda.autoinit  # noqa: F401 - initializes CUDA context
    TRT_AVAILABLE = True
except ImportError:
    TRT_AVAILABLE = False
    logger.warning("TensorRT/PyCUDA not available. Inference will not run.")


class TRTEngine:
    """
    Wraps a TensorRT engine for synchronous inference.

    Allocates device memory for input/output tensors on load.
    Provides a simple infer() method that copies data to GPU,
    runs the engine, and copies results back.
    """

    def __init__(self, engine_path: str):
        self.engine_path = Path(engine_path)
        self.engine = None
        self.context = None
        self.stream = None
        self.bindings = []
        self.inputs: list[dict] = []
        self.outputs: list[dict] = []
        self._loaded = False

    def load(self) -> bool:
        """Deserialize engine and allocate CUDA memory."""
        if not TRT_AVAILABLE:
            logger.error("TensorRT not available")
            return False

        if not self.engine_path.exists():
            logger.error("Engine file not found: %s", self.engine_path)
            return False

        logger.info("Loading TensorRT engine: %s", self.engine_path)
        trt_logger = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(trt_logger)

        with open(self.engine_path, "rb") as f:
            engine_data = f.read()

        self.engine = runtime.deserialize_cuda_engine(engine_data)
        if self.engine is None:
            logger.error("Failed to deserialize engine: %s", self.engine_path)
            return False

        self.context = self.engine.create_execution_context()
        self.stream = cuda.Stream()

        # Allocate host and device buffers for each binding
        for i in range(self.engine.num_bindings):
            name = self.engine.get_binding_name(i)
            dtype = trt.nptype(self.engine.get_binding_dtype(i))
            shape = self.engine.get_binding_shape(i)

            # Replace -1 (dynamic) with 1 for allocation sizing
            alloc_shape = tuple(max(1, s) for s in shape)
            size = int(np.prod(alloc_shape))

            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)

            self.bindings.append(int(device_mem))
            binding_info = {
                "name": name,
                "shape": shape,
                "dtype": dtype,
                "host": host_mem,
                "device": device_mem,
                "size": size,
            }

            if self.engine.binding_is_input(i):
                self.inputs.append(binding_info)
            else:
                self.outputs.append(binding_info)

        self._loaded = True
        engine_size_mb = self.engine_path.stat().st_size / (1024 * 1024)
        logger.info(
            "Engine loaded: %s (%.1f MB, %d inputs, %d outputs)",
            self.engine_path.name, engine_size_mb,
            len(self.inputs), len(self.outputs),
        )
        return True

    def infer(self, input_data: np.ndarray) -> list[np.ndarray]:
        """
        Run synchronous inference.

        Args:
            input_data: Preprocessed input tensor as numpy array (NCHW).

        Returns:
            List of output numpy arrays.
        """
        if not self._loaded:
            raise RuntimeError("Engine not loaded. Call load() first.")

        # Copy input to host buffer
        np.copyto(self.inputs[0]["host"], input_data.ravel())

        # Transfer input to device
        cuda.memcpy_htod_async(
            self.inputs[0]["device"],
            self.inputs[0]["host"],
            self.stream,
        )

        # Execute
        self.context.execute_async_v2(
            bindings=self.bindings,
            stream_handle=self.stream.handle,
        )

        # Transfer outputs back to host
        results = []
        for out in self.outputs:
            cuda.memcpy_dtoh_async(out["host"], out["device"], self.stream)

        self.stream.synchronize()

        for out in self.outputs:
            result = out["host"].copy().reshape(out["shape"])
            results.append(result)

        return results

    def release(self):
        """Free CUDA resources."""
        if self.stream is not None:
            self.stream.synchronize()
        for inp in self.inputs:
            inp["device"].free()
        for out in self.outputs:
            out["device"].free()
        self.inputs.clear()
        self.outputs.clear()
        self.bindings.clear()
        self.context = None
        self.engine = None
        self._loaded = False
        logger.info("Engine released: %s", self.engine_path.name)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def __del__(self):
        if self._loaded:
            self.release()
