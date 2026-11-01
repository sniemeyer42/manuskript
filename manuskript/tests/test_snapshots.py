#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Snapshots: zip copies of a project outside its folder (manuskript/snapshots.py)."""

import datetime
import hashlib
import logging
import os
import re
import time
import zipfile

import pytest

from manuskript import settings, snapshots
from manuskript.enums import Outline
from manuskript.load_save import version_1
from manuskript.tests.conftest import closePreviousProject
from manuskript.tests.load_save.helpers import copySample, shownDialogs

T0 = datetime.datetime(2026, 11, 1, 12, 30, 5)


@pytest.fixture
def clock(monkeypatch):
    """The time snapshots see: clock[0], which the test sets."""
    t = [T0]
    monkeypatch.setattr(snapshots, "now", lambda: t[0])
    return t


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content if isinstance(content, bytes) else content.encode("utf-8"))


def makeProject(tmp_path, files, name="My Novel"):
    """A project folder with files ({path with /: content}). Returns its .msk file."""
    project = str(tmp_path / (name + ".msk"))
    write(project, "1")
    for path, content in files.items():
        write(os.path.join(project[:-4], *path.split("/")), content)
    return project


def entries(snapshot):
    """{name: content} of a snapshot."""
    with zipfile.ZipFile(snapshot) as zf:
        return {i.filename: zf.read(i) for i in zf.infolist()}


def names(project, kind=None):
    return [s[3] for s in snapshots.snapshots(snapshots.projectFolder(project), kind)]


def serialized(MW, tmp_path, name):
    """What saveProject() writes for the current project: {name: content}."""
    current, saveToZip = MW.currentProject, settings.saveToZip
    target = str(tmp_path / name)
    settings.saveToZip = True  # It is in settings.txt
    MW.currentProject = target
    try:
        assert version_1.saveProject(zip=True)
    finally:
        MW.currentProject, settings.saveToZip = current, saveToZip
    return entries(target)


###############################################################################
# THE MODULE
###############################################################################

def test_location_and_names(tmp_path, snapshotRoot, clock):
    """One folder per project, named after its folder and a digest of its path; snapshots
    named after the time and the kind, without colons; a number on a clash."""
    project = makeProject(tmp_path, {"MANUSKRIPT": "1", "infos.txt": "Title: A\n"})
    digest = hashlib.blake2b(os.path.normcase(os.path.realpath(project[:-4]))
                             .encode("utf-8")).hexdigest()[:8]
    folder = os.path.join(snapshotRoot, "My_Novel-" + digest)
    assert snapshots.projectFolder(project) == folder

    assert snapshots.takeDisk(project) == os.path.join(folder, "20261101-123005-disk.msk")
    write(os.path.join(project[:-4], "infos.txt"), "Title: B\n")
    assert snapshots.takeDisk(project) == os.path.join(folder, "20261101-123005-disk-2.msk")
    write(os.path.join(project[:-4], "infos.txt"), "Title: C\n")
    assert snapshots.takeDisk(project) == os.path.join(folder, "20261101-123005-disk-3.msk")
    assert snapshots.takeOpen(project, zip=False) == \
        os.path.join(folder, "20261101-123005-open.msk")
    clock[0] += datetime.timedelta(seconds=1)
    write(os.path.join(project[:-4], "infos.txt"), "Title: D\n")
    assert snapshots.takeDisk(project) == os.path.join(folder, "20261101-123006-disk.msk")
    assert names(project, "disk") == ["20261101-123005-disk.msk", "20261101-123005-disk-2.msk",
                                      "20261101-123005-disk-3.msk", "20261101-123006-disk.msk"]
    assert entries(os.path.join(folder, "20261101-123005-disk-2.msk"))["infos.txt"] == \
        b"Title: B\n"

    # The same project through a link has the same folder, another one with the same
    # name another folder. Long names are cut.
    os.symlink(project[:-4], str(tmp_path / "Link"))
    assert snapshots.projectFolder(str(tmp_path / "Link.msk")) == folder
    other = str(tmp_path / "other" / "My Novel.msk")
    assert os.path.dirname(snapshots.projectFolder(other)) == snapshotRoot
    assert snapshots.projectFolder(other) != folder
    name = "Grüße an die Außerirdischen - ein langer Titel"
    assert re.match(r"^Gr--e_an_die_Au-erirdischen_-_ein_langer-[0-9a-f]{8}$",
                    os.path.basename(snapshots.projectFolder("/x/{}.msk".format(name))))
    assert version_1.slugify(name)[:40] == "Gr--e_an_die_Au-erirdischen_-_ein_langer"


