from datetime import datetime

import pytest

from orchestrator.inbox_append import INBOX, append, format_entry
from orchestrator.init_vault import init_vault
from orchestrator.vault import VaultNotInitialized

NOW = datetime(2026, 10, 23, 9, 5)


def test_format_matches_shortcut():
    assert format_entry("call  the\ndentist ", NOW) == "- [ ] 2026-10-23 09:05 call the dentist"


def test_empty_capture_rejected():
    with pytest.raises(ValueError):
        format_entry("   \n", NOW)


def test_append_to_inbox(vault):
    init_vault(vault)
    append(vault, "one", NOW)
    append(vault, "two", NOW)
    assert vault.read(INBOX).endswith("- [ ] 2026-10-23 09:05 one\n- [ ] 2026-10-23 09:05 two\n")


def test_refuses_uninitialized_vault(vault):
    with pytest.raises(VaultNotInitialized):
        append(vault, "x", NOW)
