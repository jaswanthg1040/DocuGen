# DocuGen 2.0 — AI Document Studio

A local web app for creating, editing, previewing, saving, importing and exporting documents.
Built with Python, Streamlit, SQLite, python-docx and ReportLab.

* Works fully offline. **No API key or paid service is needed.**
* Documents are stored in a local SQLite file and survive restarts.
* AI-assisted writing is **not implemented** (see "Known limitations").

## What's new in 2.0

| Area | New |
|------|-----|
| Data safety | **Autosaved drafts** are recovered after a refresh or crash; **version history** keeps the last 20 saved versions of every document and lets you restore one |
| Organising | **Favorites** (pinned to the top), **tags** with a filter, **duplicate** a document, plus search and sorting |
| Import | Load **.docx, .txt and .md** files into the editor (headings, lists, bold/italic and tables are kept) |
| Export | Word, PDF, **Markdown** and **plain text**; **A4 or Letter**; optional **page numbers** |
| Formatting | **Tables**, **nested lists** (3 levels), **horizontal rules**, literal `\*` |
| Editor | Word / character count and reading time, **find and replace**, quick-insert buttons |
| PDF | Bundled **DejaVu Sans** font, so Western European, Greek and Cyrillic text work on every PC; bold headings |
| Setup | **`Start DocuGen.bat`** one-click launcher for Windows; existing 1.x databases are upgraded automatically |

## Quick start on Windows 11