def test_single_file_format(tmp_path, snapshotRoot, clock):
    """A snapshot is a single-file project: a zip with MANUSKRIPT, POSIX names, deflate,
    fixed dates, and the digest in its comment. It is written through a temporary file."""
    project = makeProject(tmp_path, {"MANUSKRIPT": "1", "outline/0-Part/folder.txt": "x\n"})
    path = snapshots.takeDisk(project)
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        assert zf.comment.startswith(b"Manuskript snapshot, digest ")
        assert zf.comment.endswith(snapshots.digest(entries(path)).encode())
    assert [i.filename for i in infos] == ["MANUSKRIPT", "outline/0-Part/folder.txt"]
    assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in infos)
    assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in infos)
    assert os.listdir(os.path.dirname(path)) == [os.path.basename(path)]

    # The same content gives the same file
    with open(path, "rb") as f:
        first = f.read()
    os.remove(path)
    with open(snapshots.takeDisk(project), "rb") as f:
        assert f.read() == first

    # A snapshot that cannot be completed leaves nothing behind
    os.remove(path)

    def writestr(*args, **kwargs):
        raise OSError(28, "No space left on device")

    realWritestr = zipfile.ZipFile.writestr
    zipfile.ZipFile.writestr = writestr
    try:
        assert snapshots.takeDisk(project) is None
    finally:
        zipfile.ZipFile.writestr = realWritestr
    assert os.listdir(os.path.dirname(path)) == []


def test_content_of_a_project_folder(tmp_path, snapshotRoot, monkeypatch, caplog):
    """Every regular file, text with LF line endings, other files as they are; not the
    dot-folders, Manuskript's temporary files or too large files outside outline/ and
    characters/. MANUSKRIPT is added if needed, VERSION left out (the single-file format
    would take it as its version)."""
    png = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR"
    latin1 = "Été\r\n".encode("latin-1")
    project = makeProject(tmp_path, {
        "infos.txt": "Title: A\r\nAuthor: B\r\n",
        "outline/0-Scene.md": "One\rTwo\r\nThree\n",
        "outline/.0-Scene.md.tmp": "half written",
        "plots.xml": "<?xml version='1.0'?>\r\n<root/>\r\n",
        "world.opml": "<opml/>\n",
        "cover.png": png,
        "characters/0-Latin.txt": latin1,
        ".gitignore": ".*.tmp\r\n",
        ".git/config": "[core]\n",
        "notes/.svn/entries": "x",
        "notes/.hg/x": "x",
        "notes/idea.txt": "Idea",
        "big.txt": "x" * 101,
        "outline/1-Long.md": "y" * 101,
        "VERSION": "3",
    })
    monkeypatch.setattr(snapshots, "MAX_FILE_SIZE", 100)
    caplog.set_level(logging.WARNING, logger=snapshots.LOGGER.name)
    assert entries(snapshots.takeDisk(project)) == {
        "MANUSKRIPT": b"1",
        "infos.txt": b"Title: A\nAuthor: B\n",
        "outline/0-Scene.md": b"One\nTwo\nThree\n",
        "plots.xml": b"<?xml version='1.0'?>\n<root/>\n",
        "world.opml": b"<opml/>\n",
        "cover.png": png,
        "characters/0-Latin.txt": latin1,
        ".gitignore": b".*.tmp\n",
        "notes/idea.txt": b"Idea",
        "outline/1-Long.md": b"y" * 101,
    }
    assert "1 files outside outline/ and characters/ are not included" in caplog.text
    assert any(r.getMessage().endswith(" in all: big.txt") for r in caplog.records)


