# Hub

A local-first personal command hub. Small Python connectors pull school, startup, extracurricular and social data into an **Obsidian vault of plain Markdown files** that syncs to the iPhone through iCloud.

- **Markdown is the database.** Every piece of state the phone sees is a `.md` file in the vault.
- **Secrets stay on this computer.** API keys live in `.env` and HAC credentials in the OS keychain. The vault holds no secrets.
- **Each connector stands alone.** One failing source never stops the others.
- **Your notes stay yours.** The hub only rewrites text between `<!-- hub:start -->` and `<!-- hub:end -->` markers.

## Layout

```
orchestrator/
  connectors/       one module per source (added phase by phase)
    base.py         fetch() -> render() -> write() contract, --dry-run preview
  vault.py          atomic writes, frontmatter helpers, managed sections
  init_vault.py     CORE-001: create the vault tree (idempotent)
  inbox_append.py   CORE-002: capture to the inbox from the computer
  run.py            python -m orchestrator.run [connector|all]
  config.py         loads .env + config.yaml
  log.py            logs to logs/hub.log (never the vault)
tests/              run with pytest, no credentials needed
config.yaml         vault path, enabled connectors, LLM settings
.env.example        every secret, with where to get it
```

`logs/`, `state/`, and `.env` are gitignored and created as needed.

## Setup (Windows)

1. **Install Python 3.11+** from python.org. Tick "Add python.exe to PATH" during install.
2. **Install iCloud for Windows** (Microsoft Store) and sign in with the same Apple ID as your iPhone. Turn on **iCloud Drive**.
3. **Create the vault on the iPhone first.** Open Obsidian > *Create new vault* > name it `Hub` > turn on **Store in iCloud**. This creates Obsidian's iCloud folder. Wait until this folder shows up on the PC:
   `C:\Users\<you>\iCloudDrive\iCloud~md~obsidian\Hub`
4. In File Explorer, right-click that `Hub` folder and choose **Always keep on this device**. Otherwise Windows may offload files and the hub can't read your notes.
5. Get the code and install it (PowerShell, in the repo folder):
   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   copy .env.example .env
   pytest
   ```
6. **Initialize the vault.** The script prints the OS and the detected path, then asks before writing anything:
   ```powershell
   python -m orchestrator.init_vault --dry-run   # preview
   python -m orchestrator.init_vault             # asks y/N, then creates
   ```
   It only creates missing folders and files and never overwrites one. Run it as often as you like.

   If the vault lives somewhere else, set `vault_path` in `config.yaml`. Use forward slashes, or wrap the path in single quotes.

7. (Optional) Open the same folder in Obsidian on the PC: *Open folder as vault*.

## Vault structure

```
Home.md                         dashboard; "Hub status" section updated on every run
00_Inbox/Mobile_Notes.md        Action Button captures land here
01_Startups/Vrittara/           Analytics.md, Tasks.md
01_Startups/Vitrello/           Tasks.md, Sessions/
02_Academics/                   Grades.md, Assignments/, Lectures/
03_Sources/Instagram/
04_Extracurriculars/            DECA/, Robotics/Code_Status.md
```

## Mobile capture: iPhone Action Button Shortcut

No server is involved. The Shortcut appends straight to the Markdown file in iCloud.

1. Open the **Shortcuts** app, tap **+**, and name the shortcut **Hub Capture**.
2. Add **Ask for Input**. Set *Input Type* to **Text** and *Prompt* to `Capture`.
3. Add **Format Date**. Set *Date* to **Current Date**, *Date Format* to **Custom**, and the format string to `yyyy-MM-dd HH:mm`.
4. Add **Text** and type `- [ ] `. Then insert the **Formatted Date** variable, a space, and the **Provided Input** variable. The result should read:
   `- [ ] Formatted Date Provided Input`
5. Add **Append to Text File** and set:
   - *Text*: the **Text** variable from step 4
   - *File*: tap it and browse to **iCloud Drive > Obsidian > Hub > 00_Inbox > Mobile_Notes.md**
   - **Make New Line**: on
6. (Optional) Add **Show Notification** with the text `Captured`.
7. Run it once from the Shortcuts app. iOS asks for permission to access the Obsidian folder; choose **Always Allow**.
8. Go to **Settings > Action Button**, swipe to **Shortcut**, and choose **Hub Capture**.

A capture looks like `- [ ] 2026-10-23 14:05 call the dentist`. Obsidian renders it as a checkbox you can tick off.

> The phone and the computer both append to `Mobile_Notes.md`. If both write while one of them is offline, iCloud may keep a copy named `Mobile_Notes 2.md`. Merge it by hand and delete it.

### From the computer

```powershell
python -m orchestrator.inbox_append "email the robotics mentor"
echo "an idea from a pipe" | python -m orchestrator.inbox_append
```

## Running connectors

```powershell
python -m orchestrator.run --list            # connectors, enabled state, which phase builds them
python -m orchestrator.run all               # every connector enabled in config.yaml
python -m orchestrator.run linear --dry-run  # print the Markdown, write nothing
```

`run` prints a summary table and exits non-zero if any connector failed. It records each result in `state/last_runs.json` and updates the **Hub status** table in `Home.md`. Full tracebacks go to `logs/hub.log`.

## Writing a connector

```python
from orchestrator.connectors.base import Connector, Output

class Example(Connector):
    name = "example"

    def fetch(self):                      # talk to the API, return raw data
        ...

    def render(self, data) -> list[Output]:   # pure: data -> Markdown (unit-tested with fixtures)
        return [Output("01_Startups/Example.md", "| a | b |", title="Example",
                       frontmatter={"source": "example"})]
```

The base class handles `write()`, `--dry-run`, and logging. Register the connector in `orchestrator/connectors/__init__.py`, then add it to `config.yaml`.

## Tests

```powershell
pytest
```
