# Final design: the folder-mode save path of the personal fork

> **Status: design, not implemented.** Nothing in this folder is used by the code yet. The
> save rewrite (section 16, steps 1-11) is still to be done on `personal/main`.
>
> **Who wrote this.** This document and the prototype were written by Claude (Anthropic's
> AI model) in Claude Code, in a design workflow: three independent designs, each with a
> prototype, three judges (safety, Windows/git, effort) and a synthesis. The fork owner set
> the requirements (personal use, Linux and Windows, folder mode in git) and asked for the
> design, but has not reviewed it line by line. Treat every claim as checked by AI agents
> only.

Branch `fix/all-quickfixes` at `1d7320f`. All `file:line` references are to that tip and
were checked against it. Scope: one user, Linux and Windows, folder mode, the project folder
in git. LanguageTool, QtWebKit, unfinished export filters, dead modules and macOS are out.
Python >= 3.10, PyQt5. Upstream must still be able to open the result (exit strategy).

Prototype of this design (minimal's prototype plus the grafts below): [`prototype.diff`](prototype.diff),
a patch against `1d7320f` (`version_1.py`, `loadSave.py`, `mainWindow.py`, the adapted
tests and the new `test_final_probes.py`). Full suite on a fresh archive of the branch with
the patch applied: **634 passed, 8 skipped**. That is the 620 tests of minimal's prototype
plus 14 probes for the judges' loss scenarios and the two corrections made during the final
check (stems compared ignoring case, and the explicit normal-save store rule). The prototype
is a reference for steps 4-6, not code to merge as it is: section "Not in the prototype"
below lists what it lacks.

---

## 0. The design in one page

**Base: `minimal`.** Load records what Manuskript owns in one small `FolderStore`. A save
serializes the project with the existing code, lists each folder once, compares the result
with the store and the disk, and writes only what changed. The cache, `freshTarget`, the
`unreadable` global, `_lastPath`/`lastPath`, move detection and
`saveCacheState`/`restoreSaveCache` all go away.

- **One object of state.** `version_1.store` is a `FolderStore`: `root`, `ci` (is the file
  system case-insensitive?), `owned` (every file Manuskript loaded or wrote, with its owner
  and fingerprint), `unreadable`, `foreign` (files that were read but not loaded). It changes
  only after an operation on disk succeeds, so it always describes the disk. Items and
  characters carry no persistence state, and nothing travels through the clipboard.
- **Owners, not paths.** Each file has an owner: a root file, an outline ID or a character ID.
  A move or rename is just "the same owner at another path". The old file goes only when
  *all* of the owner's new files, and the `folder.txt` of every folder above them, are on
  disk.
- **Nothing silent.** Manuskript writes over or removes a file only if it owns that file and
  the file is unchanged since Manuskript read or wrote it. A file that git or an editor
  changed, deleted, or added (a loadable one) is a *conflict*. Then nothing is written, the
  in-memory project goes to a snapshot, and the user chooses Reload, Overwrite or Cancel.
- **Same-slug names do not collide.** Siblings whose titles give the same file name, ignoring
  case (`Grüße`/`Größe`, `Intro`/`intro`, long titles cut at 64 characters), get their ID
  appended. Today that happens only for identical titles. A reorder then practically never
  gives one item the file name another item had. The rare remaining cases are ordered (a
  chain) or refused (a cycle), and never written over another item's only copy.
- **No orphans.** A file is written only below folders whose new `folder.txt` is already on
  disk, so a failed or interrupted save never leaves invisible scenes.
- **Windows.** The file system's case-insensitivity is probed, and on such a file system
  every path is compared in lower case. Sharing violations are retried within a time budget,
  and autosave fails quietly while they last. Digests ignore line endings
  (`core.autocrlf`). Reserved names cannot occur by construction, and every path is
  validated.
- **Snapshots** are zip files in `%LOCALAPPDATA%` (or `~/.local/share`), outside the
  repository. They are written on open (from the text that was read), daily, at every save
  that a conflict blocks or that leaves files unsaved (deduplicated), and before an Overwrite
  or a "Save as" onto an older project. The existing single-file loader opens them.

Not adopted: planexec's op DAG, parking and FaultFS; transactional's staging folder, journal
and recovery; minimal's `\\?\` long-path helper. Section 1.3 gives the reasons.

Effort: **about 10.25 days**, in 11 commits. The suite stays green after each one.

---

## 1. Rationale

### 1.1 Why minimal is the base

| Judge | minimal | planexec | transactional |
|---|---|---|---|
| safety | 5.5 (3 fatal) | **7.5** (1 fatal) | 4.5 (3 fatal) |
| Windows/git | 4.5 (2 fatal) | **7** (1 fatal) | 5 (1 fatal) |
| effort | **8** (1 fatal) | 5 (none) | 3.5 (none) |

An average would favour planexec. Three things decide against that.

1. **Minimal's fatal findings are all local.** Each is a wrong key (one path per owner,
   case-sensitive key matching) or a missing rule (pure cycles, ID-less old files). Each fix
   is a few lines in the existing structure. The ownership fix and the ID-less files fix are
   applied to the prototype and pass the judges' own probes. The case-folding fix is
   specified (section 8), because Linux cannot emulate NTFS faithfully.
2. **Minimal is the only design that runs in the real app.** The full suite and the judges'
   probes were measured on it. Planexec's prototype is a Qt-free toy whose planner had 6 bugs
   found by fuzzing. Planexec would also rewrite the fault injection of about 15 tests, and the
   effort judge estimates it at 16-22 days.
3. **Planexec's strength is its rules, not its machinery.** The safety and Windows judges
   both recommend taking planexec's rules and putting them into minimal's structure. That is
   what this design does.

Transactional is the most expensive design (20-28 days realistic). Its journal also lost
data in the judges' commit-failure and recovery probes.

### 1.2 What was grafted, and from where

| Graft | From | Why |
|---|---|---|
| An owner may have several paths: `safe()` requires all of them on disk | planexec P3 | duplicate character IDs (git merge), safety fatal 1 |
| Duplicate or non-numeric character IDs get a new ID at load; IDs read from a file win over IDs given to ID-less files | new (root cause of the above) | also blocks `ID: ../../x` path traversal |
| Same-stem siblings get `-ID`, stems compared ignoring case | new, instead of planexec P2 parking | removes the #1320 collision class without rename ops (4.3) |
| Pure cycles are refused, never written | planexec "never overwrite another live item's only copy" | safety fatal 2 |
| Write only below folders whose new `folder.txt` is on disk | planexec P6 (inverted: parent first) | no orphans after a failed `folder.txt` (safety weakness 2) |
| Removal deepest first, `folder.txt` last | planexec P11 / transactional | a crash in the middle leaves no orphans |
| `folder.txt` is kept while its folder holds a non-owned *loadable* entry | judges (pulled scene in a deleted chapter) | git-added files are never orphaned |
| Case-insensitivity probe, and case-folded keys everywhere on such a file system | planexec P10 | Windows fatals 1 and 2 (case-only renames get stuck) |
| Validation of every generated path component | planexec P9 | reserved names, traversal through hand-edited IDs |
| `forTarget` classifies an older project with the loader's rules (`loadableFiles`) | planexec/transactional | effort fatal (ghost character); the `ID: 0` fixture hack is never committed |
| Digests over line-ending-normalized content | planexec | `core.autocrlf` checkouts are neither rewritten nor conflicts |
| Racy flag (compare content if recorded < 2 s after its mtime) | transactional | fingerprint blind spot |
| Fresh `os.stat` (not the scandir entry) for owned files about to be replaced or removed, on Windows | Windows judge | stale NTFS directory entries |
| "Added" conflict, limited to files the loader would load | planexec/transactional | git pull while the project is open |
| A normal save always uses the open project's store; only "Save as" decides by folder identity | transactional | explicit rule; a replaced folder gives conflicts (probe). Today's code already behaves this way, because `sameFolder(target, store.root)` compares a path with itself |
| An "unsaved" snapshot at every save that a conflict blocks or that leaves files unsaved (deduplicated) | transactional, extended | edits are never only in memory while saving does not work |
| Open snapshot from the text that was read (LF); disk snapshot before Overwrite and before Save as onto an older project | planexec + transactional (LF) | Windows fatal against planexec; content the parser drops |
| Quiet retry: autosave shows no dialog for sharing violations, and shows the dialog again only when the set of failed files changes | planexec + Windows judge | dialog storm and GUI freezes |
| Re-entrancy guard (B8), a `checkWritable` probe file, stale-tmp cleanup limited to Manuskript's names | transactional | small and correct |
| Load reads only the owned area (root project files, `outline/`, `characters/`) | planexec | research PDFs in the repository no longer cause "Files not loaded", and loading is faster on Windows |