def test_size_limits(tmp_path, snapshotRoot, monkeypatch, caplog):
    """Outside outline/ and characters/, files up to MAX_FILE_SIZE each and MAX_OTHER_SIZE in
    all, the smallest first. The files of the project are always included."""
    project = makeProject(tmp_path, {
        "notes/a.txt": "a" * 50, "notes/b.txt": "b" * 100, "c.pdf": "c" * 120,
        "notes/d.txt": "d" * 90, "e.png": "e" * 80,
        "infos.txt": "i" * 300, "characters/0-Big.txt": "c" * 300,
        "outline/0-Part/image.png": "p" * 300,
    })
    monkeypatch.setattr(snapshots, "MAX_FILE_SIZE", 100)
    monkeypatch.setattr(snapshots, "MAX_OTHER_SIZE", 250)
    caplog.set_level(logging.WARNING, logger=snapshots.LOGGER.name)
    assert sorted(entries(snapshots.takeOpen(project, zip=False))) == [
        "MANUSKRIPT", "characters/0-Big.txt", "e.png", "infos.txt", "notes/a.txt",
        "notes/d.txt", "outline/0-Part/image.png"]
    assert "2 files outside outline/ and characters/ are not included (0.0 MB)" in caplog.text
    assert any(r.getMessage().endswith(" in all: notes/b.txt, c.pdf") for r in caplog.records)
    assert [f for f in snapshots.PROJECT_FILES if f not in version_1.projectFiles] == []
    assert [f for f in version_1.projectFiles if f not in snapshots.PROJECT_FILES] == []


def test_file_names_that_are_not_utf8(tmp_path, snapshotRoot, caplog):
    """A file name in another encoding (Linux) is stored with %XX for its bytes that are not
    UTF-8. If another file has that name, one of them is not included."""
    if os.name == "nt":
        pytest.skip("file names are Unicode")
    project = makeProject(tmp_path, {"infos.txt": "A", "outline/x%E9.md": "Real"})
    folder = os.fsencode(project[:-4])
    try:
        write(folder + b"/outline/caf\xe9.md", b"Latin-1 name")
        write(folder + b"/notes/r\xe9sum\xe9.txt", b"Notes")
    except OSError:
        pytest.skip("the file system does not take such names")
    caplog.set_level(logging.WARNING, logger=snapshots.LOGGER.name)
    content = entries(snapshots.takeOpen(project, zip=False))
    assert content["outline/caf%E9.md"] == b"Latin-1 name"
    assert content["notes/r%E9sum%E9.txt"] == b"Notes"
    assert "is not UTF-8, it is stored as outline/caf%E9.md" in caplog.text
    assert snapshots.takeDisk(project)

    write(folder + b"/outline/x\xe9.md", b"Latin-1 too")
    problems = []
    assert snapshots.takeDisk(project, problems=problems) is None
    assert problems in [["outline/x%E9.md (another file is stored as outline/x%E9.md)"],
                        ["outline/x\udce9.md (another file is stored as outline/x%E9.md)"]]
    content = entries(os.path.join(snapshots.projectFolder(project), names(project, "disk")[-1]))
    assert content["outline/x%E9.md"] in [b"Real", b"Latin-1 too"]
    assert snapshots.takeOpen(project, zip=False)


def test_rotation(tmp_path, snapshotRoot, clock):
    """The newest 10 of each kind are kept. Only snapshots are removed (and their own
    temporary files once they are old)."""
    project = makeProject(tmp_path, {"infos.txt": "0"})
    folder = snapshots.projectFolder(project)
    snapshots.takeOpen(project, zip=False)
    os.makedirs(folder, exist_ok=True)
    others = ["notes.txt", "20261101-123005-other.msk", "20261101-1230-disk.msk",
              ".20261101-123004-disk.msk.recent.tmp"]
    for name in others:
        write(os.path.join(folder, name), "x")
    old = os.path.join(folder, ".20261101-123004-disk.msk.abc_12.tmp")
    write(old, "x")
    os.utime(old, (time.time() - 7200, time.time() - 7200))

    for i in range(1, 13):
        clock[0] = T0 + datetime.timedelta(minutes=i)
        write(os.path.join(project[:-4], "infos.txt"), str(i))
        assert snapshots.takeDisk(project)
    disk = names(project, "disk")
    assert disk == ["20261101-12{:02d}05-disk.msk".format(30 + i) for i in range(3, 13)]
    assert entries(os.path.join(folder, disk[0]))["infos.txt"] == b"3"
    assert names(project, "open") == ["20261101-123005-open.msk"]
    assert sorted(os.listdir(folder)) == sorted(others + disk + ["20261101-123005-open.msk"])


