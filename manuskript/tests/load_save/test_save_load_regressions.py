#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Regression tests for saving and loading projects (loadSave version_1)."""

import os
import shutil
import sys

import pytest

from manuskript import loadSave
from manuskript.enums import Outline

from manuskript.tests.load_save.helpers import copySample, addItem, reload, shownDialogs


def characters(MW):
    return [(c.name(), c.ID()) for c in MW.mdlCharacter.characters]


def test_characters_in_outline_path(sampleProject):
    """Outline files whose path contains "characters" are not loaded as characters."""
    MW = sampleProject
    root = MW.mdlOutline.rootItem
    MW.mdlOutline.setData(root.child(0).child(0).child(0).index(Outline.title), "Main characters")
    folder = addItem(MW, root, "Side characters", folder=True)
    addItem(MW, folder, "Scene", "Some text")
    before = characters(MW)

    for i in range(2):
        outlineBefore, outlineAfter = reload(MW)
        assert outlineAfter == outlineBefore
        assert characters(MW) == before


def test_character_named_outline(sampleProject):
    """A character file named "outline" is not loaded as an outline item."""
    MW = sampleProject
    MW.mdlCharacter.characters[0].setName("outline")
    before = characters(MW)

    outlineBefore, outlineAfter = reload(MW)
    assert outlineAfter == outlineBefore
    assert characters(MW) == before


def test_files_not_loaded_are_not_deleted(MW, tmp_path):
    """Files that are not part of the loaded project are left untouched on save (#1306)."""
    path = copySample(tmp_path)
    folder = path[:-4]
    extra = {
        # A scene without "ID:" line (written by hand or restored)
        "outline/0-Jerusalem/0-Chapter_1/9-my_new_scene.md":
            "title: My new scene\ntype: md\n\n\nTwo hours of writing.\n",
        # A chapter folder whose folder.txt is missing
        "outline/0-Jerusalem/9-Lost_chapter/0-scene.md":
            "title: Lost scene\nID: 900\ntype: md\n\n\nPrecious text.\n",
        # Notes the user keeps in the project folder
        "research-notes.txt": "my research\n",
        "research/sources.md": "sources\n",
    }
    for f, content in extra.items():
        f = os.path.join(folder, *f.split("/"))
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w", encoding="utf8") as fo:
            fo.write(content)

    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject == path
    try:
        # Something changes in the project, so that it is saved
        root = MW.mdlOutline.rootItem
        MW.mdlOutline.setData(root.child(0).index(Outline.title), "Renamed folder")
        assert loadSave.saveProject()
        assert loadSave.saveProject()
    finally:
        MW.closeProject()

    for f, content in extra.items():
        with open(os.path.join(folder, *f.split("/")), encoding="utf8") as fo:
            assert fo.read() == content


def makeUserFolder(path):
    """Creates a folder of the user with some files, returns {file: content}."""
    files = {"taxes.pdf": "important", os.path.join("drafts", "draft1.odt"): "draft"}
    for f, content in files.items():
        os.makedirs(os.path.dirname(os.path.join(path, f)), exist_ok=True)
        with open(os.path.join(path, f), "w") as fo:
            fo.write(content)
    return files


def assertFolderUnchanged(path, files):
    found = []
    for dirpath, dirnames, filenames in os.walk(path):
        found += [os.path.relpath(os.path.join(dirpath, f), path) for f in filenames]
    assert sorted(found) == sorted(files)
    for f, content in files.items():
        with open(os.path.join(path, f)) as fo:
            assert fo.read() == content


def test_save_does_not_wipe_non_project_folder(sampleProject, tmp_path, monkeypatch):
    """Saving as "Documents.msk" next to a "Documents" folder must not delete that folder."""
    MW = sampleProject
    target = os.path.join(str(tmp_path), "Documents")
    files = makeUserFolder(target)
    shown = shownDialogs(monkeypatch)

    # What "Save as..." does
    path = MW.currentProject
    loadSave.clearSaveCache()
    MW.currentProject = target + ".msk"
    try:
        assert not loadSave.saveProject()
    finally:
        MW.currentProject = path

    assertFolderUnchanged(target, files)
    # The user is told why
    assert len(shown) == 1
    assert shown[0][0] == "Project not saved"
    assert shown[0][2] == [target]


