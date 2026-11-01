#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""
Snapshots: copies of a project in the single-file format (a zip with a MANUSKRIPT entry),
kept outside the project folder, so that what was on disk, or what could not be saved, can
be restored with File > Open and "Save as...".

They are kept in the application's local data folder (writablePath("snapshots"):
~/.local/share/manuskript/manuskript/snapshots on Linux, %LOCALAPPDATA%\\manuskript\\
manuskript\\snapshots on Windows), never in the project folder, which may be in git. Each
project has its own folder there, named after the project folder and a digest of its path.
A snapshot is named after the time it was taken (UTC: daylight saving time and time zones
do not change the order of the names) and its kind:

- "open": what was on disk when the project was opened;
- "daily": the project as saved, once a day;
- "unsaved": the project as it could not be (completely) saved;
- "disk": what was on disk before it was written over or removed.

What is on disk of a project folder: the files Manuskript loads, writes and removes (in
outline/ and characters/, and the project files at the root), whatever their size, and the
other files up to 20 MB each and 50 MB in all; not the dot-folders (.git...).

Text is stored as UTF-8 with LF line endings. Identical consecutive snapshots of a kind are
not written twice, and only the newest 10 of each kind are kept.

Snapshots never stop a project from being opened or saved: every error is logged, and the
functions then return None. (Only the files of an older project are not removed by a save
if takeDisk() cannot keep them, see version_1.)
"""

import datetime
import hashlib
import logging
import os
import re
import string
import tempfile
import time
import zipfile

LOGGER = logging.getLogger(__name__)

KINDS = ("open", "daily", "unsaved", "disk")

# Snapshots kept per kind (and per project)
KEEP = 10

# A daily snapshot is taken by the first save this long after the newest daily snapshot
DAILY = datetime.timedelta(hours=24)

# Of the files outside the project area (see inProjectArea()), those larger than
# MAX_FILE_SIZE are not put into snapshots, nor those beyond MAX_OTHER_SIZE in all (the
# largest are left out first). The files of the project area are always put in.
MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_OTHER_SIZE = 50 * 1024 * 1024

# The files at the root of a project folder that Manuskript writes: version_1.projectFiles
# (which this module does not import, it needs widgets)
PROJECT_FILES = ["MANUSKRIPT", "infos.txt", "summary.txt", "labels.txt", "status.txt",
                 "settings.txt", "plots.xml", "world.opml", "revisions.xml"]

# Kinds of snapshots that are flushed to the disk before they get their name: what they hold
# may exist nowhere else (the files removed next, what could not be saved)
SYNC = ("disk", "unsaved")

# The folder that holds the snapshots of all projects. None: writablePath("snapshots").
# The tests set it to a temporary folder.
root = None

_NAME = re.compile(r"^(\d{8}-\d{6})-(open|daily|unsaved|disk)(?:-(\d+))?\.msk$")
# The temporary file a snapshot is written to before it gets its name
_TMP = re.compile(r"^\.\d{8}-\d{6}-(?:open|daily|unsaved|disk)(?:-\d+)?\.msk\.\w+\.tmp$")
# The temporary files of version_1.writeFile() (.<name>.tmp), left by a crash
_PROJECT_TMP = re.compile(r"^\..+\.tmp$")
_COMMENT = b"Manuskript snapshot, digest "
# Fixed entry dates: the same project gives the same zip
_DATE = (1980, 1, 1, 0, 0, 0)


def now():
    """The time in UTC, without a time zone (the tests replace it)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def rootFolder():
    """The folder that holds the snapshot folders of all projects (created if needed)."""
    if root:
        return root
    from manuskript.functions import writablePath
    return writablePath("snapshots")


def projectRoot(project):
    """The project folder of the project file project (it exists only in folder mode)."""
    return os.path.splitext(os.path.abspath(project))[0]


def _key(path):
    return os.path.normcase(os.path.realpath(path))


def _inside(path, folder):
    """True if path is folder or is inside it (links resolved)."""
    path, folder = _key(path), _key(folder)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def _slug(name):
    # As version_1.slugify(), which this module does not import (it needs widgets)
    return "".join(c if c in string.ascii_letters + string.digits else
                   "_" if c in string.whitespace else "-" for c in name)


