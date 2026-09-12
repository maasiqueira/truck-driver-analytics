"""Generate synthetic driver.mp4 and road.mp4 for dev_sim smoke tests."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np


def generate_driver(path: Path, width: int = 640, height: int = 480, fps: int = 15, seconds: int = 30) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    total = fps * seconds
    cx, cy = width // 2, height // 2 - 20
    for i in range(total):
        frame = np.full((height, width, 3), 48, dtype=np.uint8)
        t = i / fps
        # Cabeça
        cv2.ellipse(frame, (cx, cy), (90, 110), 0, 0, 360, (180, 150, 130), -1)
        # Olhos fecham a cada ~5s por ~1.5s (sonolência simulada)
        phase = t % 5.0
        eyes_closed = phase > 3.5
        eye_y = cy - 15
        for ex in (cx - 35, cx + 35):
            if eyes_closed:
                cv2.line(frame, (ex - 18, eye_y), (ex + 18, eye_y), (40, 30, 25), 3)
            else:
                cv2.circle(frame, (ex, eye_y), 14, (255, 255, 255), -1)
                cv2.circle(frame, (ex, eye_y), 6, (20, 20, 20), -1)
        # Distração: cabeça desloca entre 12–18s
        offset = int(40 * math.sin(t * 0.8)) if 12 < t < 18 else 0
        cv2.rectangle(frame, (cx + offset - 8, cy + 35), (cx + offset + 8, cy + 55), (60, 40, 40), -1)
        # Celular simulado 20–24s
        if 20 < t < 24:
            cv2.rectangle(frame, (cx + 60, cy + 10), (cx + 95, cy + 70), (30, 30, 180), -1)
        writer.write(frame)
    writer.release()


def generate_road(path: Path, width: int = 640, height: int = 480, fps: int = 15, seconds: int = 30) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    total = fps * seconds
    for i in range(total):
        frame = np.full((height, width, 3), (90, 90, 90), dtype=np.uint8)
        t = i / fps
        # Faixas convergentes
        for lane in (-1, 1):
            x1 = width // 2 + lane * 40
            x2 = width // 2 + lane * 180
            cv2.line(frame, (x1, height), (x2, int(height * 0.45)), (240, 240, 240), 4)
        # Desvio de faixa 8–12s (linhas deslocadas)
        shift = 80 if 8 < t < 12 else 0
        if shift:
            frame = np.roll(frame, shift, axis=1)
        # Veículo à frente (tailgating) 15–22s — bbox cresce
        if 15 < t < 22:
            progress = (t - 15) / 7.0
            bh = int(40 + progress * 120)
            bw = int(bh * 0.7)
            bx = width // 2 - bw // 2
            by = int(height * 0.55) - bh
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 0, 200), -1)
        writer.write(frame)
    writer.release()


def main() -> None:
    out = Path("data/samples")
    out.mkdir(parents=True, exist_ok=True)
    driver = out / "driver.mp4"
    road = out / "road.mp4"
    generate_driver(driver)
    generate_road(road)
    print(f"created {driver} ({driver.stat().st_size // 1024} KB)")
    print(f"created {road} ({road.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
