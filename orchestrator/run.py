"""Run connectors.

    python -m orchestrator.run all             # every connector enabled in config.yaml
    python -m orchestrator.run linear          # one connector (even if disabled)
    python -m orchestrator.run linear --dry-run  # print the Markdown, write nothing
    python -m orchestrator.run --list
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime

from . import connectors
from .config import Config, load_config
from .connectors.base import RunResult
from .log import setup_logging
from .vault import Vault, VaultError, atomic_write

log = logging.getLogger("hub.run")
STATUS_FILE = "last_runs.json"


def run_one(name: str, config: Config, vault: Vault, dry_run: bool, registry: dict[str, str] | None = None) -> RunResult:
    """Run a single connector. Never raises: a failure becomes a failed RunResult."""
    started = time.monotonic()
    try:
        cls = connectors.load(name, registry)
        return cls(config, config.connector(name)).run(vault, dry_run=dry_run)
    except connectors.ConnectorNotAvailable as exc:
        log.error("%s", exc)
        return RunResult(name, False, error=str(exc))
    except Exception as exc:  # one source failing must never break the others
        log.exception("connector %s failed", name)
        return RunResult(name, False, seconds=time.monotonic() - started, error=f"{type(exc).__name__}: {exc}")


def summary_table(results: list[RunResult]) -> str:
    lines = [f"{'connector':<12} {'status':<7} {'changed':>7} {'time':>7}"]
    for r in results:
        status = "ok" if r.ok else "FAILED"
        lines.append(f"{r.name:<12} {status:<7} {len(r.changed):>7} {r.seconds:>6.1f}s")
        if r.error:
            lines.append(f"  -> {r.error}")
    return "\n".join(lines)


def record_runs(config: Config, results: list[RunResult], now: datetime) -> dict[str, dict]:
    """Merge these results into state/last_runs.json and return the full history."""
    path = config.state_dir / STATUS_FILE
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        history = {}
    for r in results:
        history[r.name] = {
            "at": now.strftime("%Y-%m-%d %H:%M"),
            "ok": r.ok,
            "changed": len(r.changed),
            "error": r.error,
        }
    atomic_write(path, json.dumps(history, indent=2))
    return history


def render_status(history: dict[str, dict], now: datetime) -> str:
    lines = [f"Last hub run: **{now.strftime('%Y-%m-%d %H:%M')}**", ""]
    if not history:
        lines.append("_No connectors enabled yet._")
        return "\n".join(lines)
    lines += ["| Connector | Last run | Result | Files changed |", "|---|---|---|---|"]
    for name in sorted(history):
        h = history[name]
        result = "ok" if h["ok"] else f"failed: {(h.get('error') or '').replace('|', '/')[:80]}"
        lines.append(f"| {name} | {h['at']} | {result} | {h['changed']} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run hub connectors.")
    parser.add_argument("target", nargs="?", default="all", help="connector name, or 'all'")
    parser.add_argument("--dry-run", action="store_true", help="print Markdown instead of writing")
    parser.add_argument("--list", action="store_true", help="list connectors and exit")
    args = parser.parse_args(argv)

    config = load_config()
    setup_logging(config.log_dir, config.log_level)

    if args.list:
        enabled = set(config.enabled_connectors())
        for name in sorted(set(config.connectors) | set(connectors.REGISTRY)):
            built = "built" if name in connectors.REGISTRY else connectors.PLANNED.get(name, "unknown")
            print(f"{name:<12} {'enabled' if name in enabled else 'disabled':<9} {built}")
        return 0

    vault = Vault(config.vault_path)
    if not args.dry_run:
        try:
            vault.require_initialized()
        except VaultError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.target != "all" and args.target not in connectors.REGISTRY:
        try:
            connectors.load(args.target)
        except connectors.ConnectorNotAvailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    names = config.enabled_connectors() if args.target == "all" else [args.target]
    if not names:
        print("No connectors enabled yet. Turn them on in config.yaml as each phase lands.")

    results = [run_one(name, config, vault, args.dry_run) for name in names]
    if results:
        print(summary_table(results))

    if not args.dry_run:
        now = datetime.now()
        try:
            history = record_runs(config, results, now)
            vault.upsert_section("Home.md", render_status(history, now), name="status")
        except Exception:
            log.exception("could not update hub status")
            print("warning: could not update Home.md status (see logs/hub.log)", file=sys.stderr)

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