### 1.3 What was deliberately left out

- **Parking (planexec P2)** renames another item's file, or a whole folder, out of the way.
  The `-ID` suffix removes the same-folder collisions that parking handles. What is left (two
  lone same-stem items at the same row that swap folders within one autosave interval) is
  refused with a clear message, and the "unsaved" snapshot holds both texts. Parking would add
  rename ops, folder renames over open handles on Windows, `~park` names in `git status`, and
  the bug the safety judge found in it.
- **The journal and staging (transactional).** The judges confirmed losses in their recovery
  and commit paths. The crash window they close (a pure same-slug swap) no longer exists here.
  Staging would also break the tests' fault injection, which matches the target path.
- **Temp files in a self-ignored `.manuskript/` folder (transactional).** The tmp file stays
  next to its target. That keeps `os.replace` on the same volume, also below symlinked
  folders, and keeps the tests' `open`/`writeFile` patch points. A crash can leave
  `.<name>.tmp` until the next load. A `.gitignore` entry keeps it out of git (decision 10).
- **The op DAG and FaultFS (planexec).** Planexec reaches the same rules with about three times
  the code and a permanent fuzzer dependency. The tests' patch points (`version_1.open`,
  `version_1.writeFile`, `os.replace`, `os.remove`, `os.path.samefile`) stay.
- **A `\\?\` helper on every call (minimal).** Windows 10+ handles long paths when
  `LongPathsEnabled=1` (python.exe is long-path aware). Manuskript checks
  `RtlAreLongPathsEnabled()` and warns. A failure affects one file and is safe.
- **Cosmetic case renames on Windows.** With `core.ignorecase=true`, git does not see them,
  and on Linux the next save renames the file anyway. On Windows the old case is kept.

---

## 2. Judge findings and how they are addressed

"verified" = covered by a probe in `test_final_probes.py`, run on the grafted prototype.
"design" = specified here, implemented in the step named in section 16.

| Finding | Resolution | Status |
|---|---|---|
| safety F1 minimal: duplicate character IDs; rename + failed write removes the only copy | IDs normalized at load (L6) and `ownerPaths` lists every path (`safe`) | verified |
| safety F2 minimal: same-slug swap + failed write or crash loses a text | `-ID` suffix (no collision); chains ordered (W2); cycles refused (W3) | verified (swap, chain, cross-folder cycle) |
| safety F3 / win F1+F2 minimal: case-only rename (scene or folder) stuck on NTFS | probed `ci`; every key is `K(p)`, lower case on a case-insensitive file system; a case-only rename is then an in-place write | design; Windows CI test (step 8) |
| safety W minimal: on NTFS, swapping `Intro`/`intro` overwrites the other item's file | folded keys make it a W2/W3 case; stems compared ignoring case, so both get `-ID` | naming verified; folding design |
| effort F minimal: ghost character after Save as onto an older project | `forTarget` owns exactly `loadableFiles()` of the older project; original fixture kept | verified (judge's probe + original ID-less fixture) |
| safety F planexec: write goes ahead when the park name is taken | parking not adopted | n/a |
| win F planexec: CRLF bytes in the open snapshot restore as empty scenes | open snapshot stores the decoded, LF-normalized text the loader read | design (step 10) |
| transactional F1-F3 (cycle commit failure, recovery, duplicate IDs) | journal and staging not adopted; duplicate IDs fixed as above | n/a / verified |
| minimal: externally added scenes are orphaned when their chapter is deleted | R3 keep rule + "added" conflict (P8) | keep rule verified; P8 design (step 6) |
| raw digests: CRLF rewrites and false conflicts after `git stash pop` | normalized digests | verified |
| failed `folder.txt` / crash leaves orphans that later block saves | W1 (parent first) | verified |
| no persistence while saving is blocked (one emergency snapshot at most) | "unsaved" snapshot at every blocked or partial save, deduplicated | design (step 10) |
| B9 cleanup removes any `.<x>.tmp` | only `.<name>.tmp` for names Manuskript writes in that folder | design (step 4) |
| Overwrite removes changed files without a snapshot | "disk" snapshot first | design (step 11) |
| dialog + 2 s freeze at every failed autosave | retry budget 1 s per save (0.25 s after a transient failure); quiet autosave for transient failures | design (steps 8, 11) |
| stale scandir timestamps on Windows | fresh `os.stat` for files about to be replaced or removed | design (step 8) |
| loader reads every file in the folder (research/, PDFs) | owned area only | design (step 4) |
| hand-edited character ID builds a path outside the project (`version_1.py:315-318`) | L6 renumbers non-numeric IDs; P2 validates every component | L6 verified; P2 design (step 6) |
| B8: a signal handler can nest a save | re-entrancy guard in `saveProject` | design (step 6) |
| `writeFolder` mixes plan and I/O | accepted: tests use `tmp_path` and need no MainWindow (R2) | accepted |
| `test_loaded_project_with_empty_cache_is_not_wiped` asserts that saves fail | kept: with an empty `owned`, every existing file is "not owned" or "added", so the save refuses and touches nothing | kept |

---

## 3. Data structures (in `version_1.py`; this part has no Qt)

```python
store = None                       # FolderStore of the open project folder, or None
                                   # (new project, project in a single file, failed load)

@dataclass
class Entry:                       # a file Manuskript loaded or wrote, as it was then
    owner: tuple                   # ("root", name) | ("o", outline ID) | ("c", character ID)
                                   # | ("old", None): file of an older project in a Save as target
    size: int
    mtime: int                     # st_mtime_ns
    digest: bytes                  # blake2b-128 of the content with CRLF/CR -> LF
    racy: bool = False             # recorded < 2 s after mtime: compare content next time

class FolderStore:
    root: str                      # absolute project folder
    ci: bool                       # case-insensitive file system (probed, section 8)
    owned: dict[str, Entry]        # K(relative path) -> Entry
    unreadable: dict[str, str]     # K(path of file or folder) -> reason (from load)
    foreign: set[str]              # K(path) of files read at load (or seen later) but not loaded
    def K(self, rel): return rel.lower() if self.ci else rel
    def isFolder(self, folder): ...        # sameFolder(): samestat, normcase if st_ino == 0
    def inUnreadable(self, rel): ...
    @classmethod
    def forTarget(cls, root): ...          # section 6