def test_save_into_folder_with_hidden_files_only(sampleProject, tmp_path):
    """A folder that only contains hidden files (.DS_Store...) counts as empty."""
    MW = sampleProject
    target = os.path.join(str(tmp_path), "Novel")
    os.makedirs(target)
    with open(os.path.join(target, ".DS_Store"), "w") as fo:
        fo.write("finder")

    loadSave.clearSaveCache()
    MW.currentProject = target + ".msk"
    assert loadSave.saveProject()
    assert os.path.isfile(os.path.join(target, "MANUSKRIPT"))
    with open(os.path.join(target, ".DS_Store")) as fo:
        assert fo.read() == "finder"


def test_loaded_project_with_empty_cache_is_not_wiped(MW, tmp_path):
    """Only a new project or "Save as..." removes an older project from the folder. A
    project loaded from disk is not, even if nothing of it is in the cache (e.g. because
    no file could be read): the user's files in it are kept."""
    path = copySample(tmp_path)
    folder = path[:-4]
    userFile = os.path.join(folder, "outline", "0-Jerusalem", "0-Chapter_1", "9-my_scene.md")
    with open(userFile, "w", encoding="utf8") as fo:
        fo.write("title: My scene\ntype: md\n\n\nWritten by hand.\n")

    MW.closeProject()
    MW.loadProject(path)
    try:
        assert MW.currentProject == path
        from manuskript.load_save import version_1
        version_1.cache.clear()
        assert loadSave.saveProject()
        assert loadSave.saveProject()
    finally:
        MW.closeProject()

    with open(userFile, encoding="utf8") as fo:
        assert fo.read().endswith("Written by hand.\n")


def test_save_as_existing_project_keeps_user_files(sampleProject, tmp_path):
    """Overwriting a project only removes the files Manuskript writes."""
    MW = sampleProject
    target = os.path.join(str(tmp_path), "other")
    files = makeUserFolder(target)
    with open(os.path.join(target, "MANUSKRIPT"), "w") as fo:
        fo.write("1")
    os.makedirs(os.path.join(target, "outline", "0-Old_chapter"))
    with open(os.path.join(target, "outline", "0-Old_chapter", "folder.txt"), "w") as fo:
        fo.write("title: Old chapter\nID: 9999\ntype: folder\n\n")

    loadSave.clearSaveCache()
    MW.currentProject = target + ".msk"
    assert loadSave.saveProject()

    assert not os.path.exists(os.path.join(target, "outline", "0-Old_chapter"))
    for f, content in files.items():
        with open(os.path.join(target, f)) as fo:
            assert fo.read() == content


def test_ui_check_unreadable_folder(MW, tmp_path, monkeypatch):
    """A folder that cannot be listed does not crash the check, the user is warned."""
    from PyQt5.QtWidgets import QMessageBox
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args: warnings.append(args) or QMessageBox.Ok)
    target = os.path.join(str(tmp_path), "Locked")
    os.makedirs(target)

    def listdir(path):
        raise PermissionError(13, "Permission denied", path)

    monkeypatch.setattr(os, "listdir", listdir)
    assert not MW.welcome.checkProjectFolder(target + ".msk")
    monkeypatch.undo()
    assert len(warnings) == 1


def test_ui_refuses_non_project_folder(MW, tmp_path, monkeypatch):
    """New project / Save as: the user is warned and nothing is written."""
    from PyQt5.QtWidgets import QMessageBox, QFileDialog
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args: warnings.append(args) or QMessageBox.Ok)

    target = os.path.join(str(tmp_path), "Thesis")
    files = makeUserFolder(target)

    MW.closeProject()
    MW.welcome.createFile(target + ".msk", overwrite=True)
    assert MW.currentProject is None
    assert len(warnings) == 1

    path = copySample(tmp_path)
    MW.loadProject(path)
    try:
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (target + ".msk", ""))
        MW.welcome.saveAsFile()
        assert MW.currentProject == path
        assert len(warnings) == 2
    finally:
        MW.closeProject()

    assertFolderUnchanged(target, files)
    assert not os.path.exists(target + ".msk")


