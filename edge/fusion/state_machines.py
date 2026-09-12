from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from edge.fusion.events import EventType


@dataclass
class PendingEvent:
    event_type: EventType
    started_mono: float
    severity: int
    metadata: dict = field(default_factory=dict)


@dataclass
class StateMachine:
    name: str
    active: bool = False
    started_mono: float = 0.0
    metadata: dict = field(default_factory=dict)

    def begin(self, ts: float, **meta) -> None:
        if not self.active:
            self.active = True
            self.started_mono = ts
            self.metadata = meta

    def end(self) -> float:
        if not self.active:
            return 0.0
        dur = time.monotonic() - self.started_mono
        self.active = False
        self.metadata = {}
        return dur


class PhoneConfirmMachine:
    """celular_suspeito -> PHONE_USE após N janelas consecutivas."""

    def __init__(self, window_s: float, confirm_windows: int):
        self.window_s = window_s
        self.confirm_windows = confirm_windows
        self._windows: deque[bool] = deque(maxlen=confirm_windows)
        self._window_start = 0.0
        self._seen_in_window = False

    def tick(self, ts: float, phone_detected: bool) -> bool:
        if self._window_start == 0.0:
            self._window_start = ts
        if phone_detected:
            self._seen_in_window = True
        if ts - self._window_start >= self.window_s:
            self._windows.append(self._seen_in_window)
            self._window_start = ts
            self._seen_in_window = False
            if len(self._windows) == self.confirm_windows and all(self._windows):
                self._windows.clear()
                return True
        return False


class PerclosTracker:
    def __init__(self, window_s: float, ratio_threshold: float, duration_s: float):
        self.window_s = window_s
        self.ratio_threshold = ratio_threshold
        self.duration_s = duration_s
        self._samples: deque[tuple[float, bool]] = deque()
        self._overload_since: float | None = None

    def tick(self, ts: float, eyes_closed: bool) -> bool:
        self._samples.append((ts, eyes_closed))
        while self._samples and ts - self._samples[0][0] > self.window_s:
            self._samples.popleft()
        if not self._samples:
            return False
        ratio = sum(1 for _, c in self._samples if c) / len(self._samples)
        if ratio >= self.ratio_threshold:
            if self._overload_since is None:
                self._overload_since = ts
            elif ts - self._overload_since >= self.duration_s:
                self._overload_since = None
                return True
        else:
            self._overload_since = None
        return False
