# Manuskript: bug-fix branches, open problems and code-quality review

*Discussion paper for the Manuskript maintainers, written November 2026. The fix branches (`fix/*` and `fix/all-quickfixes`) are to be published in the fork [sniemeyer42/manuskript](https://github.com/sniemeyer42/manuskript). At the time of writing they exist only locally. All branches are based on `develop` at `01e0574` (2026-09-02).*

## TL;DR

- On `develop`, folder-mode projects can **lose text**, often silently. This happens when items with similar titles are reordered or moved, when the editor tree is used for drag and drop, and when a save or load fails. Duplicating a folder, or moving "Chapter 10" above "Chapter 1", makes every later save crash. Any uncaught exception closes the app without saving. These bugs explain several upstream data-loss reports (e.g. #719, #1306, #1320). They are the biggest risk for people who write real projects in Manuskript, and they can be fixed without changing its concept or file format.
- Seven fix branches (84 small commits) address many data-loss, crash, performance and usability bugs. Together they reference 36 upstream issues, several of them long-standing. `fix/all-quickfixes` combines all seven. The test suite grows **from 39 to 412 tests**.
- Some problems are still open. Section 2 lists each with an effort estimate. The most important:
  - the fail-fast excepthook (B1),
  - data-loss bugs found during this review that also exist on `develop` (A1–A3),
  - a scroll-bar segfault with some Qt styles (B2),
  - damaged project files that keep a whole project from opening (B3).
- Section 3 is a code-quality assessment with incremental proposals. Section 4 collects the questions maintainers need to decide.

## How this was produced

This work was done with an AI coding assistant (Claude Code), under the direction of the fork owner. It is disclosed here so the maintainers can review it with that in mind.

1. **Scan.** Parallel reviewers each took one subsystem (load/save, models/DnD, editors, spellcheck, import/export, UI/settings, app shell, Python compatibility, runtime behaviour). They reported 127 bugs (18 data loss, 32 crashes, 47 wrong behaviour, 30 minor) and checked them against the upstream issue tracker. 123 of them were reproduced with small scripts before any fix was written.
2. **Fix.** One branch per area. Each commit adds tests. For bug fixes, the new test reproduces the bug on `develop` and passes on the branch. Performance commits add tests that check the output is unchanged.
3. **Review.** Three rounds of adversarial review, in which independent reviewers tried to break each fix. Most of what they found was fixed. The rest is listed as trade-offs in 1.4 and as open problems in section 2. The folder-mode save path was also fuzzed with random edit sequences plus injected write and read errors: 61 seeds, no data loss. The fuzzer is not on the branches yet (see 3.4, item 15).
4. **This document.** The analysis was fact-checked against the code and git history by separate reviewers, who also reproduced the newly found bugs (A1–A5) with their own scripts.
5. **Not done yet.** No manual testing on Windows or macOS, no test under a real X server (only `offscreen`), and no review by a human Manuskript developer. Please treat the branches as well-tested proposals, not as finished work.

## Contents

1. [Changes compared to `develop`](#1-changes-compared-to-develop)
2. [Open problems and effort](#2-open-problems-and-effort)
3. [Code quality assessment](#3-code-quality-assessment)
4. [Questions for the maintainers](#4-questions-for-the-maintainers)
5. [Appendix](#appendix)

## 1. Changes compared to `develop`

All branches start from `develop` at `01e0574` ("Merge pull request #1439 …", 2026-09-02). Each branch can be merged on its own. `fix/all-quickfixes` merges all seven, one after another, with `--no-ff`.

### 1.1 Overview

| Branch | Commits | Files | Lines +/- | Tests (develop: 39) | Upstream issues |
|---|---:|---:|---:|---:|---|
| `fix/save-load-data-loss` | 12 | 14 | +2145 / −121 | 99 (+60) | #313 #719 #761 #811 #1128 #1216 #1306 #1320 #1356 #1394 |
| `fix/crashes` | 9 | 26 | +692 / −100 | 53 (+14) | #808 #918 #1010 (crash only) #1154 |
| `fix/outline-dnd` | 9 | 11 | +962 / −101 | 72 (+33) | #324 #719 #918 #1193 #1216 #1264 #1286 #1394 |
| `fix/editor-performance` | 9 | 8 | +961 / −64 | 119 (+80) | #661 #819 #963 #1286 #1376 #1393 |
| `fix/import-export` | 17 | 25 | +1151 / −101 | 94 (+55) | #351 (rel.) #694 #929 (rel.) #978 #1178 #1215 |
| `fix/spellcheck` | 13 | 5 | +1186 / −127 | 128 (+89) | #929 #1178 |
| `fix/ui-settings-search` | 15 | 23 | +1061 / −91 | 81 (+42) | #467 #997 #1127 #1220 #1228 #1421 #1449 |

The integrated branch `fix/all-quickfixes` changes 95 files (+8140 / −704 lines: about 6000 of the added lines are tests, about 2160 are production code). Its suite has **412 tests** (39 on `develop`), and all of them pass. Each commit on the seven fix branches passes the full test suite on its own. The merge conflicts were all small:

- `abstractModel.py`: keep outline-dnd's `removeUsedIDs` and also reset `_lastPath` (from save-load) when an item gets a new ID.
- `main.py`: two imports.
- Four test files that both sides had added to.

Tests ran with `QT_QPA_PLATFORM=offscreen` on two setups:

- Python 3.13 with system PyQt5 5.15.10 / Qt 5.15.19,
- Python 3.11 with the pinned `requirements.txt` wheels (PyQt5 5.15.11).

They have not run on this repository's CI yet (Python 3.9, see G2). All code parses with the Python 3.6 grammar (checked with `ast`), but it has only been run on 3.11 and 3.13.

### 1.2 What each branch fixes

**`fix/save-load-data-loss`** is the most important branch. In folder mode (the default), several common actions lost data, either silently or by making every save crash:

- Reordering or moving items whose titles slugify to the same name (umlauts, CJK, Cyrillic): one item's file silently overwrote another's (#1320).
- Moving scenes into a folder that was not on disk yet (#1306, #719).
- Moving "Chapter 10" above "Chapter 1" (one cache key is a prefix of the other) or duplicating a saved folder: every save then crashed (#1216, #761).

The fix stops moving files on disk. A moved item is written at its new path. Its old file is removed after the save, but only if the new file was written. Otherwise the old file is kept and removed by a later save. Other commits:

- Write every file atomically (temporary file, then `os.replace`), in folder mode and in single-file `.msk` mode (#811, #1128).
- Stop deleting files that were never loaded, such as a scene without an `ID:` line or the user's own notes in the project folder (#1306, #1394).
- Stop `rmtree`-ing an existing folder that happens to have the project's name.
- Cap file names at 64 slug characters, and keep saving the other files after a write error (#313).
- Load only the top-level `characters/` and `outline/` folders. Before, a scene titled "Main characters" was also loaded as a phantom character.
- Keep the World sub-items of an item with an empty name, and keep `:` in character info and label names.
- Report unreadable files instead of crashing, and go back to the welcome screen when a project fails to load. Before, autoload crashed on every start (#313, #1356).
- Ask before closing or quitting when the save failed, instead of losing the changes.
- Open a copy of the demo projects instead of the installed ones.

**`fix/outline-dnd`**:

- Drag and drop in the editor's tree deleted other items (#719, #1264). During the drop, the editor reacted to a `dataChanged` signal by re-selecting a stale row in the tree, so Qt then removed the wrong row.
- Parse dragged, copied and pasted items with `huge_tree`, so folders with more than 10 MB of XML no longer crash the app (#918, #1193).
- Ignore foreign `application/xml` drag data.
- Give pasted items new IDs.
- Emit correct `rowsInserted` rows.
- Make Move Up/Down, ctrl+click multi-selection and the right-click menu act on the right items (#1286).
- Selecting an item no longer writes its displayed (inherited) compile state into it. Before, this silently left chapters out of the manuscript.

**`fix/crashes`** fixes crashes. Because of the excepthook, a crash means the app exits and unsaved text is lost (see B1 in section 2). The fixes cover:

- removed labels and statuses,
- deleting characters (this was also a wrong-data regression: scene POVs were no longer reset, #808),
- searching in a new project, and opening a search result whose item is gone,
- full-screen mode and the word-count locker with a goal typed in this session or an empty text,
- connections left in place when a project is closed.

Thread exceptions and Qt messages are now logged at the right level. SIGTERM/SIGINT are now handled while the event loop is idle, so a logout no longer kills Manuskript without saving, as long as "save on quit" is on (the default; with it off, see B8).

**`fix/editor-performance`**:

- Typing in long texts was slow because of:
  - a click-rect scan of the whole document on every change,
  - a highlighter that re-highlighted every earlier paragraph,
  - a new highlighter stacked on each item switch.
- The last words typed were lost on a full-screen item switch (Alt+Left/Right), Ctrl+S or Ctrl+Q, because the 500 ms submit was still pending.
- Fixes to list continuation and Format > Clear.

**`fix/import-export`**:

- Export: "Ignore compile status", separators, the quote setting that grew, the granular content settings, a corrupt `exporter.ini`.
- pandoc:
  - warnings were treated as failures (#694),
  - an invalid `--markdown-headings` value,
  - negative `--shift-heading-level-by` values could not be set (#978),
  - a crash on a wrong custom path (#1178).
- HTML conversion now works without pandoc.
- Import: invalid files, non-UTF-8 text, OPML text, scene breaks or code taken as headers, hidden folders, word counts.

**`fix/spellcheck`**:

- LanguageTool errors no longer close the app.
- symspellpy detection and its dictionaries.
- The default dictionary is now one that is installed.
- Dictionary menu actions no longer pile up.
- LanguageTool is no longer started just to build the menu.
- Correct words around apostrophes are no longer underlined: closing quotes and plural possessives (`dogs'`), typographic apostrophes (`isn’t`), and contractions with a known clitic (`geht's`). Partial non-ASCII words are no longer checked while typing (`Grüße` checked as `Grü`). This is the spellcheck part of #929. See BC10 and **D5** for a possible regression with French elisions.
- No suggestion menu for multi-word selections.
- The colour setting is now applied.

**`fix/ui-settings-search`**:

- Character multi-selection (#1449).
- F3, the "Match words" regex, contractions with ’ in the frequency analyzer (#997), references cut at braces (#1127).
- UI language:
  - Traditional Chinese is detected.
  - All shipped languages are listed.
  - The active language is shown and saved (#1220).
  - Qt's own dialogs are translated.
- `--style` to get past a broken saved style (#467).
- Tooltip colours, the autosave toggle, the theme editor, duplicate recent files (#1228), side-panel visibility.
- A clear message for Python < 3.6 (#1421).

### 1.3 Commits per branch

#### `fix/save-load-data-loss`

| Commit | Change | Upstream |
|---|---|---|
| `16666ba` | **save:** rewrite moved items instead of moving their files in place | #719, #761, #1216, #1306, #1320 |
| `46781ae` | **load:** only read characters/ and outline/ top-level folders |  |
| `783979b` | **load:** leave files that were not loaded untouched on save | #1306, #1394 |
| `58c4f37` | **save:** never wipe a folder that is not a Manuskript project |  |
| `ae70ff7` | **save:** cap file name length and keep saving after a write error | #313 |
| `6fa9e41` | **save:** write single-file projects atomically | #811, #1128 |
| `db2cb50` | **save:** keep world sub-items of an item with an empty name |  |
| `6787396` | **load:** report unreadable project files instead of crashing | #313, #1356 |
| `ed710ff` | **load:** keep ":" in character info and label names |  |
| `25bfa0b` | **load:** do not crash when a project fails to load | #1356 |
| `28456a2` | **ui:** ask before closing a project that could not be saved |  |
| `6dd6695` | **ui:** open a copy of demo projects instead of the installed one |  |

#### `fix/crashes`

| Commit | Change | Upstream |
|---|---|---|
| `bbdd4fc` | **labels:** don't crash on items using a removed label or status | #918, #1010 (crash part) |
| `ad4477d` | **characters:** clear scene POVs again when deleting characters | #808 |
| `63fb49c` | **search:** don't crash when searching in a newly created project |  |
| `6c8842d` | **search:** don't crash when opening a result whose item is gone |  |
| `27510dd` | **fullscreen:** normalize word count and goal before using them |  |
| `d27cb9c` | **project:** break UI connections before replacing models on close | #1154 |
| `881ff81` | **logging:** log thread exceptions and Qt messages with the right level |  |
| `df80863` | **main:** handle SIGTERM/SIGINT while the event loop is idle |  |
| `9863633` | **mainwindow:** close other windows when the main window is closed |  |

#### `fix/outline-dnd`

| Commit | Change | Upstream |
|---|---|---|
| `308e590` | **editor:** stop drag and drop in the editor tree deleting other items | #719, #1264 |
| `029b390` | **models:** parse item XML with huge_tree in drag/drop and copy/paste | #918, #1193, #1216, #1394 |
| `a078252` | **models:** ignore foreign or malformed application/xml drag data |  |
| `81f4bcc` | **models:** give new IDs to all pasted items whose ID is already used | #324 |
| `d53f9fc` | **models:** signal the real rows when dropping or pasting on a folder |  |
| `e6abc9c` | **views:** make Move Up/Down move each selected item exactly one row |  |
| `24ab334` | **views:** make ctrl+click multi-selection work in the outline trees |  |
| `db62e4d` | **views:** make the popup menu act on the right-clicked item | #1286 |
| `d716843` | **properties:** don't write the displayed compile state into the item |  |

#### `fix/editor-performance`

| Commit | Change | Upstream |
|---|---|---|
| `b0fd4a7` | **editor:** debounce click-rect scan and limit it to visible text | #661, #819, #1286, #1376, #1393 |
| `638be4a` | **highlighter:** stop re-highlighting all previous paragraphs | #963, #1286, #1376 |
| `9af1d37` | **editor:** reuse the highlighter instead of stacking a new one | #1286, #1376 |
| `6fe2010` | **editor:** speed up toIdealText() by using str.replace | #1376 |
| `aa298f9` | **views:** connect lineEditView.textEdited to submit only once |  |
| `53ed275` | **editor:** submit pending text before item switch, save and quit |  |
| `6ab94b9` | **editor:** make Format > Clear keep prose intact and clear all lines |  |
| `dbca29e` | **editor:** do not paste into read-only text editors |  |
| `51040cf` | **editor:** continue numbered lists correctly from item 10 on |  |

#### `fix/import-export`

| Commit | Change | Upstream |
|---|---|---|
| `0e6f2bf` | **export:** make "Ignore compile status" include all items |  |
| `04651ed` | **export:** don't add separators for excluded or empty items |  |
| `9ec06b2` | **export:** stop quote replacement from growing the settings | #929 (related) |
| `d88897b` | **export:** restore granular content settings for the current depth | #978 (related) |
| `bfa9ae0` | **export:** don't crash on an empty or corrupt exporter.ini |  |
| `9830773` | **pandoc:** keep the output when pandoc only prints warnings | #694 |
| `6ad05d4` | **pandoc:** pass a valid value to --markdown-headings |  |
| `740641f` | **pandoc:** allow negative values for --shift-heading-level-by | #978 |
| `99e66a3` | **pandoc:** don't crash on a wrong custom pandoc path | #1178 |
| `52aded5` | **converters:** make HTML conversion work without pandoc on PATH | #1178 |
| `c36d9d4` | **import:** handle mind map rich content without html |  |
| `3d3ca05` | **import:** show an error instead of crashing on invalid files | #1215 |
| `9c1bf12` | **import:** read non-UTF-8 text files in markdown and folder imports | #1215 |
| `c1c629b` | **import:** keep the text of OPML outlines that have children |  |
| `4c4ce29` | **import:** don't take scene breaks and code for markdown headers |  |
| `e2b4a90` | **import:** skip hidden folders and files in the folder import | #351 (related) |
| `0893a97` | **import:** compute word counts of imported texts |  |

#### `fix/spellcheck`

| Commit | Change | Upstream |
|---|---|---|
| `eae355a` | **spellcheck:** raise NotImplementedError in BasicDictionary stubs |  |
| `b264eb4` | **spellcheck:** keep LanguageTool errors from closing the app |  |
| `272958f` | **spellcheck:** detect symspellpy without __version__ and distutils | #1178 |
| `7914f17` | **spellcheck:** reject symspellpy dictionaries without word data |  |
| `e47ee85` | **spellcheck:** remove symspellpy custom words in lowercase |  |
| `b9afed8` | **spellcheck:** pick an installed dictionary as the default |  |
| `6dfcd9c` | **editor:** re-enable spellcheck when a dictionary is chosen |  |
| `94077cc` | **spellcheck:** stop dictionary menu actions piling up |  |
| `bb2af89` | **spellcheck:** keep dictionary names without library prefix |  |
| `dd3c3b5` | **spellcheck:** do not start LanguageTool just to build the menu |  |
| `fa37b1e` | **spellcheck:** stop underlining correct words around apostrophes | #929 |
| `91296a3` | **spellcheck:** no spelling menu for multi-word selections |  |
| `042a844` | **spellcheck:** use the misspelled-word color setting |  |

#### `fix/ui-settings-search`

| Commit | Change | Upstream |
|---|---|---|
| `c3e35b4` | **characters:** keep multi-selection for the bulk info manager | #1449 |
| `ac28d47` | **search:** let F3 / Shift+F3 open the first search result |  |
| `b1d6362` | **search:** build a correct regex for the "Match words" option |  |
| `f029e18` | **frequency:** keep contractions with ’ together in the analyzer | #997 |
| `00c4286` | **references:** do not cut references at braces in item titles | #1127 |
| `de6de99` | **i18n:** detect Traditional Chinese and list all shipped languages |  |
| `3e90e18` | **settings:** show the active UI language and save any choice | #1220 |
| `9c279f8` | **i18n:** translate Qt's own dialogs and buttons as well |  |
| `c9afae8` | **startup:** allow overriding a broken saved Qt style | #467 |
| `7e41e2e` | **settings:** apply custom tooltip colours when a project is loaded |  |
| `57f2337` | **settings:** start or stop autosave as soon as it is toggled |  |
| `f299912` | **settings:** connect the theme editor's widgets only once |  |
| `7f6d81a` | **welcome:** list each recent project once and tell same names apart | #1228 |
| `4d08e74` | **ui:** keep side panel visibility after a UI language change |  |
| `d183c70` | **startup:** explain that Python 3.6 or newer is required | #1421 |

### 1.4 Behaviour changes that need a maintainer's OK

These are intentional, but they change what users see or how files are written. They should be discussed before merging.

| # | Branch | Change | Why |
|---|---|---|---|
| BC1 | save-load | Renaming or moving a folder **rewrites its whole subtree** instead of renaming one directory. Files Manuskript does not know stay in the old folder. | Moving files in place is what overwrote other items (#1320). Rewriting cannot overwrite or lose a file. Drawback: more I/O and more churn on Dropbox/OneDrive. |
| BC2 | save-load | Saving writes `.<name>.tmp` next to each file and then `os.replace()`s it. It **needs write permission on the folder**, and **hard links are replaced** (symlinks are written through, file mode is kept). A crash can leave a hidden `.tmp` file. Folder mode does not `fsync` (the `.msk` mode does). | A failed write (disk full, USB stick removed) left truncated files (#811, #1128). |
| BC3 | save-load | A project **no longer opens** if its folder is missing, if its `outline/` or `characters/` folder cannot be read, or if a root file (`MANUSKRIPT`, `settings.txt`, `plots.xml`, …) cannot be read or is not valid UTF-8. Before, it opened empty, opened without that data, or crashed. A `settings.txt` with invalid JSON still opens, with default settings. | When it opened empty, the next save (or save on quit) overwrote the real data. |
| BC4 | save-load | Saving **into an existing, non-empty folder that is not a Manuskript project is refused** with a dialog. For an older project, only what Manuskript writes is cleaned up. | Before, "Save as" `Documents.msk` in `$HOME` deleted `~/Documents` recursively. |
| BC5 | save-load | File names are capped at 64 slug characters. Items with longer titles are **renamed once** on their next save. | Long titles raised "File name too long" and aborted the save (#313). |
| BC6 | save-load | Files in the project folder that were not loaded are **kept, not deleted**. They are still not shown in the UI. | Before, the first save deleted them. |
| BC7 | save-load | Clicking a demo project opens a **copy in the user data folder**. | Edits were written into the installed sample, or lost on a read-only install. |
| BC8 | save-load | If saving fails when the user closes or quits, Manuskript **asks before discarding** unsaved changes. | Before, the window just closed and the changes were lost. |
| BC9 | spellcheck | LanguageTool dictionaries are listed only after the new menu entry **"Start LanguageTool to list its dictionaries"** has been used, unless the project's dictionary is a LanguageTool one (then LT starts on load). Starting blocks the UI, and the first start downloads about 250 MB. The new strings are untranslated. | Building the menu started a JVM (and possibly the download) on every project load. |
| BC10 | spellcheck | A word with apostrophes is accepted if the dictionary knows it (`’` is also read as `'`), after quotes and plural-possessive apostrophes around it are stripped. It is also accepted if it is a known word followed by one of the clitics `'s 'n 'm 'ne 'nen 'nem`, the same list for every language. Words are no longer split at apostrophes, so French elisions (`l’homme`) are accepted only if the dictionary knows the whole form (see **D5**). | False positives with possessives, quotes and contractions (#929). |
| BC11 | outline-dnd | Right-clicking an item outside the selection makes the context menu act **on that item, without changing the selection**. | Before, the menu acted on the old selection (#1286). |
| BC12 | import-export | Markdown import treats `#` lines as headers in fewer cases. These are no longer headers: lines in closed ```` ``` ```` code fences, scene breaks made only of `# * - _` (`#`, `# # #`), and lines with 7 or more `#`. Closing hashes need a space before them (`# C#` keeps its title). `#Title` without a space is still a header. `~~~` lines are not treated as fences on purpose, because they are common scene breaks. | Scene breaks became items titled "#" and moved the following scenes out of their chapter. |
| BC13 | editor-perf | A line that is only a list marker that cannot be incremented (`-- `, `ii. `) ends the list on Return, like `- ` does, and is cleared. | Side effect of `51040cf`: markers that cannot be incremented no longer match the continuation regex, so such a line counts as an empty item. See C5 if `-- ` should be kept. |
| BC14 | crashes | SIGTERM/SIGINT now close Manuskript normally: the handler runs within 0.5 s, then the usual close with save on quit. If save on quit is off and there are unsaved changes, the "Save project?" question still waits for an answer (B8). | Before, they were ignored until SIGKILL, so changes were lost on logout. |
| BC15 | ui-settings | New command-line option `--style STYLE`, which also accepts Qt's `-style`. It is not saved. `QT_STYLE_OVERRIDE` is still ignored on purpose. | A crashing saved style made Manuskript unusable (#467). |

The new user-visible strings use `tr()`/`safeTranslate()` (21 strings), but **no `.ts` files have been updated** (G3).

### 1.5 Suggested merge plan

1. **One PR per branch**, in this order: `save-load-data-loss` → `crashes` → `outline-dnd` → `editor-performance` → `import-export` → `spellcheck` → `ui-settings-search`. That is the order of `fix/all-quickfixes`, so the conflict resolutions shown there can be reused.
2. Each commit fixes one problem. One exception: `638be4a` also carries a small focus-mode fix that the bug it fixes had been hiding. Each message explains the bug, the root cause and the fix, and names the upstream issues where there are any. Reviewers can review commit by commit, or cherry-pick single commits.
3. Before opening the PRs, run the repository's own CI on the branches (see G2). Before releasing, test by hand with a copy of a real project, on Windows and macOS in particular: case-insensitive file systems, path length, `os.replace` over open files on Windows. These were only covered by tests on Linux.

## 2. Open problems and effort

Everything in this section is **still present on `fix/all-quickfixes`**. Each item was checked against the code, most of them with a small isolated script. File and line references are to `fix/all-quickfixes` (`eacaf8f`).

**Effort** assumes one developer who knows Python/Qt but is new to this code base, and includes tests: **S** ≤ ½ day, **M** 1–3 days, **L** 1–2 weeks, **XL** > 2 weeks or architectural. **Decision** (✋) means maintainers should agree on the behaviour before someone writes the fix (see section 4).

### 2.1 Overview

| ID | Problem | Impact | Effort | Prio | ✋ |
|---|---|---|:-:|:-:|:-:|
| **A — Newly found during this review (all also present on `develop`), mostly quick to fix** ||||||
| A1 | Outline tab, multi-selection: the "Various" summary field writes `""` into every selected item | **Silent data loss** | S | high | ✋ |
| A2 | Split at cursor (Ctrl+K) right after typing loses the last typed text and cuts at the wrong place | Data loss | S | high | |
| A3 | Adding or removing characters, plots, world items, labels or statuses does not mark the project as modified. An added entry that is then edited does, so what gets lost is removals and unedited additions. | File > Close drops them, no prompt | M | high | ✋ |
| A4 | A failed "Save as…" still switches the app to the new, unsaved path | Work "saved" nowhere | S | medium | |
| A5 | The custom dictionary file is rewritten non-atomically each time it is loaded (if it holds any word), and emptied if it is damaged | Lost custom words | S | medium | |
| **B — Robustness and data safety (known)** ||||||
| B1 | Global excepthook calls `sys.exit(1)` on any uncaught exception | Every small bug = crash + lost work | M | **highest** | ✋ |
| B2 | Main editor reparents its scroll bar without `ScrollBarAlwaysOff` (#450 #601 #1435) | Segfault with Breeze5/Adwaita | S | high | |
| B3 | One damaged `plots.xml`/`world.opml`/`revisions.xml`, a `folder.txt` without ID or a non-numeric ID keeps the whole project from opening | "Can't open my project" | M | high | ✋ |
| B4 | Multi-line metadata is not round-trip safe: indentation is lost, and trimming trailing whitespace moves notes into the scene text | Silent corruption | M | medium | |
| B5 | Deleting a label/status relabels every item that uses a later one (#1010, only the crash is fixed) | Wrong data, persistent | S | medium | ✋ |
| B6 | Character, plot and world IDs reuse the lowest free number | References attach to new entities | M | medium | ✋ |
| B7 | Files Manuskript did not load (notes, hand-made scenes) stay behind when their folder is renamed | Orphaned, invisible files | M | medium | ✋ |
| B8 | A signal handler can re-enter a running save, and the "Save?" dialog can block a logout | Rare, nasty | S | low | ✋ |
| B9 | Atomic writes: no `fsync` in folder mode, stale `.tmp` files are not cleaned up | Edge cases | S | low | ✋ |
| **C — Editor** ||||||
| C1 | Qt UTF-16 positions mixed with Python indices | Wrong underline, correction, search hit or split after emoji | M | medium | |
| C2 | Undo gets stuck after a paragraph-format change (highlighter calls `setBlockFormat`) | Ctrl+Z does nothing | M | medium | |
| C3 | An item switch re-highlights the *old* text about 7 times | ~0.8 s per switch with spellcheck | S–M | medium | |
| C4 | Every Space pushes the whole text through `setData` | Typing lag in long scenes | S | low | ✋ |
| C5 | List continuation: a `-- ` line is cleared on Return (side effect of `51040cf`), `z)` continues as `{)` | Minor: a `-- ` line is erased | S | low | ✋ |
| **D — Spellcheck / LanguageTool** ||||||
| D1 | LanguageTool: second JVM per dictionary, cache never shrinks, whole document checked on mouse move | RAM, freezes | M | medium | |
| D2 | LanguageTool checks run synchronously in the GUI thread (#280) | Typing lag | L | medium | ✋ |
| D3 | Starting LanguageTool blocks the UI (about 250 MB download the first time); a failed start shows "not installed" | UX | S–M | low | ✋ |
| D4 | The clitic whitelist is the same for every language | A few false negatives | S | low | ✋ |
| D5 | **Possible regression on `fix/spellcheck`:** French/Italian elisions (`l’homme`, `j’ai`) are underlined unless the dictionary knows the elided form. `develop` accepted them by splitting at the apostrophe. | False positives for French users | S | medium | |
| **E — Import, export, search** ||||||
| E1 | Pandoc export drops scene text shaped like a YAML block | Silent loss in exports | S | medium | ✋ |
| E2 | The default PDF engine `pdflatex` fails on common Unicode (even on the demo project); `--self-contained` is deprecated; Homebrew's pandoc is not found when Manuskript is started from the Finder (rest of #1178) | PDF export fails | S | medium | ✋ |
| E3 | PDF preview URL built by string concatenation (#825) | Blank preview on Windows | S | medium | |
| E4 | Search results keep their offsets after edits (#1319) | Wrong selection | M | medium | |
| E5 | Export filters "Subitems of", "Labels", "Status" are shown but ignored (rest of #978) | Confusing | S (hide) / M | low | ✋ |
| E6 | "Replace single quotes" pairs apostrophes in contractions (export part of #929) | Wrong typography | S | low | |
| E7 | Search: zero-length regex matches flood the results, context HTML is not escaped | Freeze, garbled tooltip | S | low | |
| E8 | Importer: empty asset folders imported, insert signals bypassed, "Import under" preselection ignored | Minor | S | low | ✋ |
| **F — App shell and UI** ||||||
| F1 | Settings (and so the UI language) need an open project | UX | M | low | ✋ |
| F2 | No "Clear list" for recent projects (rest of #1228; duplicates are fixed by `7f6d81a`) | UX | S | low | ✋ |
| F3 | Qt command-line options rejected, no `--no-autoload`, no macOS "open with" | Packagers, power users | S–M | low | |
| F4 | Small hardening: World remove loop, `with_tail`, drag-move decodes the whole payload | Latent | S | low | |
| **G — Tests, CI, i18n** ||||||
| G1 | Test fixtures leak about 220 temp entries (about 51 MB) per run and write to `~/.config/manuskript_tests` and `~/.local/share/manuskript_tests` | Developers, CI containers | S | medium | |
| G2 | The fix branches have not run on this repository's CI yet (Python 3.9, xvfb, extra spellcheck libraries) | Review risk | S | medium | |
| G3 | 21 new `tr()`/`safeTranslate()` strings are not in any `.ts`; `'Open {}'` can never be translated | Non-English users | S | low | ✋ |
| G4 | Rare segfault at interpreter exit (focusOut → submit during teardown, also on develop) | Flaky CI | S | low | |

**A bugfix round of about one to two weeks** would cover A1–A5, B2, B5, C4, D5, E1–E3, E6, E7 and G1–G3. These are mostly S items, with one M (A3). Seven of them (A1, A3, B5, C4, E1, E2, G3) need a decision first, and that time is not included. The larger items that remain after that are:

- B1, which waits for the policy decision (Q4),
- B3, B4, B6 and B7,
- C1–C3,
- D1/D2 and E4.

### 2.2 Details

#### A1 — "Various" editor erases summaries (data loss)
- **Where:** In the Outline tab, `basicItemView.py:55-60` gives a multi-selection to the full-summary editor. If the summaries differ, `textEditView.updateText` shows `""` with the placeholder "Various" (`textEditView.py:328-350`). Two triggers then write the empty text:
  1. Clicking into the field and out again: `focusOutEvent` calls `submit()` directly (`:758-761`).
  2. Any rehighlight, such as toggling spellcheck or changing the dictionary: it emits `contentsChanged`, which starts the 500 ms update timer.

  Either way, `submit()` writes `""` to **every** selected item (`:369-374`). Only the full summary is affected. The one-line summary, the goal and the POV fields submit only on real edits.
- **Status:** Present on `develop` too, and worse there. `setCurrentModelIndexes` did not flush the pending submit, so ctrl/shift-clicking a second item within 500 ms of the first click was enough to erase the summaries.
- **Fix:** Either (a) disable the field for multi-selections, as `metadataView.py:86-102` already does with a comment referencing GitHub #10, or (b) submit in multi-index mode only after a real user edit (`document().setModified(False)` in `updateText`, check `isModified()` in `submit`). Add a regression test.
- **Effort:** S. **Decision:** keep editing several summaries at once, or disable it?

#### A2 — Split at cursor loses text
- **Where:** `editorWidget.splitCursor` (`editorWidget.py:471-491`) splits the **model** text. The editor submits only on Space, on focus-out, or 500 ms after the last change, and Ctrl+K keeps the focus. So text typed since the last Space (within 500 ms) exists only in the editor. It is lost, the cut lands that many characters too far, and `setPlainText` clears the undo stack. `textEditView.callMainTreeView` was checked and does not lose text (only Duplicate copies the model text without the last unsubmitted characters).
- **Status:** Present on `develop` too (same code).
- **Fix:** Call `self.txtRedacText.submitPendingChanges()` before reading the cursor. That method comes with `53ed275` (`fix/editor-performance`). Without that branch, call `submit()`. Effort: S (1–2 h).

#### A3 — Structural changes are not "unsaved"
- **Where:** `projectDirty` is only set from `dataChanged` (`mainWindow.py:994-1000`, `:1242-1249`). `removeCharacter`, `addPlot`, `worldModel.addItem`, removing a label… emit only `rowsInserted`/`rowsRemoved`. File > Close drops these changes without saving or asking, **whatever the "save on quit" setting**, because `closeProject` only saves when `projectDirty` is set (`mainWindow.py:1095`). Quitting drops them when "save on quit" is off. The no-change autosave does not fire either.
- **Fix:** Also connect `rowsInserted/rowsRemoved/rowsMoved/modelReset` of the 7 models (and disconnect them in `breakConnections`). Then the root's invalid-index `dataChanged` (see 3.3.1) is no longer needed for the modified flag. Check whether other listeners rely on it before dropping it. Effort: M, because every path that changes rows without a user edit has to be checked. **Decision:** should every structural change mark the project modified?

#### A4 — Failed "Save as" switches path
- **Where:** `welcome.saveAsFile` (`welcome.py:200-213`) updates the recent files, `currentProject`, `lastProject` and the title without checking the result of `saveDatas`. `mainWindow.py:1272-1274` sets the path before saving.
- **Fix:** Save first. On failure, restore the old path and cache and show the reason. Effort: S.

#### A5 — Custom dictionary rewritten and possibly wiped
- **Where:** `BasicDictionary.__init__` (`spellchecker.py:240-249`) calls `self._dict.create_dictionary_entry` before the subclass has created `_dict`. The resulting `AttributeError` is swallowed by a bare `except`, which calls `_saveCustomDict()` (non-atomic). A damaged file is replaced with `[]`. This affects pyspellchecker, symspellpy and LanguageTool.
- **Fix:**
  - Remove the loop. The subclasses already add the words (`spellchecker.py:468-469`, `:546-547`).
  - Create the file only on `FileNotFoundError`.
  - On a decode error, log it, keep a backup copy (e.g. `<lang>.json.gz.damaged`) and continue with an empty list.
  - Write atomically with `writeFile`. Import it inside `_saveCustomDict` or move it to `manuskript.functions`, to avoid a circular import.
- **Effort:** S.

#### B1 — The excepthook policy (the single biggest lever)
- **Where:** `logging.py:155-167` logs and then calls `sys.exit(1)`, on purpose ("fail fast"). Checked with an offscreen probe:
  - With this hook, the first exception in a slot ends the process: no `closeEvent`, no save.
  - PyQt's default hook aborts (qFatal), so simply removing the hook is not an option.
  - A hook that *returns* lets Qt carry on: the probe survived exceptions in a slot and in `paintEvent`.
- **Proposal:**
  1. Keep exiting before the event loop runs, on re-entry, and on an exception storm (e.g. more than 10 in 10 s, typical for a broken `paintEvent`).
  2. Otherwise log the full traceback once and count repeats.
  3. Show **one** dialog, deferred via `QTimer.singleShot(0, …)` so that it never opens from inside paint or highlight code. It shows the log path and offers two choices: "Continue" and "Save a recovery copy and quit".
  4. Write the recovery copy to a **separate** file (e.g. `<project>.recovery-<time>.msk`), never over the project, because the models may be inconsistent.
  5. Test with a fake message box and a subprocess test.
- **Effort:** M (about 3 days). Agreeing on the policy will take longer than the code. **Decision:** see Q4.

#### B2 — Scroll-bar segfault (#450, #601, #1435)
- **Where:** `editorWidget.py:64-67` reparents the QTextEdit's own vertical scroll bar and keeps the "as needed" policy. Styles that call `scrollBar->mapFrom(scrollArea)` (Breeze5, Adwaita-qt) then dereference a null parent. `fullScreenEditor.py:45-51` reparents the same way but sets `ScrollBarAlwaysOff` first.
- **Evidence:** The crash primitive (`mapFrom` after reparenting) was reproduced: SIGSEGV with the same frame chain as the gdb trace in #450. It was **not** reproduced end to end, because Breeze5 and Adwaita-qt were not available.
- **Fix:** One line, `setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`, plus a manual check on Plasma 5 or GNOME. Effort: S.

#### B3 — One damaged file blocks the whole project
- **Where:** `ET.fromstring` without a recovering parser at `version_1.py:1041` (plots), `:1077` (world) and `:1164` (revisions). `outlineFromMMD` raises `KeyError` for a `folder.txt` without `ID:` (`:1231`/`:1263`), and `abstractModel.py:72` raises `ValueError` for `ID: 12a`. The only message is 5 seconds of status-bar text.
- **Fix:**
  - A `parseXMLSection` helper that, on a parse error, retries with `XMLParser(recover=True, huge_tree=True)`, keeps a `.damaged-<time>` copy and lists the file in the existing "Files not loaded" dialog.
  - A broken `revisions.xml` only drops revisions.
  - A `folder.txt` without ID gets a new ID, like other items.
  - Show a real dialog instead of the status bar.
  - Optional: a "newer format" guard (`MANUSKRIPT` > 1 is loaded and saved back as 1 today).
- **Effort:** M. **Decision:** salvage plus backup, or keep refusing to open but name the broken file?

#### B4 — Multi-line metadata
- **Where:** `parseMMDFile` runs `val += "\n" + s.strip()` (`version_1.py:1384`), which drops indentation and Markdown hard breaks. `formatMetaData` writes an empty line inside a value as whitespace only (`:83`). If an editor, a pre-commit hook, `git apply --whitespace=fix` or a sync tool trims trailing whitespace, that line becomes empty and is read as the end of the metadata: the rest of the note **moves into the scene text** (verified).
- **Fix:** Remove only the writer's indentation, and treat an empty line followed by an indented line as a continuation. Add round-trip tests, including files written by `develop`. Effort: M (the parser change is small, but compatibility needs care).

#### B5 — Deleting a label/status (#1010, part 1)
- **Where:** Items store the label/status **row number**. `settingsWindow.removeLabel/removeStatus` (`settingsWindow.py:733-756`) only call `removeRows`. Every later label shifts, and the next save writes the wrong meaning.
- **Fix:** Before removing row r, set items with value r to `""` and decrement values > r through `setData`. Optionally ask "N items use this label". The long-term option is stable IDs, which is a format change (L). Effort: S.

#### B6 — ID reuse
- **Where:** `characterModel.py:342-352`, `plotModel.py:119-132` and `worldModel.py:146-163` return the smallest unused integer. Deleting a character resets scene POVs (fixed, #808), but not plot member lists or `{C:id}` references. A new character inherits all of them.
- **Fix:** Allocate `max+1`, or keep a persisted never-reuse counter (format change). Remove deleted IDs from plots. Effort: M. **Decision:** max+1 or a persisted counter?

#### B7 — Files Manuskript did not load
- **Where:** Since the save-load fix, files that were readable but not loaded are left alone (good). When their folder is renamed they are **not** moved along, unlike unreadable files (`version_1.py:540-560`). Example: `ideas.txt` or a hand-made scene without `ID:` stays in the old, now unloaded folder. They are also not listed in any dialog.
- **Fix:**
  - Short term: move them like unreadable files and list them in "Files not loaded" (M).
  - Long term: real directory renames with a two-phase temporary name, which would also end the subtree rewrite (BC1 in 1.4). Effort L. This is exactly the path that caused the original data loss, so it needs the fuzzer.
- **Decision:** adopt, report or ignore foreign files?

#### B8 / B9 — Signals and atomic-write side effects
- **B8:**
  - The handler calls `MW.close()` synchronously (`main.py:321-333`). A signal arriving during an autosave runs a nested `saveProject`.
  - With "save on quit" off, the modal "Save?" box blocks a logout until SIGKILL.
  - Fix: schedule the handler via `QTimer.singleShot(0)` and add an "in save" guard (S). **Decision:** on SIGTERM, save anyway or write a recovery copy instead of asking?
- **B9:**
  - Folder mode does not `fsync`.
  - A crash between write and replace leaves `.<name>.tmp` until that file is written again.
  - `exporter.ini` has its own non-hardened tmp+replace.
  - Fix: clean stale `.tmp` files on load, reuse `writeFile`, and optionally `fsync` on explicit save or quit (S). **Decision:** is the `fsync` cost acceptable?

#### C1 — UTF-16 vs Python indices
- **Where:** `QTextCursor`/`QSyntaxHighlighter` count UTF-16 units, Python counts code points. After `😀😀 `:
  - The spelling underline lands on `e wr` instead of `wrod`.
  - The context menu offers a correction for another substring, and picking it overwrites the wrong text.
  - Searching for `Paul` selects `n Pa`.
  - Split at cursor puts text into the new scene's title.
  - Call sites: `basicHighlighter.py:157-196`, `textEditView.py:615-691`, `widgetSelectionHighlighter.py:46-51`, `editorWidget.splitCursor`, `MDEditCompleter`, and the LanguageTool offsets.
- **Fix:**
  - Two helpers (`qtPosToPyIndex`, `pyIndexToQtPos`) with a fast path for BMP-only text, used at the ~10 direct call sites.
  - For the highlighter and tokenizer, a "UTF-16-indexable" copy of the block text (each astral character replaced by two U+FFFD), so the ~20 tokenizer sites need no change.
- **Effort:** M (2–3 days). `MDEditView.computeClickRects` avoids the problem by using Qt's own regex on the cursor's text, so all positions stay UTF-16. That is the same idea as the UTF-16-indexable copy.

#### C2 — Undo stuck after a format change
- **Where:** `BasicHighlighter.highlightBlockBefore` calls `setBlockFormat` from inside `highlightBlock` (`basicHighlighter.py:131-145`). The docstring in `markdownHighlighter.py:139-151` warns against exactly this. After changing line spacing in Settings with a text open, Ctrl+Z stays enabled but does nothing (verified: 3 undo steps remain forever).
- **Fix:** Apply the default block format once after `setPlainText` with undo/redo disabled (`doc.setUndoRedoEnabled(False)` … `True`), so that loading leaves no undo entry. On a real settings change, apply it inside one edit block (one undo step) or clear the undo stack. Check the main editor, the folder text view and the fullscreen themes. Effort: M.

#### C3–C5 — Per-switch and per-keystroke work, list continuation
- **C3:** `setCurrentModelIndex` calls `setDefaultBlockFormat`, `updateColorScheme` and so on on the *old* document, and each of them rehighlights. Measured: 420 `highlightBlock` calls for 60 paragraphs before the new text is loaded, and **0.8–0.9 s per switch** between two ~4000–6000-word scenes with enchant. Fix: a `rehighlight=False` path and one pass at the end (S–M).
- **C4:**
  - `textEditView.py:393-394` submits on every Space, on top of the 500 ms debounce. Measured: 3.7 ms per Space vs 0.3 ms per letter in a 4300-word scene, and 20 Spaces emit 311 `dataChanged`.
  - Since `53ed275` flushes before switch, save and quit, this submit is no longer needed for those cases. A2, and any other keyboard-shortcut action that reads the model while the editor keeps focus, must be fixed or audited first.
  - Effort: S. **Decision:** the word count would update after a short pause instead of after every word.
- **C5:**
  - `MDEditView.py:23-25` and `:111-120`: a line that is only `-- ` is cleared on Return. This is a side effect of `51040cf` (BC13).
  - `z)` continues as `{)` (`:144-148`, pre-existing).
  - Fix: treat `--` as a marker only when text follows, and stop at `z`. S. **Decision:** keep `-- ` lines?

#### D1–D5 — LanguageTool, clitics and elisions
- **D1:**
  - Every LT dictionary creates its own `LanguageTool(lang)` (`spellchecker.py:723`). That is a second Java server, next to the shared one from `getTool()`.
  - The `_cache` is never evicted.
  - `mouseMoveEvent` and the context menu pass the **whole document** to the check.
  - Fix: client tools against the shared server, an LRU cache, block-relative checks. M.
- **D2:** `highlightBlockAfter` calls `checkText` synchronously, one HTTP request per paragraph when a text opens and per keystroke. Fix: debounce plus worker thread, apply results via `rehighlightBlock`. L. This would be the first thread in the editor code. **Decision:** worker thread, or document LT as a slower proof-reading mode and do only D1?
- **D3:** A confirmation dialog before the first start (the ~250 MB download), and a distinct "failed to start" label (S). A background start with progress is M.
- **D4:** `CLITICS = {s, n, m, ne, nen, nem}` applies to every language, so `your's` (and `your'm`, `could'n`) pass in English. Fix: per-language sets (S). Needs native speakers' examples. (`goin'` being flagged is a separate limitation: neither `goin` nor `goin'` is in the en_US dictionary.)
- **D5 (possible regression on `fix/spellcheck`):**
  - Since `fa37b1e`, words are no longer split at apostrophes. Elisions (`l’homme`, `j’ai`, `dell’anno`) are therefore accepted only if the dictionary knows the whole form. `develop` split them into `l` (single letters are not checked) and `homme`.
  - Shown with a fake dictionary only. Hunspell French dictionaries handle elision themselves, so enchant users are probably not affected. Word-list backends (pyspellchecker, symspellpy) probably are.
  - Fix before merging `fix/spellcheck`: accept `<elision prefix>’<known word>` for a per-language prefix list (fr: `c d j l m n s t qu jusqu lorsqu puisqu`; it: `l dell all dall nell sull un`…), together with D4. S.

#### E — Import, export, search (short)
- **E1:** `disable-YAML` defaults to off (`abstractPlainText.py:178-180`). With pandoc 3.10, a `---` / `Later: she remembered…` / `---` passage vanishes from the output without a warning. Options:
  - (a) Default to `markdown-yaml_metadata_block` and migrate `exporter.ini`.
  - (b) Detect such blocks and warn.
  - S. **Decision.**
- **E2:**
  - pdflatex fails with `Unicode character ✡ (U+2721) not set up`, and the bundled sample contains U+2721.
  - Default to xelatex or lualatex when installed.
  - Version-gate `--embed-resources --standalone` (pandoc ≥ 2.19), show the warning once per session, and add the Homebrew paths on macOS.
  - S. **Decision:** change the default engine?
- **E3:** `PDFViewer.py:17-44` builds `QUrl('file://' + … + '?file=' + pdf)`, which gives an invalid URL for `C:\…` paths and breaks on `#`, `&` or `?`. Use `QUrl.fromLocalFile` + `QUrlQuery`. Do not show the previous PDF after a failed export. S.
- **E4:** Results store fixed `(start, end)` offsets (`functions/__init__.py:493-503`). Store the matched text, re-validate when a result is opened, re-search nearby, and grey out results that are gone. M (6 result types).
- **E5:** `plainTextSettings.py:189-193` has `# FIXME: parent, labels, status`. The UI says "(Not fully implemented yet.)". Hide the filters (S) or implement them (M). **Decision.**
- **E6:** The rule `'(.*?)'` → `‘\1’` (`exporter/manuskript/plainText.py:222-224`) turns `don't … it's` into `don‘t … it’s`. Replace it with a contextual converter. S.
- **E7:** `x*` on 50k characters gives 51,301 results in 2 s, and `getSearchResultContext` puts raw text into HTML. Skip empty matches and use `html.escape`. S.
- **E8:**
  - Directories without importable files become empty folders. **Decision:** prune by default?
  - Importers build items with `outlineItem(parent=…)` and emit a bare `layoutChanged`.
  - `generalSettings` sets a source index on a proxy view, so the preselection is ignored.
  - S.

#### F — App shell (short)
- **F1:** `actSettings` is disabled without a project, and most "General" options are project settings, which are replaced on load via `importlib.reload(settings)`. Enable the settings with app-level options only, or add a language selector to the welcome screen. M. **Decision.**
- **F2:** Add a "Clear list" entry to the recent-projects menu. S, new strings. **Decision.**
- **F3:** `argparse` rejects Qt options (`-platform wayland`). Use `parse_known_args`. Add `--no-autoload`: today, a project that crashes the app after loading can only be escaped by passing another project on the command line or by editing QSettings. Handle `QEvent.FileOpen` on macOS (needs a Mac).
- **F4:** `worldModel.py:165-168` loops forever if `removeRows` fails. `ET.tostring(child)` keeps the tail text (`abstractModel.py:385`). `canDropMimeData` decodes the full payload on every drag move (12.8 ms for the sample manuscript, grows with project size).

#### G — Tests, CI, i18n (short)
- **G1:** `conftest.py:34-41` and `:64-71` use `NamedTemporaryFile` + `copytree` and never clean up. One run leaves about 120 folders and 100 `.msk` files (about 51 MB). The package also writes `~/.config/manuskript_tests/` and `~/.local/share/manuskript_tests/`. Use `tmp_path` plus a session-wide isolated HOME/XDG. S.
- **G2:** All 412 tests ran locally (Python 3.11 with the pinned `requirements.txt` wheels, and 3.13 with system PyQt5 5.15.10, offscreen), but **not yet in this repository's CI**. CI runs pytest on Python 3.9 in three jobs:
  - `pytest.yml`: Ubuntu 24.04, xvfb, PyQt5 from `requirements.txt`.
  - `build_linux.yml`: Ubuntu 22.04, latest PyQt5, offscreen, with `language_tool_python`, `symspellpy` and `pyspellchecker` installed. The local runs did not have those libraries.
  - `build_osx.yml`: macOS.

  The workflows only trigger on `develop` or by manual dispatch. So: enable Actions on the fork, then start them for each branch from the Actions tab, or open PRs inside the fork against its `develop`. S, possibly more if xvfb-only or Python-3.9-only failures show up.
- **G3:** Run `make translation` (21 new strings). Change `outlineBasics.py:123` to `safeTranslate(…, 'Open {}').format(title)`, because today the string is formatted before it is translated, so it never is. Wrap the literal in `welcome.py:317` too. Check that PyInstaller and Flatpak ship the `qtbase_*.qm` that `9c279f8` now loads. S.
- **G4:** Rare segfault at interpreter exit (`focusOutEvent → submit()` while widgets are destroyed). Pre-existing, not reliably reproducible. Guard `submit()` during teardown and use `QPersistentModelIndex` in `_indexes`. S.

## 3. Code quality assessment

### 3.1 Summary

Manuskript's **concept and file format are its biggest assets**:

- Projects are plain text in folders, readable and git-friendly.
- The models cover outline, characters, plots and world.
- The editor is a capable Markdown editor.

The code base works. It has a clear module layout (`models/`, `load_save/`, `ui/`, `exporter/`, `importer/`), comments that explain intent in many places, logging that records every relevant version at startup, and a CI that builds for three platforms.

What makes it fragile is not the style but a few **structural patterns**. Almost every data-loss and DnD bug traced back to one of them:

1. **Persistence is a stateful delta sync over module globals.** One global `cache` dict served three purposes on `develop`: skip unchanged writes, list the files Manuskript owns (and may delete), and signal "new project" (empty cache → `rmtree`). Each purpose produced a data-loss bug. The fixes added guards. They did not change the structure.
2. **The outline model breaks the Qt model contract.** It emits `dataChanged` inside `beginInsertRows/endInsertRows` and `beginRemoveRows/endRemoveRows` (13 and 12 `dataChanged` signals for one insert or remove in a top-level folder, 6 more per nesting level, measured). An in-model drag move is an XML copy followed by a delete. `editorWidget.modelDataChanged` reacting mid-transaction is exactly what made a drop delete *another* item (#719, #1264).
3. **A global service locator.** `F.mainWindow()` is called 117 times in 35 non-test files, models included (`references.py` alone has 23 calls, and `plotModel` builds a `QMenu` on a MainWindow button). Persistence and several models (e.g. `plotModel`) cannot be tested without a full window and a loaded project. `outlineModel` can, but the test package still builds a MainWindow at import time.
4. **Editors cannot tell a user edit from a programmatic change.** Any `contentsChanged` (including a highlighter pass) starts the submit timer. That is the root of A1. A related problem: the highlighter itself changes the document (`setBlockFormat` inside `highlightBlock`), which starts the submit timer and also breaks undo (C2).
5. **Every uncaught exception exits the app** (B1), for example one raised in a slot or a paint event. Small bugs therefore become crashes that lose all unsaved work.

The fix branches address the symptoms with tests, and in several places the root cause too:

- `beginMoveRows` for Move Up/Down,
- a private MIME type,
- atomic writes,
- "fail closed" loading,
- removing the documented test-suite workaround (`F.AUC = Qt.AutoConnection`, marked FIXME) for "connection is not unique", now that its cause is fixed (`d27cb9c`).

They also grew the two central functions: `saveProject` went from 346 to 465 lines (58 → 91 control-flow nodes: if/for/while/try/with/except, boolean and conditional expressions), `loadProject` from 298 to 352. That is the clearest sign that the next step should be structural, done in small steps (3.4).

### 3.2 Numbers

Measured on `fix/all-quickfixes`, with `develop` in brackets where available.

| Metric | Value |
|---|---|
| Hand-written Python (no tests, no generated UI) | ≈ 29,300 lines (27,800); generated UI code (28 pyuic5 files, including `ui/mainWindow.py`) ≈ 6,500 |
| Largest files | `mainWindow.py` 2,170 (2,049); `load_save/version_1.py` 1,409 (1,137); `settingsWindow.py` 1,124 (1,075) |
| Long functions (selection) | `version_1.saveProject` 465 lines (346); `loadProject` 352 (298); `references.infos` 318; `settingsWindow.__init__` 292; `outlineBasics.makePopupMenu` 226 (209); `MainWindow.makeConnections` 182 (175); `settings.load` 177 (168) |
| `MainWindow` | one class, 2,122 lines, 112 methods (108) |
| Coupling | `mainWindow()` 117 calls / 35 files (116 / 36); ≈ 440 `.connect(` calls; teardown is a hand-kept list of `disconnectAll` calls in `breakConnections` (54 lines vs. 182 for `makeConnections`); 64 uses of `AUC` (`AutoConnection \| UniqueConnection`) (68) |
| Threads | none: the app starts no threads (`logging.py` only installs `threading.excepthook`). Pandoc runs, LanguageTool requests and saving block the GUI thread. |
| Tests | 412 tests / 34 files / ≈ 7,000 lines (39 / 11 / ≈ 1,000) |
| Statement coverage, hand-written code | **73 %** (51 %). Large gains in the data and export code: importer 40 → 90 %, load_save 38 → 78 %, pandoc exporter 48 → 83 %, spellchecker 45 → 84 %. Most missed statements: `corkDelegate` 9 %, `MDEditView` 52 %, `markdownTokenizer` 62 %, `textEditView` 60 %, `storylineView` 27 %, `version_0` 14 % (legacy loader). Dead modules are at 0 %. |
| pyflakes | 306 findings (321): 166 unused imports, 40 star imports, 36 undefined names (all in the dead `persosProxyModel.py`), 28 unused `global`, 27 unused variables. Real bugs in live code (undefined names, `raise NotImplemented`) were fixed on the branches. |
| Qt 6 surface | 56 `QRegExp`, ≈ 295 `qApp`, 7 `exec_`, ≈ 470 unscoped enums, QtWebKit path, 28 `.ui` files |
| i18n | 37 languages × 779 messages: 12 at ≥ 98 %, 16 below 50 % (3 of them at 0 %; `en_GB` at 15 % needs few translations anyway). `.qm` files match their `.ts` sources. |

### 3.3 Strengths and weaknesses by area

#### 3.3.1 Data layer (models, load/save, settings)

**Strengths**
- The v1 format is a good design: plain text, a VCS-friendly layout, MultiMarkdown metadata. The fixes changed no on-disk keys.
- After the fixes, the save path is fail-safe in every scenario the tests and the fuzzer cover (remaining gaps: B7, B9):
  - atomic `writeFile` (`version_1.py:124-163`),
  - rewrite instead of in-place moves,
  - a `freshTarget` guard instead of `rmtree`,
  - old files kept when new ones fail,
  - case-only renames on case-insensitive file systems (emulated in a Linux test, not yet run on Windows or macOS).
- Loading fails closed instead of opening an empty project that would later be saved over the real one.
- The legacy `settings.pickle` is deliberately not loaded (no unpickling of untrusted data).

**Weaknesses**

| Weakness | Evidence | Consequence |
|---|---|---|
| Delta-sync state in module globals (`cache`, `freshTarget`, `unreadable`) that are reset only by `loadSave.clearSaveCache()`, which every "new target" path (3 call sites today) must remember to call. Persistence calls `mainWindow()` and opens dialogs itself. | `version_1.py:44-55`, `loadSave.py:26-30`, dialogs at `version_1.py:446-455`, `:628-634`, `:1192-1211` | Cannot be unit-tested or fuzzed without a MainWindow. One missed call brings back cross-project bugs. |
| `dataChanged` inside insert/remove transactions | `abstractModel.py:533-538`, `:634-640` → `outlineItem.py:197-203`, `:245-250` | Every new slot that listens to `dataChanged` can bring back the "drop deletes another item" bug. |
| `QAbstractItemModelTester` violations: `flags()` for the invalid index includes `ItemIsEditable` (`abstractModel.py:273`), the root emits `dataChanged` with an invalid index (`abstractItem.py:89-93`), and `bottomRight` is one column past the end (`abstractItem.py:93`) | 177 warnings in a 6-step scenario, from 3 distinct checks (122 × flags, 54 × invalid topLeft, 1 × bottomRight) | Proxies and persistent indexes can misbehave in hard-to-reproduce ways. |
| An internal DnD move is an XML copy plus a delete: a window with duplicate IDs, editor tabs left holding detached objects, control characters (`\x0c`) silently stripped | `abstractModel.py:295-511`, `abstractItem.py:292-318` | Variants #719, #1264, #324. Slow drags of large folders (#918, #1193). |
| A public tree-mutation API (`insertChild`, `outlineItem(parent=…)`) is used outside the model, followed by a bare `layoutChanged` | `ui/importers/importer.py:263`, `:297-320` | The model contract depends on discipline. The same pattern broke Move Up/Down. |
| Persistence state (`_lastPath`) lives on items and travels through clipboard XML. Saving mutates the model. | `abstractItem.py:39`, `:312`; `version_1.py:325`, `:761`, `:531-539` | Every new item-creation path must remember to clear it (duplicate inherited the file). |
| Four ID strategies; characters, plots and world reuse IDs; `int()` on unvalidated strings | see B6, B3 | Re-bound references; one hand-edited ID locks the user out of the project |
| The schema is scattered: the "computed, not persisted" list exists twice and has drifted (`charCount` is written to every `.md`/`folder.txt`), and the flat-data layout is hard-coded in 4 places | `version_1.py:818` vs `outlineItem.py:493-497` | Every scene edit rewrites the `folder.txt` of all its ancestors (sync churn) |
| Quadratic path helpers on every autosave | 4,000 scenes in one folder: 1.6 s | Large imported projects stutter |
| Dead code: `persosProxyModel.py`, `plotsProxyModel.py`, shadowed methods, `abstractModel.removed` grows forever | grep, pyflakes | Noise; memory held by removed items, including their full text |

#### 3.3.2 UI and editor layer

**Strengths**
- Large measured performance gains on the fix branches. For example, scrolling and typing no longer rescan the whole document, and the highlighter is no longer stacked. Pending text is flushed before every switch, save and quit, and projects close in a safe order.
- New code handles Qt subtleties and comments on them: persistent indexes across DnD, `SingleSelection` to keep Shift ranges, a deferred menu rebuild.
- The generated `*_ui.py` files match their `.ui` sources (all 28 regenerated, cosmetic differences only). The one exception is `mainEditor_ui.py:95,99`. It was hand-edited in `cc8924a` to stop translating shortcuts, but the `.ui` was never changed (it needs `notr="true"`), so `make ui` would undo that edit.

**Weaknesses**

| Weakness | Evidence | Consequence |
|---|---|---|
| God objects: `MainWindow` (2,122-line class, 112 methods) covers character, plot and world tabs, the bulk-info manager, history, load/save orchestration, timers and menus. `settingsWindow.__init__` alone has 292 lines. | 5 of the 7 fix branches touched `mainWindow.py` (git merged them without conflicts this time) | Unrelated changes meet in one file, which raises the merge-conflict risk. Hidden state flags (`_lastFocus`, `_previousSelectionEmpty`, which is inverted for World, Outline and Editor: `mainWindow.py:287`, `:296`, `:305` vs `:280`) |
| Lifecycle: models, selection models and menus are never freed | 4 open/close cycles: `outlineModel` 0 → 8, `QItemSelectionModel` +37 per cycle; `generateViewMenu()` leaks 14 `QMenu`s per call | The previous project's text stays in RAM. Correct behaviour depends on fresh objects, not on teardown (#1154). |
| Editors submit on any `contentsChanged` | `textEditView.py:62-69`, `:369-374` | A1 (data loss), the source of spurious submits |
| The highlighter changes the document | `basicHighlighter.py:131-145` | C2 (undo) |
| Too much synchronous work per keystroke and per switch | C3, C4: ~8 highlight passes per switch | Lag in long scenes (#1286) |
| UTF-16 vs Python indices, with no shared helper | C1 | Wrong positions with emoji |
| No background work at all | pandoc `Popen().communicate()`, LT start/checks, saving | Freezes; users kill the app |
| Small Qt slips | the search highlighter replaces `focusOutEvent` without chaining; `restoreOverrideCursor()` on every mouse move; `QAction.data` shadowed by an attribute; a `QMutex` as re-entrancy guard in single-threaded code; image tooltips fetch URLs into an unbounded cache | Hard-to-reproduce glitches |

#### 3.3.3 Engineering infrastructure

**Strengths**
- CI runs on GitHub Actions: tests on pull requests since 2021, Windows builds since 2022. In June 2026 the Linux and macOS build jobs that were still on Travis moved over too, and a Docker setup was added (`d32271c`). CI builds Linux (PyInstaller, deb, rpm), macOS and Windows artifacts.
- Logging is better than average for a desktop app: version information at startup, per-run log files with pruning, `faulthandler`.
- The test suite now covers most of the data layer with reusable helpers (`tests/load_save/helpers.py`), fake spellcheck backends and `tmp_path`/`monkeypatch` isolation.

**Weaknesses**

| Weakness | Evidence | Consequence |
|---|---|---|
| CI tests only Python 3.9 (EOL since October 2025), runs no tests on Windows, installs no pandoc, has no lint step. Job names reference `matrix.python_version` while the key is `python-version`, so the version shows blank. | `.github/workflows/*.yml` | The new `os.replace`-based saving has never run on Windows in CI. Regressions on 3.11–3.14 reach users first. |
| Dependencies are declared in about 9 places with conflicting pins: `requirements.txt` PyQt5 5.15.11, workflows 5.15.7 or unpinned, Docker uses the distro package. There is no `pyproject.toml` and no `requires-python`. `pyenchant` is "required" but treated as optional. macOS builds lack `markdown`, `symspellpy`, `pyspellchecker` and `language_tool_python` (only `pyenchant` is included). | `requirements.txt`, workflows, `Dockerfile`, `package/*`, `snap/` | Different features per platform; unclear support matrix |
| The test package creates the QApplication and MainWindow at import time and writes to `~/.config/manuskript_tests` and `~/.local/share/manuskript_tests`. The old fixtures leak temp data (G1). | `tests/__init__.py:11-17`, `conftest.py` | Order-dependent tests, polluted developer machines |
| The translation workflow is manual and partly broken: `util/linguist_update.py` selects `*.qm` instead of `*.ts`, the makefile `linguist` convenience target is hard-coded to `fr`, and there is no drift check | `util/linguist_update.py:24-31`, `makefile:27-34` | New strings stay English |
| Platform end-of-life risk: Qt 5.15 is the last Qt 5 series, the QtWebKit path is optional but packaged (rpm, snap), and the vendored **pdf.js 1.4.237 (2016)** predates later security fixes (e.g. CVE-2024-4367). Exposure is limited, because only PDFs Manuskript generated itself are previewed. | `ui/views/webView.py`, `PDFViewer.py`, `libs/pdf.js` | Packaging gets harder; a late migration is risky |
| Repo hygiene: Travis-era scripts (`package/prepare_*.sh`), `.codeclimate.yml`, `TODO.t2t` (2015), a 1-byte `manuskript/test.py`, a makefile `compile` target that points to a missing `setup.py`, a wrong `.msk` icon path in `manuskript.spec:92`, no `CONTRIBUTING.md` | | New contributors waste time on dead paths |

### 3.4 Recommended adjustments (incremental, each one a PR)

The order matters more than the size. Each step makes the next one safer, and none of them changes the format version. Two exceptions touch file content: item 5 stops writing the computed `charCount` key (each file is rewritten once), and a persisted ID counter in item 11 would be a format change.

#### Quick wins (S, about ½ day each)
1. **Model-tester gate.** Attach `QAbstractItemModelTester` (shipped with PyQt5) to `mdlOutline` in the DnD and load/save tests, with an allow-list. Fix the two one-line violations (`flags()` for the invalid index, `bottomRight` column).
2. **Test isolation.** Use `tmp_path` in the two old fixtures, a session-wide temp HOME/XDG, and a `closeProject()` teardown (G1). `QStandardPaths.setTestModeEnabled` alone is not enough, because it still writes to `~/.qttest`.
3. **CI matrix.** Test Python 3.9 (or the new floor), 3.11, 3.12 and 3.13. Install pandoc, fix the matrix key, remove the duplicate Linux test job.
4. **Lint gate.** `ruff check --select F --extend-exclude '*_ui.py,manuskript/ui/mainWindow.py,manuskript/ui/bulkInfoManager.py,manuskript/ui/characterInfoDialog.py' manuskript` with per-file ignores for today's findings, so the job starts green. Then one mechanical PR for unused imports and the dead modules.
5. **One source of truth for the schema.** A single "computed, not persisted" set (which drops `charCount` from `.md`/`folder.txt`) and one flat-data layout, plus a golden-file test that pins the on-disk key names.
6. **Translation refresh** and a `CONTRIBUTING.md`: dev setup, isolated test run, `make ui`/`make translation`, commit style, Weblate.

#### Medium (M, 1–3 days each)
7. **No signals inside model transactions.** Defer the word-count propagation until after `endInsertRows`/`endRemoveRows`, and add a test that fails on `dataChanged` inside a bracket. This removes one of the two roots of the DnD bug class. The other is the copy-and-delete move (item 9).
8. **Dirty flag from structural signals** (A3). Afterwards, drop the root's invalid-index `dataChanged`.
9. **Real in-model moves** (`beginMoveRows` across parents) for internal drags. Keep the XML path for copy, paste and cross-window drops.
10. **Make tree mutation private to the model.** The importer goes through `insertItems`, or a reset for bulk imports.
11. **One ID allocator** per model type (never reuse an ID within a project) and referential cleanup on delete in the model layer (B6).
12. **Editors submit only real user edits** (fixes A1 structurally), and the highlighter no longer changes block formats (C2).
13. **A symmetric project lifecycle:** `deleteLater()` the old models and selection models, keep and delete the submenus, give timers a parent.
14. **Run the tests on Windows in CI.** Add a `pyproject.toml` with extras (`spellcheck`, `export`, `test`) and a GUI entry point, and keep `requirements.txt` as the lock file.

#### Larger (L/XL, can be split further)
15. **Persistence as an object with a plan/execute split.**
    - Step 0: add the save-path fuzzer used for this review as a slow test. It covers 61 seeds, is not on any branch yet, and can be shared on request.
    - Step 1: wrap the globals in a `FolderStore`.
    - Step 2: `serialize(project) → {path: content}` (pure), then `plan(store, files) → [Write, Remove, Keep, Move]`, then `execute(plan) → SaveReport`. The plan step can be tested and fuzzed without Qt.
    - Step 3: MainWindow shows the reports, and persistence no longer imports widgets.
    - About 1–2 weeks overall, in 3–4 PRs.
16. **A `Project` container instead of `F.mainWindow()`** in models and persistence, one model per PR (start with `plotModel`, which cannot even be constructed without a window).
17. **Split `MainWindow` into per-tab controllers**: spellcheck menu, view menu, character, plot and world tabs, navigation. Start with the spellcheck menu (self-contained, already tested).
18. **Background work:** asynchronous `QProcess` for pandoc, then a LanguageTool worker (D2).
19. **Qt 6 preparation on PyQt5:** scoped enums, `QRegularExpression`, `QApplication.instance()`, `exec()`. PyQt5 5.15 already accepts these, so this can land gradually. Drop QtWebKit, then switch bindings (PyQt6 or PySide6). XL in total, but phase 1 is many small mechanical PRs, partly covered by the 412 tests (73 % statement coverage overall, editor and views about 60 %).

The excepthook (B1) is deliberately not in this list. It is a policy decision rather than a refactoring, but it is the most valuable single change for users.

## 4. Questions for the maintainers

Suggested order for the discussion: the first block determines how the fixes get merged, the rest can be decided item by item.

**Merging the fix branches**
1. **PR format:** one PR per branch, in the order of 1.5? Or a different split, for example cherry-picking single commits?
2. **Behaviour changes:** which of BC1–BC15 in section 1.4 are acceptable as new defaults? The most important are BC1 (subtree rewrite on folder rename), BC3 (refuse to open on unreadable root files) and BC9 (explicit "Start LanguageTool…"). Independently of that, the possible regression D5 (French elisions) should be fixed on `fix/spellcheck` before it is merged.
3. **Translations:** regenerate the `.ts` files in these PRs, or in the usual release step (G3)?

**Policy decisions on open items**

4. **Excepthook (B1):** keep "fail fast", or *log → one dialog → separate recovery copy → user chooses quit or continue*? If the user continues, may autosave keep writing the real project?
5. **Damaged root files (B3):** salvage what lxml can recover and keep a `.damaged` backup, or keep refusing to open but name the broken file?
6. **Multi-edit in the Outline tab (A1):** keep editing several summaries at once (and only submit real edits), or disable it like the metadata panel?
7. **Dirty flag (A3):** should every structural change (rows inserted, removed or moved) mark the project modified?
8. **IDs (B6, B5):** never reuse IDs (`max+1`, or a persisted counter)? When a label or status is deleted, reset the items that use it to "none", ask first, or move to stable IDs (a format change)?
9. **Foreign files in project folders (B7):** adopt hand-made scenes without ID, list them as "not loaded", or keep ignoring them? Is the subtree rewrite on rename acceptable long term, or are real directory renames wanted?
10. **Signals (B8):** with "save on quit" off, should SIGTERM save anyway, or write a recovery copy instead of asking?
11. **pandoc (E1, E2):** disable YAML metadata blocks by default (and migrate)? Use xelatex/lualatex by default when installed?
12. **Unfinished export filters (E5):** implement them, or hide them for now?
13. **LanguageTool (D2, D3):** is a background worker thread acceptable, or should LT be a documented "slow, proof-reading" mode? Is a blocking start acceptable if a dialog warns about the download first?
14. **Per-Space submit (C4):** is it acceptable for the word count to update about 0.5 s (the existing 500 ms debounce) after typing stops?

**Direction**

15. **Supported versions:** which Python versions are officially supported (and tested in CI)? Should the README state the tested floor rather than the 3.6 syntax floor?
16. **Packaging:** should Manuskript become pip-installable (`pyproject.toml` with extras and an entry point)? Is `pyenchant` required or optional?
17. **Refactoring:** are staged refactors welcome (3.4 items 7–13 and 15–17, split into small PRs with tests; only a persisted ID counter in item 11 would touch the format)? If so, persistence first or the model contract first?
18. **Qt 6:** is a migration planned, and with which binding? May phase-1 changes (scoped enums, `QRegularExpression`, no `qApp`) be merged now on PyQt5? Can the QtWebKit path be dropped?
19. **Tooling:** are `ruff` (F rules only to start), `pytest-qt` and mechanical cleanup PRs (unused imports, dead modules) acceptable?
20. **Low-completion languages:** with `de6de99` (on `fix/ui-settings-search`), Settings lists every shipped `.qm`, including three at 0 %. Should that branch hide languages below some threshold before it is merged?
21. **Small decisions** (marked ✋ in section 2 but without their own question):
    - B9: is the `fsync` cost acceptable?
    - C5: keep `-- ` lines?
    - D4: per-language clitic lists?
    - E8: prune empty import folders by default?
    - F1: Settings without a project, or a language selector on the welcome screen?
    - F2: is a "Clear list" entry wanted?

## Appendix

### A. Running the tests in isolation

The test package creates a MainWindow at import time and writes to the Qt settings and data folders (see G1). Until that is fixed, run the suite with a throw-away HOME:

```sh
T=$(mktemp -d)
mkdir -p "$T/config" "$T/data" "$T/tmp"
HOME=$T XDG_CONFIG_HOME=$T/config XDG_DATA_HOME=$T/data TMPDIR=$T/tmp \
QT_QPA_PLATFORM=offscreen python -m pytest -q manuskript/tests
rm -rf "$T"
```

Results: `develop` 39 passed. `fix/all-quickfixes` 412 passed, both with Python 3.13 / PyQt5 5.15.10 / Qt 5.15.19 (system packages) and with Python 3.11 using the pinned wheels from `requirements.txt`. Every single commit on the seven fix branches also passes the full suite on its own (84 runs), so `git bisect` works across them.

### B. Upstream issues referenced by the fix branches

#313 · #324 · #351 (related) · #467 · #661 · #694 · #719 · #761 · #808 · #811 · #819 · #918 · #929 (spellcheck part; export part still open, see E6) · #963 · #978 · #997 · #1010 (crash part only) · #1127 · #1128 · #1154 · #1178 · #1193 · #1215 · #1216 · #1220 · #1228 · #1264 · #1286 · #1306 · #1320 · #1356 · #1376 · #1393 · #1394 · #1421 · #1449

"Referenced" means the commit message explains how the commit relates to the issue. Some issues are only partly addressed. Please check each one before closing it.

### C. Method and limitations

- **Static and dynamic analysis:** code reading, isolated offscreen scripts (PyQt5 5.15.10 / Qt 5.15.19), `pyflakes`, `coverage.py` and an AST-based size/complexity scan. Performance numbers were measured with `QT_QPA_PLATFORM=offscreen`, so absolute times on a real display are higher.
- **Not available:** Windows, macOS, Breeze5/Adwaita-qt styles, a real X server, and a running LanguageTool server (a fake tool was used). Items that depend on these are marked as not verified end to end.
- **Line numbers** refer to `fix/all-quickfixes` at `eacaf8f`.
