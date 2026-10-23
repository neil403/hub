import pytest

from orchestrator.vault import (
    VaultError,
    atomic_write,
    get_managed_section,
    merge_frontmatter,
    replace_managed_section,
    split_frontmatter,
)


def test_atomic_write_leaves_no_temp_files(tmp_path):
    target = tmp_path / "a" / "note.md"
    atomic_write(target, "hello\n")
    atomic_write(target, "again\n")
    assert target.read_text(encoding="utf-8") == "again\n"
    assert [p.name for p in target.parent.iterdir()] == ["note.md"]


def test_replace_section_keeps_user_text():
    text = "# Title\n\nmine above\n<!-- hub:start -->\nold\n<!-- hub:end -->\nmine below\n"
    out = replace_managed_section(text, "new\nlines")
    assert out == "# Title\n\nmine above\n<!-- hub:start -->\nnew\nlines\n<!-- hub:end -->\nmine below\n"


def test_replace_section_appends_when_missing():
    assert replace_managed_section("# Mine", "x") == "# Mine\n\n<!-- hub:start -->\nx\n<!-- hub:end -->\n"
    assert replace_managed_section("", "x") == "<!-- hub:start -->\nx\n<!-- hub:end -->\n"


def test_named_sections_are_independent():
    text = replace_managed_section("", "a")
    text = replace_managed_section(text, "b", name="status")
    text = replace_managed_section(text, "a2")
    assert get_managed_section(text) == "a2"
    assert get_managed_section(text, "status") == "b"


@pytest.mark.parametrize(
    "broken",
    [
        "<!-- hub:start -->\nno end",
        "no start\n<!-- hub:end -->",
        "<!-- hub:start -->\n<!-- hub:end -->\n<!-- hub:start -->\n<!-- hub:end -->",
    ],
)
def test_broken_markers_raise_instead_of_clobbering(broken):
    with pytest.raises(VaultError):
        replace_managed_section(broken, "x")


def test_frontmatter_merge_keeps_existing_keys_and_body():
    text = "---\ntags: [school]\nmine: 1\n---\n# Body\n"
    out = merge_frontmatter(text, {"updated": "2026-10-23", "mine": 2})
    data, body = split_frontmatter(out)
    assert data == {"tags": ["school"], "mine": 2, "updated": "2026-10-23"}
    assert body == "# Body\n"


def test_invalid_frontmatter_raises():
    with pytest.raises(VaultError):
        split_frontmatter("---\n: : bad\n  - [\n---\nbody")


def test_vault_rejects_paths_outside(vault):
    with pytest.raises(VaultError):
        vault.path("../escape.md")


def test_upsert_creates_then_only_touches_section(vault):
    assert vault.upsert_section("x/Note.md", "v1", title="Note", frontmatter={"source": "test"})
    assert vault.read("x/Note.md") == "---\nsource: test\n---\n# Note\n\n<!-- hub:start -->\nv1\n<!-- hub:end -->\n"

    # The user adds their own notes; the next sync must keep them.
    vault.path("x/Note.md").write_text(vault.read("x/Note.md") + "\nmy thoughts\n", encoding="utf-8")
    assert vault.upsert_section("x/Note.md", "v2", frontmatter={"source": "test"})
    text = vault.read("x/Note.md")
    assert "v2" in text and "v1" not in text and text.endswith("my thoughts\n")

    # Unchanged content -> no rewrite.
    assert not vault.upsert_section("x/Note.md", "v2", frontmatter={"source": "test"})


def test_append_line_adds_missing_newline(vault):
    vault.path("a.md").parent.mkdir(parents=True, exist_ok=True)
    vault.path("a.md").write_text("first", encoding="utf-8")
    vault.append_line("a.md", "second")
    assert vault.read("a.md") == "first\nsecond\n"