def test_dedup(tmp_path, snapshotRoot, clock):
    """A snapshot that is the same as the newest one of its kind is not written (takeDisk()
    then returns the newest one, which holds what is on disk)."""
    project = makeProject(tmp_path, {"infos.txt": "A\n"})
    first = snapshots.takeDisk(project)
    assert first
    assert snapshots.takeDisk(project) == first
    # Only the content counts (not the time, nor the line endings)
    clock[0] += datetime.timedelta(hours=1)
    write(os.path.join(project[:-4], "infos.txt"), "A\r\n")
    assert snapshots.takeDisk(project) == first
    assert names(project, "disk") == [os.path.basename(first)]
    # Other kinds have their own
    assert snapshots.takeOpen(project, zip=False)
    files = [("MANUSKRIPT", "1"), ("infos.txt", "A")]
    assert snapshots.takeUnsaved(project, files)
    assert snapshots.takeUnsaved(project, files) is None
    assert snapshots.takeOpen(project, zip=False) is None
    # Compared with the newest only
    write(os.path.join(project[:-4], "infos.txt"), "B")
    second = snapshots.takeDisk(project)
    write(os.path.join(project[:-4], "infos.txt"), "A\n")
    third = snapshots.takeDisk(project)
    assert len({first, second, third}) == 3
    assert entries(third) == entries(first)
    # A renamed file is a change
    os.rename(os.path.join(project[:-4], "infos.txt"), os.path.join(project[:-4], "infos2.txt"))
    assert snapshots.takeDisk(project) not in [first, second, third, None]
    assert len(names(project, "disk")) == 4


def test_disk_snapshot_holds_the_whole_project_or_is_none(tmp_path, snapshotRoot, monkeypatch):
    """takeDisk() returns None if a file in outline/ or characters/, or a project file, is not
    in the snapshot (it is still written with the other files), or if no snapshot can be
    written. It tells why."""
    project = makeProject(tmp_path, {"infos.txt": "A", "outline/0-Scene.md": "x" * 101,
                                     "notes.txt": "y" * 101})
    monkeypatch.setattr(snapshots, "MAX_FILE_SIZE", 100)
    path = snapshots.takeDisk(project)
    assert sorted(entries(path)) == ["MANUSKRIPT", "infos.txt", "outline/0-Scene.md"]

    # A file that cannot be read, a hidden folder
    write(os.path.join(project[:-4], "characters", ".backup", "0-Old.txt"), "Old")
    write(os.path.join(project[:-4], "characters", "1-Locked.txt"), "Locked")
    write(os.path.join(project[:-4], "characters", "2-New.txt"), "New")
    write(os.path.join(project[:-4], ".git", "HEAD"), "ref")
    realOpen = open

    def openFile(f, *args):
        if os.path.basename(f) == "1-Locked.txt":
            raise PermissionError(13, "Permission denied", f)
        return realOpen(f, *args)

    monkeypatch.setattr(snapshots, "open", openFile, raising=False)
    problems = []
    assert snapshots.takeDisk(project, problems=problems) is None
    assert problems == ["characters/.backup (a hidden folder)",
                        "characters/1-Locked.txt (Permission denied)"]
    [first, second] = names(project, "disk")
    assert sorted(entries(os.path.join(snapshots.projectFolder(project), second))) == [
        "MANUSKRIPT", "characters/2-New.txt", "infos.txt", "outline/0-Scene.md"]
    # The same again: it is not written again, and still incomplete
    assert snapshots.takeDisk(project) is None
    assert len(names(project, "disk")) == 2
    # But the open snapshot is taken
    assert snapshots.takeOpen(project, zip=False)
    monkeypatch.setattr(snapshots, "open", realOpen, raising=False)
    os.remove(os.path.join(project[:-4], "characters", ".backup", "0-Old.txt"))
    os.rmdir(os.path.join(project[:-4], "characters", ".backup"))
    assert snapshots.takeDisk(project)

    # The snapshot folder cannot be created
    write(str(tmp_path / "file"), "not a folder")
    monkeypatch.setattr(snapshots, "root", str(tmp_path / "file" / "snapshots"))
    problems = []
    assert snapshots.takeDisk(project, problems=problems) is None
    # On Windows the message quotes the path with doubled backslashes
    assert len(problems) == 1
    assert str(tmp_path / "file") in problems[0].replace("\\\\", "\\")


