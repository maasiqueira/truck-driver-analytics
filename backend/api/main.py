from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="TDA Fleet API", version="0.1.0")

_EVENTS: list[dict[str, Any]] = []
_DEVICES: dict[str, dict[str, Any]] = {}
_OTA_VERSION = "0.1.0"


class EventBatch(BaseModel):
    device_id: str
    events: list[dict[str, Any]]


class OtaManifest(BaseModel):
    device_id: str
    version: str


@app.post("/api/v1/telemetry/events/batch")
def ingest_events(batch: EventBatch) -> dict[str, int]:
    for ev in batch.events:
        ev["device_id"] = batch.device_id
        ev["received_at"] = datetime.now(timezone.utc).isoformat()
        _EVENTS.append(ev)
    _DEVICES[batch.device_id] = {"last_seen": datetime.now(timezone.utc).isoformat(), "event_count": len(_EVENTS)}
    return {"accepted": len(batch.events)}


@app.get("/api/v1/devices/{device_id}/events")
def list_events(device_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return [e for e in _EVENTS if e.get("device_id") == device_id][-limit:]


@app.get("/api/v1/ota/manifest")
def ota_manifest(device_id: str, version: str) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "update_available": version < _OTA_VERSION,
        "version": _OTA_VERSION,
        "bundle_url": "https://example.com/ota/models-0.1.0.tgz",
        "sha256": None,
    }


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
