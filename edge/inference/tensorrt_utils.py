"""
SEEN IT FIRST - Edge AI Vehicle LPR System
TensorRT engine loading, conversion, and inference utilities.

Manages serialized TensorRT engine lifecycle on the Jetson Orin Nano Super:
  - Loading .engine files into GPU memory
  - CUDA buffer allocation and stream management
  - Synchronous inference with host<->device memory transfers
  - ONNX-to-TensorRT offline conversion with FP16/INT8 support

When TensorRT / PyCUDA are unavailable (development on non-Jetson machines),
a DummyEngine with identical interface is provided for testing.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from edge.utils.logging import get_logger

logger = get_logger("inference.tensorrt")

# ---------------------------------------------------------------------------
# Conditional TensorRT / PyCUDA imports
# ---------------------------------------------------------------------------

try:
    import tensorrt as trt
    import pycuda.driver as cuda
    import pycuda.autoinit  # noqa: F401 -- initialises CUDA context
    TRT_AVAILABLE = True
    logger.info("TensorRT %s and PyCUDA available", trt.__version__)
except ImportError:
    TRT_AVAILABLE = False
    trt = None  # type: ignore[assignment]
    cuda = None  # type: ignore[assignment]
    logger.warning("TensorRT/PyCUDA not available - inference will use CPU fallback")


# ---------------------------------------------------------------------------
# Dataclass for binding metadata
# ---------------------------------------------------------------------------

@dataclass
class _BindingInfo:
    """Metadata for a single TensorRT engine binding (input or output)."""
    name: str
    shape: Tuple[int, ...]
    dtype: np.dtype
    size_bytes: int
    is_input: bool


# ---------------------------------------------------------------------------
# TRTEngine -- production GPU inference wrapper
# ---------------------------------------------------------------------------

class TRTEngine:
    """
    Wraps a serialized TensorRT .engine file for synchronous inference.

    Lifecycle:
        1. ``__init__`` loads the engine, allocates CUDA buffers, creates
           an execution context and a dedicated CUDA stream.
        2. ``warmup()`` runs *n* dummy inferences to prime the GPU.
        3. ``infer()`` copies input to device, runs the network, and copies
           output back to host.
        4. ``destroy()`` releases all GPU resources.

    Not thread-safe -- use one instance per thread or guard with a lock.
    """

    def __init__(self, engine_path: str, max_batch_size: int = 1) -> None:
        if not TRT_AVAILABLE:
            raise RuntimeError(
                "TRTEngine requires tensorrt and pycuda. "
                "Use DummyEngine for CPU fallback."
            )

        self._engine_path = engine_path
        self._max_batch_size = max_batch_size
        self._destroyed = False

        if not os.path.isfile(engine_path):
            raise FileNotFoundError(f"TensorRT engine not found: {engine_path}")

        # -- TensorRT logger ------------------------------------------------
        self._trt_logger = trt.Logger(trt.Logger.WARNING)

        # -- Deserialise engine ---------------------------------------------
        t0 = time.monotonic()
        runtime = trt.Runtime(self._trt_logger)
        with open(engine_path, "rb") as f:
            engine_data = f.read()
        self._engine = runtime.deserialize_cuda_engine(engine_data)
        if self._engine is None:
            raise RuntimeError(f"Failed to deserialise engine: {engine_path}")

        load_ms = (time.monotonic() - t0) * 1000.0
        logger.info(
            "Engine loaded: %s (%.1f ms, %.2f MB)",
            engine_path,
            load_ms,
            len(engine_data) / (1024 * 1024),
        )

        # -- Execution context & stream -------------------------------------
        self._context = self._engine.create_execution_context()
        if self._context is None:
            raise RuntimeError("Failed to create TensorRT execution context")
        self._stream = cuda.Stream()

        # -- Discover bindings & allocate buffers ---------------------------
        self._bindings: List[_BindingInfo] = []
        self._host_buffers: Dict[str, np.ndarray] = {}
        self._device_buffers: Dict[str, cuda.DeviceAllocation] = {}
        self._binding_addrs: List[int] = []

        num_bindings = self._engine.num_bindings
        for idx in range(num_bindings):
            name = self._engine.get_binding_name(idx)
            shape = tuple(self._engine.get_binding_shape(idx))
            dtype = trt.nptype(self._engine.get_binding_dtype(idx))
            is_input = self._engine.binding_is_input(idx)

            size = int(np.prod(shape))
            host_buf = np.empty(shape, dtype=dtype)
            dev_buf = cuda.mem_alloc(host_buf.nbytes)

            info = _BindingInfo(
                name=name,
                shape=shape,
                dtype=dtype,
                size_bytes=host_buf.nbytes,
                is_input=is_input,
            )
            self._bindings.append(info)
            self._host_buffers[name] = host_buf
            self._device_buffers[name] = dev_buf
            self._binding_addrs.append(int(dev_buf))

            logger.debug(
                "Binding %d: %s  shape=%s  dtype=%s  input=%s  bytes=%d",
                idx, name, shape, dtype, is_input, host_buf.nbytes,
            )

        # Convenience references for the common single-input / single-output case
        self._input_bindings = [b for b in self._bindings if b.is_input]
        self._output_bindings = [b for b in self._bindings if not b.is_input]

        if not self._input_bindings:
            raise RuntimeError("Engine has no input bindings")
        if not self._output_bindings:
            raise RuntimeError("Engine has no output bindings")

        logger.info(
            "Engine ready: %d input(s), %d output(s)",
            len(self._input_bindings),
            len(self._output_bindings),
        )

    # ----- public API ------------------------------------------------------

    def warmup(self, n: int = 10) -> None:
        """Run *n* dummy inferences to warm up the GPU and TensorRT caches."""
        if self._destroyed:
            raise RuntimeError("Engine has been destroyed")

        logger.info("Warming up engine with %d iterations ...", n)
        dummy_input = np.zeros(
            self._input_bindings[0].shape,
            dtype=self._input_bindings[0].dtype,
        )
        t0 = time.monotonic()
        for _ in range(n):
            self.infer(dummy_input)
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        logger.info(
            "Warmup complete: %d iterations in %.1f ms (avg %.2f ms)",
            n, elapsed_ms, elapsed_ms / max(n, 1),
        )

    def infer(self, input_array: np.ndarray) -> np.ndarray:
        """
        Synchronous inference.

        Args:
            input_array: NumPy array matching the engine's input shape/dtype.

        Returns:
            NumPy array with the first output binding's data.
        """
        if self._destroyed:
            raise RuntimeError("Engine has been destroyed")

        in_binding = self._input_bindings[0]
        out_binding = self._output_bindings[0]

        # Ensure contiguous memory and correct dtype
        input_array = np.ascontiguousarray(
            input_array.astype(in_binding.dtype)
        )

        # Host -> Device
        cuda.memcpy_htod_async(
            self._device_buffers[in_binding.name],
            input_array,
            self._stream,
        )

        # Execute
        self._context.execute_async_v2(
            bindings=self._binding_addrs,
            stream_handle=self._stream.handle,
        )

        # Device -> Host
        output = np.empty(out_binding.shape, dtype=out_binding.dtype)
        cuda.memcpy_dtoh_async(
            output,
            self._device_buffers[out_binding.name],
            self._stream,
        )

        self._stream.synchronize()
        return output

    def infer_multi_output(self, input_array: np.ndarray) -> List[np.ndarray]:
        """
        Synchronous inference returning all output bindings.

        Args:
            input_array: NumPy array matching the engine's input shape/dtype.

        Returns:
            List of NumPy arrays, one per output binding in binding order.
        """
        if self._destroyed:
            raise RuntimeError("Engine has been destroyed")

        in_binding = self._input_bindings[0]

        input_array = np.ascontiguousarray(
            input_array.astype(in_binding.dtype)
        )

        # Host -> Device
        cuda.memcpy_htod_async(
            self._device_buffers[in_binding.name],
            input_array,
            self._stream,
        )

        # Execute
        self._context.execute_async_v2(
            bindings=self._binding_addrs,
            stream_handle=self._stream.handle,
        )

        # Device -> Host (all outputs)
        outputs: List[np.ndarray] = []
        for ob in self._output_bindings:
            buf = np.empty(ob.shape, dtype=ob.dtype)
            cuda.memcpy_dtoh_async(
                buf,
                self._device_buffers[ob.name],
                self._stream,
            )
            outputs.append(buf)

        self._stream.synchronize()
        return outputs

    def get_input_shape(self) -> Tuple[int, ...]:
        """Return the shape of the first input binding."""
        return self._input_bindings[0].shape

    def get_output_shape(self) -> Tuple[int, ...]:
        """Return the shape of the first output binding."""
        return self._output_bindings[0].shape

    def get_memory_usage(self) -> int:
        """Return total GPU memory allocated for buffers, in bytes."""
        return sum(b.size_bytes for b in self._bindings)

    def destroy(self) -> None:
        """Free all GPU resources. Safe to call multiple times."""
        if self._destroyed:
            return
        self._destroyed = True

        for name, dev_buf in self._device_buffers.items():
            try:
                dev_buf.free()
            except Exception:
                logger.warning("Failed to free device buffer: %s", name)

        self._device_buffers.clear()
        self._host_buffers.clear()
        self._binding_addrs.clear()

        if self._context is not None:
            del self._context
            self._context = None

        if self._engine is not None:
            del self._engine
            self._engine = None

        logger.info("Engine destroyed: %s", self._engine_path)

    def __del__(self) -> None:
        self.destroy()

    def __repr__(self) -> str:
        return (
            f"TRTEngine(path={self._engine_path!r}, "
            f"inputs={len(self._input_bindings)}, "
            f"outputs={len(self._output_bindings)})"
        )


# ---------------------------------------------------------------------------
# ONNX -> TensorRT offline conversion
# ---------------------------------------------------------------------------

def convert_onnx_to_tensorrt(
    onnx_path: str,
    engine_path: str,
    fp16: bool = True,
    int8: bool = False,
    max_batch: int = 1,
) -> str:
    """
    Convert an ONNX model to a serialized TensorRT engine.

    Args:
        onnx_path:   Path to source ONNX model.
        engine_path: Destination path for the serialized .engine file.
        fp16:        Enable FP16 precision (recommended for Jetson).
        int8:        Enable INT8 precision (requires calibration data).
        max_batch:   Maximum batch size baked into the engine.

    Returns:
        The *engine_path* on success.

    Raises:
        RuntimeError: If TensorRT is unavailable or conversion fails.
    """
    if not TRT_AVAILABLE:
        raise RuntimeError("TensorRT is required for ONNX conversion")

    if not os.path.isfile(onnx_path):
        raise FileNotFoundError(f"ONNX model not found: {onnx_path}")

    logger.info(
        "Converting ONNX -> TensorRT: %s  (fp16=%s, int8=%s, max_batch=%d)",
        onnx_path, fp16, int8, max_batch,
    )
    t0 = time.monotonic()

    trt_logger = trt.Logger(trt.Logger.WARNING)

    # -- Builder & network ---------------------------------------------------
    builder = trt.Builder(trt_logger)
    network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    network = builder.create_network(network_flags)
    parser = trt.OnnxParser(network, trt_logger)

    with open(onnx_path, "rb") as f:
        if not parser.parse(f.read()):
            for i in range(parser.num_errors):
                logger.error("ONNX parse error: %s", parser.get_error(i))
            raise RuntimeError(f"Failed to parse ONNX model: {onnx_path}")

    # -- Builder config ------------------------------------------------------
    config = builder.create_builder_config()
    config.max_workspace_size = 1 << 30  # 1 GiB workspace

    if fp16 and builder.platform_has_fast_fp16:
        config.set_flag(trt.BuilderFlag.FP16)
        logger.info("FP16 enabled")

    if int8 and builder.platform_has_fast_int8:
        config.set_flag(trt.BuilderFlag.INT8)
        logger.info("INT8 enabled (calibration cache must be provided separately)")

    # Set explicit batch dimension profile
    profile = builder.create_optimization_profile()
    for i in range(network.num_inputs):
        inp = network.get_input(i)
        shape = list(inp.shape)
        # Replace dynamic batch dim (-1) with concrete values
        min_shape = [1 if s == -1 else s for s in shape]
        opt_shape = [max_batch if s == -1 else s for s in shape]
        max_shape = [max_batch if s == -1 else s for s in shape]
        profile.set_shape(
            inp.name,
            tuple(min_shape),
            tuple(opt_shape),
            tuple(max_shape),
        )
    config.add_optimization_profile(profile)

    # -- Build engine --------------------------------------------------------
    engine = builder.build_engine(network, config)
    if engine is None:
        raise RuntimeError("TensorRT engine build failed")

    serialized = engine.serialize()

    # -- Write to disk -------------------------------------------------------
    os.makedirs(os.path.dirname(engine_path) or ".", exist_ok=True)
    with open(engine_path, "wb") as f:
        f.write(serialized)

    elapsed_s = time.monotonic() - t0
    size_mb = os.path.getsize(engine_path) / (1024 * 1024)

    logger.info(
        "Engine saved: %s  (%.1f s, %.2f MB)",
        engine_path, elapsed_s, size_mb,
    )

    return engine_path


# ---------------------------------------------------------------------------
# DummyEngine -- CPU fallback for development / testing
# ---------------------------------------------------------------------------

class DummyEngine:
    """
    Drop-in replacement for ``TRTEngine`` when TensorRT is not available.

    Returns zero arrays matching the expected output shape.  Useful for
    integration testing the pipeline on non-Jetson development machines.
    """

    def __init__(
        self,
        engine_path: str,
        max_batch_size: int = 1,
        input_shape: Tuple[int, ...] = (1, 3, 640, 640),
        output_shape: Tuple[int, ...] = (1, 84, 8400),
        num_outputs: int = 1,
    ) -> None:
        self._engine_path = engine_path
        self._max_batch_size = max_batch_size
        self._input_shape = input_shape
        self._output_shape = output_shape
        self._num_outputs = num_outputs
        self._destroyed = False

        logger.info(
            "DummyEngine created (CPU fallback): %s  "
            "input=%s  output=%s  num_outputs=%d",
            engine_path, input_shape, output_shape, num_outputs,
        )

    def warmup(self, n: int = 10) -> None:
        """No-op warmup for dummy engine."""
        logger.debug("DummyEngine warmup (no-op, %d iterations)", n)

    def infer(self, input_array: np.ndarray) -> np.ndarray:
        """Return zeros matching the configured output shape."""
        if self._destroyed:
            raise RuntimeError("Engine has been destroyed")
        return np.zeros(self._output_shape, dtype=np.float32)

    def infer_multi_output(self, input_array: np.ndarray) -> List[np.ndarray]:
        """Return list of zero arrays for each output."""
        if self._destroyed:
            raise RuntimeError("Engine has been destroyed")
        return [
            np.zeros(self._output_shape, dtype=np.float32)
            for _ in range(self._num_outputs)
        ]

    def get_input_shape(self) -> Tuple[int, ...]:
        return self._input_shape

    def get_output_shape(self) -> Tuple[int, ...]:
        return self._output_shape

    def get_memory_usage(self) -> int:
        """Return 0 -- no GPU memory used."""
        return 0

    def destroy(self) -> None:
        """Mark as destroyed."""
        self._destroyed = True
        logger.debug("DummyEngine destroyed: %s", self._engine_path)

    def __del__(self) -> None:
        self.destroy()

    def __repr__(self) -> str:
        return f"DummyEngine(path={self._engine_path!r})"


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def load_engine(
    engine_path: str,
    max_batch_size: int = 1,
    input_shape: Tuple[int, ...] = (1, 3, 640, 640),
    output_shape: Tuple[int, ...] = (1, 84, 8400),
    num_outputs: int = 1,
) -> "TRTEngine | DummyEngine":
    """
    Load a TRTEngine if TensorRT is available, otherwise return a DummyEngine.

    This is the recommended factory for all inference modules so they work
    transparently on both Jetson and development machines.
    """
    if TRT_AVAILABLE:
        return TRTEngine(engine_path, max_batch_size=max_batch_size)
    else:
        logger.warning(
            "TensorRT unavailable -- using DummyEngine for %s", engine_path,
        )
        return DummyEngine(
            engine_path,
            max_batch_size=max_batch_size,
            input_shape=input_shape,
            output_shape=output_shape,
            num_outputs=num_outputs,
        )