def test_clock_set_back(tmp_path, snapshotRoot, clock):
    """Snapshots named after a time later than now() count as the oldest. After the clock
    has been set back (or was ahead), new snapshots are kept, those of the "future" are
    removed first, and daily snapshots are taken."""
    project = makeProject(tmp_path, {"infos.txt": "0"})
    folder = snapshots.projectFolder(project)
    for i in range(10):
        clock[0] = T0 + datetime.timedelta(hours=1, minutes=i)
        write(os.path.join(project[:-4], "infos.txt"), str(i))
        assert snapshots.takeOpen(project, zip=False)
    future = names(project, "open")
    assert future[0] == "20261101-133005-open.msk"

    clock[0] = T0
    write(os.path.join(project[:-4], "infos.txt"), "back")
    path = snapshots.takeOpen(project, zip=False)
    assert os.path.isfile(path)
    assert names(project, "open") == future[1:] + [os.path.basename(path)]
    # Compared with the snapshot just taken
    assert snapshots.takeOpen(project, zip=False) is None
    write(os.path.join(project[:-4], "infos.txt"), "9")
    clock[0] += datetime.timedelta(seconds=1)
    assert snapshots.takeOpen(project, zip=False)
    assert names(project, "open") == future[2:] + [os.path.basename(path),
                                                   "20261101-123006-open.msk"]

    # Daily: one of the "future" does not count
    files = [("MANUSKRIPT", "1"), ("infos.txt", "A")]
    clock[0] = datetime.datetime(2099, 1, 1)
    assert snapshots.takeDaily(project, files)
    clock[0] = T0
    assert snapshots.takeDaily(project, files[:1])
    clock[0] = T0 + datetime.timedelta(hours=23)
    assert snapshots.takeDaily(project, files) is None
    clock[0] = T0 + datetime.timedelta(hours=24, seconds=1)
    assert snapshots.takeDaily(project, files)
    assert names(project, "daily") == ["20990101-000000-daily.msk", "20261101-123005-daily.msk",
                                       "20261102-123006-daily.msk"]
    assert sorted(os.listdir(folder)) == sorted(names(project))


def test_names_are_in_utc():
    t = snapshots.now()
    assert t.tzinfo is None
    utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    assert abs(t - utc) < datetime.timedelta(minutes=1)


def test_existing_names_are_never_replaced(tmp_path, snapshotRoot, clock, monkeypatch):
    """Another Manuskript may write a snapshot with the same name while this one is being
    written: neither replaces the other."""
    project = makeProject(tmp_path, {"infos.txt": "A"})
    folder = snapshots.projectFolder(project)
    os.makedirs(folder)
    realClaim = snapshots._claim

    def claim(tmp, folder, stamp, kind):
        write(os.path.join(folder, "{}-{}.msk".format(stamp, kind)), "The other one")
        return realClaim(tmp, folder, stamp, kind)

    monkeypatch.setattr(snapshots, "_claim", claim)
    files = [("MANUSKRIPT", "1"), ("infos.txt", "A")]
    path = snapshots.takeUnsaved(project, files)
    assert path == os.path.join(folder, "20261101-123005-unsaved-2.msk")
    assert entries(path) == {"MANUSKRIPT": b"1", "infos.txt": b"A"}
    with open(os.path.join(folder, "20261101-123005-unsaved.msk"), "rb") as f:
        assert f.read() == b"The other one"

    # A file system without hard links
    def link(*args):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(snapshots.os, "link", link)
    path = snapshots.takeUnsaved(project, files[:1])
    assert path == os.path.join(folder, "20261101-123005-unsaved-3.msk")
    assert entries(path) == {"MANUSKRIPT": b"1"}
    assert sorted(os.listdir(folder)) == sorted(names(project))


