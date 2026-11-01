#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""File > Save as...: if the project cannot be saved there, it stays where it was."""

import errno
import os
import shutil
import sys
import zipfile

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from manuskript import settings
from manuskript.enums import Character, Outline
from manuskript.load_save import version_1
from manuskript.tests.conftest import closePreviousProject
from manuskript.tests.load_save.helpers import copySample, shownDialogs


def makeReadOnly(folder):
    """Makes folder read-only, skips the test if that has no effect (root, Windows)."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root can write to read-only folders")
    os.makedirs(folder, exist_ok=True)
    os.chmod(folder, 0o555)
    if os.access(folder, os.W_OK):
        os.chmod(folder, 0o755)
        pytest.skip("cannot make a folder read-only")


@pytest.fixture
def project(MW, tmp_path, monkeypatch):
    """Opens a copy of the sample project, in which the file of a scene cannot be read
    (so that the save cache holds a file that must never be removed). Returns its path."""
    closePreviousProject(MW)
    (tmp_path / "project").mkdir()
    path = copySample(tmp_path / "project")
    unreadable = unreadableFile(path)
    realOpen = open

    def failingOpen(file, mode="r", *args, **kwargs):
        if "r" in mode and file == unreadable:
            raise OSError(5, "Input/output error", file)
        return realOpen(file, mode, *args, **kwargs)

    shownDialogs(monkeypatch)  # "Files not loaded"
    with monkeypatch.context() as m:
        m.setattr(version_1, "open", failingOpen, raising=False)
        MW.loadProject(path)
    assert MW.currentProject == path
    assert version_1.unreadable

    QSettings().setValue("recentFiles", [path])
    yield path
    for dirpath, dirnames, filenames in os.walk(str(tmp_path)):
        os.chmod(dirpath, 0o755)
    closePreviousProject(MW)


def cacheState():
    """What the save cache knows about the project folder."""
    return dict(version_1.cache), version_1.freshTarget, dict(version_1.unreadable)


def unreadableFile(path):
    """The file of the project at path that could not be read when it was loaded."""
    return os.path.join(path[:-4], "outline", "0-Jerusalem", "0-Chapter_1",
                        "0-Introduction.md")


def chapter1(MW):
    return MW.mdlOutline.rootItem.child(0).child(0)


def saveAs(MW, monkeypatch, target):
    """File > Save as... target. Returns the dialogs shown: (QMessageBox.warning
    texts, ListDialogs)."""
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args: warnings.append(args[2]) or QMessageBox.Ok)
    shown = shownDialogs(monkeypatch)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (target, ""))
    # In the app, an uncaught exception closes it
    uncaught = []
    with monkeypatch.context() as m:
        m.setattr(sys, "excepthook", lambda *exc: uncaught.append(exc[1]))
        MW.actSaveAs.trigger()
    assert uncaught == []
    return warnings, shown


def changeProject(MW):
    """Removes a scene: the next save must remove its file, which only the save cache
    knows."""
    assert [c.title() for c in chapter1(MW).children()] == \
        ["Jesus taken up into heaven", "Matthias chosen to replace Judas"]
    MW.mdlOutline.removeIndex(chapter1(MW).child(1).index())
    assert MW.projectDirty


def assertProjectStaysWhereItWas(MW, path, title, cache):
    assert MW.currentProject == path
    assert QSettings().value("lastProject") == path
    assert QSettings().value("recentFiles") == [path]
    assert MW.windowTitle() == title
    assert cacheState() == cache
    assert MW.projectDirty


def assertSaveGoesToProject(MW, path):
    """A normal save after the failed "Save as..." saves the project where it was,
    correctly."""
    unreadable = unreadableFile(path)
    with open(unreadable, "rb") as f:
        before = f.read()

    MW.mdlOutline.setData(chapter1(MW).child(0).index(Outline.text), "Edited afterwards")
    assert MW.saveDatas()
    assert MW.currentProject == path

    with open(unreadable, "rb") as f:
        assert f.read() == before  # never overwritten nor removed
    MW.closeProject()
    MW.loadProject(path)
    assert [c.title() for c in chapter1(MW).children()] == \
        ["Introduction", "Jesus taken up into heaven"]  # the removed scene stays removed
    assert chapter1(MW).child(1).data(Outline.text) == "Edited afterwards"


def test_save_as_into_read_only_folder(MW, project, tmp_path, monkeypatch):
    path = project
    title = MW.windowTitle()
    changeProject(MW)
    cache = cacheState()
    folder = str(tmp_path / "readonly")
    makeReadOnly(folder)

    warnings, shown = saveAs(MW, monkeypatch, os.path.join(folder, "copy.msk"))

    assertProjectStaysWhereItWas(MW, path, title, cache)
    assert os.listdir(folder) == []
    # The user is told why, once
    assert len(warnings) == 1 and folder in warnings[0]
    assert shown == []

    assertSaveGoesToProject(MW, path)


def test_save_as_fails_while_writing(MW, project, tmp_path, monkeypatch):
    """The project file can be written, but not the folder with its content."""
    path = project
    title = MW.windowTitle()
    changeProject(MW)
    cache = cacheState()
    target = str(tmp_path / "copy.msk")
    makeReadOnly(target[:-4])

    warnings, shown = saveAs(MW, monkeypatch, target)

    assertProjectStaysWhereItWas(MW, path, title, cache)
    # The user is told why, once: by saveProject()
    assert warnings == []
    assert len(shown) == 1 and shown[0][0] == "Files not saved"

    assertSaveGoesToProject(MW, path)


@pytest.mark.parametrize("readOnly, nameOnly", [("", False), ("characters", False),
                                               ("characters", True)],
                         ids=["read-only folder", "read-only characters folder",
                              "error with the file name only"])
def test_save_as_into_older_read_only_project(MW, project, tmp_path, monkeypatch, readOnly,
                                              nameOnly):
    """The folder of the new project holds an older Manuskript project, whose files
    cannot all be removed."""
    path = project
    title = MW.windowTitle()
    changeProject(MW)
    cache = cacheState()
    target = str(tmp_path / "copy.msk")
    folder = target[:-4]
    os.makedirs(os.path.join(folder, "outline"))
    os.makedirs(os.path.join(folder, "characters"))
    with open(os.path.join(folder, "characters", "0-Someone.txt"), "w") as f:
        f.write("Name: Someone\n")
    with open(os.path.join(folder, "MANUSKRIPT"), "w") as f:
        f.write("1")
    makeReadOnly(os.path.join(folder, readOnly))
    realRmtree = shutil.rmtree

    def rmtree(path, *args, **kwargs):
        try:
            realRmtree(path, *args, **kwargs)
        except OSError as e:
            # As with Python 3.11 (Python 3.13 names the folder)
            e.filename = "0-Someone.txt"
            raise

    with monkeypatch.context() as m:
        if nameOnly:
            m.setattr(version_1.shutil, "rmtree", rmtree)
        warnings, shown = saveAs(MW, monkeypatch, target)

    assertProjectStaysWhereItWas(MW, path, title, cache)
    if readOnly:
        # The outline folder was removed before the error
        assert sorted(os.listdir(folder)) == ["MANUSKRIPT", "characters"]
        failed = os.path.join(folder, "characters")
    else:
        assert sorted(os.listdir(folder)) == ["MANUSKRIPT", "characters", "outline"]
        failed = os.path.join(folder, "outline")
    assert not os.path.exists(target)
    # The user is told why, once, without claiming that nothing was removed
    assert warnings == []
    assert len(shown) == 1 and shown[0][0] == "Project not saved"
    assert "could not all be removed (some of them may have been removed already)" in \
        shown[0][1]
    assert shown[0][2] == ["{} ({})".format(failed, os.strerror(errno.EACCES))]

    assertSaveGoesToProject(MW, path)


def test_failed_save_as_keeps_the_moves(MW, project, tmp_path, monkeypatch):
    """Items renamed before a failed "Save as..." are still handled as moved by the next
    save: e.g. a renamed folder takes along the file in it that could not be read when
    loading."""
    path = project
    MW.mdlOutline.setData(chapter1(MW).index(Outline.title), "Chapter One")
    character = MW.mdlCharacter.characters[0]
    MW.mdlCharacter.setData(character.index(Character.name), "Someone else")
    lastPaths = character.lastPath, chapter1(MW)._lastPath, chapter1(MW).child(0)._lastPath
    target = str(tmp_path / "copy.msk")
    # Only one file cannot be written: the renamed items are written at the new place
    realWrite = version_1.writeFile

    def writeFile(filename, *args, **kwargs):
        if filename == os.path.join(target[:-4], "plots.xml"):
            raise OSError(28, "No space left on device", filename)
        return realWrite(filename, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(version_1, "writeFile", writeFile)
        warnings, shown = saveAs(MW, monkeypatch, target)

    assert MW.currentProject == path
    assert len(shown) == 1 and shown[0][0] == "Files not saved"
    assert os.path.exists(os.path.join(target[:-4], "outline", "0-Jerusalem", "0-Chapter_One"))
    assert (character.lastPath, chapter1(MW)._lastPath,
            chapter1(MW).child(0)._lastPath) == lastPaths

    assert MW.saveDatas()
    MW.closeProject()
    MW.loadProject(path)
    assert [c.title() for c in MW.mdlOutline.rootItem.child(0).children()][:2] == \
        ["Chapter One", "Chapter 2"]
    assert [c.title() for c in chapter1(MW).children()] == \
        ["Introduction", "Jesus taken up into heaven", "Matthias chosen to replace Judas"]
    assert not os.path.exists(os.path.dirname(unreadableFile(path)))


def symlink(source, link):
    """Creates a symbolic link, skips the test if that is not possible (Windows without
    the privilege)."""
    try:
        os.symlink(source, link)
    except (OSError, NotImplementedError) as e:
        pytest.skip("cannot create a symbolic link: {}".format(e))


@pytest.mark.parametrize("throughLink", [False, True],
                         ids=["same path", "path through a link to its folder's parent"])
def test_save_as_onto_itself(MW, project, tmp_path, monkeypatch, throughLink):
    """"Save as..." the project's own file saves it, without removing its files that
    could not be read when loading."""
    path = project
    with open(unreadableFile(path), "rb") as f:
        before = f.read()
    changeProject(MW)
    target = path
    if throughLink:
        symlink(os.path.dirname(path), str(tmp_path / "link"))
        target = str(tmp_path / "link" / os.path.basename(path))

    warnings, shown = saveAs(MW, monkeypatch, target)

    assert warnings == [] and shown == []
    # The project is the file chosen, as the window title and the recent files say
    assert MW.currentProject == target
    assert QSettings().value("lastProject") == target
    assert not MW.projectDirty
    with open(unreadableFile(path), "rb") as f:
        assert f.read() == before
    MW.closeProject()
    MW.loadProject(path)
    assert [c.title() for c in chapter1(MW).children()] == \
        ["Introduction", "Jesus taken up into heaven"]  # the removed scene stays removed


def test_save_as_into_link_to_own_folder(MW, project, monkeypatch):
    """"Save as..." a file with another name, whose folder is a link to the project's
    folder, saves into the project's own folder: its files must not be removed first, as
    those of an older project (with the files that could not be read when loading)."""
    path = project
    with open(unreadableFile(path), "rb") as f:
        before = f.read()
    changeProject(MW)
    target = os.path.join(os.path.dirname(path), "other.msk")
    symlink(path[:-4], target[:-4])

    warnings, shown = saveAs(MW, monkeypatch, target)

    assert warnings == [] and shown == []
    assert MW.currentProject == target
    assert QSettings().value("lastProject") == target
    assert QSettings().value("recentFiles") == [target, path]
    assert MW.windowTitle().startswith("other - ")
    assert not MW.projectDirty
    with open(unreadableFile(path), "rb") as f:
        assert f.read() == before
    # Both files open the project as it was saved
    for p in [target, path]:
        MW.closeProject()
        MW.loadProject(p)
        assert MW.currentProject == p
        assert [c.title() for c in chapter1(MW).children()] == \
            ["Introduction", "Jesus taken up into heaven"]


@pytest.mark.parametrize("link", ["symbolic", "hard"])
def test_save_as_onto_link_to_project_file(MW, project, tmp_path, monkeypatch, link):
    """"Save as..." onto a link to the project file under another name, next to another
    folder, writes a copy of the project there: the project is stored in the folder named
    like the project file."""
    path = project
    changeProject(MW)
    (tmp_path / "other").mkdir()
    target = str(tmp_path / "other" / "copy.msk")
    if link == "symbolic":
        symlink(path, target)
    else:
        try:
            os.link(path, target)
        except (OSError, NotImplementedError) as e:
            pytest.skip("cannot create a hard link: {}".format(e))

    warnings, shown = saveAs(MW, monkeypatch, target)

    assert warnings == [] and shown == []
    assert MW.currentProject == target
    assert QSettings().value("lastProject") == target
    assert QSettings().value("recentFiles")[0] == target
    assert MW.windowTitle().startswith("copy - ")
    assert not MW.projectDirty
    assert os.path.isdir(target[:-4])

    # The copy is complete
    shown = shownDialogs(monkeypatch)
    MW.closeProject()
    MW.loadProject(target)
    assert shown == []
    assert MW.currentProject == target
    assert [c.title() for c in chapter1(MW).children()] == ["Jesus taken up into heaven"]


def test_project_folder_without_file_numbers(MW, project, tmp_path, monkeypatch):
    """On a file system without file numbers (st_ino 0), any two files would be the same
    file: the paths of the folders are compared instead."""
    path = project
    other = str(tmp_path / "other.msk")
    os.makedirs(other[:-4])
    realStat = os.stat

    def stat(p, *args, **kwargs):
        s = realStat(p, *args, **kwargs)
        return os.stat_result((s.st_mode, 0, 0) + tuple(s)[3:])

    with monkeypatch.context() as m:
        m.setattr(os, "stat", stat)
        assert MW.isCurrentProjectFolder(path)
        assert MW.isCurrentProjectFolder(os.path.join(os.path.dirname(path), ".",
                                                      os.path.basename(path)))
        assert not MW.isCurrentProjectFolder(other)


def test_save_as_single_file_fails_while_writing(MW, project, tmp_path, monkeypatch):
    path = project
    title = MW.windowTitle()
    changeProject(MW)
    cache = cacheState()
    target = str(tmp_path / "copy.msk")
    monkeypatch.setattr(settings, "saveToZip", True)

    def writestr(*args, **kwargs):
        raise OSError(28, "No space left on device")

    with monkeypatch.context() as m:
        m.setattr(zipfile.ZipFile, "writestr", writestr)
        warnings, shown = saveAs(MW, monkeypatch, target)

    assertProjectStaysWhereItWas(MW, path, title, cache)
    assert not os.path.exists(target)
    # The user is told why, once
    assert warnings == []
    assert shown == [("Files not saved", "The following files could not be saved:",
                      ["{} (No space left on device)".format(target)])]


def test_save_as(MW, project, tmp_path, monkeypatch):
    """A "Save as..." that succeeds switches to the new project."""
    changeProject(MW)
    target = str(tmp_path / "copy.msk")

    warnings, shown = saveAs(MW, monkeypatch, target)

    assert warnings == [] and shown == []
    assert MW.currentProject == target
    assert QSettings().value("lastProject") == target
    assert QSettings().value("recentFiles") == [target, project]
    assert MW.windowTitle().startswith("copy - ")
    assert not MW.projectDirty

    # The new project is complete
    MW.closeProject()
    MW.loadProject(target)
    assert [c.title() for c in chapter1(MW).children()] == ["Jesus taken up into heaven"]
