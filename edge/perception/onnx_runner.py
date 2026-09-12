from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class InferenceResult:
    stream: str
    timestamp_mono: float
    detections: list[dict[str, Any]]
    metrics: dict[str, float]
    raw: dict[str, Any] | None = None


class OnnxRunner:
    """ONNX Runtime wrapper — CPU on dev; AM67A can use ORT + EP or TIDL delegate."""

    def __init__(self, model_path: str, input_name: str | None = None):
        self.model_path = Path(model_path)
        self.session = None
        self.input_name = input_name
        if self.model_path.exists():
            import onnxruntime as ort

            providers = ort.get_available_providers()
            prefer = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            use = [p for p in prefer if p in providers] or providers
            self.session = ort.InferenceSession(str(self.model_path), providers=use)
            if self.input_name is None:
                self.input_name = self.session.get_inputs()[0].name

    @property
    def ready(self) -> bool:
        return self.session is not None

    def run(self, tensor: np.ndarray) -> list[np.ndarray]:
        if self.session is None:
            raise FileNotFoundError(f"ONNX model missing: {self.model_path}")
        feeds = {self.input_name: tensor}
        return self.session.run(None, feeds)
