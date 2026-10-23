from orchestrator.init_vault import FILES, FOLDERS, init_vault, plan


def test_creates_full_tree(vault):
    init_vault(vault)
    for folder in FOLDERS:
        assert vault.path(folder).is_dir()
    for rel in FILES:
        assert vault.path(rel).is_file()
    assert vault.is_initialized()
    assert plan(vault) == ([], [])


def test_is_idempotent_and_never_overwrites(vault):
    init_vault(vault)
    vault.path("Home.md").write_text("my own home", encoding="utf-8")
    vault.path("00_Inbox/Mobile_Notes.md").unlink()

    folders, created = init_vault(vault)
    assert folders == []
    assert created == ["00_Inbox/Mobile_Notes.md"]
    assert vault.read("Home.md") == "my own home"


def test_home_has_status_section_and_links(vault):
    init_vault(vault)
    home = vault.read("Home.md")
    assert "<!-- hub:start:status -->" in home
    for target in ["00_Inbox/Mobile_Notes", "01_Startups/Vrittara/Analytics", "02_Academics/Grades",
                   "04_Extracurriculars/Robotics/Code_Status"]:
        assert f"[[{target}|" in home
