"""CORE-002: append a capture to 00_Inbox/Mobile_Notes.md from the computer.

Same line format as the iPhone Shortcut:  - [ ] 2026-10-23 14:05 call the dentist

    python -m orchestrator.inbox_append "call the dentist"
    echo "idea from a pipe" | python -m orchestrator.inbox_append
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from .config import load_config
from .vault import Vault, VaultError

INBOX = "00_Inbox/Mobile_Notes.md"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"  # matches the Shortcut's "yyyy-MM-dd HH:mm"


def format_entry(text: str, now: datetime | None = None) -> str:
    text = " ".join(text.split())  # one line per capture
    if not text:
        raise ValueError("nothing to capture")
    return f"- [ ] {(now or datetime.now()).strftime(TIMESTAMP_FORMAT)} {text}"


def append(vault: Vault, text: str, now: datetime | None = None) -> str:
    vault.require_initialized()
    entry = format_entry(text, now)
    vault.append_line(INBOX, entry)
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append a checkbox line to the vault inbox.")
    parser.add_argument("text", nargs="*", help="what to capture (reads stdin if omitted)")
    args = parser.parse_args(argv)

    text = " ".join(args.text) if args.text else sys.stdin.read()
    try:
        entry = append(Vault(load_config().vault_path), text)
    except (ValueError, VaultError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Added to {INBOX}: {entry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
