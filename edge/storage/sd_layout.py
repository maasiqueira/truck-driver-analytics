from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def resolve_data_dir(configured: str) -> Path:
    """Usa data_dir do YAML; fallback para ./data/runtime se microSD ausente."""
    path = Path(configured)
    if path.is_absolute():
        try:
            path.mkdir(parents=True, exist_ok=True)
            test = path / ".write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            return path
        except OSError:
            log.warning("data_dir not writable: %s — falling back to local runtime", path)
    fallback = Path(os.environ.get("TDA_DATA_DIR", "./data/runtime"))
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback.resolve()
