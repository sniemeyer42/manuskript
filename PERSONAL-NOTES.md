# Manuskript personal fork (`personal/main`): changes, open problems and plan

*Notes for the fork owner, written November 2026. Branch `personal/main` at `80e904e` (2026-11-02): 15 commits on top of `fix/all-quickfixes` at `1d7320f`. This is the owner's own version (one user, Linux and Windows, folder-mode projects in git), not a proposal for upstream. **Nothing of it is published.** In the local remote-tracking refs (not fetched again for this document), `origin` has no `personal/main`, and `origin/fix/all-quickfixes` is at `26f618e`: 10 commits behind `1d7320f` (8 commits and 2 merges), without the six `fix/review-findings` commits, D5 (`92bee56`) and REVIEW-NOTES v2. The fix branches themselves are described in `REVIEW-NOTES.md` on `fix/all-quickfixes`; this document keeps its IDs (A1…G4, BC1…BC21), so both can be read side by side.*

## TL;DR

- `personal/main` cuts what a one-user Linux/Windows version does not need: LanguageTool, the unfinished export filters (E5, hidden), QtWebKit and the vendored pdf.js (the PDF preview now opens the system viewer), about 1,100 lines of dead code, Python before 3.10, and macOS. It adds a CI matrix with Windows, Windows-safe test fixtures, a fix for single-file projects, and **zip snapshots of every project outside its folder** (step 10 of the save design, done ahead of the rest).
- The suite grows from 630 to **682 tests**. Every code commit passes on Linux on its own (674 passed, 8 skipped at the tip; 682 passed with the optional spellcheck backends). Under Wine with a Windows Python, 647 pass and 5 fail, all because of the embeddable Python used there.
- **CI has never run** (the branch is not pushed), and **Windows was only tested under Wine**. Both are the first things to fix.
- The most important open problems for personal use:
  - A9: reordering two siblings whose titles give the same file name (`Grüße`/`Größe`) loses a scene if one write fails and the changes are discarded. Step 3 of the save rewrite closes it in about ¼ day.
  - P4: external changes (`git pull`, `checkout`, another editor) are not detected while a project is open. Close the project before using git on it, until the rewrite is done.
  - B1: any uncaught exception still closes the app without saving.
  - A6: a crash when the first selection in the Outline tab is a multi-selection.
- Recommended order (section 3): let CI run, then save-rewrite steps 1–3 (¾ day), steps 4–9 and 11 (8.5 days), B1 (about 3 days), then A6, B4, B5, B6, E1, E7 (about 6 days). In total, **about 18 working days**.
- Ten design decisions (save design, section 18) and three snapshot deviations are still open (section 4).
- **All code and text were written by an AI model** (Claude), directed by the fork owner, and not reviewed line by line by a human.

## Who wrote this and how it was produced

**Who wrote this.** This document, the code and tests of the 15 commits, and their commit messages were written by Claude, an AI model made by Anthropic, working in Claude Code. The fork owner (sniemeyer42) set the scope (one user, Linux and Windows, folder mode in git, what to cut) and asked for each piece of work, but has not reviewed the code line by line. The only manual check by the owner is B2 (see 2.1). The commits name the fork owner as author and carry a `Co-Authored-By: Claude` trailer. Treat every claim here as checked by AI agents only.

How the work was done:

1. **Save design** (`9288eb9`). Three independent designs with prototypes (minimal, planexec, transactional), three judges (data safety, Windows/git, effort) and a synthesis. The judges ran their loss scenarios against the prototypes and against a tree of `1d7320f`. A9 comes from there.
2. **Cuts.** Three implementers in separate worktrees (LanguageTool and E5; QtWebKit, pdf.js, dead code and Python 3.10; macOS, repo leftovers and CI), each followed by an adversarial reviewer and a fixer. In parallel, a probe ran the full suite under Wine with a Windows Python. The reviews found 4 low-severity problems (LT-1, WD-1, WD-2, CIMAC-1), the Wine probe 2 more (the test fixtures, two POSIX file-mode tests). All were fixed. The file-mode tests needed no further change: the CI commit already skips them on Windows.
3. **Snapshots.** One implementer, two adversarial reviewers (data safety, platform), one fixer. The reviewers found 12 problems (5 medium, 7 low), most of them reproduced with a probe, the others shown in the code. All 12 were fixed.
4. **Integration.** The work branches were put onto `fix/all-quickfixes` in the order of 1.1. Each of the 13 code commits was then tested on a fresh `git archive` with an isolated HOME (appendix C), and the last code commit (`fd57142`) also with the real spellcheck backends and under Wine.
5. **This document.** Every item was checked against the code at `80e904e` for this document (file and line references), and the test results were read from the logs. The suite and the reviewers' probes were not run again for it.
6. **Not done.** CI has never run. No real Windows, only Wine. The fixes of the review findings were checked by the fixers' own tests and the full suite, but not reviewed a second time. No human review of the code, neither by a Manuskript developer nor by the fork owner.

## Contents