def lastText(MW):
    """Returns the last text item of the outline (the last one to be saved)."""
    items = []

    def rec(item):
        for c in item.children():
            items.append(c)
            rec(c)

    rec(MW.mdlOutline.rootItem)
    return [i for i in items if i.isText()][-1]


def test_long_titles(sampleProject):
    """Very long titles must not make the save fail (file name too long, #313)."""
    MW = sampleProject
    mdl = MW.mdlOutline
    scene = mdl.rootItem.child(0).child(0).child(0)
    mdl.setData(scene.index(Outline.title), "A very long title" * 20)
    MW.mdlCharacter.characters[0].setName("A very long name" * 20)
    mdl.setData(lastText(MW).index(Outline.text), "Text written today")
    names = characters(MW)

    before, after = reload(MW)
    assert after == before
    assert characters(MW) == names


def test_failed_write_keeps_previous_file(sampleProject, monkeypatch):
    """When writing a file fails half way (disk full, quota), its previous version is kept
    and no truncated or temporary file is left."""
    import errno
    from manuskript.load_save import version_1
    MW = sampleProject
    scene = lastText(MW)
    filename = os.path.join(MW.currentProject[:-4], scene._lastPath)
    with open(filename, encoding="utf8") as f:
        previous = f.read()
    filesBefore = sorted(os.listdir(os.path.dirname(filename)))
    MW.mdlOutline.setData(scene.index(Outline.text), "Text written today")

    class FullDisk:
        def __init__(self, f):
            self.f = f

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.f.close()

        def write(self, data):
            self.f.write(data[:len(data) // 2])
            self.f.flush()
            raise OSError(errno.ENOSPC, "No space left on device")

    realOpen = open

    def fullDiskOpen(file, mode="r", *args, **kwargs):
        f = realOpen(file, mode, *args, **kwargs)
        if "w" in mode and os.path.basename(filename) in os.path.basename(file):
            return FullDisk(f)
        return f

    monkeypatch.setattr(version_1, "open", fullDiskOpen, raising=False)
    assert not loadSave.saveProject()
    monkeypatch.undo()

    with open(filename, encoding="utf8") as f:
        assert f.read() == previous
    assert sorted(os.listdir(os.path.dirname(filename))) == filesBefore

    assert loadSave.saveProject()
    with open(filename, encoding="utf8") as f:
        assert f.read().endswith("Text written today")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX file modes")
def test_save_keeps_symlinks_and_modes(sampleProject, tmp_path):
    """A file that is a symbolic link is written through the link, and the mode of the
    files that are replaced is kept."""
    import stat
    MW = sampleProject
    scene = lastText(MW)
    filename = os.path.join(MW.currentProject[:-4], scene._lastPath)
    target = os.path.join(str(tmp_path), "elsewhere.md")
    shutil.move(filename, target)
    try:
        os.symlink(target, filename)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    os.chmod(target, 0o600)
    os.chmod(MW.currentProject, 0o600)

    MW.mdlOutline.setData(scene.index(Outline.text), "Text written today")
    assert loadSave.saveProject()

    assert os.path.islink(filename)
    with open(target, encoding="utf8") as f:
        assert f.read().endswith("Text written today")
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(MW.currentProject).st_mode) == 0o600


def test_read_only_file_is_not_replaced(sampleProject):
    """A file that is not writable is reported as not saved, it is not replaced."""
    MW = sampleProject
    scene = lastText(MW)
    filename = os.path.join(MW.currentProject[:-4], scene._lastPath)
    with open(filename, encoding="utf8") as f:
        previous = f.read()
    os.chmod(filename, 0o444)
    try:
        if os.access(filename, os.W_OK):
            pytest.skip("cannot make a file read-only (running as root?)")
        MW.mdlOutline.setData(scene.index(Outline.text), "Text written today")
        assert not loadSave.saveProject()
        with open(filename, encoding="utf8") as f:
            assert f.read() == previous
    finally:
        os.chmod(filename, 0o644)
    assert loadSave.saveProject()


def test_save_without_chmod_support(sampleProject, monkeypatch):
    """On file systems that do not support chmod (some network or FUSE mounts), the files
    are saved without keeping their mode."""
    import errno
    MW = sampleProject
    scene = lastText(MW)
    filename = os.path.join(MW.currentProject[:-4], scene._lastPath)

    def chmod(path, *args, **kwargs):
        raise OSError(errno.ENOTSUP, os.strerror(errno.ENOTSUP), path)

    monkeypatch.setattr(os, "chmod", chmod)
    MW.mdlOutline.setData(scene.index(Outline.text), "Text written today")
    assert loadSave.saveProject()
    monkeypatch.undo()
    with open(filename, encoding="utf8") as f:
        assert f.read().endswith("Text written today")
    assert not [f for f in os.listdir(os.path.dirname(filename)) if f.endswith(".tmp")]


def test_write_error_does_not_stop_save(sampleProject):
    """A file that cannot be written is reported, the other files are still written."""
    MW = sampleProject
    mdl = MW.mdlOutline
    folder = MW.currentProject[:-4]
    first = mdl.rootItem.child(0).child(0).child(0)
    last = lastText(MW)

    # Something prevents writing the first scene's file (here: a folder with that name)
    path = os.path.join(folder, first._lastPath)
    os.remove(path)
    os.mkdir(path)
    open(os.path.join(path, "file"), "w").close()
    mdl.setData(first.index(Outline.text), "Not saved")
    mdl.setData(last.index(Outline.text), "Text written today")

    assert not loadSave.saveProject()
    with open(os.path.join(folder, last._lastPath), encoding="utf8") as f:
        assert f.read().endswith("Text written today")

    # The problem is fixed: the next save writes the file
    shutil.rmtree(path)
    assert loadSave.saveProject()
    with open(path, encoding="utf8") as f:
        assert f.read().endswith("Not saved")


def test_zip_save_is_atomic(sampleProject, tmp_path, monkeypatch):
    """A failed save to a single file must keep the previous version (#811)."""
    import zipfile
    from manuskript import settings
    MW = sampleProject
    path = os.path.join(str(tmp_path), "zipped.msk")
    monkeypatch.setattr(settings, "saveToZip", True)
    MW.currentProject = path
    assert loadSave.saveProject()
    with zipfile.ZipFile(path) as zf:
        good = {f: zf.read(f) for f in zf.namelist()}

    # The disk gets full while saving
    def writestr(*args, **kwargs):
        raise OSError(28, "No space left on device")

    shown = shownDialogs(monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(zipfile.ZipFile, "writestr", writestr)
        MW.mdlOutline.setData(lastText(MW).index(Outline.text), "New text")
        assert not loadSave.saveProject()

    # The user is told why
    assert shown == [("Files not saved", "The following files could not be saved:",
                      ["{} (No space left on device)".format(path)])]
    with zipfile.ZipFile(path) as zf:
        assert {f: zf.read(f) for f in zf.namelist()} == good
    assert [f for f in os.listdir(str(tmp_path)) if f.endswith(".tmp")] == []

    # The new version is written to the disk before it replaces the previous one
    synced = []
    realFsync = os.fsync
    with monkeypatch.context() as m:
        m.setattr(os, "fsync", lambda fd: synced.append(fd) or realFsync(fd))
        assert loadSave.saveProject()
    assert len(synced) == 1
    with zipfile.ZipFile(path) as zf:
        assert any(b"New text" in zf.read(f) for f in zf.namelist())


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX file modes")
def test_zip_save_keeps_symlink_and_mode(sampleProject, tmp_path, monkeypatch):
    """A single-file project opened through a symbolic link (e.g. to a synced folder) is
    saved to the file the link points to, with its mode."""
    import stat
    import zipfile
    from manuskript import settings
    MW = sampleProject
    monkeypatch.setattr(settings, "saveToZip", True)
    real = os.path.join(str(tmp_path), "synced", "novel.msk")
    os.makedirs(os.path.dirname(real))
    MW.currentProject = real
    assert loadSave.saveProject()
    os.chmod(real, 0o600)
    link = os.path.join(str(tmp_path), "novel.msk")
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")

    MW.currentProject = link
    MW.mdlOutline.setData(lastText(MW).index(Outline.text), "Text written today")
    assert loadSave.saveProject()

    assert os.path.islink(link)
    with zipfile.ZipFile(real) as zf:
        assert any(b"Text written today" in zf.read(f) for f in zf.namelist())
    assert stat.S_IMODE(os.stat(real).st_mode) == 0o600
    assert sorted(os.listdir(os.path.dirname(real))) == ["novel.msk"]


def test_open_damaged_project_file(MW, tmp_path):
    """A damaged .msk file is reported, it does not crash the app (#1128)."""
    path = copySample(tmp_path)
    with open(path, "wb") as f:
        f.write(b"PK\x03\x04\xa5\xff truncated zip")
    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject is None


def test_open_project_file_with_newline(MW, tmp_path):
    """The version number in the .msk file can be followed by a newline."""
    path = copySample(tmp_path)
    with open(path, "w") as f:
        f.write("1\n")
    MW.closeProject()
    MW.loadProject(path)
    try:
        assert MW.currentProject == path
    finally:
        MW.closeProject()


def test_world_item_with_empty_name_keeps_children(sampleProject):
    MW = sampleProject
    wm = MW.mdlWorld
    category = wm.addItem(title="Magic system", parent=wm.invisibleRootItem())
    for title in ["Fire runes", "Water runes"]:
        wm.addItem(title=title, parent=category)
    category.setText("")

    def world():
        out = []

        def rec(item, depth):
            for r in range(item.rowCount()):
                out.append((depth, item.child(r, 0).text()))
                rec(item.child(r, 0), depth + 1)

        rec(MW.mdlWorld.invisibleRootItem(), 0)
        return out

    before = world()
    assert before[-3:] == [(0, ""), (1, "Fire runes"), (1, "Water runes")]
    reload(MW)
    assert world() == before


def test_open_project_with_unreadable_files(MW, tmp_path):
    """Scenes that cannot be read (dangling symlink, permissions) are reported and not
    loaded, the project opens (#313, #1356). See also test_unreadable_files.py."""
    path = copySample(tmp_path)
    folder = path[:-4]
    try:
        os.symlink(os.path.join(str(tmp_path), "nonexistent.md"),
                   os.path.join(folder, "outline", "dangling.md"))
    except (OSError, NotImplementedError):
        pass  # symlinks are not available (e.g. Windows without privileges)
    unreadable = [os.path.join(folder, "outline", "0-Jerusalem", "0-Chapter_1",
                               "0-Introduction.md")]
    for f in unreadable:
        os.chmod(f, 0)

    MW.closeProject()
    try:
        MW.loadProject(path)
        assert MW.currentProject == path
    finally:
        for f in unreadable:
            os.chmod(f, 0o644)
        MW.closeProject()


def test_colons_in_names(sampleProject):
    """Character infos and labels whose name contains ":" are saved and loaded unchanged."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QStandardItem, QColor
    from manuskript.functions import iconColor, iconFromColor
    from manuskript.models.characterModel import CharacterInfo
    MW = sampleProject
    c = MW.mdlCharacter.characters[0]
    c.infos.append(CharacterInfo(c, "Height: (cm)", "182"))
    MW.mdlLabels.appendRow(QStandardItem(iconFromColor(QColor("#ff0000")), "TODO: fix"))
    MW.mdlLabels.appendRow(QStandardItem("No color: here"))

    def labels():
        mdl = MW.mdlLabels
        out = []
        for i in range(1, mdl.rowCount()):
            icon = mdl.data(mdl.index(i, 0), Qt.DecorationRole)
            out.append((mdl.data(mdl.index(i, 0)),
                        iconColor(icon).name(QColor.HexRgb) if icon is not None else None))
        return out

    before = labels()
    assert before[-2:] == [("TODO: fix", "#ff0000"), ("No color: here", None)]
    for i in range(2):
        reload(MW)
        c = MW.mdlCharacter.characters[0]
        assert [(i.description, i.value) for i in c.infos][-1] == ("Height: (cm)", "182")
        assert labels() == before
