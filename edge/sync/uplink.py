from __future__ import annotations

import hashlib
import logging
import shutil
import threading
import time
from pathlib import Path

import httpx

from edge.storage.db import EventStore

log = logging.getLogger(__name__)


class SyncWorker:
    def __init__(
        self,
        store: EventStore,
        api_base: str,
        device_id: str,
        interval_s: float = 60.0,
        batch_size: int = 50,
    ):
        self.store = store
        self.api_base = api_base.rstrip("/")
        self.device_id = device_id
        self.interval_s = interval_s
        self.batch_size = batch_size
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.flush_once()
            except Exception:
                log.exception("sync failed")
            time.sleep(self.interval_s)

    def flush_once(self) -> None:
        pending = self.store.pending_sync(self.batch_size)
        if not pending:
            return
        payloads = [p["payload"] for p in pending]
        ids = [p["id"] for p in pending]
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.api_base}/telemetry/events/batch",
                json={"device_id": self.device_id, "events": payloads},
            )
            resp.raise_for_status()
        self.store.mark_synced(ids)
        log.info("synced %d events", len(ids))


class OtaManager:
    """Download model bundles via STM32MP157 4G link."""

    def __init__(self, models_dir: Path, api_base: str, device_id: str):
        self.models_dir = models_dir
        self.api_base = api_base.rstrip("/")
        self.device_id = device_id

    def check_and_apply(self, current_version: str) -> str:
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(
                f"{self.api_base}/ota/manifest",
                params={"device_id": self.device_id, "version": current_version},
            )
            resp.raise_for_status()
            manifest = resp.json()
        if not manifest.get("update_available"):
            return current_version
        url = manifest["bundle_url"]
        expected = manifest.get("sha256")
        tmp = self.models_dir / "_ota_bundle.tgz"
        with httpx.stream("GET", url, timeout=120.0) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        if expected:
            digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
            if digest != expected:
                tmp.unlink(missing_ok=True)
                raise ValueError("OTA checksum mismatch")
        import tarfile

        with tarfile.open(tmp, "r:gz") as tar:
            tar.extractall(self.models_dir)
        tmp.unlink(missing_ok=True)
        return manifest.get("version", current_version)
