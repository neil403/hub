from pathlib import Path

import pytest

from orchestrator.config import Config
from orchestrator.vault import Vault


@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    return Vault(tmp_path / "vault")


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(hub_root=tmp_path / "hub", vault_path=tmp_path / "vault", vault_path_source="config")