def projectFolder(project):
    """
    The folder that holds the snapshots of the project file project:
    <name of the project folder>-<digest of its path>, in rootFolder().
    """
    folder = _key(projectRoot(project))
    digest = hashlib.blake2b(folder.encode("utf-8", "surrogateescape")).hexdigest()
    name = _slug(os.path.basename(os.path.realpath(projectRoot(project))))[:40] or "project"
    return os.path.join(rootFolder(), "{}-{}".format(name, digest[:8]))


def isSnapshot(project):
    """True if the project file project is in the snapshot folder (it is a snapshot)."""
    try:
        return _inside(project, rootFolder())
    except Exception as e:  # The folder cannot be created: nothing is in it
        LOGGER.error("Cannot find the snapshot folder: %s", e)
        return False


###############################################################################
# CONTENT: {entry name (with /): bytes}
###############################################################################

def _text(content):
    """str: UTF-8 with LF line endings."""
    if "\r" in content:
        content = content.replace("\r\n", "\n").replace("\r", "\n")
    return content.encode("utf-8", "replace")


def _data(data):
    """bytes: text (UTF-8) with LF line endings, other files as they are."""
    if b"\r" not in data or b"\0" in data:
        return data
    try:
        return _text(data.decode("utf-8"))
    except UnicodeDecodeError:
        return data


def _entry(content):
    return _text(content) if isinstance(content, str) else _data(content)


def inProjectArea(name):
    """True for the files of a project folder that Manuskript loads, writes and removes (name
    relative to the folder, with /): the files in outline/ and characters/, and the project
    files at the root. A save onto an older project removes them (see version_1)."""
    return name in PROJECT_FILES or name.split("/")[0] in ("outline", "characters")


def _entryName(name):
    """name as a zip entry name. A file name that is not UTF-8 (Linux: a name in another
    encoding, which Python gives with surrogates) cannot be one: its bytes that are not
    UTF-8 are written as %XX."""
    try:
        name.encode("utf-8")
        return name
    except UnicodeEncodeError:
        return "".join("%{:02X}".format(ord(c) - 0xdc00) if "\udc80" <= c <= "\udcff" else
                       "%u{:04X}".format(ord(c)) if "\ud800" <= c <= "\udfff" else c
                       for c in name)


def _walk(folder, notIncluded):
    """Yields (DirEntry, name relative to folder with /) for the regular files in folder, not in
    dot-folders (.git, .svn...). The dot-folders, and the folders and files that cannot be
    listed or read, are put into notIncluded ({name: reason}); the latter are logged."""
    stack = [(folder, "")]
    while stack:
        path, prefix = stack.pop()
        try:
            with os.scandir(path) as it:
                found = list(it)
        except OSError as e:
            if not prefix:
                raise
            LOGGER.warning("Snapshot of %s: cannot list %s: %s", folder, path, e)
            notIncluded[prefix[:-1]] = e.strerror or str(e)
            continue
        for e in found:
            try:
                if e.is_dir(follow_symlinks=False):
                    if e.name[:1] != ".":
                        stack.append((e.path, prefix + e.name + "/"))
                    else:
                        notIncluded[prefix + e.name] = "a hidden folder"
                elif e.is_file():
                    yield e, prefix + e.name
            except OSError as err:
                LOGGER.warning("Snapshot of %s: cannot read %s: %s", folder, e.path, err)
                notIncluded[prefix + e.name] = err.strerror or str(err)