class SaveReport:
    failed: list[(rel, reason)]    # not written: "Files not saved" ListDialog
    conflicts: list[(rel, kind)]   # "modified" | "deleted" | "added" outside Manuskript
    warnings: list[(rel, reason)]  # old file not removed, foreign entry not moved, long path
    retryable: bool                # every failure was a sharing violation (winerror 5/32/33)
    __bool__ = not failed and not conflicts
```

`sameFolder(a, b)` is the body of `MainWindow.isCurrentProjectFolder`
(`mainWindow.py:1259-1277`), moved here. The method becomes a one-line wrapper.

---

## 4. Algorithms

### 4.1 Load (`loadProject`, folder branch)

- **L1** Walk only the owned area: the root `projectFiles`, `outline/**` and `characters/**`.
  Hidden names are skipped, as today (`version_1.py:916-927`). Other files in the project
  folder are never read or touched.
- **L2** Read each file as bytes and take `os.fstat` of the open handle. Text is decoded as
  UTF-8 with universal newlines, as `"rt"` does today (`:937`). XML/OPML stays bytes. The
  tests' `failReading`/`failingOpen` patches check `"r" in mode`, so they still apply to
  `"rb"`. (Prototyped.)
- **L3** Unreadable files and folders go to `notRead`, with the same fail-closed rule for the
  root and main folders (`:950-961`). Undecodable files stay "unreadable" and are reported: a
  scene saved as Latin-1 by another editor must not silently disappear.
- **L4** Stale temporary files are removed: `.<name>.tmp` in a folder where `<name>` is a name
  Manuskript writes there (a root project file, `folder.txt`, `\d+-*.md` under `outline/`,
  `\d+-*.txt` under `characters/`), and `.<project>.msk.tmp` next to the `.msk`. Nothing
  else is removed (B9).
- **L5** Models are built as today. `addTextItems` and the character loop record
  `path -> item` and `path -> character` instead of setting `_lastPath`/`lastPath`
  (`:1125`, `:1261`, `:1274`). (Prototyped.)
- **L6** Character IDs. A character created from a file without an `ID:` line gets the
  "smallest unused" ID (B6), which can equal an ID read from a later file. IDs read from a
  file win: an auto-assigned ID that is used again gets `max + 1`. Then, among IDs read from
  files, an ID that is not a number, or that an earlier file (sorted order) already has, gets
  `max + 1`. Its file is renamed at the next save (once). References keep resolving to the
  first character with that ID, as `getCharacterByID` does today. Outline IDs are already made
  unique by `checkIDs()` (`:1197`). (Prototyped without the "read IDs win" preference.)
- **L7** `store = FolderStore(root, ci=probe(root), owned=…, unreadable=notRead, foreign=…)`.
  `owned` holds the loaded root files, characters and items, with owners taken *after* L6 and
  `checkIDs`. This is exactly today's "used" set (`:1204-1216`). `foreign` holds the other
  files read.
- **L8** Open snapshot from the files read (section 10).
- `store` is set to `None` at the start of every load (prototyped), so a failed load leaves
  no store. This replaces `:959`.

`loadableFiles(files)` is a pure function with the loader's rules. It covers the root
project files, everything under `characters/`, and under `outline/` the `folder.txt` with an
ID of every folder whose parent is loaded, plus the text files with an ID in loaded folders.
A test asserts `loadableFiles(read) == set(store.owned)` after a real load with foreign extras
(verified). `forTarget` and P8 use it.

### 4.2 Save (`writeFolder(store, files, force=False) -> SaveReport`)

`saveProject()` keeps its serialization (`:206-379`). Each entry becomes
`(path, content, owner)`. `exportOutlineItem` builds the paths top-down in linear time. The
`moves`/`removes` lists disappear. Every lookup below uses `K(p)`.

```
produced   = {p: (bytes, owner)} in tree order (a folder's folder.txt before its children)
ownerPaths = {owner: [its produced paths]}
listing    = one os.scandir per folder of a produced or owned path (not inside unreadable)

PLAN (nothing changes on disk)
 P1 p is or is inside an unreadable path            -> failed (reason from load)
 P2 a component of p is not a fixed name and does not match
    ^\d+-[A-Za-z0-9_-]*(\.md|\.txt)?$               -> failed "invalid file name"
 P3 p not on disk: owned -> CONFLICT "deleted";  not owned -> write
 P4 on disk, not a regular file                      -> failed
 P5 on disk, not owned (on a case-sensitive store also: only a case variant exists and it is
    not owned)                                       -> failed "exists, and was not loaded by Manuskript"
 P6 owned: now = recorded digest if (size, mtime) equal and not racy, else digest(read)
    (on Windows the size and mtime of a file to be written come from os.stat, not the listing)
    now not in {recorded, new}                       -> CONFLICT "modified"
    now == new                                       -> unchanged: refresh entry, owner := producer
    else                                             -> write
 P7 stale = owned paths not produced: gone -> forget;  changed -> CONFLICT "modified"
 P8 an entry of a listed loaded folder that is not owned, foreign or unreadable: if
    loadableFiles() would load it (root project file; any file under characters/; under
    outline/ a text file with an ID line, or a subfolder with folder.txt)
                                                     -> CONFLICT "added"; otherwise -> foreign
 conflicts and not force -> return the report: nothing was written or removed

WRITE (each file: tmp ".<name>.tmp" next to it, fsync, copymode, os.replace with retry; the
       store entry is updated after success, racy=True; on error the old version stays)
 W1 p is written only when every folder above it is ready: its folder.txt at the new path is
    on disk and belongs to the folder item that produces it (unchanged, written in this save,
    or an older version of that same item's file). Not ready because it failed -> failed.
 W2 a path whose current file is the only copy of another live owner waits until that owner
    is safe; if that owner failed -> failed "file name still used by another item"
 W3 a round without progress means the rest is a cycle -> failed "same file name as an item
    that took its place; rename one of them". It is never written.
 W4 POSIX: fsync every folder that got new entries, before anything is removed
safe(owner) = every path in ownerPaths[owner] is written or unchanged, and every folder above
              each of them is ready

MOVE ALONG (B7) for each stale folder.txt whose owner is live and safe and whose folder changed:
 M1 every entry of the old folder that is not owned and not a Manuskript subfolder (one with
    an owned folder.txt) is os.replace'd into the new folder, unless the name is taken there.
    Unreadable and foreign keys are re-keyed. A failure is a warning, and the old folder is
    "stuck" (it keeps its folder.txt; retried at the next save).

REMOVE stale paths, deepest first, folder.txt last in its folder:
 R1 keep if the owner is live and not safe          (its only copy)
 R2 keep ("old", _) entries if anything failed      (a failed Save as removes nothing)
 R3 keep a folder.txt while its folder holds kept files, unreadable entries, stuck entries,
    or a non-owned loadable entry (scene with ID, subfolder with folder.txt: e.g. git pull)
 R4 a stale path whose folded form equals a written path and os.path.samefile -> forget
    (a case-sensitive store on a case-insensitive mount; test_rename_only_case_insensitive_fs)
 R5 os.remove with retry; failure -> warning, stays owned, retried at the next save
 R6 rmdir the folders emptied by these removals, walking up, never outline/, characters/ or
    the root. A failed rmdir leaves an empty folder: harmless, git does not track it.

MARKER <name>.msk = "1": written only if it is missing or different, never by a failed save
```

Properties, each pinned by a test:

- Files not owned are never written or removed: foreign files, unreadable files, and files
  added by git. Move-along moves foreign entries but never changes them (R1 of the
  requirements).
- An old copy goes only after its replacement and the replacement's folders are on disk,
  judged per owner over all of the owner's paths.
- Old files of removed items are removed even if other writes failed (pinned by
  `test_failed_write_removes_other_old_files`). R3 still keeps a `folder.txt` that something
  still needs.
- Moves are derived from the store at every save, so a failed move is retried automatically.
  There is no state to repair after a failure.
- A no-change save opens no file for writing. Load → save → reload → save rewrites nothing
  (verified). Editing one scene rewrites exactly that file (measured, section 12).

### 4.3 File names (`fileStem`)

`name = <row zero-padded>-<stem><.md if scene>`, where `stem = slugify(title)[:64]`. If
another sibling has the same stem, **ignoring case**, the stem becomes
`slugify(title)[:64 - len(ID) - 1] + "-" + ID`. For identical short titles, this is exactly
today's `slugify(title + "-" + ID)[:64]` (`version_1.py:829-837`), so those names do not
change. Names differ from today only for titles that slugify alike but differ (`Grüße`/`Größe`
→ `Gr--e`; every CJK title → `---`; `Intro`/`intro`), and for long identical titles, where
today the ID is cut off. The rule depends only on the model, so Linux and Windows produce the
same names.

Why this practically ends the #1320 class within a folder: an item can take the path another
item had only if it gets the same row and the same name. Two siblings with the same stem
(ignoring case) both carry their unique ID. So within one folder, a collision needs a
coincidence: one title equal to another item's stem plus that item's ID (for example `Teil 7`
next to two items titled `Teil`, one with ID 7). Those cases and moves across folders are
chains, which W2 orders, or cycles, which W3 refuses without writing anything. Verified: a
swap with a failed write, the judges' chain, and the cross-folder cycle.

`outlineItemPath` uses the same rule. It stays for the tests, and a test checks that the
linear builder gives the same paths.

---

## 5. Failure handling and reporting

- A per-file write error (permission, read-only, name too long, disk full, a sharing
  violation that outlasts the budget) keeps the old version. The item is not safe, so its old
  copy stays. It appears in the existing "Files not saved" ListDialog as
  `"<abs path> (<reason>)"` (`:656-663`). The next save retries by itself.
- A save that leaves failed files or is blocked by a conflict writes an "unsaved" snapshot of
  the in-memory project (section 10, deduplicated). What the user typed is then on disk
  somewhere even if the app crashes (B1) or the user closes without saving.
- A failed removal or move is a warning (log and status bar), and the next save retries it.
- `writeFolder` has no UI. `saveProject(zip=None, path=None, force=False, quiet=False)` shows
  the existing dialogs from the report unless `quiet`. `MainWindow` handles conflicts and the
  autosave throttle (7.3). Until step 11, conflicts are listed in the "Files not saved" dialog
  with the reason "changed outside Manuskript".
- Re-entrancy guard (B8): `saveProject` returns a failed report at once if a save is already
  running. A signal handler during a retry sleep can no longer nest a save on the same store.
  (Scheduling the SIGTERM handler with `QTimer.singleShot(0)` is a separate B8 fix.)

---

## 6. Save, Save as, new project, single file

`MainWindow.saveDatas` loses the `isCurrentProjectFolder` branch, `saveCacheState`,
`clearSaveCache` and the `try/finally` restore (`mainWindow.py:1301-1313`, `:1327-1338`). It
calls `loadSave.saveProject(path=projectName)` for "Save as" and `loadSave.saveProject()`
otherwise, because tests patch it with `lambda: False`. It sets `currentProject` only on
success.

| Situation | Store used | Adopted as `store` |
|---|---|---|
| normal save, `store` exists | `store`, always | always (it describes the disk even after a partial failure) |
| new project, project loaded from a zip, `store` is `None` | `forTarget(folder)` | always |
| "Save as" onto the own file, or onto a link to the own folder (`store.isFolder(target)`) | `store` | always (root updated on success) |
| "Save as" elsewhere | `forTarget(target)` | **only if the save succeeded** |
| zip mode | none | `None` on success |

A normal save never chooses by folder identity. If the folder was replaced on disk while the
project was open (moved away and cloned again, another checkout), the save compares with what
the open project knows, which gives conflicts. It never treats the folder as an "older
project" to overwrite. The prototype already behaves like this; the rule is made explicit and
a probe pins it.

`forTarget(root)`:

- Missing or empty (hidden files ignored, as `:444-447`) → empty store.
- Not empty and no `MANUSKRIPT` → `NotAProjectFolder` → the existing "Project not saved"
  dialog (`:451-462`).
- An older project: read its owned area (L1-L3). `owned = loadableFiles(read)` with owner
  `("old", None)`. Everything else becomes `foreign` and stays. A "disk" snapshot of the
  older project is written first. Old files at produced paths are overwritten in place.
  The other old files are removed only after the whole save succeeded (R2). **No rmtree.**
  The same applies to a new project created over an existing one
  (`welcome.createFile(overwrite=True)`).

A failed "Save as" leaves the files already written in the target (as today, A4 "Not
changed"), never leaves a `.msk` there, and never removes anything of an older project.
The current store is never touched, so there is nothing to restore.

---

## 7. External changes and git (R3)

### 7.1 Defined behaviour

| On disk since load or the last save | Outcome |
|---|---|
| unchanged | normal |
| touched only (same content, also CRLF vs LF) | fingerprint refreshed, no write, no conflict |
| changed, and equal to what Manuskript would write | no write, entry refreshed |
| changed otherwise (owned file) | conflict "modified" |
| deleted (owned file) | conflict "deleted" (no silent resurrection, unlike `:520` today) |
| added, and the loader would load it | conflict "added" |
| added, not loadable (a note, `desktop.ini`) | recorded as foreign, ignored |
| the whole folder replaced (new clone, other checkout) | conflicts as above, file by file |

Any conflict means nothing is written. This also detects a second Manuskript instance on the
same folder.

### 7.2 git specifics

- `git commit` changes no working-tree file, so nothing happens. `pull`/`checkout`/`stash`
  give conflicts, and Reload is the recommended answer. `stash` + `stash pop` of
  Manuskript's own content gives no conflict (normalized digests).
- Deterministic output: sorted settings JSON (`settings.py:190`), metadata in enum order,
  lxml in model order, LF only. Same models give the same bytes, on Linux and on Windows.
- Churn that remains because of the v1 format: names start with the zero-padded row, so
  inserting an item renames the siblings after it, and crossing 10, 100 or 1000 siblings
  renames all of them. Upstream relies on this naming for the order, so it stays. Only
  the renamed files are rewritten, with unchanged content, which git shows as renames.
- In the project repository, recommended: `.gitignore` with `.*.tmp` (a crash between write
  and replace leaves one until the next load), and `.gitattributes` with `* -text`, or
  `core.autocrlf=false` on Windows. Normalized digests make this optional. Manuskript itself
  creates no file in the repository.
- A fresh clone needs `<name>.msk` (content `1`) next to the folder in order to be opened.
- Churn outside this design (decision 8): `settings.txt` holds UI state (`viewSettings`,
  `corkSizeFactor`, `folderView`, `outlineViewColumns`, `lastTab`, `openIndexes`, and the
  machine-specific `dict`). `revisions.xml` is the whole outline with all texts, when
  `revisions.keep` is on (the sample has it on).

### 7.3 UI (MainWindow)

- Timers call `saveDatas(auto=True)`, which calls `saveProject(quiet=True)`.
- **Conflict:** `saveProject` writes an "unsaved" snapshot. An explicit save, close or quit
  asks: **Reload from disk** (close without saving, then load; the dialog names the
  snapshot that holds the current version) / **Overwrite with Manuskript's version** (a
  "disk" snapshot first, then `saveProject(force=True)`; added files stay untouched and R3
  keeps them loadable) / **Cancel**. Autosave asks once per conflict set (non-modal), and
  after that only shows the status bar.
- **Failed files:** an explicit save always shows "Files not saved". Autosave shows it only
  when the set of failed files changed since it was last shown. If every failure was a
  sharing violation (`retryable`), autosave shows the status bar only, until the same files
  have failed 3 autosaves in a row.
- Optional (step 12): check for external changes on
  `applicationStateChanged → ApplicationActive`. That is the listing plus digests of the
  files whose stamp changed, about 15-20 ms for 4000 files. Any change offers Reload.

---

## 8. Windows (R4)

Reasoned from CPython documentation and source. It must be confirmed by the Windows CI job
and one manual session (step 8).

| Topic | Design |
|---|---|
| `os.replace`/`os.remove`/`os.rename`/tmp `open` while AV, the indexer, OneDrive or an editor holds the file | `_retry`: only `PermissionError` with `winerror` 5, 32 or 33. Back-off of 50/100/200/400 ms, with a budget of 1 s of sleep per save (0.25 s if the previous save failed the same way); after that, no more sleeping. A failed write keeps the old version and is retried at the next save; the report is `retryable` (quiet autosave). On Linux the predicate is false. Tests emulate it by patching `version_1._transient`. |
| Delete-pending files (removed while another process holds them with `FILE_SHARE_DELETE`) | The name stays until the handle closes: a write to it fails with winerror 5 (retried, then reported), and rmdir of its folder fails (harmless, R6). |
| Read-only files | `writeFile` keeps its `os.access(file, W_OK)` check (`:135`). It is reliable for files on Windows, and it raises EACCES without `winerror`, so it is not retried. |
| Case-insensitive, case-preserving | `ci` = `samestat(stat(root/MANUSKRIPT), stat(root/manuskript))` once the marker file exists. Before that (first save of a new project), the same test on the nearest existing ancestor with a cased letter. Fallback: `os.name == "nt"`. If `ci`, every key in `owned`, `unreadable`, `foreign`, `produced` and the listing is lower case. Manuskript's names are ASCII, so Python's `lower()` matches NTFS's comparison for them. A case-only rename of a scene or folder is then an in-place write of the changed `folder.txt` or scene, and the old case stays on disk. On a case-sensitive store, the R4 `samefile` guard stays. Linux mounts of vfat/exFAT are detected by the same probe. |
| MAX_PATH 260 | No `\\?\` prefix. Required one-time setup: `LongPathsEnabled=1` and `git config core.longpaths true`. If a produced absolute path, plus the 5 characters of its tmp name, reaches 260 characters and `RtlAreLongPathsEnabled()` is false, the report gets a warning that names the setting. A failure affects one file and is safe. The cap stays at 64 (decision 5). |
| Reserved names, trailing dots and spaces | Impossible by construction: every component is a fixed name or `<digits>-[A-Za-z0-9_-]*` + `.md`/`.txt`, and P2 enforces it. `welcome` refuses project names that end in `.` or a space, or that are reserved (`os.path.isreserved` on 3.13, a small list before). |
| `os.access` on folders | Drop the folder-mode pre-check (`:383-386`; zip mode keeps it). `welcome.checkWritable` (`welcome.py:248-262`) creates and removes a probe file (`tempfile.mkstemp(dir=…, prefix=".manuskript-probe-")`) in the folder, or in its parent if it does not exist yet. |
| Folder renames over open handles | Manuskript folders are never renamed: renames and moves rewrite the subtree. Only move-along renames foreign entries, with retry. A failure means "stuck": the old `folder.txt` is kept and the move is retried at the next save. |
| `scandir` stamps | `st_ino` is 0 and is never used. Size and mtime come with the listing for the comparison, and from `os.stat` for owned files about to be replaced or removed. |
| fsync | `os.fsync` → `FlushFileBuffers` for every file. Folders cannot be synced on Windows; NTFS journals metadata. |
| Line endings | normalized digests (7.2). |

---

## 9. Crash consistency (R5)

- Every file is old or new: tmp, fsync, `os.replace`.
- On POSIX, the touched folders are fsynced before any old file is removed.
- Ordering: parents before children (W1), and removals deepest first with `folder.txt` last.
  So no crash point leaves a folder without `folder.txt` above content that must load.
- What the next load can find:
  - a mix of old and new files: it loads;
  - an item at both its old and new path: duplicate IDs, which `checkIDs` (outline) and L6
    (characters) renumber; visible and lossless, as today;
  - a new folder with its `folder.txt` and only part of its children: the old folder still
    holds the rest, so it loads twice; visible and lossless;
  - a hidden `.<name>.tmp`: ignored and removed (L4);
  - no orphans, and no overwritten only copy (the `-ID` suffix, W2 and W3).
- **fsync policy:** always fsync each written file in folder mode. An autosave writes 1-3
  files. A bulk rewrite (inserting a part at row 0, the first save) costs one fsync per
  file. This cost is not measured on real disks yet, so step 9 measures it (decision 6).

---

## 10. Snapshots (R6)

New module `manuskript/snapshots.py`, about 120 lines, QtCore only.

- **Where:** `F.writablePath("snapshots")` (`functions/__init__.py:291`), which is
  `AppLocalDataLocation`: `~/.local/share/manuskript/manuskript/snapshots` on Linux and
  `%LOCALAPPDATA%\manuskript\manuskript\snapshots` on Windows (not roaming). Tests use their
  own location (`manuskript_tests`, `main.py:86`). One folder per project:
  `<slugify(folder name)[:40]>-<blake2b(normcase(realpath(root)))[:8]>`. A check asserts
  that it is outside the project folder.
- **Files:** `YYYYmmdd-HHMMSS-<kind>.msk` (no colons), where kind is `open`, `daily`,
  `unsaved` or `disk`. The content is the single-file format: `MANUSKRIPT`, POSIX entry
  names, deflate level 1, fixed entry dates, written atomically.
- **Content:** text entries are always LF. For `open`, that is the decoded text the loader
  read: what was on disk in the owned area, including foreign files and content the parser
  drops. For `daily` and `unsaved`, it is the serialized in-memory project (the `files` list
  that `saveProject` already built). For `disk`, it is a fresh read of the owned area,
  decoded and normalized.
- **When:** after a successful folder load (`open`); at the end of the first successful save
  more than 24 h after the newest snapshot (`daily`); at every save that a conflict blocks or
  that leaves failed files (`unsaved`); before Overwrite, and before a save onto an older
  project (`disk`).
- **Dedup:** the zip comment holds a digest over the sorted (path, content digest) pairs. If
  the newest snapshot has the same digest, nothing is written. A long Windows lock therefore
  creates a snapshot only when the content changed.
- **Rotation:** keep the newest 10 per kind. Only files that match the name pattern are
  deleted. Errors are logged and never block opening or saving.
- **Cost:** a typical novel takes about 10 ms, 4000 scenes about 200 ms (level 1, measured by
  planexec).
- **Restore:** File > Open the snapshot. `loadSave.loadProject` detects the zip with
  `MANUSKRIPT` (`loadSave.py:87-94`). Saving into the snapshot folder is refused ("this is a
  snapshot: use Save as…"). If the current project is a snapshot, Save as turns
  `settings.saveToZip` off first, because loading a zip turns it on (`version_1.py:986`).
  Optional: a menu item "Open snapshot folder".

---

## 11. B7 (R7): files Manuskript did not load, inside a renamed or moved folder

**Move along** (M1). Readable foreign files (ideas.txt, a scene without `ID:`, a folder
without `folder.txt`) are treated as unreadable files are today. git sees a rename. If the
name is taken or the file is in use, the entry stays, its old folder keeps `folder.txt`
(the old chapter reappears next to the renamed one, as for unreadable files today), the user
gets a warning, and the next save retries.

Foreign entries of a *deleted* folder stay where they are and are never deleted. If one of
them would load (a scene with an ID, e.g. pulled by git), the `folder.txt` stays (R3), so
the folder comes back on the next load instead of hiding it.

Known limitation (rare, lossless): a deleted subfolder that holds an unreadable file, inside
a renamed parent, keeps its parent's old `folder.txt`. The deleted folder comes back, next to
the renamed parent, until the file is readable or removed.

Behaviour change pinned by an adapted test: `test_files_not_loaded_are_not_deleted`
expects the two foreign entries of the renamed part at their new place.

---

## 12. Performance (R8)

Measured again for this document on the grafted prototype (Linux, tmpfs, Python 3.13,
minimal's `proto3.py`):

| Project | no-change save | one-scene edit + save | files rewritten | insert a top-level folder at row 0 |
|---|---|---|---|---|
| 4 × 20 × 50 = 4000 scenes | 151-180 ms | 132 ms | 1 | 542 ms |
| 1 × 4000 (one folder) | 154-181 ms | 139 ms | 1 | 492 ms |
| 30 × 10 (typical novel) | 15-17 ms | 20 ms | 1 | 49 ms |

Today the no-change save takes 530-1900 ms for 4000 scenes (minimal's measurement). The upper
end of each no-change range is the save right after a bulk write: every entry is racy, so
all files are read once. The serialization (about 90 ms) dominates. On Windows the comparison
uses the stamps from the listing (no open per file), with an estimated 150-250 ms for 4000
scenes. `revisions.xml` adds about 400 ms per save at 4000 scenes when it is kept.

---

## 13. Format compatibility (R9)

The format is unchanged: version 1, the same keys and layout, the `.msk` marker, the zip
layout. Upstream opens the result normally, builds its own cache, and saves in its own way.
Each one-time churn below is its own commit:

1. **`charCount` is no longer written** (add `Outline.charCount` to the exclude list at
   `:847`). It is computed, and for a folder it changes with every edit below it, so today one
   edit rewrites the `folder.txt` of every ancestor. Upstream recomputes it. Every `.md` and
   `folder.txt` that has the line is rewritten once.
2. **`-ID` for siblings with the same stem, ignoring case** (4.3). Upstream loads any name.
   Only affected items are renamed, once. Upstream would rename them back with its own rule,
   which is harmless.
3. **`lastPath` attributes disappear from `revisions.xml`** (only with `revisions.keep`).
   Upstream's `appendRevisions` reads only `<revision>` children and `ID` (`:1313-1343`).
4. **Duplicate or non-numeric character IDs** get a new ID. That file is renamed once.

Hidden temp files are ignored by upstream too.

---

## 14. What is deleted

- `version_1.py`:
  - `:44-55`, the globals `cache`, `freshTarget` and `unreadable` (→ `store = None`);
  - `:166-172`, `isUnreadable`;
  - `:190-195`, the `removes`/`moves` lists;
  - `:320-325`, character rename detection;
  - `:336-339`;
  - `:383-386`, the folder-mode `os.access` pre-check;
  - `:424-668`, the whole folder branch: the rmtree cleanup and its dialog, the move log,
    the cache writes, the phantom, `notMoved` and `keepOldPath` logic, the unreadable mover,
    phantom removal, the `os.walk` `removedirs` sweep and the unconditional marker write;
  - `:761-810`, `exportOutlineItem` with move detection;
  - the cache, `freshTarget` and `unreadable` assignments in `loadProject` (`:947`, `:959`,
    `:966-969`), `:1125`, the cache pruning at `:1199-1216`, and `:1261`/`:1274`.
- `loadSave.py:27-57`: `saveCacheState`, `restoreSaveCache`. `clearSaveCache` becomes
  `v1.store = None`.
- `mainWindow.py`: `:1301-1313` and `:1327-1338`. The body of `isCurrentProjectFolder`
  becomes a one-line wrapper.
- Models:
  - `abstractItem.py:39-40`, `:196-205` (`clearLastPath`), `:311-312`; the attribute read at
    `:335-336` is ignored (old clipboard data and old `revisions.xml` still parse);
  - `abstractModel.py:496-499` (the `_lastPath` line);
  - `characterModel.py:262`.
- Tests: `test_copied_item_has_no_lastPath`, the `nameOnly` parameter of
  `test_save_as_into_older_read_only_project`, the `copy._lastPath == ""` assertion.

Size (measured on the prototype): `version_1.py` grows from 1438 to about 1700 lines.
Most of that is `writeFolder` (about 300 lines), which replaces the 245-line folder branch,
plus the store, `forTarget` and `loadableFiles`. `loadSave.py` loses about 30 lines,
`mainWindow.py` about 32, the models about 15. New: `snapshots.py` (about 120 lines), and
the conflict and throttle code in MainWindow (about 60).

---

## 15. Test plan

### 15.1 Existing tests (status on the grafted prototype: all green)

K = kept, A = adapted, O = obsolete. The adaptations are minimal's (`minimal/adapt_tests.py`),
without its `ID: 0` fixture change.

- `test_ParseMMDFile.py`: all K.
- `test_save_load_regressions.py`:
  - K: characters_in_outline_path, character_named_outline,
    save_does_not_wipe_non_project_folder, save_into_folder_with_hidden_files_only,
    save_as_existing_project_keeps_user_files, ui_check_unreadable_folder,
    ui_refuses_non_project_folder, long_titles, zip_save_is_atomic,
    zip_save_keeps_symlink_and_mode, open_damaged_project_file,
    open_project_file_with_newline, world_item_with_empty_name_keeps_children,
    open_project_with_unreadable_files, colons_in_names.
  - A, mechanical (`X._lastPath` → `relPath(X)`, a helper over `outlineItemPath`):
    failed_write_keeps_previous_file, save_keeps_symlinks_and_modes,
    read_only_file_is_not_replaced, save_without_chmod_support.
  - A, behaviour:
    - files_not_loaded_are_not_deleted (B7: files move with the renamed part);
    - loaded_project_with_empty_cache_is_not_wiped (`store.owned.clear()`: the saves refuse
      and nothing is touched);
    - write_error_does_not_stop_save (the obstacle is a patched `writeFile`; a file replaced
      by a folder is now an external change).
- `test_save_moves.py`:
  - K: reorder_titles_with_same_slug, chapter_10_moved_above_chapter_1,
    scenes_moved_into_new_unsaved_folder, rename_only_case,
    failed_folder_txt_keeps_items_moved_into_it.
  - A (`relPath`; the old path is taken before the rename):
    duplicate_saved_folder_and_save_twice, rename_only_case_insensitive_fs (it still patches
    `os.remove` and `os.path.samefile`, so R4 must call them through `os`),
    failed_write_keeps_old_files_of_renamed_folder, failed_write_removes_other_old_files,
    failed_write_keeps_items_moved_out_of_a_changed_parent[2].
  - O: copied_item_has_no_lastPath.
- `test_unreadable_files.py`: all K, except two A: new_project_after_failed_load
  (`store is None`), and unreadable_scene_that_cannot_be_moved (every save retries the move,
  so the test checks while `os.replace` still fails and ends with `projectDirty = False`).
- `ui/test_saveAsFailure.py`:
  - A: the fixture (`store.unreadable`), `cacheState()` → `(store, dict(owned),
    dict(unreadable))`, failed_save_as_keeps_the_moves.
  - A: save_as_into_older_read_only_project. Its 2 parameters keep the original ID-less
    fixture. Expected: one "Files not saved" dialog, nothing of the older project removed,
    no `.msk`.
  - K: the rest.
- `test_mainWindow_load_save.py::test_load_damaged_project_does_not_raise`: A
  (`store = object()`, then `store is None`).

### 15.2 New tests

- `test_final_probes.py`, written and green on the prototype (14 tests):
  - same-stem names get `-ID`, and the linear paths equal `outlineItemPath`;
  - stems that differ only in case get `-ID`;
  - a same-slug swap with a failed write, then Discard;
  - the judges' chain;
  - the cross-folder cycle is refused, and nothing is lost;
  - duplicate character IDs, a rename and a failed write;
  - a pulled scene in a deleted chapter stays loadable;
  - a failed new `folder.txt` writes nothing below it;
  - a CRLF checkout is neither rewritten nor a conflict;
  - an external change is a conflict;
  - a normal save into a folder replaced on disk is a conflict and overwrites nothing;
  - a no-change save after a reload writes nothing;
  - `loadableFiles == store.owned`;
  - the judge's ghost character after Save as onto an older project.
- `test_folder_store.py`: pure `writeFolder` on `tmp_path`, no MainWindow:
  - the conflict matrix (7.1, with "added" loadable and non-loadable);
  - force;
  - racy entries;
  - the R1-R6 removal rules;
  - W1-W3;
  - move-along and its retry;
  - `forTarget` with an ID-less character and a foreign note;
  - P2 rejects `../x` and reserved-looking names;
  - `_transient` emulation of sharing violations, with the budget and `retryable`;
  - `ci=True` key folding on stores whose disk names already match;
  - L4 removes only Manuskript's tmp names; L6 prefers IDs read from files.
- Windows-only (skipped elsewhere), run in CI on `windows-latest`:
  - a case-only rename of a scene and of a chapter, each followed by edit + save twice;
  - a locked file (opened without `FILE_SHARE_DELETE` through `ctypes`/`msvcrt`) gives a
    retryable failure and a later success;
  - a long-path warning.
- UI: the conflict question is asked once; Reload; Overwrite (with a disk snapshot); the
  autosave throttle; the B8 guard.
- Snapshots: the location is outside the project, rotation, dedup, LF content (a CRLF file
  restores with its body), restore through the zip loader, saving into the snapshot folder is
  refused, Save as from a snapshot in folder mode, an "unsaved" snapshot after a failed save.
- **Fuzzer (slow):** `test_save_fuzz.py`. Each seed:
  1. copies the sample and adds a foreign note, a scene without ID and an unreadable scene;
  2. applies random edits (rename, move, delete, add, swap, text edits), with titles from
     `[Grüße, Größe, 第一章, 第二章, A, a, Intro, intro, a long title ×2 with a common
     64-char prefix]`;
  3. saves with a fault injected at the k-th file operation (`writeFile`, `os.replace`,
     `os.remove`, `os.rmdir`, `os.makedirs`), either an `OSError` (the save goes on) or a
     `Crash(BaseException)` (the save stops; the store and models are dropped, as if the
     process died);
  4. reloads.

  Invariants:
  - the load succeeds;
  - every item has its old or new text somewhere in the loaded project;
  - every foreign file's bytes still exist (possibly moved);
  - no file outside the owned area changed;
  - after a clean save and reload, the project equals the model, and no `.tmp` is left.

  20 seeds by default (about 1 minute), 500 with `MANUSKRIPT_SLOW=1`. The existing CI does
  not need to run the slow mode.

---

## 16. Implementation plan (one commit per step; the suite is green after each)

| # | Commit | Tests in the same commit | Days |
|---|---|---|---|
| 1 | **perf: linear outline paths.** Top-down path builder in `exportOutlineItem` (still returning moves for the old code), a set for phantoms (`:537-538`). No behaviour change. | equality with `outlineItemPath` on random trees | 0.25 |
| 2 | **format: stop writing charCount.** One line at `:847`. The commit message notes the one-time churn. | golden test: no computed keys in `.md`/`folder.txt`; one scene edit rewrites one file | 0.25 |
| 3 | **names: `-ID` for siblings with the same stem, ignoring case** (`fileStem`, used by both path functions). One-time rename of affected items. Works with the old cache save (a rename is a rewrite). | name tests (same stem, case variants, long titles); same-slug swap with a failed write + Discard | 0.25 |
| 4 | **load: FolderStore recorded at load.** L1-L7: read as bytes, normalized digest, racy, owners after `checkIDs`, character ID normalization, `foreign`, `ci` probe, owned area only, stale-tmp cleanup, `loadableFiles`. The old cache is still filled and used by the save. | `loadableFiles == owned`; duplicate character IDs renumbered; tmp cleanup only for Manuskript's names | 1 |
| 5 | **save: writeFolder replaces the cache sync.** Minimal's prototype core (plan, write, move-along, remove), conflicts "modified"/"deleted" (listed in the "Files not saved" dialog for now), owner path lists, `forTarget` via `loadableFiles`, the marker policy, `saveProject(path=…)`, the store table of section 6, Save as without snapshot/restore, `sameFolder`. Deletes `cache`, `freshTarget`, `unreadable`, `saveCacheState`, `restoreSaveCache`. | minimal's test adaptations (15.1) without the fixture change; `test_folder_store.py` core; ghost-character and replaced-folder probes | 1.25 |
| 6 | **save: the grafts.** W1 (folder ready), W2/W3 (chains wait, cycles refused), removal order, R3 keep rule, P2 validation, P8 "added" conflicts, the B8 guard. | the remaining `test_final_probes.py`; `test_folder_store.py` rules | 1.25 |
| 7 | **models: drop `_lastPath`/`lastPath`.** `abstractItem`, `abstractModel`, `characterModel`; `revisions.xml` changes once. | obsolete test removed; a clipboard copy has no attribute | 0.5 |
| 8 | **windows: case folding, retry, checks.** Folded keys on `ci` stores; `_retry` with budget and `retryable`; fresh `os.stat` before replace/remove; `checkWritable` probe; drop the folder `os.access` pre-check; project-name checks; long-path warning; a `windows-latest` CI job running `tests/load_save`, `test_saveAsFailure` and the store tests; one manual session (Defender, OneDrive, an editor holding a file, a case-only rename, a deep path). | Windows-only tests (15.2); `_transient` emulation | 2 |
| 9 | **crash: fsync and the fuzzer.** Per-file fsync in folder mode, POSIX folder fsync before removals; the fuzzer as a slow test; one measurement of the fsync cost on each machine. | fuzzer (20 seeds by default) | 1.25 |
| 10 | **snapshots.** The module; open/daily/unsaved/disk; rotation, dedup, read-only guard, Save as from a snapshot in folder mode. | snapshot tests (15.2) | 1 |
| 11 | **ui: conflicts and quiet autosave.** The Reload/Overwrite/Cancel question asked once, Overwrite with a disk snapshot, the autosave throttle, `saveDatas(auto=True)` on the timers. | UI tests (15.2) | 1.25 |
| (12) | *optional:* check on window activation (7.3). | activation test | 0.5 |

Total: **10.25 days** for steps 1-11, plus 0.5 for step 12. The effort judge estimated 9-12
days for minimal alone. The Windows step carries the most uncertainty.

Steps 5 and 6 can be one commit. Keeping them apart means a regression can be bisected to
"the port" or "the grafts". Step 5 reproduces a prototype that is known to be green.

---

## 17. Risks

1. **A conflict stops all saving** until the user decides. The edits are not only in memory:
   every blocked save writes an "unsaved" snapshot. The status bar, and the question on
   explicit save and on quit, remind the user.
2. **The Windows behaviour is reasoned, not run.** Open questions: case folding against real
   NTFS, which winerror codes Defender and OneDrive really cause, delete-pending files keeping
   folders non-empty, and how fresh scandir stamps are. Step 8 includes CI and one manual
   session. Linux cannot emulate a case-insensitive file system faithfully.
3. **Fingerprint blind spot:** an external change with the same size inside the racy window
   of a file system with coarse timestamps. Mitigated by the racy flag, and on Windows by the
   fresh stat before a replace.
4. **The cycle refusal** blocks the save of two items until one is renamed or moved back. It
   needs two lone same-stem items at the same row that swap folders within one autosave
   interval, or a title that coincides with another item's stem plus ID. The message says
   what to do, and the "unsaved" snapshot holds both texts.
5. **One-time renames and churn** (13.1-13.4) appear in git once, in separate commits. The
   row-prefix renames of the v1 format remain (7.2).
6. **fsync cost** of bulk rewrites on the user's disks is unmeasured (step 9 measures it).
7. **Move-along moves user files** with their folder (B7). Notes elsewhere that refer to them
   by path then point to the old place.
8. **Any file dropped into `characters/` loads as a character.** While the project is open,
   such a file is an "added" conflict and pauses autosave until Reload or Overwrite. That is
   consistent with the loader, but it may surprise the user.
9. **`loadableFiles` must follow the loader.** A test pins their equality, and later B3 work
   on the loader must update both.
10. **The test patch points pin the code** in `version_1.py`. Moving it later to a Qt-free
    module needs mechanical test edits.
11. **No journal:** after a crash, an item can appear twice (visible, lossless).
12. **`revisions.xml`**, if it is kept, stays slow (about 400 ms per save at 4000 scenes) and
    churns.

---

## 18. Decisions for the user (each with a recommendation)

1. **Conflict policy.** Stop the whole save and ask (**recommended**), or write the files
   that do not conflict? A partial write mixes the states of two machines.
2. **Added files.** Treat new loadable files (a pull adding scenes or characters) as a
   conflict that offers Reload (**recommended**), or ignore them until the next open?
3. **B7.** Move foreign files along with their renamed folder (**recommended**), or leave
   them and report?
4. **Same-stem names.** Append `-ID` only to siblings whose stems collide, ignoring case
   (**recommended**: a one-time rename of the few affected items; a rare cycle is refused).
   Or append the ID to every outline file name: no collision of any kind, but every file is
   renamed once and the names get longer. Parking is not recommended.
5. **Long paths on Windows.** Keep `maxSlugLength` 64 and set `LongPathsEnabled=1` and
   `core.longpaths=true` once (**recommended**), or cap at 40 (a one-time rename of items
   with long titles; paths stay below 260 without any setup)?
6. **fsync.** Always, per file (**recommended**, revisit if step 9 measures stutter), or only
   on explicit save and close?
7. **Snapshots.** Keep 10 per kind (open, daily, unsaved, disk) in `%LOCALAPPDATA%` /
   `~/.local/share` (**recommended**), with daily snapshots on top of the open snapshot
   (**recommended: yes**)?
8. **`settings.txt` churn.** Move UI state (`lastTab`, `openIndexes`, `viewSettings`,
   `corkSizeFactor`, `folderView`, `outlineViewColumns`) and machine-specific values (`dict`,
   fonts) to per-project QSettings in a later, separate change (**recommended: later**, out
   of this design). Turn `revisions.keep` off for git projects (**recommended**: git is the
   history).
9. **Code location.** Keep the store and `writeFolder` in `version_1.py` (**recommended**:
   the tests' patch points stay), or move them to a Qt-free `folderstore.py` now
   (+0.5 day for the test edits)?
10. **Project repository hygiene:** add `.*.tmp` to `.gitignore` and `* -text` to
    `.gitattributes` yourself (**recommended**). Manuskript creates no files in the
    repository.
11. **Window-activation check** (step 12): add it (**recommended if time allows**). It makes a
    `git pull` in a terminal visible at once.

---

## Appendix: reproduce the prototype

The prototype was built in a temporary folder by scripts that are not kept. Their combined
result is [`prototype.diff`](prototype.diff):

```
mkdir /tmp/proto && git archive 1d7320f | tar -x -C /tmp/proto
cd /tmp/proto && git apply -p1 /path/to/docs/save-design/prototype.diff
QT_QPA_PLATFORM=offscreen python -m pytest -q manuskript/tests
```

Use an isolated `HOME` (and `XDG_CONFIG_HOME`, `XDG_DATA_HOME`) for the test run, as for any
run of the suite.

Results for this document, each on a fresh archive:

- Without the last correction, with the first 12 probes: **632 passed, 8 skipped** (124 s).
- With all corrections and all 14 probes: **634 passed, 8 skipped** (117 s). The patch was
  regenerated from the scripts when this document was added to the repository, applied to a
  fresh archive of `1d7320f`, and the full suite was run again on the result.
- One pitfall: closing a project whose save is blocked by a conflict asks "close without
  saving?" modally, so a test that leaves a conflict must set `projectDirty = False` first.
  Otherwise the fixture's teardown hangs.
- The prototype changes the ghost-character fixture to `ID: 0` and then puts the original
  back, so the patch leaves it unchanged. The implementation must never commit that change
  (step 5).

**In the prototype:**

- the store, `writeFolder` (P1, P3-P7, W1-W4, M1, R1-R6), `forTarget` via `loadableFiles`,
  and the marker policy;
- the linear paths, `charCount` dropped, and the `-ID` rule ignoring case;
- character ID normalization (without the "read IDs win" preference);
- normalized digests and the racy flag;
- the `_retry` predicate, without the per-save budget;
- the normal-save store rule;
- MainWindow and loadSave without snapshot/restore.

**Not in the prototype**, specified above, new code in steps 4-11: L1 (owned area only), L4
(tmp cleanup), the `foreign` set, P2 validation, P8 "added" conflicts, the B8 guard, case
folding and the `ci` probe, the retry budget and `retryable`, the fresh stat, the
`checkWritable` probe, snapshots, and the conflict UI and throttle.
