"""Logging to hub/logs/ (never the vault).

Tracebacks go to the log file only; the console gets run.py's summary table.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(getattr(h, "_hub", False) for h in root.handlers):
        return
    root.setLevel(level)

    file_handler = RotatingFileHandler(log_dir / "hub.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    file_handler._hub = True  # type: ignore[attr-defined]

    root.addHandler(file_handler)
