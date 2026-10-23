"""The fetch() -> render() -> write() contract every connector follows."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..config import Config
from ..vault import Vault, render_frontmatter, section_markers


@dataclass
class Output:
    """One piece of Markdown a connector wants in the vault."""

    path: str                               # vault-relative, e.g. "02_Academics/Grades.md"
    content: str                            # goes between the hub markers
    section: str | None = None              # named managed section; None = default markers
    frontmatter: dict[str, Any] | None = None
    title: str | None = None                # H1 used only when the file is created
    create_only: bool = False               # write once, never update (e.g. templates)


@dataclass
class RunResult:
    name: str
    ok: bool
    changed: list[str] = field(default_factory=list)
    outputs: int = 0
    seconds: float = 0.0
    error: str | None = None


class Connector:
    name: ClassVar[str]

    def __init__(self, config: Config, settings: dict[str, Any]):
        self.config = config
        self.settings = settings
        self.log = logging.getLogger(f"hub.{self.name}")

    def fetch(self) -> Any:
        raise NotImplementedError

    def render(self, data: Any) -> list[Output]:
        raise NotImplementedError

    def write(self, outputs: list[Output], vault: Vault) -> list[str]:
        changed = []
        for out in outputs:
            if out.create_only:
                text = render_frontmatter(out.frontmatter or {}) + out.content
                did_change = vault.create_if_missing(out.path, text)
            else:
                did_change = vault.upsert_section(
                    out.path, out.content, name=out.section, frontmatter=out.frontmatter, title=out.title
                )
            if did_change:
                changed.append(out.path)
        return changed

    def run(self, vault: Vault, dry_run: bool = False) -> RunResult:
        started = time.monotonic()
        outputs = self.render(self.fetch())
        changed = [] if dry_run else self.write(outputs, vault)
        if dry_run:
            print(preview(outputs))
        self.log.info("%s: %d outputs, %d changed", self.name, len(outputs), len(changed))
        return RunResult(self.name, True, changed, len(outputs), time.monotonic() - started)


def preview(outputs: list[Output]) -> str:
    """What --dry-run prints: the Markdown each output would write."""
    parts = []
    for out in outputs:
        start, end = section_markers(out.section)
        body = out.content if out.create_only else f"{start}\n{out.content.strip(chr(10))}\n{end}"
        parts.append(f"===== {out.path} =====\n{render_frontmatter(out.frontmatter or {})}{body}\n")
    return "\n".join(parts)
