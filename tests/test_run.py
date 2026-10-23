from datetime import datetime

from orchestrator.connectors.base import Connector, Output
from orchestrator.init_vault import init_vault
from orchestrator.run import record_runs, render_status, run_one

REGISTRY = {"good": "tests.test_run:Good", "bad": "tests.test_run:Bad", "broken": "tests.no_such_module:X"}


class Good(Connector):
    name = "good"

    def fetch(self):
        return ["a", "b"]

    def render(self, data):
        return [Output("Test/Good.md", "\n".join(f"- {x}" for x in data), title="Good")]


class Bad(Connector):
    name = "bad"

    def fetch(self):
        raise RuntimeError("API down")


def test_failures_are_isolated(config, vault):
    init_vault(vault)
    results = [run_one(n, config, vault, False, REGISTRY) for n in ["bad", "broken", "good", "missing"]]
    assert [r.ok for r in results] == [False, False, True, False]
    assert "API down" in results[0].error
    assert results[2].changed == ["Test/Good.md"]
    assert "- a\n- b" in vault.read("Test/Good.md")


def test_dry_run_writes_nothing(config, vault, capsys):
    result = run_one("good", config, vault, True, REGISTRY)
    assert result.ok and result.changed == []
    assert not vault.path("Test/Good.md").exists()
    assert "===== Test/Good.md =====" in capsys.readouterr().out


def test_status_history_and_render(config, vault):
    init_vault(vault)
    now = datetime(2026, 10, 23, 8, 0)
    results = [run_one(n, config, vault, False, REGISTRY) for n in ["good", "bad"]]
    history = record_runs(config, results, now)
    status = render_status(history, now)
    assert "| good | 2026-10-23 08:00 | ok | 1 |" in status
    assert "| bad | 2026-10-23 08:00 | failed: RuntimeError: API down | 0 |" in status
    assert render_status({}, now).endswith("_No connectors enabled yet._")