def test_disk_and_unsaved_snapshots_are_flushed(tmp_path, snapshotRoot, clock, monkeypatch):
    """Before it gets its name (and its folder after that, on POSIX): they may hold what
    exists nowhere else."""
    project = makeProject(tmp_path, {"infos.txt": "A"})
    calls = []
    realFsync, realClaim = os.fsync, snapshots._claim
    monkeypatch.setattr(snapshots.os, "fsync", lambda fd: calls.append("fsync") or realFsync(fd))
    monkeypatch.setattr(snapshots, "_claim", lambda *args: calls.append("name") or
                        realClaim(*args))
    synced = ["fsync", "name"] + (["fsync"] if os.name != "nt" else [])
    assert snapshots.takeOpen(project, zip=False)
    assert snapshots.takeDaily(project, [("infos.txt", "B")])
    assert calls == ["name", "name"]
    calls.clear()
    assert snapshots.takeDisk(project)
    assert calls == synced
    calls.clear()
    assert snapshots.takeUnsaved(project, [("infos.txt", "B")])
    assert calls == synced


###############################################################################
# OPEN
###############################################################################

def crlf(folder):
    """Gives all text files in folder CRLF line endings."""
    for dirpath, dirnames, filenames in os.walk(folder):
        for f in filenames:
            path = os.path.join(dirpath, f)
            with open(path, "rb") as fo:
                content = fo.read()
            with open(path, "wb") as fo:
                fo.write(content.replace(b"\n", b"\r\n"))


@pytest.mark.parametrize("lineEndings", ["LF", "CRLF"])
def test_open_snapshot_of_a_project_folder(MW, tmp_path, snapshotRoot, monkeypatch,
                                           lineEndings):
    """Opening a project takes an "open" snapshot of what is on disk. It opens like the
    project folder: it gives the same project."""
    closePreviousProject(MW)
    path = copySample(tmp_path)
    if lineEndings == "CRLF":
        crlf(path[:-4])
    MW.loadProject(path)
    assert MW.currentProject == path
    expected = serialized(MW, tmp_path, "expected.msk")
    [name] = names(path)
    assert name.endswith("-open.msk")
    snapshot = os.path.join(snapshots.projectFolder(path), name)
    content = entries(snapshot)
    assert not any(b"\r" in c for c in content.values())
    with open(os.path.join(path[:-4], "outline", "0-Jerusalem", "folder.txt"), "rb") as f:
        assert content["outline/0-Jerusalem/folder.txt"] == f.read().replace(b"\r\n", b"\n")

    closePreviousProject(MW)
    shown = shownDialogs(monkeypatch)
    MW.loadProject(snapshot)
    try:
        assert MW.currentProject == snapshot
        assert shown == []
        assert serialized(MW, tmp_path, "fromSnapshot.msk") == expected
        # A snapshot has no snapshots
        assert sorted(os.listdir(snapshotRoot)) == sorted(
            os.path.basename(snapshots.projectFolder(str(tmp_path / n)))
            for n in ["book-of-acts.msk", "expected.msk", "fromSnapshot.msk"])
    finally:
        closePreviousProject(MW)


def test_open_snapshot_reuses_what_was_read(MW, tmp_path, monkeypatch):
    """The files the loader has read are not read again for the snapshot."""
    closePreviousProject(MW)
    path = copySample(tmp_path)
    write(os.path.join(path[:-4], ".gitignore"), ".*.tmp\n")
    opened = []
    monkeypatch.setattr(snapshots, "open", lambda f, *args: opened.append(f) or open(f, *args),
                        raising=False)
    MW.loadProject(path)
    try:
        assert MW.currentProject == path
        assert opened == [os.path.join(path[:-4], ".gitignore")]
        assert ".gitignore" in entries(os.path.join(snapshots.projectFolder(path),
                                                    names(path)[0]))
    finally:
        closePreviousProject(MW)


