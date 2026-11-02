# Manuskript: bug-fix branches, open problems and code-quality review

*Discussion paper for the Manuskript maintainers, written November 2026 (version 3). The fix branches (`fix/*` and `fix/all-quickfixes`) are in the fork [sniemeyer42/manuskript](https://github.com/sniemeyer42/manuskript). At the time of writing (according to the remote-tracking branches of a local clone, not checked on GitHub itself), six of the branches are there as described here. Three are not, or not completely: `fix/review-findings` is not on the fork at all, `fix/spellcheck` there lacks its last commit (D5, `92bee56`), and `fix/all-quickfixes` there is at `26f618e` (version 1 of this document), without the 10 commits that followed (the `fix/review-findings` and D5 work, their merges, and version 2 of this document, `1d7320f`). All branches are based on `develop` at `01e0574` (2026-09-02), except `fix/review-findings`, which builds on `fix/all-quickfixes` (see section 1).*

**What changed in version 3.** The code of the fix branches has not changed since version 2, so the test counts stay. New in this version:

- **A9**, a data loss that is still open on `fix/all-quickfixes` and also on `develop`: two sibling items whose titles give the same file name are reordered, one write of the next save fails, and the user discards (or the app ends) before a later save succeeds. One scene is then gone. Fix: S.
- **A10, F5, G5, G6**: bugs in upstream code that were fixed on the fork owner's personal branch (`personal/main`, not on GitHub at the time of writing). They are listed here as open, with the commit that fixes them there.
- **B10**, and additions to **B3** and **B7**: problems in the current code that the panel behind the save design (3.4 item 15) noted, checked here on `1d7320f`: two characters with the same ID (deleting one can delete the other), a non-numeric character ID (the project does not open, or the app exits), and a scene added outside Manuskript in a chapter that is then deleted (it no longer loads). No fix exists yet.
- **B2**: a first manual test with the Breeze style (no crash). Adwaita-qt is still open.
- **Windows**: the suite ran under Wine with a Windows CPython (G5). No failure pointed to product code. One test fixture (used by 39 tests) and two test assertions fail there, and a second fixture has the same pattern.
- Pointers to a concrete design for a store-based folder save, as reference material (3.4 item 15, Q4, Q17).

## TL;DR

- On `develop`, folder-mode projects can **lose text**, often silently. This happens when items with similar titles are reordered or moved, when the editor tree is used for drag and drop, and when a save or load fails. Duplicating a folder, or moving "Chapter 10" above "Chapter 1", makes every later save crash. Any uncaught exception closes the app without saving. These bugs explain several upstream data-loss reports (e.g. #719, #1306, #1320). They are the biggest risk for people who write real projects in Manuskript, and they can be fixed without changing its concept or file format.
- Eight fix branches (91 small commits) address many data-loss, crash, performance and usability bugs. Together they reference 39 upstream issues, several of them long-standing. `fix/all-quickfixes` combines all eight. The test suite grows **from 39 to 630 tests**.
- The data-loss bugs found while writing the first version of this document (A1–A5), the scroll-bar segfault (B2) and a spell-check regression on one of the branches (D5) are fixed too, on `fix/review-findings` and `fix/spellcheck`.
- Some problems are still open. Section 2 lists each with an effort estimate. The most important:
  - the fail-fast excepthook (B1),
  - a scene that is lost when two sibling titles give the same file name and a save fails after a reorder (A9, new in version 3, also on `develop`; fix S),
  - damaged project files that keep a whole project from opening (B3),
  - two crashes found during the last fix round (A6, A8),
  - a manual check of the scroll-bar fix with Adwaita-qt (B2; a first manual test with Breeze showed no crash).
- **All code and text were written by an AI model** (Claude), directed by the fork owner but not reviewed line by line by a human. See below.
- Section 3 is a code-quality assessment with incremental proposals. Section 4 collects the questions maintainers need to decide.

## How this was produced

**Who wrote this.** The code, the tests, the commit messages and this document were written by Claude, an AI model made by Anthropic, working in Claude Code. The fork owner (sniemeyer42) started the work, set its scope, and approved the proposals in it, but did not write the code and has not reviewed it line by line: at the pace it was produced, that was not possible. The commits name the fork owner as author because they come from the fork, and each one carries a `Co-Authored-By: Claude` trailer.

Please review the branches as you would review a large contribution from a new contributor that no human has checked yet. The tests and the adversarial reviews described below lower the risk, but they do not replace a review by someone who knows the code base.

How the work was done:

1. **Scan.** Parallel reviewers each took one subsystem (load/save, models/DnD, editors, spellcheck, import/export, UI/settings, app shell, Python compatibility, runtime behaviour). They reported 127 bugs (18 data loss, 32 crashes, 47 wrong behaviour, 30 minor) and checked them against the upstream issue tracker. 123 of them were reproduced with small scripts before any fix was written.
2. **Fix.** One branch per area. Each commit adds tests. For bug fixes, the new test reproduces the bug on `develop` and passes on the branch. Performance commits add tests that check the output is unchanged.
3. **Review.** Three rounds of adversarial review, in which independent reviewers tried to break each fix. Most of what they found was fixed. The rest is listed as trade-offs in 1.4 and as open problems in section 2. The folder-mode save path was also fuzzed with random edit sequences plus injected write and read errors: 61 seeds, no data loss. The fuzzer is not on the branches yet (see 3.4, item 15).
4. **This document.** The analysis was fact-checked against the code and git history by separate reviewers, who also reproduced the newly found bugs (A1–A5) with their own scripts.
5. **Follow-up round.** A1–A5, B2 and D5 were then fixed the same way: one commit per item, each with a regression test that fails without the fix, then two rounds of adversarial review. Both rounds found real problems in two of the fixes, and both fixes were reworked each time:
   - The D5 fix first accepted wrong elisions such as `un’amico` and `l’chat`, and changed what Hunspell dictionaries report. After the first rework it accepted missing-accent typos such as `jusqu’a` and `dov’e`.
   - The A4 fix first did not restore everything after a failed "Save as…". After the first rework it wrote no copy when the target was a link to the project file.

   The last rework of these two fixes was checked with the reviewers' scripts and the full test suite, but not reviewed a third time. Problems found along the way that the fixes did not cause are listed as new open items (A6–A8, D6).
6. **After version 2.** The fork owner then had a personal version made on top of `fix/all-quickfixes` (branch `personal/main`: one user, Linux and Windows, folder-mode projects kept in git). That work, again done by Claude, produced the version 3 additions:
   - A9 was found by one of the three designs of a design panel for a new folder-mode save, and two of the panel's judges reproduced it on a copy of `1d7320f`. For this document it was reproduced again with small tests on fresh copies of `1d7320f` and of `develop`.
   - B10 and the additions to B3 and B7 start from notes in the reports of the same panel's judges. They were checked here with small tests on a fresh copy of `1d7320f`.
   - A10, F5, G5 and G6 were fixed on `personal/main` (the matrix-key part of G6 was already noted in 3.3.3). Each was checked here against the code of `fix/all-quickfixes` and `develop`. The A10 and G5 fixes were also applied to a copy of `1d7320f` and run there.
   - The suite was run under Wine with a Windows CPython (G5).
   - The fork owner tested the B2 fix by hand with Breeze.
7. **Not done yet.** No testing on a real Windows (only under Wine) or on macOS, no automated test under a real X server (only `offscreen`), one manual test (the fork owner's B2 check with Breeze), and no review by a human: neither by a Manuskript developer nor by the fork owner. Please treat the branches as well-tested proposals, not as finished work.

## Contents

1. [Changes compared to `develop`](#1-changes-compared-to-develop)
2. [Open problems and effort](#2-open-problems-and-effort)
3. [Code quality assessment](#3-code-quality-assessment)
4. [Questions for the maintainers](#4-questions-for-the-maintainers)
5. [Appendix](#appendix)

## 1. Changes compared to `develop`

All branches start from `develop` at `01e0574` ("Merge pull request #1439 …", 2026-09-02). Each of the first seven branches can be merged on its own. `fix/review-findings` is different: it was written on top of `fix/all-quickfixes` at `eacaf8f` and uses code from several branches (`submitPendingChanges()` from `fix/editor-performance`, the save cache and the atomic `writeFile` from `fix/save-load-data-loss`, and their test helpers). It has to be merged last. `fix/all-quickfixes` merges all eight, one after another, with `--no-ff`. `fix/spellcheck` is merged twice: the second merge brings in D5 (`92bee56`), after `fix/ui-settings-search`.

### 1.1 Overview

| Branch | Commits | Files | Lines +/- | Tests (develop: 39) | Upstream issues |
|---|---:|---:|---:|---:|---|
| `fix/save-load-data-loss` | 12 | 14 | +2145 / −121 | 99 (+60) | #313 #719 #761 #811 #1128 #1216 #1306 #1320 #1356 #1394 |
| `fix/crashes` | 9 | 26 | +692 / −100 | 53 (+14) | #808 #918 #1010 (crash only) #1154 |
| `fix/outline-dnd` | 9 | 11 | +962 / −101 | 72 (+33) | #324 #719 #918 #1193 #1216 #1264 #1286 #1394 |
| `fix/editor-performance` | 9 | 8 | +961 / −64 | 119 (+80) | #661 #819 #963 #1286 #1376 #1393 |
| `fix/import-export` | 17 | 25 | +1151 / −101 | 94 (+55) | #351 (rel.) #694 #929 (rel.) #978 #1178 #1215 |
| `fix/spellcheck` | 14 | 5 | +1669 / −127 | 274 (+235) | #929 #1178 |
| `fix/ui-settings-search` | 15 | 23 | +1061 / −91 | 81 (+42) | #467 #997 #1127 #1220 #1228 #1421 #1449 |
| `fix/review-findings` ¹ | 6 | 16 | +1644 / −37 | 484 (+72) | #450 #601 #1435 |

¹ Counted against `fix/all-quickfixes` at `eacaf8f` (412 tests), not against `develop`.

The integrated branch `fix/all-quickfixes` changes 101 files (+10256 / −730 lines: about 7760 of the added lines are tests, about 2500 are production code). Its suite has **630 tests** (39 on `develop`), and all of them pass (8 only run when optional spell-check backends or dictionaries are installed, see appendix A). Each commit on the eight fix branches passes the full test suite on its own. The merge conflicts were all small:

- `abstractModel.py`: keep outline-dnd's `removeUsedIDs` and also reset `_lastPath` (from save-load) when an item gets a new ID.
- `main.py`: two imports.
- Four test files that both sides had added to.
- `spellchecker.py`: one import line (`unicodedata` for D5, `zlib` for A5).

Tests ran with `QT_QPA_PLATFORM=offscreen` on two Linux setups:

- Python 3.13 with system PyQt5 5.15.10 / Qt 5.15.19,
- Python 3.11 with the pinned `requirements.txt` wheels (PyQt5 5.15.11).

For version 3, the suite also ran under Wine with the Windows CPython 3.12.10 and PyQt5 5.15.11 / Qt 5.15.2. That is not a real Windows. There, 39 tests stop with a setup error in a fixture and 2 fail on POSIX file modes, all in test code, and 2 more fail because of the embeddable Python itself (G5). The branches have not run on this repository's CI yet (Python 3.9, see G2). All code parses with the Python 3.6 grammar (checked with `ast`), but it has only been run on 3.11 and 3.13 (Linux) and 3.12 (Wine).

### 1.2 What each branch fixes

**`fix/save-load-data-loss`** is the most important branch. In folder mode (the default), several common actions lost data, either silently or by making every save crash:

- Reordering or moving items whose titles slugify to the same name (umlauts, CJK, Cyrillic): one item's file silently overwrote another's (#1320). One case is still open: the same reorder plus a failed write (A9).
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
- Correct words around apostrophes are no longer underlined: closing quotes and plural possessives (`dogs'`), typographic apostrophes (`isn’t`), and contractions with a known clitic (`geht's`). Partial non-ASCII words are no longer checked while typing (`Grüße` checked as `Grü`). This is the spellcheck part of #929 (BC10).
- French, Italian and Catalan elisions (`l’homme`, `qu’il`, `bell’aspetto`) are accepted with the word-list backends (pyspellchecker, symspellpy; Catalan only with a word list of one's own). With `’`, `develop` accepted most of them by splitting the word at `’`; `fa37b1e` broke that (D5). enchant checks the whole elided form, as since `fa37b1e` (BC21).
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

**`fix/review-findings`** fixes A1–A5 from section 2, which were found while writing the first version of this document, and the known scroll-bar segfault B2 (#450 #601 #1435). All of them also exist on `develop`:

- Outline tab with several items selected: clicking into the "Various" summary field and out again, or toggling spellcheck, erased the summaries of all selected items (A1).
- Split at cursor (Ctrl+K) right after typing lost the text typed last and cut at the wrong place (A2).
- The main editor no longer lets its text area show the scroll bar that was moved out of it. Some styles are reported to crash on that (B2). In a first manual test with Breeze, the fork owner saw no crash. Adwaita-qt still needs a check.
- Adding or removing characters, plots, world items, labels or statuses marks the project as modified, so File > Close saves the change or asks first. Before, it was dropped (A3).
- A failed "Save as…" leaves the project where it was and tells the user why. "Save as…" into the project's own folder no longer deletes files that could not be read when loading (A4).
- Loading a dictionary no longer rewrites the custom-word file, and a damaged file is kept as `.damaged` instead of being emptied (A5).

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
| `92bee56` | **spellcheck:** accept French, Italian and Catalan elisions (D5) |  |

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

#### `fix/review-findings` (based on `eacaf8f`)

| Commit | Change | Upstream |
|---|---|---|
| `2a53412` | **editor:** keep the summaries of several selected outline items (A1) |  |
| `1765c09` | **editor:** split at the cursor including the text just typed (A2) |  |
| `07dce72` | **editor:** do not let the text edit show its moved scroll bar (B2) | #450, #601, #1435 |
| `2f348bd` | **ui:** mark the project modified when rows are added or removed (A3) |  |
| `9b9e2fa` | **ui:** keep the project where it was when "Save as..." fails (A4) |  |
| `0c13f97` | **spellcheck:** do not rewrite or empty the custom dictionary on load (A5) |  |

### 1.4 Behaviour changes that need a maintainer's OK

These are intentional, but they change what users see or how files are written. They should be discussed before merging.

| # | Branch | Change | Why |
|---|---|---|---|
| BC1 | save-load | Renaming or moving a folder **rewrites its whole subtree** instead of renaming one directory. Files Manuskript does not know stay in the old folder. | Moving files in place is what overwrote other items (#1320). Rewriting cannot overwrite or lose a file. Drawback: more I/O and more churn on Dropbox/OneDrive. |
| BC2 | save-load | Saving writes `.<name>.tmp` next to each file and then `os.replace()`s it. It **needs write permission on the folder**, and **hard links are replaced** (symlinks are written through, file mode is kept). A crash can leave a hidden `.tmp` file. Folder mode does not `fsync` (the `.msk` mode does). | A failed write (disk full, USB stick removed) left truncated files (#811, #1128). |
| BC3 | save-load | A project **no longer opens** if its folder is missing, if its `outline/` or `characters/` folder cannot be read, or if a root file (`MANUSKRIPT`, `settings.txt`, `plots.xml`, …) cannot be read or is not valid UTF-8. Before, it opened empty, opened without that data, or crashed. A `settings.txt` with invalid JSON still opens, with default settings. | When it opened empty, the next save (or save on quit) overwrote the real data. |
| BC4 | save-load | Saving **into an existing, non-empty folder that is not a Manuskript project is refused** with a dialog. For an older project, only what Manuskript writes is cleaned up. | Before, "Save as" `Documents.msk` in `$HOME` deleted `~/Documents` recursively. |
| BC5 | save-load | File names are capped at 64 slug characters. Items with longer titles are **renamed once** on their next save. Sibling titles that differ only after the cut then share a file name (A9). | Long titles raised "File name too long" and aborted the save (#313). |
| BC6 | save-load | Files in the project folder that were not loaded are **kept, not deleted**. They are still not shown in the UI. | Before, the first save deleted them. |
| BC7 | save-load | Clicking a demo project opens a **copy in the user data folder**. | Edits were written into the installed sample, or lost on a read-only install. |
| BC8 | save-load | If saving fails when the user closes or quits, Manuskript **asks before discarding** unsaved changes. | Before, the window just closed and the changes were lost. |
| BC9 | spellcheck | LanguageTool dictionaries are listed only after the new menu entry **"Start LanguageTool to list its dictionaries"** has been used, unless the project's dictionary is a LanguageTool one (then LT starts on load). Starting blocks the UI, and the first start downloads about 250 MB. The new strings are untranslated. | Building the menu started a JVM (and possibly the download) on every project load. |
| BC10 | spellcheck | A word with apostrophes is accepted if the dictionary knows it (`’` is also read as `'`), after quotes and plural-possessive apostrophes around it are stripped. It is also accepted if it is a known word followed by one of the clitics `'s 'n 'm 'ne 'nen 'nem`, the same list for every language. Words are no longer split at apostrophes. For the word-list backends, elisions (`l’homme`) are handled separately, see BC21. | False positives with possessives, quotes and contractions (#929). |
| BC11 | outline-dnd | Right-clicking an item outside the selection makes the context menu act **on that item, without changing the selection**. | Before, the menu acted on the old selection (#1286). |
| BC12 | import-export | Markdown import treats `#` lines as headers in fewer cases. These are no longer headers: lines in closed ```` ``` ```` code fences, scene breaks made only of `# * - _` (`#`, `# # #`), and lines with 7 or more `#`. Closing hashes need a space before them (`# C#` keeps its title). `#Title` without a space is still a header. `~~~` lines are not treated as fences on purpose, because they are common scene breaks. | Scene breaks became items titled "#" and moved the following scenes out of their chapter. |
| BC13 | editor-perf | A line that is only a list marker that cannot be incremented (`-- `, `ii. `) ends the list on Return, like `- ` does, and is cleared. | Side effect of `51040cf`: markers that cannot be incremented no longer match the continuation regex, so such a line counts as an empty item. See C5 if `-- ` should be kept. |
| BC14 | crashes | SIGTERM/SIGINT now close Manuskript normally: the handler runs within 0.5 s, then the usual close with save on quit. If save on quit is off and there are unsaved changes, the "Save project?" question still waits for an answer (B8). | Before, they were ignored until SIGKILL, so changes were lost on logout. |
| BC15 | ui-settings | New command-line option `--style STYLE`, which also accepts Qt's `-style`. It is not saved. `QT_STYLE_OVERRIDE` is still ignored on purpose. | A crashing saved style made Manuskript unusable (#467). |
| BC16 | review-findings | Outline tab with several items selected: the "Various" full-summary field writes only after a real edit. Differing summaries can no longer be emptied in one step; that now takes two (type something and let it be written, then delete it). | Focus-out or a rehighlight erased all selected summaries (A1). |
| BC17 | review-findings | Adding or removing characters, character info, plots, plot steps, world items, labels or statuses **marks the project modified** and starts the "autosave if no changes" timer. File > Close saves the change, or asks first when "save on quit" is off. | These changes were dropped on close (A3). |
| BC18 | review-findings | A failed "Save as…" keeps the old path, window title and recent files. A read-only target gets a warning before anything is written. A failed save in single-file (`.msk`) mode shows the "Files not saved" dialog; before, only the status bar said so. "Save as…" into the project's own folder (its own file, or a file whose folder links to it) keeps what the save code knows about that folder, so it no longer removes the folder's files first. | The app switched to a path where nothing had been saved (A4). |
| BC19 | review-findings | The custom-word file is no longer rewritten on load. It is written atomically and sorted. A damaged or unreadable file is moved to `<name>.json.gz.damaged` and the words start empty. A transient read error moves it aside too. | Custom words were lost (A5). |
| BC20 | review-findings | Once the text is longer than the window, the main editor's text area keeps its full width (10 px wider than before). Where the text area reaches the editor's right edge ("Max width" 0, or an editor narrower than "Max width"), the transparent scroll bar covers its last 9 px, as it already did for short texts. | Some styles crashed on the scroll bar (B2). |
| BC21 | spellcheck | With pyspellchecker or symspellpy and a French, Italian or Catalan dictionary, an elision from a per-language list (`l`, `qu`, `dell`…), followed by `'` or `’` and a known word that starts with a vowel, `h`, `y` or a digit, is accepted. Where the word needs an accent after the elision, the accent is required (`jusqu’à`, `d’où`, `dov’è`; `jusqu’a` is underlined and `jusqu’à` suggested). With these word lists, some wrong forms are accepted (h aspiré `l’héros`, Italian plurals `l’amici`), and some correct ones are underlined (colloquial `j’suis`; Italian `un’estate`, which `develop` accepted with `’`). enchant checks the whole elided form, as since `fa37b1e` (`develop` split at `’` for every backend). | Since `fa37b1e`, most elisions were underlined with these backends (D5). The lists need a review by native speakers (Q22). |

The new user-visible strings use `tr()`/`safeTranslate()` (23 strings), but **no `.ts` files have been updated** (G3).

### 1.5 Suggested merge plan

1. **One PR per branch**, in this order: `save-load-data-loss` → `crashes` → `outline-dnd` → `editor-performance` → `import-export` → `spellcheck` → `ui-settings-search` → `review-findings`. That is the order of `fix/all-quickfixes` (where `fix/spellcheck` is merged a second time for D5), so the conflict resolutions shown there can be reused. `review-findings` needs all the others first.
2. Each commit fixes one problem, with three exceptions: `638be4a` also carries a small focus-mode fix that the bug it fixes had been hiding; `9b9e2fa` (A4) also fixes two related "Save as…" cases; `2f348bd` (A3) also disconnects the old `dataChanged` connections on close. Each message explains the bug, the root cause and the fix, and names the upstream issues where there are any. Reviewers can review commit by commit, or cherry-pick single commits.
3. Before opening the PRs, run the repository's own CI on the branches (see G2). Before releasing, test by hand with a copy of a real project, on Windows and macOS in particular: case-insensitive file systems, path length, `os.replace` over open files on Windows. These were only covered by tests on Linux, and by one run of the suite under Wine (G5), which does not show how a real Windows, its antivirus or a sync client behave.

## 2. Open problems and effort

Items marked ✅ were fixed after the first version of this document: D5 on `fix/spellcheck`, the others on `fix/review-findings`. They stay in the lists so that their IDs remain stable. Everything else is **still present on `fix/all-quickfixes`**. Each item was checked against the code, most of them with a small isolated script. File and line references are to `fix/all-quickfixes` at `eacaf8f`, before these fixes. The items and additions made in version 3 (A9, A10, B10, F5, G5, G6, and parts of B2, B3, B7 and G1) refer to the current tip `1d7320f`, and to `develop` where it says so. For A10, F5, G5 and G6, a fix exists on the fork owner's personal branch `personal/main`, which was not on GitHub at the time of writing. They are still open on the fix branches.

**Effort** assumes one developer who knows Python/Qt but is new to this code base, and includes tests: **S** ≤ ½ day, **M** 1–3 days, **L** 1–2 weeks, **XL** > 2 weeks or architectural. **Decision** (✋) means maintainers should agree on the behaviour before someone writes the fix (see section 4).

### 2.1 Overview

| ID | Problem | Impact | Effort | Prio | ✋ |
|---|---|---|:-:|:-:|:-:|
| **A — Newly found during this review and after it (all also present on `develop`)** ||||||
| A1 | ✅ `2a53412` Outline tab, multi-selection: the "Various" summary field writes `""` into every selected item | Silent data loss | — | — | ✋ |
| A2 | ✅ `1765c09` Split at cursor (Ctrl+K) right after typing loses the last typed text and cuts at the wrong place | Data loss | — | — | |
| A3 | ✅ `2f348bd` Adding or removing characters, plots, world items, labels or statuses does not mark the project as modified. An added entry that is then edited does, so what gets lost is removals and unedited additions. | File > Close drops them, no prompt | — | — | ✋ |
| A4 | ✅ `9b9e2fa` A failed "Save as…" still switches the app to the new, unsaved path | Work "saved" nowhere | — | — | |
| A5 | ✅ `0c13f97` The custom dictionary file is rewritten non-atomically each time it is loaded (if it holds any word), and emptied if it is damaged | Lost custom words | — | — | |
| A6 | Outline tab: if the first selection is already a multi-selection (e.g. Ctrl+A), the first key typed into the full summary raises `AttributeError` and the app exits | Crash, unsaved work lost | S | high | |
| A7 | Browsing plot steps, or switching tabs in a new project made from a template, marks the project modified without an edit | Needless "Save?" prompt and autosave | S | low | |
| A8 | Segfault when a project is closed and another one is opened in the same event-loop pass, after an editor tab showed a folder in "outline" view | Crash; not known whether the app reaches it | S–M | medium | |
| A9 | Two sibling titles give the same file name (`Grüße`/`Größe`, titles that differ only after the 64-character cut, case variants on Windows/macOS). After a reorder, one write of the save fails, then the user discards or the app ends before a later save succeeds: one scene's text is gone. New in version 3. | Silent data loss | S | high | ✋ |
| A10 | A single-file project (`.msk` zip) with one entry that is not UTF-8 does not open (on `develop`: the app exits), and hidden entries are loaded. Fixed on `personal/main` by `2d7a5de`. | "Can't open my project" | S | medium | |
| **B — Robustness and data safety (known)** ||||||
| B1 | Global excepthook calls `sys.exit(1)` on any uncaught exception | Every small bug = crash + lost work | M | **highest** | ✋ |
| B2 | ✅ `07dce72` Main editor reparents its scroll bar without `ScrollBarAlwaysOff` (#450 #601 #1435). Breeze: no crash in one manual test by the fork owner. Adwaita-qt still needs a manual check. | Segfault with Breeze5/Adwaita | S (manual check) | high | |
| B3 | One damaged `plots.xml`/`world.opml`/`revisions.xml`, a `folder.txt` without ID or a non-numeric ID keeps the whole project from opening (a non-numeric character ID can also close the app) | "Can't open my project" | M | high | ✋ |
| B4 | Multi-line metadata is not round-trip safe: indentation is lost, and trimming trailing whitespace moves notes into the scene text | Silent corruption | M | medium | |
| B5 | Deleting a label/status relabels every item that uses a later one (#1010, only the crash is fixed) | Wrong data, persistent | S | medium | ✋ |
| B6 | Character, plot and world IDs reuse the lowest free number | References attach to new entities | M | medium | ✋ |
| B7 | Files Manuskript did not load (notes, hand-made scenes) stay behind when their folder is renamed. A scene added while the project is open (`git pull`) stays behind when its chapter is deleted, and no longer loads. | Orphaned, invisible files | M | medium | ✋ |
| B8 | A signal handler can re-enter a running save, and the "Save?" dialog can block a logout | Rare, nasty | S | low | ✋ |
| B9 | Atomic writes: no `fsync` in folder mode, stale `.tmp` files are not cleaned up | Edge cases | S | low | ✋ |
| B10 | Two characters with the same ID (after a git merge of two copies that each added one, or from a character file without `ID:`) are kept as they are. Every lookup by ID finds the first one, so deleting the second deletes the first. New in version 3. | Wrong character deleted (data loss) | S | medium | ✋ |
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
| D5 | ✅ `92bee56` Regression on `fix/spellcheck`: French/Italian elisions (`l’homme`, `j’ai`) are underlined unless the dictionary knows the elided form. `develop` accepted them by splitting at `’`. | False positives for French users | — | — | |
| D6 | A word in typographic single quotes (`‘hello’`) gets a spelling menu without being underlined | Confusing menu | S | low | |
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
| F5 | Help > Locate log file: the fallback of `showInFolder()` opens `QUrl(path)`, which is not a file URL (on Windows the drive letter becomes the scheme). Fixed on `personal/main` inside `de38879`. | The log folder may not open | S | low | |
| **G — Tests, CI, i18n** ||||||
| G1 | Test fixtures leak about 220 temp entries (about 51 MB) per run and write to `~/.config/manuskript_tests` and `~/.local/share/manuskript_tests` | Developers, CI containers | S | medium | |
| G2 | The fix branches have not run on this repository's CI yet (Python 3.9, xvfb, extra spellcheck libraries) | Review risk | S | medium | |
| G3 | 23 new `tr()`/`safeTranslate()` strings are not in any `.ts`; `'Open {}'` can never be translated | Non-English users | S | low | ✋ |
| G4 | Rare segfault at interpreter exit (focusOut → submit during teardown, also on develop) | Flaky CI | S | low | |
| G5 | On Windows (run under Wine), 39 tests stop with a setup error in the `MWSampleProject` fixture (a `NamedTemporaryFile` that is still open), and 2 tests assert POSIX file modes. No failure points to product code. Fixed on `personal/main` by `a709177` and `71a1ad5`. | No Windows CI possible | S | medium | |
| G6 | CI: job names use `matrix.python_version` (the key is `python-version`), and `requirements.txt` pins `PyQt5-Qt5==5.15.17`, which has no Windows wheel. Fixed for the fork's own matrix on `personal/main` by `71a1ad5`. | Blank job names; `pip install -r requirements.txt` cannot work on Windows | S | medium | |

**A second bugfix round of about one week** would cover A6–A8, B5, C4, D6, E1–E3, E6, E7 and G1–G3. All of them are S items, except A8 (S–M). Five of them (B5, C4, E1, E2, G3) need a decision first, and that time is not included. A9, A10, B10, F5, G5 and G6 (all S) would add two to three days. For all of them except B10, a fix exists, on `personal/main` or as a prototype (see the details). A9 needs a decision on a one-time rename of the affected files, B10 on which character keeps the ID. The larger items that remain after that are:

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
- **✅ Fixed** in `2a53412` with option (b). In multi-selection mode the editor writes only if the user changed the document and its text differs from what it showed. Typing, pasting, undo/redo, spelling corrections and completions still reach all selected items. A write to several items still clears the editor's undo history. Q6 asks whether option (a) is preferred.

#### A2 — Split at cursor loses text
- **Where:** `editorWidget.splitCursor` (`editorWidget.py:471-491`) splits the **model** text. The editor submits only on Space, on focus-out, or 500 ms after the last change, and Ctrl+K keeps the focus. So text typed since the last Space (within 500 ms) exists only in the editor. It is lost, the cut lands that many characters too far, and `setPlainText` clears the undo stack. `textEditView.callMainTreeView` was checked and does not lose text (only Duplicate copies the model text without the last unsubmitted characters).
- **Status:** Present on `develop` too (same code).
- **Fix:** Call `self.txtRedacText.submitPendingChanges()` before reading the cursor. That method comes with `53ed275` (`fix/editor-performance`). Without that branch, call `submit()`. Effort: S (1–2 h).
- **✅ Fixed** in `1765c09` this way. The UTF-16 offset problem (C1) and the cleared undo stack remain.

#### A3 — Structural changes are not "unsaved"
- **Where:** `projectDirty` is only set from `dataChanged` (`mainWindow.py:994-1000`, `:1242-1249`). `removeCharacter`, `addPlot`, `worldModel.addItem`, removing a label… emit only `rowsInserted`/`rowsRemoved`. File > Close drops these changes without saving or asking, **whatever the "save on quit" setting**, because `closeProject` only saves when `projectDirty` is set (`mainWindow.py:1095`). Quitting drops them when "save on quit" is off. The no-change autosave does not fire either.
- **Fix:** Also connect `rowsInserted/rowsRemoved/rowsMoved/modelReset` of the 7 models (and disconnect them in `breakConnections`). Then the root's invalid-index `dataChanged` (see 3.3.1) is no longer needed for the modified flag. Check whether other listeners rely on it before dropping it. Effort: M, because every path that changes rows without a user edit has to be checked. **Decision:** should every structural change mark the project modified?
- **✅ Fixed** in `2f348bd`. `rowsInserted`, `rowsRemoved`, `rowsMoved`, `modelReset` and `layoutChanged` of the 7 models mark the project modified. On close, these and the old `dataChanged` connections are disconnected; before, the `dataChanged` ones were never disconnected, so a change to a closed project's models marked the next project modified. A test opens the sample project, browses every tab, character, plot, world item and outline item (not plot steps, see A7), saves and reopens it, and checks that no change signal fired. The root's invalid-index `dataChanged` is kept (3.4, item 8). A7 is a separate, older false positive.

#### A4 — Failed "Save as" switches path
- **Where:** `welcome.saveAsFile` (`welcome.py:200-213`) updates the recent files, `currentProject`, `lastProject` and the title without checking the result of `saveDatas`. `mainWindow.py:1272-1274` sets the path before saving.
- **Fix:** Save first. On failure, restore the old path and cache and show the reason. Effort: S.
- **✅ Fixed** in `9b9e2fa`. The path changes only after a successful save. On failure, the old path comes back, together with the save cache and the paths the items were last saved to. Without those, the next normal save could bring back removed items or leave a renamed folder behind as a duplicate. The user is told why once. The same commit fixes two related cases. First, a target folder that holds an older, read-only Manuskript project made the cleanup raise an uncaught `PermissionError`, which closed the app. Second, "Save as…" into the project's own folder (its own file, or a file whose folder links to it) deleted the files that could not be read when loading. A link to the project file under another name, next to another folder, is a real "Save as…" and writes a copy. Not changed: files written at the target before the failure stay there. After a "Save as…" onto a symbolic link of the project file, the recent-files list replaces the original's entry, because entries are compared by their real path (`welcome.recentFileKey`).

#### A5 — Custom dictionary rewritten and possibly wiped
- **Where:** `BasicDictionary.__init__` (`spellchecker.py:240-249`) calls `self._dict.create_dictionary_entry` before the subclass has created `_dict`. The resulting `AttributeError` is swallowed by a bare `except`, which calls `_saveCustomDict()` (non-atomic). A damaged file is replaced with `[]`. This affects pyspellchecker, symspellpy and LanguageTool.
- **Fix:**
  - Remove the loop. The subclasses already add the words (`spellchecker.py:468-469`, `:546-547`).
  - Create the file only on `FileNotFoundError`.
  - On a decode error, log it, keep a backup copy (e.g. `<lang>.json.gz.damaged`) and continue with an empty list.
  - Write atomically with `writeFile`. Import it inside `_saveCustomDict` or move it to `manuskript.functions`, to avoid a circular import.
- **Effort:** S.
- **✅ Fixed** in `0c13f97` as proposed, except that the damaged file is moved aside, not copied (BC19). `writeFile` is imported inside `_saveCustomDict`. Moving it to `manuskript.functions` would be cleaner, but several tests inject write errors by patching `version_1.open` and would have to be rewritten.

#### A6 — Completer crash on a first multi-selection
- **Where:** `MDEditCompleter.completer` is set only in `setCurrentModelIndex()` (`MDEditCompleter.py:34-41`). If the first selection in the Outline tab is a multi-selection (e.g. Ctrl+A before any single item was clicked), `keyPressEvent` calls `self.completer.isVisible()` and `self.completer.setVisible(False)` on `None` (`:85-100`). The `AttributeError` reaches the excepthook, and the app exits. The same code is on `develop`. Found during the A1 fix: A1 keeps this multi-edit path, and its tests click a single item first.
- **Fix:** Guard both uses in `keyPressEvent`, or create the completer in `setCurrentModelIndexes()`. Add a test that selects all items and types into the full summary. Effort: S.

#### A7 — Browsing marks a project modified
- **Where:** Some editors write `""` over a value that is not set (`None`), for example `txtSubPlotSummary` when plot steps are browsed, and fields of a new project made from a welcome-screen template. That emits `dataChanged`, so the project counts as modified without an edit, and closing it asks to save or autosaves. Found while checking A3, which excludes this case from its "opening does not modify" test. The plot-step case is present on `develop` too (checked); the template case was not checked there.
- **Fix:** Treat `None` and `""` as equal before submitting. Effort: S.

#### A8 — Segfault on a project switch after an "outline" folder view
- **Where:** Closing a project closes the editor tabs, but the closed `editorWidget`s are only `deleteLater`'d. If another project is created or loaded before control returns to the event loop, `loadProject` calls `tabSplitter.updateStyleSheet()` (`mainWindow.py:974`, `tabSplitter.py:101`), which reaches a stale tree view and segfaults in `QTreeViewPrivate::itemHeight`. Reproduced with a script on `eacaf8f` and on `develop`: show a folder in an editor's "outline" folder view, then close the project and create one without returning to the event loop. If the closed project's models are garbage-collected in between, it crashes on the first switch, otherwise after a few. In the app, File > Open and the recent-files menu are disabled while a project is open, so a switch normally goes through File > Close in a separate slot first. Whether any path reaches the crash was not checked. The B2 tests avoid it with `closeAllTabs()` and `sendPostedEvents(DeferredDelete)`.
- **Fix:** Delete or detach the closed editors' views synchronously in `closeProject`, or skip editors that are pending deletion in `updateStyleSheet`. Effort: S–M.

#### A9 — Two siblings with the same file name, a failed write, and a scene is gone (data loss)
- **Where:** `outlineItemPath` (`version_1.py:829-837`) adds the item's ID to the file name only when two sibling titles are *identical*. Siblings whose titles only give the same stem, `slugify(title)[:64]`, get the same name apart from the row prefix:
  - titles that differ only in non-ASCII letters: `Grüße` and `Größe` both give `Gr--e`, and CJK titles of the same length all give dashes;
  - titles that differ only after the 64-character cut of `ae70ff7` (BC5), and identical titles that long, where the cut also removes the ID;
  - on case-insensitive file systems (Windows, macOS), titles that differ only in case (`Intro`, `intro`).

  After a reorder, one item's new path is then the other item's old path. The save writes in tree order (`:505-534`), so the first write replaces the other item's only file. If the other item's own write then fails, the rule that keeps the old file of a moved item whose new file was not written (`:546-568`) keeps a path that now holds the first item's text. This is the part of #1320 that `16666ba` does not cover.
- **Scenario:** A chapter holds `Grüße` (`0-Gr--e.md`) and `Größe` (`1-Gr--e.md`), both saved. Drag `Größe` above `Grüße`. The next save writes `Größe` into `0-Gr--e.md`. The write of `Grüße` to `1-Gr--e.md` fails: disk full, a read-only file, or on Windows a file held by an indexer, an antivirus or a sync client. The "Files not saved" dialog appears. The user closes the project and picks Discard in "Project not saved" (BC8), whose text says only that "the changes since the last successful save will be lost". On disk, both files now hold `Größe`. The text of `Grüße`, saved long before, is gone.
  - A chain loses data too: move `Später` to the top of `Grüße`, `Größe`, `Später`, and let the write of `2-Gr--e.md` fail. `Größe` is gone.
  - A crash or a kill between the two writes, or after the failed save, should end the same way (code reading, not run).
  - A later save that succeeds writes both texts again (checked).
- **Evidence:** Found by one of the three designs of the panel that wrote the save design in 3.4 item 15 (the one called "planexec" in `docs/save-design/README.md`). Two of the panel's judges (safety and effort) then reproduced it on a `1d7320f` tree. Reproduced again for this document on a fresh copy of `1d7320f` with three tests: the swap, the chain, and two titles of about 70 characters that differ only in their last word. Each one ends with one text twice and the other one gone. Without the failed write, the swap is saved correctly. The case variant was not run, because the Linux file systems used are case-sensitive.
- **Status on `develop`:** Present, and worse. Reproduced with the swap on a fresh copy of `develop`, with a `PermissionError` on the second write: after reopening, `Größe` is there twice. On `develop`, even a later save that succeeds does not bring `Grüße` back. Its in-place moves (`version_1.py:351-372` on `develop`) overwrite the file first, and the write loop records the failed file as written in the cache (`:398`), so it is not written again. `develop` has no 64-character cap, so the long-title variant is new on the fix branches.
- **Fix:** Step 3 of the plan in the save design (see 3.4 item 15): when the stems of siblings collide, ignoring case, each of them gets its ID: `slugify(title)[:64 - len(ID) - 1] + "-" + ID`. For identical short titles, that is the name used today. The affected items are renamed once, on their next save, through the normal rewrite of renamed items (`16666ba`). This works with the current save code.
  - Checked with a six-line prototype of this rule in `outlineItemPath` on a copy of `1d7320f`: the three tests keep both texts, and the rest of the suite gives the same result as before (622 passed, 8 skipped). The prototype was not reviewed. Tests for case variants and for the one-time rename are still missing.
  - What stays open with the current save code: an item moved into another folder can still land on the old path of an item that left that folder in the same save (same row, same stem). The design orders such writes (W2), as part of the larger rewrite.
- **Effort:** S. **Decision:** is a one-time rename of the affected files acceptable (Q21)? The alternative, an ID in every outline file name, rules out every collision, but renames every file once.

#### A10 — A single-file project with an entry that is not UTF-8, or a hidden entry
- **Where:** The zip branch of `loadProject` (`version_1.py:882-888`; `:658-664` on `develop`) decodes every entry except `.xml` and `.opml` as UTF-8. `loadFilesFromZip` (`version_0.py:182-191`) keeps hidden entries. The folder branch skips hidden files and reports files that are not UTF-8 (`6787396`). The zip branch does neither:
  - One entry that is not UTF-8 raises `UnicodeDecodeError`: a scene saved as Latin-1, an image, or the `__MACOSX/._*` entries that macOS's archive tool adds. On `fix/all-quickfixes` the project then does not open. The status bar says "Loading project … failed." and does not name the file. On `develop` the exception is not caught, so the excepthook (B1) closes the app (code reading).
  - Hidden entries are loaded: `characters/.DS_Store` becomes a character.

  Manuskript itself writes only UTF-8 text into a `.msk` file. So this needs a project file that another tool made or changed, for example a project folder zipped by hand.
- **Status:** Checked: the two tests of the fix below fail on a copy of `1d7320f`, with `UnicodeDecodeError` in the log.
- **Fix:** On `personal/main`, `2d7a5de` "fix(load): skip hidden and undecodable entries of a single-file project" applies the folder branch's rules to the zip branch:
  - entries with a hidden path component are skipped;
  - an entry that is not UTF-8 is not loaded and is listed in the "Files not loaded" dialog, which says that it is not kept when the project is saved (a single-file save writes only what was loaded);
  - if it is one of the root project files, the project does not open.

  `version_1.py` is the same on `1d7320f` and on the parent of `2d7a5de`, so its change applies unchanged. With its two tests, the suite gives 624 passed, 8 skipped there. It adds one string (G3). Effort: S.

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
- **✅ Fixed** in `07dce72`. A test checks that no scroll area in the main window shows a scroll bar outside itself, and that the moved bar still follows the text. The installed Breeze (6.8.1, Qt 5 plugin) did not take the crashing path in an offscreen session, even without the fix, and Adwaita-qt was not available, so the end-to-end crash is still not reproduced. **A manual check on Plasma 5 and on GNOME with Adwaita-qt is needed before the issues are closed.** Side effect: BC20.
- **Manual test (version 3):** The fork owner used `fix/all-quickfixes` by hand with the Breeze style and saw no crash ("B2 seems to work"). The Breeze version and the desktop were not recorded. `develop` was not tried in the same setup, so the test does not show that this setup crashed before the fix. Still open: Adwaita-qt on GNOME, and a before/after comparison with Breeze on Plasma 5.

#### B3 — One damaged file blocks the whole project
- **Where:** `ET.fromstring` without a recovering parser at `version_1.py:1041` (plots), `:1077` (world) and `:1164` (revisions). `outlineFromMMD` raises `KeyError` for a `folder.txt` without `ID:` (`:1231`/`:1263`), and `abstractModel.py:72` raises `ValueError` for `ID: 12a`. The only message is 5 seconds of status-bar text.
- **Character IDs (version 3):** a character file with a non-numeric `ID:` is worse. Checked on a copy of `1d7320f` with `ID: ../../x`:
  - If another character is loaded after it, `int(c.ID())` in `assignUniqueID` (`characterModel.py:342-352`) raises, and the project does not open ("Loading project … failed.").
  - If it is the last one, the project loads, but `int()` in `plotModel.updatePlotPersoButton` (`plotModel.py:260`) raises in `makeConnections`. That is outside the `try` of `25bfa0b`, so in the app the excepthook (B1) closes it. With "Load last project on startup", that should happen on every start (code reading).
  - The same `int()` calls are on `develop`, where the first case is not caught either (code reading).
  - The ID also goes unchecked into the character's file name (`version_1.py:315-318`, `:239` on `develop`). The save-design panel noted that `../../x` would build a path outside the project. In the checks here, the project never got far enough to be saved.
- **Fix:**
  - A `parseXMLSection` helper that, on a parse error, retries with `XMLParser(recover=True, huge_tree=True)`, keeps a `.damaged-<time>` copy and lists the file in the existing "Files not loaded" dialog.
  - A broken `revisions.xml` only drops revisions.
  - A `folder.txt` without ID gets a new ID, like other items. A character with a non-numeric ID gets a new one too (together with B10).
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
- **Added while open (version 3):** a scene added to the project folder while the project is open, for example by `git pull`, is not known to the save either. If the user then deletes its chapter, the save removes the chapter's `folder.txt` and leaves the scene. On the next load the scene no longer shows up: its text is still on disk, but nothing shows it. Found by the safety judge of the save-design panel, checked here on a copy of `1d7320f` with a scene that has an `ID:`. Not checked on `develop`.
- **Fix:**
  - Short term: move them like unreadable files and list them in "Files not loaded" (M). Keep a folder's `folder.txt` while the folder still holds a file the loader would load, as the save design does (3.4 item 15).
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

#### B10 — Two characters with the same ID
- **Where:** Nothing makes character IDs unique on load. Two ways to get duplicates:
  - Two copies of a project (two machines, or two git branches) each add a character. Both get the lowest free number (B6), for example `6-Anna.txt` and `6-Bert.txt`, and a git merge keeps both files.
  - A character file without `ID:` gets the lowest number that is free *at that point of the load*. If a file with that ID is loaded after it, both keep it.

  Every lookup by ID (`characterModel.getCharacterByID`, `characterModel.py:159-166`) returns the first match. The Characters tab passes the selected character's ID (`characterTreeView.py:141-162`, `:214-220`). So deleting the second character deletes the first, and the next save removes the first one's file. Changing the colour or the POV check box of the second changes the first in the same way (`characterTreeView.py:165-185`, code reading). POVs, plot members and `{C:id}` references cannot tell the two apart.
- **Evidence:** Checked on a copy of `1d7320f` with `1-Paul.txt`, a copy of it named `1-Saul.txt`, and a file `0-Abe.txt` without `ID:`. Both pairs load with the same ID (`0` twice, `1` twice). `removeCharacter` with Saul's ID removes Paul, and after the next save `1-Paul.txt` is gone and `1-Saul.txt` is left. `characterModel.py` is the same on `develop` (not run there). The safety judge of the save-design panel named duplicate IDs as a risk for the save; the delete case was found here.
- **Fix:** On load, give every duplicate after the first a new ID (`max+1`, see B6) and list the renumbered characters once. References stay with the first one, because they cannot be told apart. Add a test for both ways. The save design renumbers duplicates at load (its rule L6). Effort: S. **Decision:** which character keeps the ID, and is a notice enough?

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
- **D5 (regression on `fix/spellcheck`), ✅ fixed in `92bee56`:**
  - Since `fa37b1e`, words are no longer split at apostrophes. Elisions (`l’homme`, `j’ai`, `dell’anno`) were therefore accepted only if the dictionary knew the whole form. `develop` split them into `l` (single letters are not checked) and `homme`. Confirmed with the real pyspellchecker and symspellpy word lists: `L’homme`, `qu’il`, `c’est`, `j’ai` were underlined.
  - The fix applies to the word-list backends only. They accept an elision from a per-language list (`ELISIONS` in `spellchecker.py`: French, Italian, Catalan), followed by a known word that starts with a vowel, `h`, `y` or a digit. After some elisions the word needs an accent that the list cannot enforce, because the bare form is a word too: French `jusqu’à`, `d’où`, Italian `c’è`, `dov’è`, `cos’è` (table `ELISION_ACCENTS`). Suggestions keep the elision and the apostrophe that was typed (`l’hommme` → `l’homme`, `jusqu’a` → `jusqu’à`).
  - enchant is unchanged: it checks the whole elided form, as before. Splitting would hide wrong forms that dictionaries reject: the Italian Hunspell dictionary rejects `un’amico` and `l’libro`, and an old French one (v2.1) rejects `l’chat` and `l’héros`. Current French dictionaries (7.x) accept those two.
  - Remaining, with the word lists: some wrong forms are accepted: h aspiré (`l’héros`), `y` words (`l’yaourt`), `l’onze`, `s’elle`, `c’a`, Italian plurals (`l’amici`), and the forms that can be right without the accent (`qu’a`, `d’a`, `tutt’e`). Some correct forms are underlined: colloquial `j’suis`, and Italian `un’` and `qualcun’` before feminine words the list does not know (`un’estate`, `qualcun’altra`), which `develop` accepted with `’`. With symspellpy, `dell’800` is underlined, because it does not know numbers. With enchant, `l’hommme` gets no suggestions with `’` (only with `'`), as before. The lists need a review by native speakers (Q22).

- **D6:** `BasicDictionary.findSuggestions` does not strip quotes and apostrophes around the selected word the way `checkText` does, and Qt's `WordUnderCursor` includes `‘` and `’` but stops at the ASCII `'`. So `‘hello’` gets a spelling menu with "Add to dictionary" (in English also suggestions) although it is not underlined, and right-clicking the `l` of `l'amico` with the Italian word list opens a menu for `l`. Same on `develop`. Fix: strip like `checkText` before checking. S.

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
- **F5:** `showInFolder()` (`functions/__init__.py:577-610`; the same code at `:561-594` on `develop`) ends with `QDesktopServices.openUrl(QUrl(path …))`. `QUrl(path)` is not a file URL. On Windows the drive letter becomes the scheme: with PyQt5 5.15.10, `QUrl('C:\\Users\\…')` has the scheme `c` and `isLocalFile()` is False. On any platform, a `#` in the path starts a fragment. The only caller is Help > Locate log file… (`mainWindow.py:1721`). On Linux every call goes through this fallback, on Windows only when Explorer cannot be started. Whether the Linux platform still opens a path without a scheme (for example through `xdg-open`) was not checked, and the effect on Windows was not checked either. Fix: `QUrl.fromLocalFile(…)`. On `personal/main` this is part of `de38879` "chore(macos): remove macOS support", with tests that replace `QProcess` and `QDesktopServices`, so nothing is started. That commit also removes the macOS branch, so for upstream port only the one line and the fallback tests. S.

#### G — Tests, CI, i18n (short)
- **G1:** `conftest.py:34-41` and `:64-71` use `NamedTemporaryFile` + `copytree` and never clean up. One run leaves about 120 folders and 100 `.msk` files (about 51 MB). The package also writes `~/.config/manuskript_tests/` and `~/.local/share/manuskript_tests/`. Use `tmp_path` plus a session-wide isolated HOME/XDG. S. The fixture part is done by the G5 fix: with it, a run on a copy of `1d7320f` left only pytest's own `pytest-of-<user>` folder in the temporary folder. The writes to `~/.config/manuskript_tests/` and `~/.local/share/manuskript_tests/` remain. On Windows, HOME and the XDG variables isolate nothing: Qt keeps these settings in the registry (`QSettings` with organization and application name, native format) and the data under `%LOCALAPPDATA%` (`AppLocalDataLocation`, `functions/__init__.py:292-293`). The Wine run (G5) wrote `HKCU\Software\manuskript_tests\manuskript_tests` and `AppData\Local\manuskript_tests\manuskript_tests` into its prefix. On a developer's Windows machine the suite writes there too; on a CI runner it does not matter. The `test_main` tests that start the app in a child process skip outside Linux, partly for this reason (`test_main.py:124-126`).
- **G2:** All 630 tests passed locally with Python 3.13 (system PyQt5 5.15.10, offscreen), pyspellchecker 0.9.1, symspellpy 6.10.1 and French and Italian Hunspell dictionaries. Without these, 622 pass and 8 are skipped, with Python 3.13 and with Python 3.11 using the pinned `requirements.txt` wheels. They have **not yet run in this repository's CI**. CI runs pytest on Python 3.9 in three jobs:
  - `pytest.yml`: Ubuntu 24.04, xvfb, PyQt5 from `requirements.txt`.
  - `build_linux.yml`: Ubuntu 22.04, latest PyQt5, offscreen, with `language_tool_python`, `symspellpy` and `pyspellchecker` installed. `language_tool_python` was not installed locally.
  - `build_osx.yml`: macOS.

  The workflows only trigger on `develop` or by manual dispatch. So: enable Actions on the fork, then start them for each branch from the Actions tab, or open PRs inside the fork against its `develop`. S, possibly more if xvfb-only or Python-3.9-only failures show up. Version 3: still not run in CI. The suite has run under Wine with a Windows CPython (G5), and G6 lists two workflow problems found on the way.
- **G3:** Run `make translation` (23 new strings). Change `outlineBasics.py:123` to `safeTranslate(…, 'Open {}').format(title)`, because today the string is formatted before it is translated, so it never is. Wrap the literal in `welcome.py:317` too. Check that PyInstaller and Flatpak ship the `qtbase_*.qm` that `9c279f8` now loads. S.
- **G4:** Rare segfault at interpreter exit (`focusOutEvent → submit()` while widgets are destroyed). Pre-existing, not reliably reproducible. Guard `submit()` during teardown and use `QPersistentModelIndex` in `_indexes`. S.
- **G5:** The suite under Windows, run under Wine (not a real Windows).
  - **Setup:** Wine on Linux, the embeddable Windows CPython 3.12.10, PyQt5 5.15.11 / Qt 5.15.2, offscreen, no pandoc, an isolated Wine prefix. The tree was that of `personal/main`'s first commit `9288eb9`, which adds only `docs/` to `1d7320f`, so the code is that of `fix/all-quickfixes`.
  - **Result:** 4 failed, 563 passed, 24 skipped, 39 errors (630 tests).
    - 39 setup errors, all in `MWSampleProject` (`conftest.py:76-78`): it copies the sample project onto the name of a `NamedTemporaryFile` that is still open. Windows opens such a file with delete-on-close and refuses a second open: `PermissionError: [Errno 13]` in `shutil.copyfile`. `MWEmptyProject` (`:46-50`) has the same pattern, but did not fail, because `welcome.createFile()` writes nothing there.
    - 2 failures in `test_save_keeps_symlinks_and_modes` and `test_zip_save_keeps_symlink_and_mode` (`test_save_load_regressions.py:336`, `:473`): they assert mode `0o600`. Windows files only have a read-only flag, so `os.stat()` reports `0o666`. The symlink and write parts of both tests passed.
    - 2 failures in `test_pythonVersion`: an artefact of the embeddable Python, whose `python312._pth` leaves the current folder off `sys.path`, so the child Python cannot import `manuskript`. Both passed once the tree was added to that file. A normal CPython, as in CI, should not show this.
    - With two changes made only in the throwaway copy (the fixture with `delete=False` and `close()`, and the `._pth` line): 2 failed (the mode tests), 604 passed, 24 skipped.
    - 24 skips against 8 on Linux: all 5 `test_saveAsFailure` tests (a folder cannot be made read-only), 7 unreadable-file tests, 4 `test_main` tests (`/proc`, POSIX signals), 2 enchant tests without French and Italian dictionaries, and 6 pandoc or POSIX-permission tests. So the failed "Save as" path is not tested on Windows.
  - **What it means for upstream:** No failure pointed to product code. Nothing failed in `os.replace`, locking, path case, separators or line endings. Before a Windows CI job can pass, the test code needs two small fixes. Wine is not Windows: antivirus, indexers, sync clients and real NTFS behaviour were not part of the run.
  - **Fix:** On `personal/main`, `a709177` "test(fixtures): put the test projects in temporary folders": both fixtures make a folder with `tmp_path_factory.mktemp()`, close their project afterwards and remove the folder. `conftest.py` is the same on `1d7320f`, so the commit applies unchanged. Applied there together with the A10 fix, the Linux suite gave 624 passed, 8 skipped (622 plus A10's two tests). `71a1ad5` (G6) skips the two mode tests on Windows. With both, a Wine run on `personal/main` at `fd57142` (its last code commit) gave 5 failed, 647 passed, 30 skipped. All 5 failures are tests that start a child Python with `-c` and fail with "No module named 'manuskript'", because of the `._pth` artefact: the 3 `test_pythonVersion` tests and 2 `test_htmlPreviewFallback` tests, which exist only on `personal/main`. S.
- **G6:** Two problems in the workflows, both also on `develop`:
  - The job names use `matrix.python_version` (`pytest.yml:19`, `build_windows.yml:23`), but the matrix key is `python-version`, so the version shows blank (also listed in 3.3.3).
  - `requirements.txt` pins `PyQt5-Qt5==5.15.17`. On PyPI that release has wheels for macOS and manylinux only, and no source archive. The last release with Windows wheels is 5.15.2 (checked on PyPI on 2026-11-02). So `pip install -r requirements.txt` cannot work on Windows (not run). The Windows build job does not use `requirements.txt` (it installs `pyqt5==5.15.7`), so this hits Windows developers and any future Windows test job (3.4 item 14).
  - **Fix:** On `personal/main`, `71a1ad5` "ci(workflows): test on Linux (Python 3.10, 3.13) and Windows (3.12)" fixes the key, adds a `windows-latest` test job that installs `requirements.txt` with PyQt5-Qt5 5.15.2, and skips the two mode tests of G5 on Windows. Its Python versions follow the fork's floor (3.10), not a proposal for upstream (Q15). It has not run on GitHub Actions. S, plus whatever a first real Windows run shows.

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

Measured on `fix/all-quickfixes` at `eacaf8f` (before the D5 and `fix/review-findings` merges), with `develop` in brackets where available.

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
- After the fixes, the save path is fail-safe in every scenario the tests and the fuzzer cover (remaining gaps: B7, B9, and A9, which neither covered: two siblings with the same file name plus a failed write):
  - atomic `writeFile` (`version_1.py:124-163`),
  - rewrite instead of in-place moves,
  - a `freshTarget` guard instead of `rmtree`,
  - old files kept when new ones fail,
  - case-only renames on case-insensitive file systems (emulated in a Linux test; it also passed under Wine, see G5, but did not run on a real Windows or macOS).
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
| Four ID strategies; characters, plots and world reuse IDs; duplicate character IDs are kept; `int()` on unvalidated strings | see B6, B10, B3 | Re-bound references; one hand-edited ID locks the user out of the project |
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
| CI tests only Python 3.9 (EOL since October 2025), runs no tests on Windows, installs no pandoc, has no lint step. Job names reference `matrix.python_version` while the key is `python-version`, so the version shows blank (G6). | `.github/workflows/*.yml` | The new `os.replace`-based saving has never run on Windows in CI (only once under Wine, G5). Regressions on 3.11–3.14 reach users first. |
| Dependencies are declared in about 9 places with conflicting pins: `requirements.txt` PyQt5 5.15.11, workflows 5.15.7 or unpinned, Docker uses the distro package. There is no `pyproject.toml` and no `requires-python`. `pyenchant` is "required" but treated as optional. macOS builds lack `markdown`, `symspellpy`, `pyspellchecker` and `language_tool_python` (only `pyenchant` is included). `requirements.txt` cannot be installed on Windows (`PyQt5-Qt5==5.15.17`, G6). | `requirements.txt`, workflows, `Dockerfile`, `package/*`, `snap/` | Different features per platform; unclear support matrix |
| The test package creates the QApplication and MainWindow at import time and writes to `~/.config/manuskript_tests` and `~/.local/share/manuskript_tests`. The old fixtures leak temp data (G1) and fail on Windows (G5). | `tests/__init__.py:11-17`, `conftest.py` | Order-dependent tests, polluted developer machines |
| The translation workflow is manual and partly broken: `util/linguist_update.py` selects `*.qm` instead of `*.ts`, the makefile `linguist` convenience target is hard-coded to `fr`, and there is no drift check | `util/linguist_update.py:24-31`, `makefile:27-34` | New strings stay English |
| Platform end-of-life risk: Qt 5.15 is the last Qt 5 series, the QtWebKit path is optional but packaged (rpm, snap), and the vendored **pdf.js 1.4.237 (2016)** predates later security fixes (e.g. CVE-2024-4367). Exposure is limited, because only PDFs Manuskript generated itself are previewed. | `ui/views/webView.py`, `PDFViewer.py`, `libs/pdf.js` | Packaging gets harder; a late migration is risky |
| Repo hygiene: Travis-era scripts (`package/prepare_*.sh`), `.codeclimate.yml`, `TODO.t2t` (2015), a 1-byte `manuskript/test.py`, a makefile `compile` target that points to a missing `setup.py`, a wrong `.msk` icon path in `manuskript.spec:92`, no `CONTRIBUTING.md` | | New contributors waste time on dead paths |

### 3.4 Recommended adjustments (incremental, each one a PR)

The order matters more than the size. Each step makes the next one safer, and none of them changes the format version. Two exceptions touch file content: item 5 stops writing the computed `charCount` key (each file is rewritten once), and a persisted ID counter in item 11 would be a format change.

#### Quick wins (S, about ½ day each)
1. **Model-tester gate.** Attach `QAbstractItemModelTester` (shipped with PyQt5) to `mdlOutline` in the DnD and load/save tests, with an allow-list. Fix the two one-line violations (`flags()` for the invalid index, `bottomRight` column).
2. **Test isolation.** Use `tmp_path` in the two old fixtures, a session-wide temp HOME/XDG, and a `closeProject()` teardown (G1; a fix for the fixtures is listed in G5). `QStandardPaths.setTestModeEnabled` alone is not enough, because it still writes to `~/.qttest`.
3. **CI matrix.** Test Python 3.9 (or the new floor), 3.11, 3.12 and 3.13. Install pandoc, fix the matrix key, remove the duplicate Linux test job (G6).
4. **Lint gate.** `ruff check --select F --extend-exclude '*_ui.py,manuskript/ui/mainWindow.py,manuskript/ui/bulkInfoManager.py,manuskript/ui/characterInfoDialog.py' manuskript` with per-file ignores for today's findings, so the job starts green. Then one mechanical PR for unused imports and the dead modules.
5. **One source of truth for the schema.** A single "computed, not persisted" set (which drops `charCount` from `.md`/`folder.txt`) and one flat-data layout, plus a golden-file test that pins the on-disk key names.
6. **Translation refresh** and a `CONTRIBUTING.md`: dev setup, isolated test run, `make ui`/`make translation`, commit style, Weblate.

#### Medium (M, 1–3 days each)
7. **No signals inside model transactions.** Defer the word-count propagation until after `endInsertRows`/`endRemoveRows`, and add a test that fails on `dataChanged` inside a bracket. This removes one of the two roots of the DnD bug class. The other is the copy-and-delete move (item 9).
8. **Dirty flag from structural signals** (A3, done in `2f348bd`). Next, drop the root's invalid-index `dataChanged`.
9. **Real in-model moves** (`beginMoveRows` across parents) for internal drags. Keep the XML path for copy, paste and cross-window drops.
10. **Make tree mutation private to the model.** The importer goes through `insertItems`, or a reset for bulk imports.
11. **One ID allocator** per model type (never reuse an ID within a project) and referential cleanup on delete in the model layer (B6).
12. **Editors submit only real user edits.** `2a53412` does this for the multi-selection case (A1); this item makes it the rule for every editor. Also, the highlighter no longer changes block formats (C2).
13. **A symmetric project lifecycle:** `deleteLater()` the old models and selection models, keep and delete the submenus, give timers a parent.
14. **Run the tests on Windows in CI.** Add a `pyproject.toml` with extras (`spellcheck`, `export`, `test`) and a GUI entry point, and keep `requirements.txt` as the lock file. Under Wine the suite already runs; G5 and G6 list the test and workflow fixes a Windows job needs first.

#### Larger (L/XL, can be split further)
15. **Persistence as an object with a plan/execute split.**
    - Step 0: add the save-path fuzzer used for this review as a slow test. It covers 61 seeds, is not on any branch yet, and can be shared on request.
    - Step 1: wrap the globals in a `FolderStore`.
    - Step 2: `serialize(project) → {path: content}` (pure), then `plan(store, files) → [Write, Remove, Keep, Move]`, then `execute(plan) → SaveReport`. The plan step can be tested and fuzzed without Qt.
    - Step 3: MainWindow shows the reports, and persistence no longer imports widgets.
    - About 1–2 weeks overall, in 3–4 PRs.
    - Reference material: the fork owner's branch `personal/main` (not on GitHub at the time of writing) has a concrete design for a store-based folder save in `docs/save-design/README.md` (written for that branch's scope: one user, Linux and Windows, projects in git), with a prototype patch against `1d7320f` that passes the suite (634 passed, 8 skipped, re-run for this document), and implements zip snapshots of each project outside its folder (`manuskript/snapshots.py`).
16. **A `Project` container instead of `F.mainWindow()`** in models and persistence, one model per PR (start with `plotModel`, which cannot even be constructed without a window).
17. **Split `MainWindow` into per-tab controllers**: spellcheck menu, view menu, character, plot and world tabs, navigation. Start with the spellcheck menu (self-contained, already tested).
18. **Background work:** asynchronous `QProcess` for pandoc, then a LanguageTool worker (D2).
19. **Qt 6 preparation on PyQt5:** scoped enums, `QRegularExpression`, `QApplication.instance()`, `exec()`. PyQt5 5.15 already accepts these, so this can land gradually. Drop QtWebKit, then switch bindings (PyQt6 or PySide6). XL in total, but phase 1 is many small mechanical PRs, partly covered by the 630 tests (at `eacaf8f`, the 412 tests covered 73 % of the statements, editor and views about 60 %).

The excepthook (B1) is deliberately not in this list. It is a policy decision rather than a refactoring, but it is the most valuable single change for users.

## 4. Questions for the maintainers

Suggested order for the discussion: the first block determines how the fixes get merged, the rest can be decided item by item.

**Merging the fix branches**
1. **PR format:** one PR per branch, in the order of 1.5? Or a different split, for example cherry-picking single commits?
2. **Behaviour changes:** which of BC1–BC21 in section 1.4 are acceptable as new defaults? The most important are BC1 (subtree rewrite on folder rename), BC3 (refuse to open on unreadable root files), BC9 (explicit "Start LanguageTool…") and BC17 (structural changes mark the project modified).
3. **Translations:** regenerate the `.ts` files in these PRs, or in the usual release step (G3)?

**Policy decisions on open items**

4. **Excepthook (B1):** keep "fail fast", or *log → one dialog → separate recovery copy → user chooses quit or continue*? If the user continues, may autosave keep writing the real project? Reference material for the recovery copy: `personal/main` implements zip snapshots outside the project folder, including one when a save fails, unless it equals the newest snapshot of that kind: a file that stays locked gives one snapshot per change, not one per autosave (`manuskript/snapshots.py`, `f2bf84b`, see 3.4 item 15).
5. **Damaged root files (B3):** salvage what lxml can recover and keep a `.damaged` backup, or keep refusing to open but name the broken file?
6. **Multi-edit in the Outline tab (A1):** `2a53412` keeps editing several summaries at once and writes only real edits. Is that wanted, or should the field be disabled for multi-selections, like the metadata panel?
7. **Dirty flag (A3):** `2f348bd` makes every structural change (rows inserted, removed or moved) mark the project modified. Is that OK?
8. **IDs (B6, B5, B10):** never reuse IDs (`max+1`, or a persisted counter)? When a label or status is deleted, reset the items that use it to "none", ask first, or move to stable IDs (a format change)? When two characters share an ID, which one keeps it, and is a notice enough?
9. **Foreign files in project folders (B7):** adopt hand-made scenes without ID, list them as "not loaded", or keep ignoring them? Is the subtree rewrite on rename acceptable long term, or are real directory renames wanted?
10. **Signals (B8):** with "save on quit" off, should SIGTERM save anyway, or write a recovery copy instead of asking?
11. **pandoc (E1, E2):** disable YAML metadata blocks by default (and migrate)? Use xelatex/lualatex by default when installed?
12. **Unfinished export filters (E5):** implement them, or hide them for now?
13. **LanguageTool (D2, D3):** is a background worker thread acceptable, or should LT be a documented "slow, proof-reading" mode? Is a blocking start acceptable if a dialog warns about the download first?
14. **Per-Space submit (C4):** is it acceptable for the word count to update about 0.5 s (the existing 500 ms debounce) after typing stops?

**Direction**

15. **Supported versions:** which Python versions are officially supported (and tested in CI)? Should the README state the tested floor rather than the 3.6 syntax floor?
16. **Packaging:** should Manuskript become pip-installable (`pyproject.toml` with extras and an entry point)? Is `pyenchant` required or optional?
17. **Refactoring:** are staged refactors welcome (3.4 items 7 and 9–13, and 15–17, split into small PRs with tests; only a persisted ID counter in item 11 would touch the format)? If so, persistence first or the model contract first? For persistence, a concrete design with a prototype that passes the suite exists on `personal/main` (3.4 item 15).
18. **Qt 6:** is a migration planned, and with which binding? May phase-1 changes (scoped enums, `QRegularExpression`, no `qApp`) be merged now on PyQt5? Can the QtWebKit path be dropped?
19. **Tooling:** are `ruff` (F rules only to start), `pytest-qt` and mechanical cleanup PRs (unused imports, dead modules) acceptable?
20. **Low-completion languages:** with `de6de99` (on `fix/ui-settings-search`), Settings lists every shipped `.qm`, including three at 0 %. Should that branch hide languages below some threshold before it is merged?
21. **Small decisions** (marked ✋ in section 2 but without their own question):
    - A9: may the items whose file names collide be renamed once (an `-ID` suffix), or should every outline file get its ID?
    - B9: is the `fsync` cost acceptable?
    - C5: keep `-- ` lines?
    - D4: per-language clitic lists?
    - E8: prune empty import folders by default?
    - F1: Settings without a project, or a language selector on the welcome screen?
    - F2: is a "Clear list" entry wanted?
22. **Elisions (D5):** can French, Italian and Catalan speakers review the elision lists (`ELISIONS` and `ELISION_ACCENTS` in `spellchecker.py`)? Should colloquial elisions before a consonant (`j’suis`) be accepted?

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

On Windows this isolates nothing: the settings go to the registry and the data to `%LOCALAPPDATA%` (see G1).

Results: `develop` 39 passed. `fix/all-quickfixes` 622 passed and 8 skipped (630 tests), both with Python 3.13 / PyQt5 5.15.10 / Qt 5.15.19 (system packages) and with Python 3.11 using the pinned wheels from `requirements.txt`. The skipped tests need pyspellchecker, symspellpy, or French and Italian dictionaries for enchant. With them installed (checked with Python 3.13), all 630 pass. Every single commit on the eight fix branches also passes the full suite on its own (91 runs), so `git bisect` works across them.

Windows, under Wine (version 3, G5): a tree with the code of `1d7320f`, the embeddable Windows CPython 3.12.10, PyQt5 5.15.11 / Qt 5.15.2, offscreen, without pandoc. 4 failed, 563 passed, 24 skipped, 39 errors. With the fixture and the embeddable Python's `._pth` changed in a throwaway copy: 2 failed (the POSIX file-mode tests), 604 passed, 24 skipped. This was not a real Windows, and the Windows workflows were not run.

Checks made for version 3 on fresh copies (Python 3.13, isolated HOME), all outside the branches:

- A9: three tests (swap, chain, long titles) lose a scene on `1d7320f`, and the swap loses one on `develop`. With the six-line `-ID` prototype on `1d7320f`, the three tests pass, and the rest of the suite gives 622 passed, 8 skipped.
- A10 and G5: `2d7a5de`'s two tests fail on `1d7320f`. With `2d7a5de`'s `version_1.py` change and `a709177`'s `conftest.py` applied: 624 passed, 8 skipped.
- The save design's prototype patch (3.4 item 15) on `1d7320f`: 634 passed, 8 skipped.
- B3, B7 and B10 on `1d7320f`: a character with `ID: ../../x` (the project does not open, or `loadProject` raises), a scene added while the project is open in a chapter that is then deleted (it no longer loads), and two pairs of characters with the same ID (deleting one removes the other). Results in the details.

### B. Upstream issues referenced by the fix branches

#313 · #324 · #351 (related) · #450 · #467 · #601 · #661 · #694 · #719 · #761 · #808 · #811 · #819 · #918 · #929 (spellcheck part; export part still open, see E6) · #963 · #978 · #997 · #1010 (crash part only) · #1127 · #1128 · #1154 · #1178 · #1193 · #1215 · #1216 · #1220 · #1228 · #1264 · #1286 · #1306 · #1320 (a remaining case: A9) · #1356 · #1376 · #1393 · #1394 · #1421 · #1435 · #1449

"Referenced" means the commit message explains how the commit relates to the issue. Some issues are only partly addressed. Please check each one before closing it.

### C. Method and limitations

- **Static and dynamic analysis:** code reading, isolated offscreen scripts (PyQt5 5.15.10 / Qt 5.15.19), `pyflakes`, `coverage.py` and an AST-based size/complexity scan. Performance numbers were measured with `QT_QPA_PLATFORM=offscreen`, so absolute times on a real display are higher.
- **Not available:** a real Windows (the suite ran under Wine only, G5), macOS, Adwaita-qt, a real X server, and a running LanguageTool server (a fake tool was used). A Breeze style (6.8.1, Qt 5 plugin) was installed, but did not take the crashing path of B2 in an offscreen session. The only manual test is the fork owner's B2 check with Breeze. Items that depend on these are marked as not verified end to end.
- **Line numbers** refer to `fix/all-quickfixes` at `eacaf8f`, before the D5 and `fix/review-findings` merges. The items added in version 3 refer to `1d7320f`, or to `develop` where it says so.
- **Version 3 sources:** the reports of the agents that made `personal/main` and of the save-design panel, the Wine runs, and the checks listed in appendix A. Commits on `personal/main` are cited by short hash and subject; that branch was not on GitHub at the time of writing.
