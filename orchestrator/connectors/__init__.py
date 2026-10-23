"""Connector registry.

Connectors are imported lazily by name, so a broken import or missing
dependency in one connector can't stop the others from running.
"""
from __future__ import annotations

import importlib

from .base import Connector

# name -> "module:Class" (module relative to this package). Each phase adds its entries.
REGISTRY: dict[str, str] = {}

# Known slots that aren't built yet, so `run.py` can say why instead of failing.
PLANNED: dict[str, str] = {
    "cloudflare": "Phase 2 (BUS-001)",
    "linear": "Phase 2 (BUS-002)",
    "classroom": "Phase 3 (SCH-001)",
    "hac": "Phase 3 (SCH-002)",
    "github": "Phase 4 (EC-002)",
    "instagram": "Phase 5 (SOC-001)",
    # Out of scope for now; reserved slots.
    "comet": "not planned yet (browser-agent integration)",
}


class ConnectorNotAvailable(LookupError):
    pass


def load(name: str, registry: dict[str, str] | None = None) -> type[Connector]:
    registry = REGISTRY if registry is None else registry
    target = registry.get(name)
    if target is None:
        if name in PLANNED:
            raise ConnectorNotAvailable(f"'{name}' is not built yet: {PLANNED[name]}")
        raise ConnectorNotAvailable(f"unknown connector '{name}'")
    module_name, _, class_name = target.partition(":")
    if "." not in module_name:  # bare names live in this package
        module_name = f"{__name__}.{module_name}"
    return getattr(importlib.import_module(module_name), class_name)