def test_open_snapshot_of_a_single_file_project(MW, tmp_path, clock):
    """A single-file project: the snapshot holds its entries, and opens like it."""
    closePreviousProject(MW)
    path = copySample(tmp_path)
    MW.loadProject(path)
    zipped = str(tmp_path / "zipped.msk")
    serialized(MW, tmp_path, "zipped.msk")
    closePreviousProject(MW)

    MW.loadProject(zipped)
    try:
        assert MW.currentProject == zipped
        expected = serialized(MW, tmp_path, "expected.msk")
    finally:
        closePreviousProject(MW)
    [name] = names(zipped, "open")
    snapshot = os.path.join(snapshots.projectFolder(zipped), name)
    assert entries(snapshot) == entries(zipped)

    MW.loadProject(snapshot)
    try:
        assert MW.currentProject == snapshot
        assert serialized(MW, tmp_path, "fromSnapshot.msk") == expected
    finally:
        closePreviousProject(MW)


def test_failed_open_takes_no_snapshot(MW, tmp_path, snapshotRoot, monkeypatch):
    closePreviousProject(MW)
    path = copySample(tmp_path)
    os.chmod(os.path.join(path[:-4], "settings.txt"), 0)
    if os.access(os.path.join(path[:-4], "settings.txt"), os.R_OK):
        pytest.skip("cannot make a file unreadable")
    shownDialogs(monkeypatch)
    try:
        MW.loadProject(path)
        assert MW.currentProject is None
        assert os.listdir(snapshotRoot) == []
    finally:
        os.chmod(os.path.join(path[:-4], "settings.txt"), 0o644)


###############################################################################
# DAILY
###############################################################################

def test_daily_snapshot(MW, tmp_path, clock):
    """At the end of the first successful save more than 24 h after the newest daily snapshot
    (or the first one, if there is none): the project as it is saved. Opening the project
    does not put it off."""
    closePreviousProject(MW)
    path = copySample(tmp_path)
    MW.loadProject(path)
    try:
        assert names(path) == ["20261101-123005-open.msk"]
        scene = MW.mdlOutline.rootItem.child(0).child(0).child(0)

        clock[0] = T0 + datetime.timedelta(hours=1)
        MW.mdlOutline.setData(scene.index(Outline.text), "Day 1")
        assert MW.saveDatas()
        assert names(path, "daily") == ["20261101-133005-daily.msk"]
        daily = entries(os.path.join(snapshots.projectFolder(path), names(path, "daily")[0]))
        with open(os.path.join(path[:-4], scene._lastPath), "rb") as f:
            assert daily[scene._lastPath.replace(os.sep, "/")] == f.read()
        assert b"Day 1" in daily[scene._lastPath.replace(os.sep, "/")]
        assert daily["MANUSKRIPT"] == b"1"

        clock[0] = T0 + datetime.timedelta(hours=24)
        MW.mdlOutline.setData(scene.index(Outline.text), "Day 1, later")
        assert MW.saveDatas()
        assert len(names(path, "daily")) == 1

        # Opened again
        closePreviousProject(MW)
        MW.loadProject(path)
        assert names(path, "open") == ["20261101-123005-open.msk", "20261102-123005-open.msk"]
        scene = MW.mdlOutline.rootItem.child(0).child(0).child(0)
        clock[0] = T0 + datetime.timedelta(hours=25, seconds=1)
        MW.mdlOutline.setData(scene.index(Outline.text), "Day 2")
        assert MW.saveDatas()
        assert names(path, "daily") == ["20261101-133005-daily.msk", "20261102-133006-daily.msk"]

        # Not when it has not changed
        clock[0] = T0 + datetime.timedelta(hours=74)
        assert MW.saveDatas()
        assert len(names(path, "daily")) == 2
    finally:
        closePreviousProject(MW)