def readFolder(project, read=None, missing=None):
    """
    The files of the project folder of project: those of the project area (inProjectArea())
    whatever their size, the others up to MAX_FILE_SIZE each and MAX_OTHER_SIZE in all (the
    smallest first); not those in dot-folders, nor Manuskript's temporary files
    (.<name>.tmp).
    @param read: {path relative to the folder (os.sep): content (str or bytes)}, what the
    loader has just read: these files are not read again.
    @param missing: a dict, or None. The files and folders of the project area that are not
    included (they cannot be read, or are in a dot-folder) are put there: {name: reason}.
    """
    folder = projectRoot(project)
    read = read or {}
    notIncluded = {}
    entries = {}
    others = []

    def add(name, content):
        entry = _entryName(name)
        if entry != name:
            LOGGER.warning("Snapshot of %s: the name of %r is not UTF-8, it is stored as %s.",
                           project, name, entry)
        if entry in entries:
            LOGGER.warning("Snapshot of %s: %r is not included, another file is stored as %s.",
                           project, name, entry)
            notIncluded[name] = "another file is stored as {}".format(entry)
            return
        entries[entry] = _entry(content)

    for e, name in _walk(folder, notIncluded):
        if _PROJECT_TMP.match(e.name):
            continue
        try:
            if inProjectArea(name):
                content = read.get(name.replace("/", os.sep))
                if content is None:
                    with open(e.path, "rb") as f:
                        content = f.read()
                add(name, content)
            else:
                others.append((e.stat().st_size, name, e.path))
        except OSError as err:
            LOGGER.warning("Snapshot of %s: cannot read %s: %s", project, e.path, err)
            notIncluded[name] = err.strerror or str(err)

    # The other files (notes, images, research...): the large ones would make every snapshot
    # slow and large
    total, left = 0, []
    for size, name, path in sorted(others):
        if size > MAX_FILE_SIZE or total + size > MAX_OTHER_SIZE:
            left.append((name, size))
            continue
        content = read.get(name.replace("/", os.sep))
        try:
            if content is None:
                with open(path, "rb") as f:
                    content = f.read()
        except OSError as err:
            LOGGER.warning("Snapshot of %s: cannot read %s: %s", project, path, err)
            continue
        total += size
        add(name, content)
    if left:
        LOGGER.warning("Snapshot of %s: %d files outside outline/ and characters/ are not "
                       "included (%.1f MB): those larger than %d MB, and the largest beyond "
                       "%d MB in all: %s", project, len(left),
                       sum(size for name, size in left) / (1024 * 1024),
                       MAX_FILE_SIZE // (1024 * 1024), MAX_OTHER_SIZE // (1024 * 1024),
                       ", ".join(name for name, size in left))

    if missing is not None:
        missing.update((name, reason) for name, reason in notIncluded.items()
                       if inProjectArea(name))

    # A file named VERSION would be taken as the version of the single-file format
    if "VERSION" in entries:
        LOGGER.warning("Snapshot of %s: VERSION is not included.", project)
        del entries["VERSION"]
    # The single-file format is recognized by its MANUSKRIPT entry (a folder project by its
    # .msk file)
    version = entries.get("MANUSKRIPT", b"")
    if not version.isdigit() or int(version) < 1:
        entries["MANUSKRIPT"] = b"1"
    return entries


def readZip(project, missing=None):
    """The entries of the single-file project project (all of them: they are the project).
    @param missing: a dict, or None. The entries that cannot be read are put there:
    {name: reason}."""
    entries = {}
    with zipfile.ZipFile(project) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            try:
                entries[info.filename] = _data(zf.read(info))
            except Exception as e:  # A damaged entry (CRC, compression...)
                LOGGER.warning("Snapshot of %s: cannot read %s: %s", project, info.filename, e)
                if missing is not None:
                    missing[info.filename] = str(e)
    return entries


def readProject(project, zip=None, read=None, missing=None):
    """What is on disk of project: its single file if zip (None: if it is a zip file),
    otherwise its folder. See readZip() and readFolder()."""
    if zip is None:
        zip = zipfile.is_zipfile(project)
    return readZip(project, missing) if zip else readFolder(project, read, missing)


def fromFiles(files):
    """The entries of a project as saveProject() serializes it: [(path, str or bytes)]."""
    return {path.replace(os.sep, "/"): _entry(content) for path, content in files}


def digest(entries):
    """A digest of entries, over the sorted (name, digest of the content) pairs."""
    h = hashlib.blake2b(digest_size=16)
    for name in sorted(entries):
        h.update(name.encode("utf-8", "surrogateescape") + b"\0")
        h.update(hashlib.blake2b(entries[name], digest_size=16).digest())
    return h.hexdigest()