1. [Changes compared to `fix/all-quickfixes`](#1-changes-compared-to-fixall-quickfixes)
2. [Open problems and effort](#2-open-problems-and-effort)
3. [Recommended order of the next steps](#3-recommended-order-of-the-next-steps)
4. [Decisions](#4-decisions)
5. [Appendix](#appendix)

## 1. Changes compared to `fix/all-quickfixes`

All 15 commits are on top of `fix/all-quickfixes` at `1d7320f`. `9288eb9` and `80e904e` change only `docs/`, so the code of `9288eb9` is that of `1d7320f`.

### 1.1 Overview

Tests are the Linux results of each commit on its own (passed; 8 skipped in every run, see appendix C).

| # | Commit | Change | Files | Lines +/− | Tests after | Purpose |
|---|---|---|---:|---:|---:|---|
| 1 | `9288eb9` | **docs:** add the design for the folder-mode save rewrite | 2 | +2974 / −0 | 622 (code of `1d7320f`) | The plan for the rest of the work (`docs/save-design/`, with `prototype.diff`) |
| 2 | `db6cbe6` | **spellcheck:** remove LanguageTool support | 8 | +155 / −547 | 616 (−6) | No Java, no 250 MB download, no checks in the GUI thread |
| 3 | `6feb53d` | **export:** hide the unfinished content filters | 2 | +85 / −60 | 619 (+3) | E5: filters that did nothing are no longer shown |
| 4 | `1139049` | **export:** remove QtWebKit and the embedded pdf.js PDF preview | 377 | +340 / −84914 | 630 (+11) | No QtWebKit, no pdf.js 1.4.237 (2016); the PDF opens in the system viewer |
| 5 | `a80ed45` | delete dead modules, shadowed methods and uncalled functions | 29 | +3 / −1136 | 630 | Code that could not run |
| 6 | `f5ede04` | require Python 3.10 and drop fallbacks for older Python and Qt | 7 | +22 / −37 | 631 (+1) | One supported floor |
| 7 | `de38879` | **macos:** remove macOS support | 13 | +60 / −494 | 634 (+3) | Linux and Windows only; "Show in folder" uses a real file URL |
| 8 | `071dab9` | **repo:** remove unused Travis, CodeClimate and TODO leftovers | 5 | +1 / −53 | 634 | Repo hygiene |
| 9 | `a709177` | **test(fixtures):** put the test projects in temporary folders | 1 | +30 / −22 | 634 | 39 setup errors on Windows (Wine), leaked sample copies |
| 10 | `71a1ad5` | **ci:** test on Linux (Python 3.10, 3.13) and Windows (3.12) | 5 | +80 / −39 | 634 | A CI matrix with Windows |
| 11 | `2d7a5de` | **load:** skip hidden and undecodable entries of a single-file project | 2 | +98 / −6 | 636 (+2) | One bad zip entry no longer blocks a `.msk`; snapshots must open |
| 12 | `a24f2c8` | **snapshots:** keep zip snapshots of each project outside its folder | 5 | +1317 / −3 | 658 (+22) | "open" and "daily" snapshots |
| 13 | `f2bf84b` | **snapshots:** take unsaved and disk snapshots | 4 | +423 / −10 | 667 (+9) | After a failed save; before an older project is replaced |
| 14 | `fd57142` | **snapshots:** open snapshots from the menu and never save into them | 3 | +386 / −7 | 674 (+7) | Restore with "Save as"; snapshots stay as they were taken |
| 15 | `80e904e` | **docs:** note that the snapshots are implemented ahead | 1 | +17 / −2 | — | Status note in `docs/save-design/README.md` |

In total, `personal/main` changes 445 files against `fix/all-quickfixes` (+5,980 / −87,319 lines). Without `libs/` and `docs/`, it is 76 files (+2,991 / −2,488), of which tests are +1,964 / −274. The suite has **682 tests** (630 on `fix/all-quickfixes`).

Where it ran:

- **Linux**, every commit: Python 3.13.16 (a venv with the system packages), system PyQt5 5.15.10 / Qt 5.15.19, `QT_QPA_PLATFORM=offscreen`, each on a fresh `git archive` with an isolated HOME, XDG folders and TMPDIR. With pyspellchecker, symspellpy and French, Italian and Catalan Hunspell dictionaries, `fd57142` gives 682 passed.
- **Windows under Wine**, `fd57142`: Windows CPython 3.12.10 (embeddable), PyQt5 5.15.11 / Qt 5.15.2, offscreen, no pandoc: 647 passed, 30 skipped, 5 failed (all from the embeddable Python, see appendix B).
- **Only on the CI work branch, before it was combined with the other work** (so without the LanguageTool, web, dead-code and snapshot commits): a real Python 3.10.20 with the CI's pip set (631 passed, 2 skipped, at its commit before the fixture fix), and Xvfb with the `xcb` platform, as in the Linux CI job (625 passed, 8 skipped). The snapshot code has not run on Python 3.10, and not under Xvfb.
- **Not run:** CI (the test jobs and the two build jobs), a real Windows, the pinned `requirements.txt` wheels on Linux for `personal/main` (they ran on `fix/all-quickfixes` with Python 3.11), and the Windows dependency set of CI anywhere: `requirements.txt` with `lxml==6.1.0`, `pyenchant==3.2.2` and `PyQt5-Qt5` set to 5.15.2. The Wine run used unpinned lxml 6.1.3 and pyenchant 3.3.0.

All Python files changed on `personal/main` parse with the Python 3.10 grammar (checked for this document with `ast`, `feature_version=(3, 10)`).

### 1.2 What was removed, added and fixed

**LanguageTool** (`db6cbe6`):

- Removed from `spellchecker.py`: `LanguageToolDictionary`, `LanguageToolCache`, the `get_languagetool_*` helpers and the `language_tool_python` / `language_check` imports.
- Removed the "start the library first" mechanism that only LanguageTool used: `BasicDictionary.isStarted/start`, `Spellchecker.startLibrary`, the `None` entries of `availableDictionaries`, and in `mainWindow.py` the "Start … to list its dictionaries" entry (BC9) and `startDictionaryLibrary`.
- Tests: 11 LanguageTool tests removed, 5 added (old projects with a LanguageTool dictionary, with and without spellcheck libraries).
- `language_tool_python` is gone from `build_linux.yml`, `build_windows.yml`, the `Dockerfile` and `package/build_for_windows.sh`.
- Kept: enchant, pyspellchecker and symspellpy, the elision handling (D5), and the default dictionary in the system's language. Old projects: P-BC1. Left behind: P13.

**Unfinished export filters, E5** (`6feb53d`):

- The six widgets of "Subitems of", "Labels" and "Status" are hidden (`ui/exporters/manuskript/plainTextSettings.py:42-49`). The code that only filled them is removed. "Ignore compile status" stays.
- The note "(Not fully implemented yet.)" is removed from the translated label at run time (`:50-54`), so the sentence before it keeps its translations. The regex was checked on all 21 finished translations. The `.ui` and `_ui.py` files are unchanged.
- `exporter.ini` keeps the keys `Parent`, `Labels` and `Status`: upstream reads them and raises `KeyError` without them (checked in `origin/develop`). The exporters never read them, so an export does not change.

**QtWebKit and pdf.js** (`1139049`):

- `ui/views/webView.py` uses QtWebEngine when it is installed, otherwise a `QTextEdit`.
- `ui/views/PDFViewer.py` and `libs/pdf.js` (pdf.js 1.4.237 from 2016) are removed: 84,914 lines.
- The pandoc PDF preview (`exporter/pandoc/PDF.py:58-108`) writes `msk_pdfpreview.pdf` to the temp folder and opens it with `QDesktopServices.openUrl(QUrl.fromLocalFile(…))` (P-BC4).
- Packaging: `manuskript.spec` no longer bundles `libs/`, the rpm spec drops `python3-qt5-webkit`, the deb control the `python3-pyqt5.qtwebkit` alternative, and `snapcraft.yaml` its qtwebkit packages.
- 11 new tests in `tests/exporters/test_pdfPreview.py`, with `openUrl` replaced. Nothing is launched. One of them runs the real pandoc and LaTeX when they are installed.

**Dead code** (`a80ed45`, −1,136 lines). Checked with an AST import scan, `.ui` headers, imports by string and pyflakes:

- Modules nothing imports:
  - `converters/markdownConverter.py`,
  - `models/persosProxyModel.py` (importing it raised `NameError`; it held all 36 undefined names of REVIEW-NOTES 3.2),
  - `models/plotsProxyModel.py`,
  - `test.py` (one newline),
  - `ui/collapsibleGroupBox.py` (`collapsibleGroupBox2` is the one in use),
  - `ui/editors/MDFunctions.py`, `ui/editors/blockUserData.py`,
  - `ui/editors/textFormat.py` with `textFormat_ui.ui` and `textFormat_ui.py`.
- Methods shadowed by a later definition: `Signal.disconnect(func)`, `characterModel.addCharacterInfo(ID)`, the second `outlineItem.charCount()`.
- Uncalled functions:
  - `functions`: `totalObjects`, `printObjects`, `inspect`;
  - `abstractModel.indexFromPath`, `plotModel.getSubPlotTextsByID`, `outlineItem.isMD/isMMD`;
  - 11 `MarkdownHighlighter` methods plus `getLuminance`, `applyAlpha` and `applyAlphaToChannel`;
  - `HighlightTokenizer.tokenLessThan`;
  - `MDEditView.getPriorMarkdownBlockItemStart` and `clearedFormatForStats`;
  - `abstractImporter.addPage`, `opmlImporter.saveNewlines`, `style.appPalette`.
- The deleted files are also gone from `i18n/manuskript.pro` and `main.pyproject`.

**Python 3.10** (`f5ede04`):

- `manuskript/__init__.py:9-12` stops older Python with a message.
- `logging.logFutureExceptions()` no longer checks for `threading.excepthook` and `sys.unraisablehook`.
- Fallbacks for Qt before 5.15 are gone: the `DataLocation` branch of `writablePath()`, the `setSupportedSchemes` check, the `setPlaceholderText` guard in `corkDelegate`, and the `QTranslator.filePath` checks.
- The README says 3.10 (`README.md:65`, from `71a1ad5`).

**macOS** (`de38879`):

- Removed: `build_osx.yml`, `package/build_osx.sh`, `package/prepare_osx.sh`, `package/osx/`, the BUNDLE section of `manuskript.spec` (with its wrong `icons/Manuscript` icon path), `Manuskript.icns`, and the Finder branch of `showInFolder()` (`functions/__init__.py:550`).
- The fallback of `showInFolder()` now opens `QUrl.fromLocalFile(path)`. `QUrl(path)` was no file URL, and a reviewer checked that this also fixes paths with spaces or `#` on Linux. New tests replace `QProcess` and `QDesktopServices`.
- The README says "runs on GNU/Linux and Windows" (`README.md:10`).

**Repo hygiene** (`071dab9`): `package/prepare_linux.sh` (Travis), `.codeclimate.yml`, `TODO.t2t` (last changed in 2015), and the makefile `compile` target, which called a `setup.py` that never existed. `package/build_for_windows.sh` is left (P14).

**Test fixtures** (`a709177`). `MWEmptyProject` and `MWSampleProject` (`tests/conftest.py:79-117`) put their project into `tmp_path_factory.mktemp()`. After the test they close it and remove the folder. Before, `MWSampleProject` copied the sample onto the name of a `NamedTemporaryFile` that was still open: Windows refuses that, which gave 39 setup errors under Wine. Each use also leaked a copy of the sample project (part of G1).

**CI** (`71a1ad5`):

- `pytest.yml` runs three jobs: `ubuntu-24.04` with Python 3.10 and 3.13 under xvfb, and `windows-latest` with Python 3.12, offscreen. `fail-fast` is off, with a 30-minute timeout.
- Each job installs `requirements.txt`, pytest, pytest-faulthandler, pyspellchecker, symspellpy and markdown. Pandoc comes from apt on Linux and from choco on Windows. A failed choco install only skips the pandoc tests.
- On Windows, `requirements.txt` is installed with `PyQt5-Qt5==5.15.2`, the last release with Windows wheels (P3).
- The job-name bug (`matrix.python_version`) is fixed in `pytest.yml` and `build_windows.yml`.
- Triggers: pushes to `develop` and `personal/**`, pull requests to `develop`, manual dispatch.
- `build_linux.yml` no longer runs the suite a second time. Both build workflows use Python 3.12 and `setup-python@v5`, and now also run on pushes to `personal/**` (`build_linux.yml:8`, `build_windows.yml:15`). Neither has run on 3.12 (P1).
- Two tests are skipped on Windows because they check POSIX file modes (`test_save_load_regressions.py:315`, `:449`).

**Single-file loader** (`2d7a5de`, `load_save/version_1.py:951-980`). The zip branch of `loadProject` now follows the folder branch's rules: hidden entries are skipped, and an entry that is not UTF-8 is listed in "Files not loaded" instead of making the whole project fail (P-BC7). Snapshots need this: they store a project folder as a single file, with its hidden files and its non-UTF-8 files.

**Snapshots** (`a24f2c8`, `f2bf84b`, `fd57142`). New module `manuskript/snapshots.py` (568 lines, standard library plus `writablePath()`, no widgets), and `tests/test_snapshots.py` (1,314 lines, 38 tests). Step 10 of the save design, implemented on today's save code. Where it hooks in:

- open: `loadSave.py:134-138`, after every successful load;
- daily and unsaved: `version_1.saveProject` (`load_save/version_1.py:176-206`), which now wraps the old body, `_saveProject`, and also takes a snapshot when the save raises;
- disk: `version_1.keepBeforeReplacing` (`:209-234`), called in the `freshTarget` branch (`:509`, `:529`) and from `MainWindow.saveDatas` for a single-file "Save as" (`mainWindow.py:1405-1409`);
- the menu: File > "Open snapshot..." (`mainWindow.py:120-126`, `:1321-1347`);
- the read-only guard: `MainWindow.refuseToSaveSnapshot` and `saveDatas` (`:1360-1393`); no last project (`:1027-1030`); no recent file (`ui/welcome.py:152-155`); a note at the first change (`:1278-1280`, `:1349-1358`);
- "Save as" from a snapshot turns `saveToZip` off (`ui/welcome.py:206-208`).

The tests never write to the user's data folder. Autouse fixtures point `snapshots.root` to temporary folders (`tests/conftest.py:12-34`); after a full isolated run, the reviewers found no snapshot outside pytest's temporary folders.

The reviews found 12 problems, all fixed:

- local-time names, which let a clock set back delete the snapshot just written: names are now UTC;
- no total size limit: other files are now capped at 20 MB each and 50 MB in all;
- a file name that is not UTF-8 made the whole snapshot fail: such names are now escaped;
- two writers in the same second could overwrite each other: the name is claimed with `os.link`;
- no `fsync` before the older project was removed: disk and unsaved snapshots are flushed;
- no daily snapshots for a project opened every day: the daily is counted from the newest daily;
- a "Save as" onto an older project removed it even when its disk snapshot was missing or incomplete: it is now refused;
- the unsaved snapshot of a failed "Save as" was filed under the target: it now goes with the project saved from;
- a snapshot became the last project and a recent file: it no longer does.

Measured on tmpfs by the implementer and the fixer: 6 ms for the sample project (the whole load takes 121 ms); 199 ms for 4,000 scenes of 300 words and 499 ms for 4,000 scenes of 1,500 words (load 2.6 s and 5.1 s); 1, 31 and 80 ms when nothing has changed.

**Design** (`9288eb9`, `80e904e`). `docs/save-design/README.md` and `prototype.diff`. Its `file:line` references are to `1d7320f`. The status note at the top says that step 10 is done and lists the deviations (section 4.3).

### 1.3 Behaviour changes the owner should know

| # | Area | Change | Why |
|---|---|---|---|
| P-BC1 | Spellcheck | A project whose dictionary is a LanguageTool one (`"dict": "LanguageTool:en-US"` in `settings.txt`) opens with the default dictionary (one in the system's language first), **without a dialog or a log message**. The next save writes that name. Without any spellcheck library, the setting is kept and nothing is checked. LanguageTool's custom-word files in the data folder (`resources/dictionaries/LanguageTool/`) are neither removed nor migrated. | LanguageTool is gone. |
| P-BC2 | Export | "Subitems of", "Labels" and "Status" and their note are hidden. `exporter.ini` keeps the three keys (`False` when missing). Exports do not change. | They did nothing (E5). Upstream reads the keys. |
| P-BC3 | Export | The HTML previews use QtWebEngine when it is installed, otherwise a `QTextEdit` (basic HTML). Where both were installed, they now render with QtWebEngine. `QT_WEB=qtwebkit`, or any value other than `qtwebengine`, gives the `QTextEdit`. Packages: the Fedora rpm (`package/create_rpm/manuskript.spec:28-30`) and the snap no longer depend on any web engine, so their HTML preview is always the `QTextEdit`. The deb now depends on `python3-pyqt5.qtwebengine` only (`package/create_deb/control:16`). | QtWebKit is gone. |
| P-BC4 | Export | Pandoc PDF "Preview" writes `msk_pdfpreview.pdf` to the temp folder and **opens it in the system's default PDF viewer**. The preview area only shows a note and the path. A failed export opens nothing and says "No PDF has been produced". If a viewer still holds the old file (Windows), a new `msk_pdfpreview-*.pdf` is used, and a later preview removes it. | pdf.js and QtWebKit are gone. |
| P-BC5 | Start | **Python 3.10 or newer.** Older versions stop with "Manuskript requires Python 3.10 or newer (running Python …)". Qt 5.15 is assumed: a PyQt5 built on an older Qt now fails with `AttributeError` instead of falling back. | One floor for code, README and CI. |
| P-BC6 | Platform | No macOS build and no macOS support. "Show in folder" opens a real file URL in its fallback (Linux, and Windows when Explorer cannot be started). | Linux and Windows only. |
| P-BC7 | Single file | In a `.msk` file, hidden entries are skipped. An entry that is not UTF-8 is not loaded. "Files not loaded" lists it and says it is not kept: **the next save of the `.msk` drops it** (the open snapshot keeps its raw bytes). A root project file that is not UTF-8 keeps the project closed. | Before, one such entry kept the whole project from opening. |
| P-BC8 | Snapshots | Location: `~/.local/share/manuskript/manuskript/snapshots` on Linux, `%LOCALAPPDATA%\manuskript\manuskript\snapshots` on Windows (not roaming). One folder per project path: `<folder name, 40 characters>-<8 hex digits of its real path>`. Names `YYYYmmdd-HHMMSS-<kind>.msk` **in UTC**, so an hour or two off local time. Files are created with mode 0600. A snapshot folder inside the project folder is refused. | Outside the project's git repository. |
| P-BC9 | Snapshots | **open**: after every successful open. **daily**: at the end of the first successful save more than 24 h after the newest *daily* snapshot, or when there is none. **unsaved**: after every save that fails once the project was serialized (also on an exception). **disk**: before an older project is removed or written over. An open or disk snapshot holds every regular file of the folder except dot-folders (`.git`) and Manuskript's `.tmp` files. The project files (`outline/`, `characters/`, the root files) are always complete. Other files go in only up to 20 MB each and 50 MB in all, smallest first. | Design section 10, with the deviations of 4.3. |
| P-BC10 | Snapshots | The newest 10 of each kind are kept (up to **40 per project path**), never removing the one just written. A snapshot equal to the newest of its kind is not written. The history is short: the last 10 opens after a change and the last 10 daily snapshots. Older states are only in git. | Disk use. |
| P-BC11 | Snapshots | **Snapshots are read-only.** File > Save, autosave, and saving on close or quit refuse. The title says "(snapshot)", the status bar says to use "Save as...", and the first change shows a note that does not wait for an answer. Closing with changes asks, as for any save that failed. "Save as" into the snapshot folder is refused. A snapshot is never a recent file or the last project. Anything inside the snapshot folder counts as a snapshot. | A snapshot must stay as it was taken, and rotation removes old ones. |
| P-BC12 | Snapshots | "Save as" from a snapshot always writes a **project folder**, also for the snapshot of a single-file project. Onto the project it was taken of, a disk snapshot of the newer state is taken first. Only what Manuskript loads is written back (P11). | The restore path. |
| P-BC13 | Save as | "Save as", or a new project, onto an older project **removes or replaces nothing unless its disk snapshot holds that project completely**. Otherwise "Project not saved" lists the reasons: the snapshot folder cannot be written, or a project file cannot be read or is in a dot-folder. Large files outside the project files are left out of the snapshot, and they are not removed either. This is the one case where a snapshot error blocks a save. | Removing the older project cannot be undone. |
| P-BC14 | Open | Every open takes an open snapshot in the GUI thread (P6). | |

### 1.4 Items of REVIEW-NOTES that are resolved or obsolete here

| REVIEW-NOTES item | On `personal/main` | Why |
|---|---|---|
| D1 LanguageTool: second JVM, cache, whole document on mouse move | obsolete | `db6cbe6` removes LanguageTool |
| D2 LanguageTool checks in the GUI thread (#280) | obsolete | `db6cbe6` |
| D3 Starting LanguageTool blocks the UI | obsolete | `db6cbe6` |
| BC9 "Start LanguageTool to list its dictionaries" | obsolete | `db6cbe6` removes the menu entry |
| E3 PDF preview URL built by concatenation (#825) | obsolete | `1139049`: `PDFViewer.py` is gone. The new preview uses `QUrl.fromLocalFile` (`exporter/pandoc/PDF.py:103`), tested with `# & ? %` and `é` in the path |
| E5 Export filters shown but ignored (rest of #978) | ✅ hidden | `6feb53d` (the "hide" option of Q12) |
| E2, part: Homebrew pandoc not found from the Finder | obsolete | `de38879`. The `pdflatex` default and `--self-contained` remain (E2 in 2.1) |
| F3, part: macOS "open with" (`QEvent.FileOpen`) | obsolete | `de38879`. `parse_known_args` and `--no-autoload` remain |
| G1, part: fixtures leak a sample copy per test | ✅ | `a709177`. The MainWindow at import time and the writes to `manuskript_tests` remain |
| G2, part: CI tests only Python 3.9, no Windows | done, never run | `71a1ad5` (P1) |
| 3.2: 36 undefined names in `persosProxyModel.py` | gone | `a80ed45` |
| 3.3.1: dead `persosProxyModel`, `plotsProxyModel`, shadowed methods | gone | `a80ed45`. `abstractModel.removed`, which grows forever, is live code and remains (`abstractModel.py:61`, `:637`) |
| 3.3.3: QtWebKit packaged, pdf.js 1.4.237 (e.g. CVE-2024-4367) | gone | `1139049` |
| 3.3.3: CI only on 3.9, no Windows tests, the matrix-key bug, a duplicate Linux test job | fixed, not run | `71a1ad5`. Still no lint step and no `pyproject.toml` |
| 3.3.3: macOS builds without the spellcheck libraries | obsolete | `de38879` |
| 3.3.3: Travis scripts, `.codeclimate.yml`, `TODO.t2t`, `manuskript/test.py`, the makefile `compile` target, the wrong `.msk` icon path in `manuskript.spec` | gone | `071dab9`, `de38879`, `a80ed45`. Still no `CONTRIBUTING.md` |
| 3.4 item 2 (test isolation) | part | `a709177`: the two old fixtures use temporary folders and close and remove their project afterwards (`tests/conftest.py:79-117`). The session-wide temporary HOME/XDG is still missing (G1, P16) |
| 3.4 item 3 (CI matrix), item 14 (Windows in CI), item 19 (drop QtWebKit) | done (3 and 14 not run, no `pyproject.toml`) | `71a1ad5`, `1139049` |
| 3.4 item 18, part: a LanguageTool worker (D2) | obsolete | `db6cbe6`. The asynchronous `QProcess` for pandoc remains |
| Q12 (E5), Q13 (LanguageTool), Q15 (versions), Q18 (QtWebKit part) | decided for this fork | Hide E5; no LanguageTool; Python 3.10, Linux and Windows; QtWebKit dropped |

## 2. Open problems and effort

Items marked ✅ are fixed. They stay in the list so that their IDs remain stable. File and line references are to `personal/main` at `80e904e`. Inherited items keep the IDs of REVIEW-NOTES; their details are in REVIEW-NOTES 2.2 (with line numbers of `eacaf8f`). For them, "open" means that the code at `80e904e` was checked and has not changed in that place.

**Effort**, as in REVIEW-NOTES: one developer who knows Python/Qt but is new to this code base, tests included. **S** ≤ ½ day, **M** 1–3 days, **L** 1–2 weeks, **XL** > 2 weeks or architectural. The S rows give the days of `docs/save-design` section 16. **Prio** is the priority **for personal use**: one user, Linux and Windows, folder-mode projects in git. **Decision** (✋) means the behaviour should be decided first (section 4).

### 2.1 Overview

| ID | Problem | Status | Effort | Prio | ✋ |
|---|---|---|:-:|:-:|:-:|
| **P — New on `personal/main`, or found or left during the personal work** ||||||
| P1 | CI has never run: the branch is not pushed. Several Windows-only paths have never run on a real runner. The first push also starts the two build workflows, never run on Python 3.12. | open | S + fixes | **high** | |
| P2 | Windows was only tested under Wine: no NTFS, Defender, indexer or OneDrive locks, no real `%LOCALAPPDATA%`. 30 tests skip there (8 on Linux). | open | S (one manual session; part of S8) | **high** | |
| P3 | Windows uses Qt 5.15.2, Linux CI Qt 5.15.17, the local runs Qt 5.15.19. `build_windows.yml` pins `pyqt5==5.15.7`. | known | — | low | |
| P4 | External changes (`git pull`, `checkout`, `stash`, another editor, a second instance) are not detected while a project is open: an edit overwrites a changed file, a deleted file is written again | open | in S5, S6, S11 | **high** | ✋ |
| P5 | `prototype.diff` no longer applies to `personal/main` (`loadSave.py`, `version_1.py`, `mainWindow.py`) | open | S (estimate) | medium | |
| P6 | Open, daily and unsaved snapshots are built in memory and compressed in the GUI thread | open | S–M | low | |
| P7 | Up to 40 snapshots per project path. The folders of moved or deleted projects are never removed. No "Open snapshot folder". | open | S | low | |
| P8 | Open and disk snapshots read the whole project folder (with caps), not the area Manuskript owns | open | in S4 | low | |
| P9 | `takeDisk()` has no call site for "Overwrite" yet (no conflict UI) | open | in S11 | low | |
| P10 | Edits in an opened snapshot live only in memory until "Save as": autosave refuses, a crash loses them | open | S–M | low | |
| P11 | Restoring with "Save as" writes back only what Manuskript loads: notes, images, research, hidden and non-UTF-8 files stay in the zip | open | S–M | medium | ✋ |
| P12 | About 17 new user-visible strings are in no `.ts` file (on top of G3) | open | S | low | |
| P13 | Dead code left by the LanguageTool removal. The mouse-move tooltip still copies the whole text at every mouse move while spellcheck is on. | open | S | low | |
| P14 | `package/build_for_windows.sh` is outdated (Python 3.8.10, pandoc 2.16.1, clones upstream) | open | S | low | ✋ |
| P15 | The README badge shows upstream's workflow (`README.md:6`) | open | S | low | |
| P16 | Running the suite on a Windows machine is not isolated by HOME/XDG | open | S | low | |
| P17 | The QtWebEngine path of the HTML preview has never run | open | S | low | |
| **S — The rest of the save rewrite (`docs/save-design` section 16; step 10 is done)** ||||||
| S1 | Linear outline paths (no behaviour change). Ends the quadratic path helpers (REVIEW-NOTES 3.3.1). | open | 0.25 d | medium | |
| S2 | Stop writing the computed `charCount`. One scene edit then no longer rewrites every ancestor `folder.txt` (git churn); every file is rewritten once. | open | 0.25 d | medium | |
| S3 | `-ID` for siblings with the same stem, ignoring case. **Closes A9** for same-folder collisions; works with today's save. | open | 0.25 d | **high** | ✋ |
| S4 | `FolderStore` recorded at load: owned area only (P8), stale `.tmp` cleanup (B9), duplicate or non-numeric character IDs renumbered | open | 1 d | high | |
| S5 | `writeFolder` replaces the cache sync: "modified" and "deleted" conflicts (P4), move-along of foreign files (**B7**), `forTarget`, no `saveCacheState` | open | 1.25 d | high | ✋ |
| S6 | The grafts: parents first, chains ordered and cycles refused (the rest of **A9**), the keep rule, path validation, "added" conflicts (P4), the re-entrancy guard (**B8**, part) | open | 1.25 d | high | ✋ |
| S7 | Models drop `_lastPath`/`lastPath` (REVIEW-NOTES 3.3.1) | open | 0.5 d | low | |
| S8 | Windows: case folding, retry on sharing violations, write probe, long-path warning, Windows-only tests in CI, one manual session (P2) | open | 2 d | high | ✋ |
| S9 | `fsync` per file in folder mode (**B9**), the save fuzzer as a slow test | open | 1.25 d | medium | ✋ |
| S11 | Reload / Overwrite / Cancel asked once, Overwrite with a disk snapshot (P9), quiet autosave (P4) | open | 1.25 d | high | ✋ |
| S12 | *Optional:* check for external changes when the window is activated (P4) | open | 0.5 d | low | ✋ |
| **A — Data loss and crashes (inherited)** ||||||
| A1–A5 | ✅ on `fix/review-findings`, part of `personal/main` | — | — | — | |
| A6 | Outline tab: when the first selection is a multi-selection, the first key in the full summary raises `AttributeError` and the app exits (`ui/views/MDEditCompleter.py:34-41`, `:85-100`) | open | S | **high** | |
| A7 | Browsing plot steps, or a new project from a template, marks the project modified (the plot steps: `mainWindow.py:697-698`) | open | S | low | |
| A8 | Segfault when a project is closed and another opened in the same event-loop pass, after an "outline" folder view (`mainWindow.py:986`, `ui/editors/tabSplitter.py:100-103`) | open | S–M | low | |
| A9 | Two siblings whose titles give the same file name (`Grüße`/`Größe` → `Gr--e`; CJK titles of the same length; long titles cut at 64) swap rows: one failed write plus "Discard", or a crash between the two writes, loses one scene (`load_save/version_1.py:880-907`) | open | S (S3, then S6) | **high** | ✋ |
| **B — Robustness and data safety (inherited)** ||||||
| B1 | Global excepthook calls `sys.exit(1)` on any uncaught exception (`logging.py:155-167`) | open | M | **highest** | ✋ |
| B2 | ✅ `07dce72`. The fork owner checked it by hand on `fix/all-quickfixes` with the Breeze style: no crash seen. Adwaita-qt was not checked. Whether `develop` crashes in the same setup was not checked either, so this does not prove the fix. | — | — | — | |
| B3 | One damaged `plots.xml`/`world.opml`/`revisions.xml` (`version_1.py:1164`, `:1200`, `:1287`), a `folder.txt` without ID (`:1392`) or a non-numeric outline ID (`models/abstractModel.py:72`) keeps the project from opening. A merge conflict left in one of these files would do the same (reasoned, not tested). | open | M | medium | ✋ |
| B4 | Multi-line metadata is not round-trip safe (`version_1.py:84`, `:1513`). An editor, a hook or `git apply --whitespace=fix` that trims trailing whitespace moves notes into the scene text. | open | M | medium | |
| B5 | Deleting a label or status relabels items (`settingsWindow.py:733-756`) | open | S | medium | ✋ |
| B6 | Character, plot and world IDs reuse the lowest free number (`models/characterModel.py:331-341`, `plotModel.py:110-123`, `worldModel.py:146-163`) | open | M | medium | ✋ |
| B7 | Files Manuskript did not load stay behind when their folder is renamed: only unreadable files are moved (`version_1.py:637-658`) | open, by S5/S6 | M | medium | ✋ |
| B8 | The signal handler calls `MW.close()` directly (`main.py:318-332`): it can nest a save, and the modal "Save?" blocks a logout | open; S6 adds the guard | S | low | ✋ |
| B9 | No `fsync` in folder mode (`writeFile(…, sync=False)`, `version_1.py:125`), stale `.tmp` files stay, `exporter.ini` has its own tmp+replace | open, by S4 and S9 | S | low | ✋ |
| **C — Editor (inherited)** ||||||
| C1 | Qt UTF-16 positions mixed with Python indices | open | M | low (needs characters outside the BMP, such as emoji) | |
| C2 | Undo stuck after a paragraph-format change (`ui/highlighters/basicHighlighter.py:132-144`) | open | M | low | |
| C3 | An item switch re-highlights the old text about 7 times (`ui/views/textEditView.py:119`) | open | S–M | medium | |
| C4 | Every Space submits the whole text (`textEditView.py:414-415`) | open | S | low | ✋ |
| C5 | List continuation: a `-- ` line is cleared, `z)` continues as `{)` (`ui/views/MDEditView.py:23-25`, `:111-123`, `:143-147`) | open | S | low | ✋ |
| **D — Spellcheck (inherited)** ||||||
| D1–D3 | Obsolete: LanguageTool is gone (1.4) | — | — | — | |
| D4 | The clitic list is the same for every language (`functions/spellchecker.py:199`) | open | S | low | ✋ |
| D5 | ✅ `92bee56` | — | — | — | |
| D6 | A word in `‘…’` gets a spelling menu without an underline (`spellchecker.py:471-482`) | open | S | low | |
| **E — Import, export, search (inherited)** ||||||
| E1 | Pandoc export drops scene text shaped like a YAML block (`exporter/pandoc/abstractPlainText.py:178-180`) | open | S | medium | ✋ |
| E2 | Default PDF engine `pdflatex` fails on common Unicode (also on the sample), `--self-contained` is deprecated (`abstractPlainText.py:197-211`). The Homebrew part is obsolete. | open (part) | S | medium if PDF export is used | ✋ |
| E3 | Obsolete (1.4) | — | — | — | |
| E4 | Search results keep their offsets after edits (`functions/__init__.py:466-476`) | open | M | medium | |
| E5 | ✅ hidden (`6feb53d`) | — | — | — | |
| E6 | "Replace single quotes" pairs apostrophes (`exporter/manuskript/plainText.py:224`) | open | S | low | |
| E7 | Zero-length regex matches flood the results, context HTML not escaped (`functions/__init__.py:475`, `:479-506`) | open | S | low | |
| E8 | Importer: empty folders, insert signals bypassed (`ui/importers/importer.py:263`), "Import under" ignored | open | S | low | ✋ |
| **F — App shell (inherited)** ||||||
| F1 | Settings need an open project (`mainWindow.py:1019`, `:1151`) | open | M | low | ✋ |
| F2 | No "Clear list" for recent projects | open | S | low | ✋ |
| F3 | `argparse` rejects Qt options (`main.py:368`), no `--no-autoload`. The macOS part is obsolete. | open (part) | S | low | |
| F4 | World remove loop (`models/worldModel.py:165-168`), `with_tail` (`abstractModel.py:385`), `canDropMimeData` decodes everything (`:316`) | open | S | low | |
| **G — Tests, CI, i18n (inherited)** ||||||
| G1 | The fixture leaks are fixed (`a709177`). The test package still creates the MainWindow at import time (`tests/__init__.py:11-17`) and writes to `manuskript_tests` (`main.py:84-86`) | open (part) | S | low | |
| G2 | → P1 | — | — | — | |
| G3 | The 23 strings of the fix branches (minus the LanguageTool menu entry, which is gone) are in no `.ts`; `'Open {}'` can never be translated (`ui/views/outlineBasics.py:123`); a literal at `ui/welcome.py:343` | open | S | low | ✋ |
| G4 | Rare segfault at interpreter exit (`textEditView.py:779-782`) | open | S | low | |

**What this adds up to.** The rest of the save rewrite is **9.25 days** (S1–S9, S11), plus 0.5 for S12. It closes A9, B7, B9, P4, P8 and P9 and part of B8, and S8 includes the manual Windows session P2 asks for. P5 adds some porting work on top (section 2.2). B1 is M (about 3 days). The small fixes the owner was pointed to (A6, B4, B5, B6, E1, E7) are about 6 days, and B5, B6 and E1 need a decision first. The larger items left after that are B3, C1–C3, E4 and F1.

### 2.2 Details

Only the P items and A9 are described here. For the other inherited items, see REVIEW-NOTES 2.2. For the S steps, see `docs/save-design` sections 4–11 and 16.

#### A9 — Same-slug swap loses a scene (data loss)
- **Where:** `outlineItemPath` (`load_save/version_1.py:880-907`) appends the ID only when titles are *identical*. Titles that differ but slugify alike share a stem: `slugify` (`:107-122`) turns each character that is not an ASCII letter, digit or whitespace into one `-` (whitespace into `_`). Examples: `Grüße` and `Größe` both give `Gr--e`; CJK titles of the same length collide (`你好` gives `--`, `第一章` gives `---`, `世界和平` gives `----`); long titles that share their first 64 characters collide after the cut. When two such siblings swap rows (`0-Gr--e.md` ↔ `1-Gr--e.md`), each write goes over the other item's only file. If the second write fails (disk full, permission, a Windows lock) and the user then chooses "Discard", or the app exits (B1), one text is in no file. A crash between the two writes has the same effect.
- **Evidence:** Found by the save-design judges, and reproduced on a tree of `1d7320f` (a reorder with a failed write and "Discard" loses `Größe`). The naming code and the folder-mode move code are unchanged on `personal/main`. The probe was not run again on `80e904e`.
- **Fix:** S3 (¼ day): siblings whose stems collide, ignoring case, all get `-ID`. For identical short titles that gives today's names. The rare cases left (chains across folders, a title equal to another item's stem plus its ID) are ordered or refused by S6. Decision 4 (section 4.2) chooses between `-ID` for colliding siblings and an ID in every outline file name.
- The save fuzzer of REVIEW-NOTES (61 seeds, no loss) did not find it. Why was not checked.

#### P1 — CI has never run
- **State:** `pytest.yml` runs on pushes to `personal/**`, but `personal/main` has never been pushed. GitHub Actions may need to be enabled on the fork (not checked). The owner pushes the branches. One agent reported that the fork's last "Pytest Run (Linux)" on `develop` passed (2026-10-31), which would mean that Actions is already enabled. That was not verified (`gh` was not available).
- **Two build workflows start too.** Since `71a1ad5`, `build_linux.yml` and `build_windows.yml` also run on every push to `personal/**` (`build_linux.yml:8`, `build_windows.yml:15`). Neither has ever run with Python 3.12 and `setup-python@v5` (before: Python 3.9). The Windows build pins `pyqt5==5.15.7` (`build_windows.yml:42`), and its "Remove W7 File Issues" step deletes DLLs by fixed paths under `dist/manuskript/` (`:49-53`). Whether those paths exist in a build on 3.12 was not checked.
- **What may fail first** (expected from reading the code and from the Wine run, not observed):
  - Windows: `QSettings` uses the registry there, so `recentFiles` can come back as another list type in `ui/test_welcome` and `ui/test_saveAsFailure`.
  - Windows: the symlink and hard-link tests run on GitHub's runners. Their `realpath`/`islink` behaviour on NTFS has never run.
  - Windows: the `sed` override of `PyQt5-Qt5` and the choco/`refreshenv` pandoc step have never run. A failed pandoc install only skips the pandoc tests.
  - Windows: the dependency set of the job has never run anywhere. It is `requirements.txt` (`lxml==6.1.0`, `pyenchant==3.2.2`, `PyQt5==5.15.11`) with `PyQt5-Qt5==5.15.2`. The Wine run used unpinned lxml 6.1.3 and pyenchant 3.3.0 (appendix B). A reviewer checked on PyPI that all pinned versions have Windows wheels.
  - Linux 3.10: the snapshot code has never run on Python 3.10 (1.1).
  - The two build jobs (above): never run on Python 3.12.
  - Any job: a modal dialog would block the job until the 30-minute timeout.
- **Fix:** push, read the logs of the three test jobs and the two build jobs, fix what fails. S, plus the fixes.

#### P2 — Windows only under Wine
- **State:** The Wine run (appendix B) shows that the suite runs with a Windows Python and Qt 5.15.2, and that nothing in the product code failed. Wine is not Windows. Not covered:
  - `os.replace` over a file that another program holds open (Defender, the indexer, OneDrive, a PDF viewer);
  - case-only renames on NTFS (a Linux test emulates them);
  - paths over 260 characters;
  - the real `%LOCALAPPDATA%` snapshot folder.
- **Skipped under Wine** (30 tests, 8 on Linux): 5 read-only-folder tests in `ui/test_saveAsFailure.py` (so the failed "Save as" path is untested there), 7 unreadable-file tests, 2 POSIX file-mode tests, 4 `test_main` tests (`/proc`, POSIX signals), 3 snapshot tests (non-UTF-8 names, an unreadable file), 7 pandoc and POSIX-permission tests, and 2 enchant tests without French or Italian dictionaries.
- **Fix:** S8 includes a Windows CI job for the store tests and one manual session (Defender, OneDrive, an editor holding a file, a case-only rename, a deep path). Until then, keep the Windows project in git and commit often.

#### P3 — Qt versions differ
- `PyQt5-Qt5` 5.15.2 is the last release with Windows wheels (checked on PyPI by an agent), so Windows runs Qt 5.15.2 (2020) and Linux the pinned 5.15.17. The local runs used the system Qt 5.15.19.
- `build_windows.yml:42` installs `pyqt5==5.15.7` and the other packages unpinned, so the Windows build is not the tested set.
- Nothing to fix in the tests. Keep it in mind when a bug shows up on one platform only. Aligning the build's pins is S.

#### P4 — External changes are not detected
- **Where:** today's save writes a file only if its content differs from the cache or the file is missing (`load_save/version_1.py:585-594`). The disk is never compared with what was loaded. While a project is open:
  - a file that git or an editor changed is overwritten the next time that item is edited;
  - a file that git deleted is written again at the next save;
  - files that git added are not loaded until the next open, and can be orphaned if their folder is removed in Manuskript;
  - a second Manuskript instance on the same folder overwrites the other's changes.
- **Workaround now:** close the project (or quit) before `git pull`, `checkout`, `merge`, `stash` or `rebase` on the project repository, and open it again afterwards.
- **Fix:** S5 ("modified" and "deleted" conflicts), S6 ("added"), S11 (Reload / Overwrite / Cancel), optionally S12. Decisions 1 and 2.

#### P5 — The prototype no longer applies
- `git apply --check` of `docs/save-design/prototype.diff` (run with a temporary index for this document) passes on `1d7320f` and fails on `personal/main` in `manuskript/loadSave.py`, `manuskript/load_save/version_1.py` and `manuskript/mainWindow.py`. The snapshot commits split `saveProject` into `saveProject`/`_saveProject`, added `keepBeforeReplacing` to the `freshTarget` branch that S5 deletes, and added the open snapshot to `loadSave.loadProject`.
- S4–S6 must therefore port the prototype by hand. In the design, the disk snapshot moves into `forTarget`. The design's estimate assumed the patch applies. The extra work is probably S (an estimate, not measured).

#### P6 — Snapshot cost in the GUI thread
- The open snapshot runs inside `loadSave.loadProject` (`loadSave.py:134-138`) before the window shows the project. The daily and unsaved snapshots run at the end of a save. A snapshot is built in memory, and files that are already compressed (images, PDF) are deflated again.
- Measured on tmpfs: 6 ms for the sample, 199–499 ms for 4,000 scenes, 652 ms for the sample plus 25 random 19 MB images (2 of them included). Real disks and Windows were not measured.
- **Fix:** store compressed files with `ZIP_STORED`, stream instead of building in memory, or move the work to a thread. S–M. Low priority for a novel-sized project.

#### P7 — Snapshot disk use and cleanup
- 10 per kind and 4 kinds give up to 40 snapshots per project path. Project files have no size cap. For a generated 32 MB project (16.9 MB per snapshot), that is up to about 680 MB.
- Each project path gets its own folder. Rotation only works inside a folder, so the folder of a moved, renamed or deleted project stays forever.
- There is no menu item that shows the snapshot folder. File > "Open snapshot..." opens a file dialog in it.
- **Fix:** an "Open snapshot folder" item, and removing project folders without a project after some months. S.

#### P8 — Snapshots read the whole project folder
- Without a `FolderStore`, `readFolder` (`snapshots.py:211`) reads every regular file outside dot-folders. Research files go in up to the caps of P-BC9.
- Once S4 records the owned area, open and disk snapshots can be limited to it, as the design says. In S4.

#### P9 — No "Overwrite" yet
- `takeDisk()` is called only before an older project is replaced (`version_1.py:509`, `:529`; `mainWindow.py:1409`). The design's other call site, before "Overwrite" after a conflict, comes with S11. Nothing to do before S11.

#### P10 — Edits in a snapshot are only in memory
- After File > "Open snapshot...", every save is refused (P-BC11). The note at the first change says so, but a crash, a kill or a power loss loses those edits. No unsaved snapshot is written, because that needs a save path that only serializes.
- **Fix:** a serialize-only path, and an unsaved snapshot of the snapshot at autosave (S–M). The same path would serve B1's recovery copy (section 3). Low priority: restore with "Save as" first, then edit.

#### P11 — Restoring writes back only what Manuskript loads
- "Save as" from a snapshot writes the project as Manuskript serializes it (the tests compare that). Everything else in the zip is not written back: notes, images and research in the folder, hidden files such as `.gitignore`, files that are not UTF-8, and anything the parser drops. In the zip loader (`version_1.py:951-980`), hidden entries are skipped and non-UTF-8 entries are not loaded. Other files are read but belong to no model, and a save writes only the models.
- Opening the snapshot of a folder that holds images or PDFs therefore shows "Files not loaded" each time.
- Onto the original folder (`test_restore_a_snapshot_over_its_project`), the save first takes a disk snapshot, then removes `outline/`, `characters/` and the root project files (`version_1.py:529-540`) and writes the project. Files elsewhere in the folder (`research/`, notes at the root) stay. Foreign files inside `outline/` or `characters/` are removed, but they are in that disk snapshot. Into a new folder, everything Manuskript does not load must be extracted from the zip by hand (any unzip tool).
- **Fix:** let "Save as" from a snapshot also extract the entries it does not load, or skip binary files in the "Files not loaded" dialog for snapshots. S–M. **Decision:** is extracting by hand acceptable?

#### P12 — New strings are not translated
- About 17 new strings use `tr()`/`safeTranslate()`: 4 in the PDF preview, 1 in the single-file loader ("Files not loaded"), and about 12 for snapshots (the refusal to replace an older project, the menu action and its status tip, the title, the status messages, the note, the refusal dialog, the file dialog). None is in `i18n/*.ts`. They show in English in every language. G3 is the same for the fix branches.
- **Fix:** `make translation` once the strings are stable. S.

#### P13 — Dead code left by the LanguageTool removal
- Only LanguageTool matches reached:
  - the grammar and style branch of the editor's context menu (`ui/views/textEditView.py:703-738`);
  - the issue-type colour table (`ui/highlighters/basicHighlighter.py:36-64`; only `misspelling` is used);
  - `BasicMatch.locqualityissuetype` and `msg` (`functions/spellchecker.py:182-188`).
- `Spellchecker.availableLibraries` (`spellchecker.py:116`) has no caller.
- The mouse-move tooltip (`textEditView.py:490-517`) can never show anything: `cursorForPosition` gives an empty selection, and `findSuggestions` returns `[]` for it (`spellchecker.py:471-482`). It still calls `self.toPlainText()`, a copy of the whole text, at every mouse move while spellcheck is on. Not measured.
- **Fix:** remove them in one commit. S.

#### P14 — `package/build_for_windows.sh`
- It builds under Wine with Python 3.8.10 (below the new floor) and pandoc 2.16.1, from a clone of upstream (`REPOSITORY="https://github.com/olivierkes/manuskript.git"`), so it never builds this fork. `build_windows.yml` builds on GitHub instead.
- **Fix:** delete it, or point it at the fork with Python 3.12. S. **Decision:** keep a local Windows build path or not.

#### P15 — README badge
- `README.md:6` shows upstream's workflow "Pytest Run (Linux)". This fork's workflow is "Pytest" (`pytest.yml`). S.

#### P16 — The suite on a Windows machine
- On Windows, `QSettings` writes to the registry (`HKCU\Software\manuskript_tests`) and `writablePath()` to `%LOCALAPPDATA%\manuskript_tests`, with the test names from `main.py:84-86`. HOME and XDG do not isolate these. The real `manuskript` settings are not touched: the subprocess tests that use the real names are Linux-only (`tests/test_main.py:29`, `:124`). Snapshots go to temporary folders (P-BC8 does not apply to tests). This was reasoned from the code, not checked on Windows.
- **Fix:** a note in a CONTRIBUTING file, or `QSettings.setDefaultFormat(IniFormat)` and a temporary path for the tests. S.

#### P17 — QtWebEngine path not run
- QtWebEngine was not installed in the test environment, so every HTML-preview check used the `QTextEdit`. On a machine with QtWebEngine, the HTML preview takes the other branch of `webView.py`. Check by hand once. S.

## 3. Recommended order of the next steps

This is the order the owner was given, with step 0 added. Step 0 costs little and needs the owner, because the owner pushes the branches.

| Step | What | Effort | Closes |
|---|---|---|---|
| 0 | Push `personal/main` to the fork (check that Actions is enabled, not checked so far), read the first run of the test and build jobs, fix what fails | S + fixes | P1 |
| 1 | Save rewrite S1–S3 (decision 4 first) | 0.75 d | **A9** (most of it), quadratic paths, `charCount` churn |
| 2 | Save rewrite S4–S9 and S11, porting the prototype (P5). S12 if time allows. | 8.5 d (+0.5) + P5 | **B7**, B8 (guard), **B9**, **P4**, P8, P9, the rest of A9. S8 brings the manual Windows session (P2) |
| 3 | The excepthook B1 (decision Q4 first) | M (about 3 d) | **B1** |
| 4 | Small fixes: A6 (S), B4 (M), B5 (S, ✋), B6 (M, ✋), E1 (S, ✋), E7 (S) | about 6 d | A6, B4, B5, B6, E1, E7 |
| | **Total** | **about 18 d** | plus CI fixes and the time for decisions |

Why this order:

- S1–S3 work with today's save code (design section 16), take less than a day, and S3 removes the only known data loss that is left (A9).
- The rest of the rewrite comes before B1, because B1's "save a recovery copy" is simpler once saving is one object that does not change the models. The recovery copy could be an "unsaved" snapshot written to the snapshot folder (an idea, not in the design). The serialize-only path it needs would also fix P10.
- B7 needs no separate fix: S5 moves foreign files along with a renamed folder (decision 3).
- Until step 2 is done: close the project before using git on it (P4).

After that, in no fixed order: B3 (M, more likely with git merges), A8 (S–M), C3 (S–M), E2 (S), E4 (M), P10 and P11 (S–M each), P12–P17 (S each), G3 (S).

## 4. Decisions

### 4.1 Decided

- **The cuts:** LanguageTool, the unfinished export filters (hidden), QtWebKit and pdf.js, dead modules, Python before 3.10, macOS (`docs/save-design/README.md:30`; commits 2–8).
- **A Windows job in CI** (`71a1ad5`), next to Linux with Python 3.10 and 3.13.
- **Snapshots as recommended** in decision 7 of the design: 10 per kind, in `AppLocalDataLocation`, daily snapshots on top of the open ones. Implemented ahead of the rewrite (`a24f2c8`–`fd57142`).

### 4.2 Open: the save design (section 18)

The owner has not answered these yet. Each has a recommendation in the design. The "Needed by" column says which step needs the answer.

| # | Question | Recommendation | Needed by |
|---|---|---|---|
| 1 | Conflict policy: stop the whole save and ask, or write the files that do not conflict? | Stop and ask. A partial write mixes the states of two machines. | S5 |
| 2 | New loadable files from outside (a pull that adds scenes): a conflict offering Reload, or ignore them until the next open? | Conflict with Reload | S6 |
| 3 | B7: move foreign files along with their renamed folder, or leave them and report? | Move them along | S5 |
| 4 | Same-stem names: `-ID` only for siblings whose stems collide (ignoring case), or an ID in every outline file name? | `-ID` only where stems collide (a one-time rename of the few affected items) | **S3, the first step** |
| 5 | Long paths on Windows: keep 64 and set `LongPathsEnabled=1` and `core.longpaths=true` once, or cap names at 40? | Keep 64 and set them once | S8 |
| 6 | `fsync`: always per file, or only on explicit save and close? | Always (revisit if S9 measures stutter) | S9 |
| 8 | `settings.txt` churn: move UI state to per-project QSettings later; turn `revisions.keep` off for git projects? | Later; turn `revisions.keep` off now | any time (`revisions.keep` is a project setting) |
| 9 | Code location: keep the store in `version_1.py`, or a Qt-free `folderstore.py` now (+0.5 d)? | Keep it in `version_1.py` | S4 |
| 10 | Project repository: add `.*.tmp` to `.gitignore` and `* -text` to `.gitattributes` yourself? | Yes. Manuskript creates no files in the repository. | any time |
| 11 | Check for external changes when the window is activated (S12)? | Yes, if time allows | S12 |

### 4.3 Open: three deviations taken by the snapshot implementer

Each is explained in its commit message and in the status note of `docs/save-design/README.md:3-19`. The owner has not confirmed them.

| Deviation | Design text | Implemented | Recommendation |
|---|---|---|---|
| Names in UTC | not specified (local time in the first version) | UTC; a name dated in the future counts as the oldest (`snapshots.py:82-84`) | Keep. With local time, a clock set back (daylight saving, NTP) deleted the snapshot just written (reproduced by a reviewer). |
| Daily snapshot | due 24 h after the newest snapshot of any kind | due 24 h after the newest *daily* snapshot (`snapshots.py:556-563`) | Keep. Otherwise a project opened every day never gets one, and the history is only 10 opens deep (reproduced). |
| "Save as" onto an older project | "errors never block saving" | refused, with nothing removed, unless the disk snapshot is complete (`version_1.py:209-234`) | Keep. It is the one irreversible step, and the snapshot is the only copy. |

### 4.4 Open: decisions the next fixes need (from REVIEW-NOTES section 4)

- **B1 (Q4):** keep "fail fast", or log → one dialog → separate recovery copy → the user chooses. May autosave keep writing the real project after "Continue"?
- **B5, B6 (Q8):** reset items that use a deleted label or status to "none", or ask first? IDs: `max+1`, or a persisted counter (a format change)?
- **E1 (Q11):** turn YAML metadata blocks off by default (and migrate `exporter.ini`), or detect and warn?
- Later: B3 (Q5), salvage damaged files, or refuse to open but name the broken file? C4 (Q14), C5, D4, E8, F1, F2 (Q21). P11 and P14 (section 2.2).

## Appendix

### A. Running the tests in isolation (Linux)

The test package still creates a MainWindow at import time and writes to the Qt settings and data folders (G1). Run the suite with a throw-away HOME:

```sh
T=$(mktemp -d)
mkdir -p "$T/config" "$T/data" "$T/tmp"
HOME=$T XDG_CONFIG_HOME=$T/config XDG_DATA_HOME=$T/data TMPDIR=$T/tmp \
QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider manuskript/tests
rm -rf "$T"
```

Expected at `fd57142`/`80e904e`: **674 passed, 8 skipped**. The 8 skipped tests need pyspellchecker, symspellpy, or French, Italian and Catalan dictionaries for enchant. For those runs, the `.aff`/`.dic` files were copied into `$T/config/enchant/hunspell/`, and pyspellchecker and symspellpy came through `PYTHONPATH`. With them, all **682 pass**. The snapshot tests write only to pytest's temporary folders (autouse fixtures in `tests/conftest.py:12-34`).

### B. Checking Windows under Wine (a recipe to repeat)

This is how the Wine runs in this document were made. **Set the isolation before the first `wine` call.** In the first probe, `wineboot` ran before HOME was isolated. Wine's `winemenubuilder` then rewrote six `wine-extension-*.desktop` files, the MIME cache and some icons under the real `~/.local/share`. The agent repaired the six files by hand (copies of what Wine left are in the scratchpad's `wine_incident/`) and rebuilt the caches. It could not prove that the icons are byte for byte the old ones. Checking those six files once is worthwhile.

```sh
S=/path/to/an/empty/folder        # not your own Wine prefix
mkdir -p $S/home/c $S/home/d $S/home/cache $S/home/tmp
# 1. Isolation, before anything starts Wine
export HOME=$S/home XDG_CONFIG_HOME=$S/home/c XDG_DATA_HOME=$S/home/d \
       XDG_CACHE_HOME=$S/home/cache TMPDIR=$S/home/tmp
export WINEPREFIX=$S/prefix WINEDEBUG=-all \
       WINEDLLOVERRIDES="mscoree,mshtml=;winemenubuilder.exe=d"
unset DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS
wineboot -i
# 2. The prefix's user folders can be links into a real home: make them plain folders
U=$WINEPREFIX/drive_c/users/$USER
for d in Desktop Documents Downloads Music Pictures Videos \
         AppData/Roaming/Microsoft/Windows/Templates; do
  if [ -L "$U/$d" ]; then rm "$U/$d"; mkdir -p "$U/$d"; fi
done
# 3. Windows Python (embeddable), with site-packages enabled
cd $S && curl -LO https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip
mkdir py && (cd py && unzip -q ../python-3.12.10-embed-amd64.zip)
printf 'python312.zip\r\n.\r\nLib\\site-packages\r\nimport site\r\n' > py/python312._pth
# 4. Windows wheels, unpacked (colorama separately: pip does not apply
#    pytest's win32 marker for a foreign platform)
python3 -m pip download --only-binary=:all: --platform win_amd64 --python-version 3.12 \
  -d $S/wheels PyQt5==5.15.11 PyQt5-Qt5==5.15.2 PyQt5_sip lxml pytest pyenchant \
  markdown pyspellchecker symspellpy
python3 -m pip download --only-binary=:all: --platform win_amd64 --python-version 3.12 \
  --no-deps -d $S/wheels colorama
mkdir -p $S/py/Lib/site-packages
for w in $S/wheels/*.whl; do unzip -q -o "$w" -d $S/py/Lib/site-packages; done
# 5. The tree and the run
mkdir $S/tree && git -C /path/to/manuskript archive personal/main | tar -x -C $S/tree
cd $S/tree && QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  timeout 1500 wine $S/py/python.exe -m pytest -q -p no:cacheprovider -rs manuskript/tests \
  > $S/result.txt 2>&1
iconv -f latin1 -t utf-8 $S/result.txt | tr -d '\r' | tail -40    # latin-1, CRLF
# 6. Clean up: a run leaves about 44,000 files of pytest folders in the prefix's Temp
wineserver -k
rm -rf $S/tree "$U/AppData/Local/Temp/"*
```

The probe used PyQt5 5.15.11 / Qt 5.15.2, lxml 6.1.3, pyenchant 3.3.0 and pytest 9.2.0. CI installs `lxml==6.1.0` and `pyenchant==3.2.2` from `requirements.txt` instead. To test that set, pin them in the `pip download` line. Inside Wine, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA` and `TEMP` point into the prefix, so the suite's settings and data stay there. A full run takes 2–4 minutes. The prefix takes about 460 MB and the Python with the wheels about 290 MB.

**Known artefact failures.** At `fd57142` the result is "5 failed, 647 passed, 30 skipped". All 5 are tests that start a child Python with `-c` and get `ModuleNotFoundError: No module named 'manuskript'`: `test_htmlPreviewFallback[qtwebkit]`, `test_htmlPreviewFallback[none]`, `test_tooOldPython[version0]`, `test_tooOldPython[version1]` and `test_supportedPython`. The embeddable Python's `python312._pth` leaves the current folder off `sys.path`. With the tree's folder added to `python312._pth` for the run, the two `test_pythonVersion` failures went away (checked once, on `9288eb9`). A normal CPython, like the one `setup-python` installs in CI, should not have them (expected, not checked).

### C. Test results per commit

Linux: the full suite on a fresh `git archive` of each commit, with an isolated HOME, Python 3.13.16, system PyQt5 5.15.10 / Qt 5.15.19, offscreen. "Real backends": with pyspellchecker, symspellpy and Hunspell fr/it/ca. Wine: appendix B.

| Commit | Linux | Real backends | Wine (Windows Python 3.12.10, Qt 5.15.2) |
|---|---|---|---|
| `1d7320f` (`fix/all-quickfixes`, code of `f78f2bb`) | 622 passed, 8 skipped | 630 passed | — |
| `9288eb9` (docs only, code of `1d7320f`) | (as `1d7320f`) | | 563 passed, 24 skipped, 4 failed, 39 errors. With two probe-only test patches: 604 passed, 24 skipped, 2 failed |
| `db6cbe6` | 616 passed, 8 skipped | | |
| `6feb53d` | 619 passed, 8 skipped | | |
| `1139049` | 630 passed, 8 skipped | | |
| `a80ed45` | 630 passed, 8 skipped | | |
| `f5ede04` | 631 passed, 8 skipped | | |
| `de38879` | 634 passed, 8 skipped | | |
| `071dab9` | 634 passed, 8 skipped | | |
| `a709177` | 634 passed, 8 skipped | | |
| `71a1ad5` | 634 passed, 8 skipped | | |
| `2d7a5de` | 636 passed, 8 skipped | | |
| `a24f2c8` | 658 passed, 8 skipped | | |
| `f2bf84b` | 667 passed, 8 skipped | | |
| `fd57142` | **674 passed, 8 skipped** | **682 passed** | **647 passed, 30 skipped, 5 failed** (artefacts, appendix B) |
| `80e904e` (docs only) | (as `fd57142`) | | |

On `9288eb9`, the 39 errors were all the `MWSampleProject` fixture (`PermissionError` on an open `NamedTemporaryFile`), fixed by `a709177`. Two of the 4 failures were the POSIX file-mode tests, now skipped on Windows by `71a1ad5`, and two were `test_pythonVersion` (the embeddable Python). The probe-only patches were the fixture change that `a709177` later made, and the tree added to `python312._pth`.

### D. Method and limitations

- **Sources:** the commit messages of `fix/all-quickfixes..personal/main`, `docs/save-design/README.md`, the reports of the implementers, reviewers, fixers and judges, and the test logs. REVIEW-NOTES v2 for the inherited items.
- **Checked for this document:** every `file:line` reference at `80e904e`; that the inherited open items are unchanged in the code; that `prototype.diff` applies to `1d7320f` but not to `personal/main` (`git apply --check` with a temporary index); that the changed Python files parse with the 3.10 grammar; the test counts in the Linux and Wine logs; what is on `origin` (local remote-tracking refs, not fetched again).
- **Not run again for this document:** the test suite, the reviewers' and judges' probes (A9, the snapshot findings), and the measurements. Those numbers come from the agents' reports.
- **Not available:** CI, a real Windows, NTFS, Defender or OneDrive, QtWebEngine, Adwaita-qt, pandoc under Wine, Python 3.10 for the snapshot commits, a real X server for them (one Xvfb run before them).
- **Line numbers:** `80e904e` unless stated otherwise. `docs/save-design` refers to `1d7320f`, REVIEW-NOTES to `eacaf8f`.
- **Effort** figures are estimates, as in REVIEW-NOTES. The S rows are the design's own figures, made before the snapshot commits (P5).
