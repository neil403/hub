"""Load config.yaml + .env into a single Config object."""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

HUB_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    pass


def default_vault_path(vault_name: str = "Hub", system: str | None = None, home: Path | None = None) -> Path:
    """The iCloud Obsidian folder for this OS, so the phone sees every write."""
    system = system or platform.system()
    home = home or Path.home()
    if system == "Windows":
        return home / "iCloudDrive" / "iCloud~md~obsidian" / vault_name
    if system == "Darwin":
        return home / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / vault_name
    return home / "Obsidian" / vault_name


def _expand(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value)))


@dataclass(frozen=True)
class Config:
    hub_root: Path
    vault_path: Path
    vault_path_source: str  # "env", "config" or "auto"
    connectors: dict[str, dict[str, Any]] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    log_level: str = "INFO"

    @property
    def log_dir(self) -> Path:
        return self.hub_root / "logs"

    @property
    def state_dir(self) -> Path:
        return self.hub_root / "state"

    def connector(self, name: str) -> dict[str, Any]:
        return dict(self.connectors.get(name) or {})

    def enabled_connectors(self) -> list[str]:
        return [name for name, opts in self.connectors.items() if (opts or {}).get("enabled")]


def env(name: str, required: bool = True) -> str | None:
    """Read a secret from the environment (.env is loaded by load_config)."""
    value = os.environ.get(name, "").strip()
    if not value and required:
        raise ConfigError(f"{name} is not set. Add it to .env (see .env.example).")
    return value or None


def load_config(config_path: Path | None = None, env_file: Path | None = None, hub_root: Path = HUB_ROOT) -> Config:
    load_dotenv(env_file or hub_root / ".env", override=False)
    config_path = config_path or hub_root / "config.yaml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConfigError(f"{config_path} must be a YAML mapping")

    vault_name = str(raw.get("vault_name") or "Hub")
    configured = str(raw.get("vault_path") or "auto").strip()
    if os.environ.get("HUB_VAULT_PATH", "").strip():
        vault_path, source = _expand(os.environ["HUB_VAULT_PATH"].strip()), "env"
    elif configured.lower() != "auto":
        vault_path, source = _expand(configured), "config"
    else:
        vault_path, source = default_vault_path(vault_name), "auto"

    return Config(
        hub_root=hub_root,
        vault_path=vault_path,
        vault_path_source=source,
        connectors=dict(raw.get("connectors") or {}),
        llm=dict(raw.get("llm") or {}),
        log_level=str(raw.get("log_level") or "INFO").upper(),
    )