###############################################################################
# SNAPSHOT FOLDER
###############################################################################

def snapshots(folder, kind=None):
    """
    The snapshots in folder (of kind), oldest first: [(time, number, kind, file name)].
    Files whose name is not a snapshot name are ignored.

    Snapshots named after a time later than now() count as older than all others: they were
    taken before the clock was set back (or while it was wrong). Otherwise, after such a
    change, the snapshots taken next would count as the oldest, and be removed at once.
    """
    try:
        names = os.listdir(folder)
    except FileNotFoundError:
        return []
    found = []
    for name in names:
        m = _NAME.match(name)
        if not m or kind and m.group(2) != kind:
            continue
        try:
            t = datetime.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
        except ValueError:
            continue
        found.append((t, int(m.group(3) or 1), m.group(2), name))
    current = now()
    return sorted(found, key=lambda s: (s[0] <= current,) + s)


def _digestOf(path):
    try:
        with zipfile.ZipFile(path) as zf:
            comment = zf.comment
    except (OSError, zipfile.BadZipFile) as e:
        LOGGER.warning("Cannot read snapshot %s: %s", path, e)
        return None
    if comment.startswith(_COMMENT):
        return comment[len(_COMMENT):].decode("ascii", "replace")
    return None


def _claim(tmp, folder, stamp, kind):
    """Gives the file tmp in folder the first free snapshot name for stamp and kind (-2, -3...
    on a clash), and returns it. A file that has this name, also one that another Manuskript
    has just written, is never replaced."""
    n = 1
    while True:
        name = "{}-{}{}.msk".format(stamp, kind, "-{}".format(n) if n > 1 else "")
        path = os.path.join(folder, name)
        try:
            if os.name == "nt":
                os.rename(tmp, path)  # Never replaces a file on Windows
                return name
            try:
                os.link(tmp, path)  # Never replaces a file
            except FileExistsError:
                raise
            except OSError:
                # No hard links on this file system (FAT, some network shares...)
                if os.path.lexists(path):
                    raise FileExistsError(path)
                os.replace(tmp, path)
                return name
            try:
                os.remove(tmp)
            except OSError as e:  # It is removed with the old temporary files
                LOGGER.warning("Cannot remove the temporary file %s: %s", tmp, e)
            return name
        except FileExistsError:
            n += 1


def _syncFolder(folder):
    """Flushes the names of the files in folder to the disk (not on Windows, which cannot)."""
    if os.name == "nt":
        return
    try:
        fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as e:  # Some file systems cannot
        LOGGER.debug("Cannot flush the folder %s: %s", folder, e)


def _writeZip(folder, kind, entries, comment, sync=False):
    """Writes entries to a new snapshot of kind in folder, and returns its name. It is written
    to a temporary file that gets its name only once it is complete (and on the disk, if
    sync)."""
    stamp = now().strftime("%Y%m%d-%H%M%S")
    fd, tmp = tempfile.mkstemp(prefix=".{}-{}.msk.".format(stamp, kind), suffix=".tmp",
                               dir=folder)
    try:
        with os.fdopen(fd, "wb") as f:
            with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.comment = comment
                for entry in sorted(entries):
                    info = zipfile.ZipInfo(entry, date_time=_DATE)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    zf.writestr(info, entries[entry], compresslevel=1)
            if sync:
                f.flush()
                os.fsync(f.fileno())
        name = _claim(tmp, folder, stamp, kind)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    if sync:
        _syncFolder(folder)
    return name


def _rotate(folder, kind, written):
    """Removes the snapshots of kind but the newest KEEP, never the one just written
    (written), and the temporary files of snapshots that were not completed (a crash) and
    are older than an hour."""
    for t, n, k, name in snapshots(folder, kind)[:-KEEP]:
        if name == written:
            continue
        try:
            os.remove(os.path.join(folder, name))
        except OSError as e:
            LOGGER.warning("Cannot remove the old snapshot %s: %s", name, e)
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        try:
            if _TMP.match(name) and os.path.getmtime(path) < time.time() - 3600:
                os.remove(path)
        except OSError as e:
            LOGGER.warning("Cannot remove the temporary file %s: %s", path, e)