def test_daily_snapshots_of_a_project_opened_often(tmp_path, snapshotRoot, clock):
    """Opened and saved three times a day for 15 days: the open snapshots go back 3 days, the
    daily ones (one every 24 h at most) 12 days."""
    project = makeProject(tmp_path, {"infos.txt": "0"})
    for day in range(15):
        for hour in (8, 14, 20):
            clock[0] = datetime.datetime(2026, 11, 1 + day, hour)
            write(os.path.join(project[:-4], "infos.txt"), "{} {}".format(day, hour))
            assert snapshots.takeOpen(project, zip=False)
            clock[0] += datetime.timedelta(hours=1)
            snapshots.takeDaily(project, [("infos.txt", "{} {} saved".format(day, hour))])
    assert names(project, "open")[0] == "20261112-200000-open.msk"
    assert names(project, "daily") == [
        "20261103-210000-daily.msk", "20261105-090000-daily.msk", "20261106-150000-daily.msk",
        "20261107-210000-daily.msk", "20261109-090000-daily.msk", "20261110-150000-daily.msk",
        "20261111-210000-daily.msk", "20261113-090000-daily.msk", "20261114-150000-daily.msk",
        "20261115-210000-daily.msk"]


def test_daily_snapshot_of_a_new_project(MW, tmp_path, clock):
    """A new project has no snapshot yet: its first save takes one."""
    closePreviousProject(MW)
    path = str(tmp_path / "new.msk")
    MW.welcome.createFile(path, overwrite=True)
    try:
        assert MW.currentProject == path
        assert names(path) == []
        assert MW.saveDatas()
        assert names(path) == ["20261101-123005-daily.msk"]
    finally:
        closePreviousProject(MW)


###############################################################################
# ERRORS
###############################################################################

def test_errors_never_block_opening_or_saving(MW, tmp_path, monkeypatch, caplog):
    """A snapshot that cannot be written is logged; the project is opened and saved."""
    closePreviousProject(MW)
    write(str(tmp_path / "file"), "not a folder")
    monkeypatch.setattr(snapshots, "root", str(tmp_path / "file" / "snapshots"))
    path = copySample(tmp_path)
    caplog.set_level(logging.ERROR, logger=snapshots.LOGGER.name)
    MW.loadProject(path)
    try:
        assert MW.currentProject == path
        assert "Cannot take the open snapshot of {}".format(path) in caplog.text
        scene = MW.mdlOutline.rootItem.child(0).child(0).child(0)
        MW.mdlOutline.setData(scene.index(Outline.text), "Saved")
        new = str(tmp_path / "new.msk")
        assert MW.saveDatas(new)  # No snapshot yet: a daily one is due
        assert "Cannot take the daily snapshot of {}".format(new) in caplog.text
    finally:
        closePreviousProject(MW)

    # Not even a bug
    def digest(entries):
        raise ValueError("bug")

    monkeypatch.setattr(snapshots, "root", str(tmp_path / "snapshots"))
    monkeypatch.setattr(snapshots, "digest", digest)
    caplog.clear()
    MW.loadProject(path)
    try:
        assert MW.currentProject == path
        assert "ValueError: bug" in caplog.text
        assert MW.saveDatas()
    finally:
        closePreviousProject(MW)


def test_never_inside_the_project(MW, tmp_path, monkeypatch, caplog):
    """Snapshots are never written into the project folder (which may be in git)."""
    closePreviousProject(MW)
    path = copySample(tmp_path)
    before = sorted(os.listdir(path[:-4]))
    monkeypatch.setattr(snapshots, "root", os.path.join(path[:-4], "snapshots"))
    caplog.set_level(logging.ERROR, logger=snapshots.LOGGER.name)
    MW.loadProject(path)
    try:
        assert MW.currentProject == path
        assert MW.saveDatas()
        assert "would be inside the project folder" in caplog.text
    finally:
        closePreviousProject(MW)
    assert sorted(os.listdir(path[:-4])) == before
    assert snapshots.takeDisk(path) is None
    assert sorted(os.listdir(path[:-4])) == before
