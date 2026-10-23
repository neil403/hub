"""Safe Markdown writers for the vault.

Rules every connector gets for free:
  * Writes are atomic (temp file in the same folder -> os.replace), so a
    half-written file never syncs to the phone.
  * Hub-owned content lives between <!-- hub:start --> / <!-- hub:end -->
    markers. Everything outside the markers is yours and is never touched.
  * Unchanged files are not rewritten, which keeps iCloud quiet.
"""
from __future__ import annotations

import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

import yaml

ENCODING = "utf-8"
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


class VaultError(RuntimeError):
    pass


class VaultNotInitialized(VaultError):
    pass


# --- files ------------------------------------------------------------------

def atomic_write(path: Path, text: str, retries: int = 5) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=ENCODING, newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(retries):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                # Windows: iCloud or Obsidian can hold the target open for a moment.
                if attempt == retries - 1:
                    raise
                time.sleep(0.2 * 2**attempt)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# --- frontmatter --------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter, body). Raises VaultError on frontmatter we can't parse."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise VaultError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise VaultError("frontmatter is not a key/value mapping")
    return data, text[match.end():]


def render_frontmatter(data: Mapping[str, Any]) -> str:
    if not data:
        return ""
    dumped = yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{dumped}---\n"


def merge_frontmatter(text: str, updates: Mapping[str, Any]) -> str:
    """Set the given keys, keeping every other key (and the body) as-is."""
    data, body = split_frontmatter(text)
    data.update(updates)
    return render_frontmatter(data) + body


# --- managed sections ---------------------------------------------------------

def section_markers(name: str | None = None) -> tuple[str, str]:
    suffix = f":{name}" if name else ""
    return f"<!-- hub:start{suffix} -->", f"<!-- hub:end{suffix} -->"


def _find_section(text: str, name: str | None) -> tuple[int, int] | None:
    start, end = section_markers(name)
    s = text.find(start)
    if s == -1:
        if end in text:
            raise VaultError(f"found {end} without {start}")
        return None
    if text.find(start, s + len(start)) != -1:
        raise VaultError(f"{start} appears more than once")
    e = text.find(end, s + len(start))
    if e == -1:
        raise VaultError(f"found {start} without {end}")
    return s, e + len(end)


def get_managed_section(text: str, name: str | None = None) -> str | None:
    span = _find_section(text, name)
    if span is None:
        return None
    start, end = section_markers(name)
    return text[span[0] + len(start):span[1] - len(end)].strip("\n")


def replace_managed_section(text: str, content: str, name: str | None = None) -> str:
    """Replace the content between the markers; append a new section if absent."""
    start, end = section_markers(name)
    block = f"{start}\n{content.strip(chr(10))}\n{end}"
    span = _find_section(text, name)
    if span is None:
        if not text:
            sep = ""
        elif text.endswith("\n\n"):
            sep = ""
        elif text.endswith("\n"):
            sep = "\n"
        else:
            sep = "\n\n"
        return f"{text}{sep}{block}\n"
    return text[:span[0]] + block + text[span[1]:]


# --- vault --------------------------------------------------------------------

class Vault:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser()

    def path(self, rel: str | Path) -> Path:
        root = self.root.resolve()
        target = (root / rel).resolve()
        if not target.is_relative_to(root):
            raise VaultError(f"{rel} is outside the vault")
        return target

    def is_initialized(self) -> bool:
        return (self.root / "Home.md").is_file()

    def require_initialized(self) -> None:
        if not self.is_initialized():
            raise VaultNotInitialized(
                f"No hub vault at {self.root}. Run: python -m orchestrator.init_vault"
            )

    def read(self, rel: str | Path) -> str | None:
        p = self.path(rel)
        return p.read_text(encoding=ENCODING) if p.is_file() else None

    def _write_if_changed(self, rel: str | Path, text: str, old: str | None) -> bool:
        if text == old:
            return False
        atomic_write(self.path(rel), text)
        return True

    def create_if_missing(self, rel: str | Path, text: str) -> bool:
        if self.path(rel).exists():
            return False
        atomic_write(self.path(rel), text)
        return True

    def write_file(self, rel: str | Path, text: str) -> bool:
        """Replace a whole file. Only for files the hub fully owns."""
        return self._write_if_changed(rel, text, self.read(rel))

    def upsert_section(
        self,
        rel: str | Path,
        content: str,
        *,
        name: str | None = None,
        frontmatter: Mapping[str, Any] | None = None,
        title: str | None = None,
    ) -> bool:
        """Write `content` into the file's managed section, creating the file if needed.

        Frontmatter keys passed here are merged into any existing frontmatter.
        Returns True if the file changed on disk.
        """
        old = self.read(rel)
        if old is None:
            text = render_frontmatter(frontmatter or {}) + (f"# {title}\n\n" if title else "")
        else:
            text = merge_frontmatter(old, frontmatter) if frontmatter else old
        text = replace_managed_section(text, content, name)
        return self._write_if_changed(rel, text, old)

    def append_line(self, rel: str | Path, line: str) -> None:
        old = self.read(rel) or ""
        if old and not old.endswith("\n"):
            old += "\n"
        atomic_write(self.path(rel), f"{old}{line.rstrip(chr(10))}\n")