def _take(project, kind, content, due=None, problems=None):
    """
    Writes a snapshot of kind of project with the entries content(missing) returns (it puts
    the files of the project it cannot include into missing: {name: reason}), unless they are
    the same as in the newest snapshot of this kind.
    Returns (written, kept): the path of the snapshot written, or None; and the path of the
    snapshot that holds the whole content: this one, or the newest one if it is the same.
    kept is None if a file could not be included, on an error, or if the snapshot is not due.
    @param due: if given, due(folder) tells whether the snapshot is to be taken.
    @param problems: a list, or None. If the content is not kept, why is appended there.
    """
    problems = [] if problems is None else problems
    try:
        start = time.perf_counter()
        if isSnapshot(project):
            LOGGER.debug("No snapshot of %s: it is a snapshot.", project)
            problems.append("{} is a snapshot".format(project))
            return None, None
        folder = projectFolder(project)
        if _inside(folder, projectRoot(project)):
            LOGGER.error("No snapshot of %s: the snapshot folder %s would be inside the "
                         "project folder.", project, folder)
            problems.append("The snapshot folder {} would be inside the project folder"
                            .format(folder))
            return None, None
        if due and not due(folder):
            return None, None
        missing = {}
        entries = content(missing)
        for name, reason in sorted(missing.items()):
            LOGGER.warning("The %s snapshot of %s does not include %s (%s).",
                           kind, project, name, reason)
            problems.append("{} ({})".format(name, reason))
        d = digest(entries)
        newest = snapshots(folder, kind)[-1:]
        if newest and _digestOf(os.path.join(folder, newest[0][3])) == d:
            LOGGER.debug("No %s snapshot of %s: it has not changed since %s.",
                         kind, project, newest[0][3])
            return None, (None if missing else os.path.join(folder, newest[0][3]))
        os.makedirs(folder, exist_ok=True)
        name = _writeZip(folder, kind, entries, _COMMENT + d.encode("ascii"), kind in SYNC)
        path = os.path.join(folder, name)
        try:
            _rotate(folder, kind, name)
        except OSError as e:
            LOGGER.warning("Cannot remove the old snapshots in %s: %s", folder, e)
        LOGGER.info("Snapshot of %s: %s (%d files, %.0f ms).", project, path, len(entries),
                    (time.perf_counter() - start) * 1000)
        return path, (None if missing else path)
    except OSError as e:
        LOGGER.error("Cannot take the %s snapshot of %s: %s", kind, project, e)
        problems.append(str(e))
    except Exception as e:
        LOGGER.exception("Cannot take the %s snapshot of %s.", kind, project)
        problems.append(repr(e))
    return None, None


###############################################################################
# THE SNAPSHOTS
###############################################################################

def takeOpen(project, zip, read=None):
    """After project has been opened: what is on disk (see readProject())."""
    return _take(project, "open", lambda missing: readProject(project, zip, read, missing))[0]


def takeDisk(project, zip=None, problems=None):
    """
    Before what is on disk of project (see readProject()) is written over or removed.
    Returns the path of the snapshot that holds it: the one written, or the newest disk
    snapshot if it has not changed since. Returns None if it could not be taken, or if a file
    of the project area (inProjectArea()) or an entry of the single file could not be put
    into it; the snapshot is then written with the other files.
    @param problems: a list, or None. Why None is returned is appended there.
    """
    return _take(project, "disk", lambda missing: readProject(project, zip, None, missing),
                 problems=problems)[1]


def takeDaily(project, files):
    """After project has been saved as files ([(path, content)], as saveProject() serializes
    it): if the newest daily snapshot of project is older than DAILY (or there is none)."""
    def due(folder):
        current = now()
        times = [t for t, n, k, name in snapshots(folder, "daily") if t <= current]
        return not times or current - max(times) > DAILY
    return _take(project, "daily", lambda missing: fromFiles(files), due)[0]


def takeUnsaved(project, files):
    """After project could not be saved (completely) as files ([(path, content)])."""
    return _take(project, "unsaved", lambda missing: fromFiles(files))[0]