**Easiest:** unzip the folder and double-click **`Start DocuGen.bat`**. The first run creates a
virtual environment and installs the dependencies (internet required), then opens the app in your browser.
(Python 3.10+ must be installed first: https://www.python.org/downloads/ — tick **"Add python.exe to PATH"**.)

**Manual setup (PowerShell, inside the DocuGen folder):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If PowerShell refuses to activate the environment, run once:
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.
The app opens at http://localhost:8501. Stop it with `Ctrl+C` (or close the launcher window).
Next time you only need to activate the environment and run the last command.

## Using DocuGen

| Page | What you can do |
|------|-----------------|
| Dashboard | Quick actions, live statistics, recent documents, recovery prompt |
| Create Document | Title, description, tags, editor with Preview tab, import, find/replace, save, export, version history |
| My Documents | Search, sort, tag filter, favorites; Open, Edit, Export, Copy, Pin, Delete (with confirmation) |
| Templates | Blank, Project Report, Meeting Minutes, Business Proposal, Professional Letter, Study Notes, Resume/CV, Research Report |
| Settings | Light/Dark theme, default export, page size, Word font, page numbers, description in exports, database backup |

### Formatting syntax (editor, preview and all exports)

```
# Heading 1      ## Heading 2      ### Heading 3
- bullet          (indent 2 spaces per level for sub-items)
1. numbered item
**bold**   *italic*   ***bold italic***   \*  = literal asterisk
| Column A | Column B |        tables: first row is the header
| cell     | cell     |        (a |---|---| row is optional)
---                              horizontal rule
```
A blank line starts a new paragraph; a single line break inside a paragraph is kept.
The editor is a plain-text box with this syntax (not WYSIWYG); the Preview tab shows the result.

## Running the tests

```powershell
python -m pytest -q
```

Covers the database (including upgrade from 1.x, versions, tags, drafts), formatting parser, Word/PDF/Markdown/text
export, the importer (including a Word → import round trip), Python syntax of every file, and the app itself
(navigation, save/update, template flow, unsaved-change prompts, recovery after a simulated restart, version restore,
pin/duplicate/tag filter, theme and settings persistence).

## Project layout

```
DocuGen/
├── Start DocuGen.bat      One-click Windows launcher
├── app.py                 Streamlit UI and page logic
├── database.py            All SQLite access (parameterised queries, validation, migration)
├── requirements.txt, pytest.ini, .env.example, .gitignore
├── components/ui.py       Theme CSS (light/dark) and small HTML components
├── services/
│   ├── formatting.py      Markdown-subset parser shared by preview + every export
│   ├── word_export.py     .docx generation (python-docx)
│   ├── pdf_export.py      .pdf generation (ReportLab)
│   ├── text_export.py     Markdown and plain-text export
│   ├── importer.py        .docx / .txt / .md import
│   ├── templates.py       Starter templates (application data)
│   └── utils.py           Safe filenames
├── fonts/                 Bundled DejaVu Sans (free licence, see LICENSE-DejaVu.txt)
├── data/                  SQLite database is created here (docugen.db)
├── tests/
└── .streamlit/config.toml
```

## Where is my data?

`data\docugen.db` inside the project folder (override with `DOCUGEN_DB_PATH` in a `.env` file).
Back it up from **Settings → Download a backup**, or copy the file. If you used DocuGen 1.x, copy your old
`data\docugen.db` into this version's `data` folder: it is upgraded automatically on first start.

## Security and privacy

* DocuGen is a **single-user, local** application. There is **no login**, and the database file is **not encrypted**.
  Anyone with access to your computer or the `data` folder can read your documents. Do not expose the app to a network.
* All SQL uses parameters. Document text is never rendered as HTML or executed; the preview escapes anything outside the
  supported formatting. Filenames are sanitised. Imported files are parsed, never executed (limit 5 MB).
* The autosaved draft (one row in the same database) is removed when you save or discard it.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `'python' is not recognized` | Python is not installed or not on PATH. Reinstall and tick "Add python.exe to PATH", or use `py -m venv .venv`. |
| `Start DocuGen.bat` closes immediately or says dependencies failed | Run it from a terminal (`cmd`) to read the message; usually Python is missing or there is no internet for the first install. |
| `No module named streamlit` (or docx, reportlab) | The environment is not active or dependencies are missing. Activate `.venv` (prompt starts with `(.venv)`) and run `python -m pip install -r requirements.txt`. |
| Wrong interpreter in VS Code | Ctrl+Shift+P → *Python: Select Interpreter* → `.venv\Scripts\python.exe`. |
| `File does not exist: app.py` | Wrong folder. `cd` into the folder that contains `app.py`. |
| `Port 8501 is already in use` | Close the other Streamlit app or run `python -m streamlit run app.py --server.port 8502`. |
| "DocuGen cannot open its database" | The `data` folder is read-only or locked. Move DocuGen out of protected folders, or set `DOCUGEN_DB_PATH` in `.env` to a writable path. |
| `SyntaxError` / `IndentationError` | A file was edited or pasted incorrectly (e.g. Markdown code fences pasted into a `.py` file). Re-extract the ZIP; `python -m pytest -q` names the broken file. |

## Known limitations

* **AI features are not implemented.** Settings says so; nothing pretends to be AI.
* The editor is plain text with Markdown-style syntax, not WYSIWYG. Not supported: images, links, colours, alignment,
  merged table cells, nested tables.
* **PDF fonts:** Western European, Greek and Cyrillic text work everywhere (Arial, or the bundled DejaVu Sans).
  Chinese, Japanese, Korean, Telugu and other Indic scripts, Arabic and emoji do **not** render correctly in the **PDF**
  (ReportLab cannot shape complex scripts). The **Word, Markdown and text** exports store any Unicode text correctly.
* Unsaved text is autosaved on every edit and offered back after a refresh, but only the most recent single draft is kept.
* Word numbered lists use typed numbers with a hanging indent (so every list restarts at 1) rather than Word's automatic numbering.
* Importing a .docx converts structure only (headings, lists, tables, bold, italic); images, links, comments and tracked changes are dropped.
* The preview approximates, but does not exactly match, the exported layout. It refreshes when the text box loses focus
  (click outside it or press Ctrl+Enter).
* Dark mode is custom CSS over Streamlit; future Streamlit versions may rename internal elements.
* `Start DocuGen.bat` was written for Windows but could not be executed in the Linux build environment; the
  manual PowerShell steps above are the tested path.
