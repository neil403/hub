"""CORE-001: create the vault folder tree and starter notes.

Idempotent: creates what's missing, never overwrites an existing file.

    python -m orchestrator.init_vault             # shows the path and asks first
    python -m orchestrator.init_vault --dry-run   # list what would be created
    python -m orchestrator.init_vault --vault "D:/Some/Other/Vault" --yes
"""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from .config import load_config
from .vault import Vault, section_markers

FOLDERS = [
    "00_Inbox",
    "01_Startups/Vrittara",
    "01_Startups/Vitrello/Sessions",
    "02_Academics/Assignments",
    "02_Academics/Lectures",
    "03_Sources/Instagram",
    "04_Extracurriculars/DECA",
    "04_Extracurriculars/Robotics",
]


def _placeholder(title: str, source: str) -> str:
    start, end = section_markers()
    return (
        f"# {title}\n\n"
        f"{start}\n_Not synced yet. Filled in by the `{source}` connector._\n{end}\n\n"
        "## Notes\n\n"
    )


def _home() -> str:
    start, end = section_markers("status")
    return f"""# Home

## Capture
- [[00_Inbox/Mobile_Notes|Inbox]]

## Startups
- **Vrittara**: [[01_Startups/Vrittara/Analytics|Analytics]] | [[01_Startups/Vrittara/Tasks|Tasks]]
- **Vitrello**: [[01_Startups/Vitrello/Tasks|Tasks]] | session logs in `01_Startups/Vitrello/Sessions/`

## Academics
- [[02_Academics/Grades|Grades]] | assignments in `02_Academics/Assignments/` | lectures in `02_Academics/Lectures/`

## Extracurriculars
- **Robotics**: [[04_Extracurriculars/Robotics/Code_Status|Code status]]
- **DECA**: notes in `04_Extracurriculars/DECA/`

## Sources
- Instagram saves in `03_Sources/Instagram/`

## Hub status
{start}
_No runs yet._
{end}

## My notes

"""


FILES: dict[str, str] = {
    "Home.md": _home(),
    "00_Inbox/Mobile_Notes.md": "# Mobile Notes\n\nCaptured from the iPhone Action Button and `inbox_append`.\n\n",
    "01_Startups/Vrittara/Analytics.md": _placeholder("Vrittara Analytics", "cloudflare"),
    "01_Startups/Vrittara/Tasks.md": _placeholder("Vrittara Tasks", "linear"),
    "01_Startups/Vitrello/Tasks.md": _placeholder("Vitrello Tasks", "linear"),
    "02_Academics/Grades.md": _placeholder("Grades", "hac"),
    "04_Extracurriculars/Robotics/Code_Status.md": _placeholder("Robotics Code Status", "github"),
}


def plan(vault: Vault) -> tuple[list[str], list[str]]:
    """(folders to create, files to create) -- anything that already exists is skipped."""
    folders = [f for f in FOLDERS if not vault.path(f).is_dir()]
    files = [f for f in FILES if not vault.path(f).exists()]
    return folders, files


def init_vault(vault: Vault) -> tuple[list[str], list[str]]:
    folders, files = plan(vault)
    vault.root.mkdir(parents=True, exist_ok=True)
    for folder in folders:
        vault.path(folder).mkdir(parents=True, exist_ok=True)
    created = [rel for rel in files if vault.create_if_missing(rel, FILES[rel])]
    return folders, created


def _icloud_warning(vault_root: Path) -> str | None:
    container = next((p for p in vault_root.parents if p.name == "iCloud~md~obsidian"), None)
    if container is not None and not container.is_dir():
        return (
            f"WARNING: {container} does not exist.\n"
            "  Create the vault on your iPhone first (Obsidian > Create new vault > Store in iCloud),\n"
            "  then wait for that folder to appear on this computer before continuing."
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the hub folder tree in the Obsidian vault.")
    parser.add_argument("--vault", help="vault path (overrides config.yaml / HUB_VAULT_PATH)")
    parser.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="only list what would be created")
    args = parser.parse_args(argv)

    config = load_config()
    root = Path(args.vault).expanduser() if args.vault else config.vault_path
    source = "--vault" if args.vault else config.vault_path_source
    vault = Vault(root)

    print(f"OS:    {platform.system()}")
    print(f"Vault: {root}  (from {source})")
    warning = _icloud_warning(root)
    if warning:
        print(warning)

    folders, files = plan(vault)
    if not folders and not files:
        print("Vault already has every hub folder and file. Nothing to do.")
        return 0
    for f in folders:
        print(f"  + folder {f}/")
    for f in files:
        print(f"  + file   {f}")
    if args.dry_run:
        return 0
    if not args.yes:
        answer = input("Create these in the vault above? Existing files are never touched. [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Cancelled. Nothing was written.")
            return 1

    folders, created = init_vault(vault)
    print(f"Done: {len(folders)} folders, {len(created)} files created.")
    if args.vault:
        print(f"Tip: set vault_path in config.yaml to '{root}' so the connectors use it too.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
