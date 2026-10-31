#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Projects with files that cannot be read (permissions, files locked or not downloaded by a
sync tool, I/O errors...): they must never be saved without these files."""

import os
import shutil

import pytest

from manuskript import loadSave
from manuskript.enums import Outline

from manuskript.tests.load_save.helpers import copySample, addItem, shownDialogs, tree


def snapshot(folder):
    """All files in folder: {relative path: content}."""
    res = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        for f in filenames:
            f = os.path.join(dirpath, f)
            if os.path.islink(f):
                res[os.path.relpath(f, folder)] = "-> " + os.readlink(f)
            else:
                with open(f, "rb") as fo:
                    res[os.path.relpath(f, folder)] = fo.read()
    return res


def failReading(monkeypatch, paths, error=PermissionError(13, "Permission denied")):
    """Reading the files in paths (or in the folders in paths) raises error."""
    from manuskript.load_save import version_1
    realOpen = open

    def failingOpen(file, mode="r", *args, **kwargs):
        if "r" in mode and any(file == p or file.startswith(p + os.sep) for p in paths):
            raise type(error)(error.errno, error.strerror, file)
        return realOpen(file, mode, *args, **kwargs)

    monkeypatch.setattr(version_1, "open", failingOpen, raising=False)


def quit(MW, monkeypatch):
    """Quits like the user does, with "save on quit". Returns True if accepted."""
    from PyQt5.QtGui import QCloseEvent
    from manuskript import settings
    monkeypatch.setattr(settings, "saveOnQuit", True)
    event = QCloseEvent()
    MW.closeEvent(event)
    return event.isAccepted()


@pytest.mark.parametrize("unreadable", [["plots.xml", "summary.txt"], ["world.opml"],
                                        ["MANUSKRIPT"], ["settings.txt"]])
def test_open_project_with_unreadable_main_files(MW, tmp_path, monkeypatch, unreadable):
    """If files at the root of the project cannot be read, the project is not opened, and
    nothing is changed on disk: it would be saved without them (#313, #1356)."""
    path = copySample(tmp_path)
    folder = path[:-4]
    before = snapshot(folder)
    shown = shownDialogs(monkeypatch)
    failReading(monkeypatch, [os.path.join(folder, f) for f in unreadable])

    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject is None
    assert len(shown) == 1 and shown[0][0] == "Files not loaded"
    assert all(any(i.startswith(os.path.join(folder, f)) for i in shown[0][2]) for f in unreadable)

    monkeypatch.undo()
    assert quit(MW, monkeypatch)
    assert snapshot(folder) == before


@pytest.mark.parametrize("error", [PermissionError(13, "Permission denied"),
                                   OSError(5, "Input/output error")])
def test_open_project_with_no_readable_file(MW, tmp_path, monkeypatch, error):
    """No file of the project can be read (permissions after a restore, cloud files that
    cannot be downloaded, I/O errors): the project is not opened, and quitting (save on
    quit) must not save an empty project over it."""
    path = copySample(tmp_path)
    folder = path[:-4]
    before = snapshot(folder)
    failReading(monkeypatch, [folder], error)

    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject is None
    assert quit(MW, monkeypatch)
    monkeypatch.undo()
    assert snapshot(folder) == before


def test_open_project_with_unreadable_permissions(MW, tmp_path, monkeypatch):
    """Same with real permissions: no file can be read."""
    path = copySample(tmp_path)
    folder = path[:-4]
    before = snapshot(folder)
    for dirpath, dirnames, filenames in os.walk(folder):
        for f in filenames:
            os.chmod(os.path.join(dirpath, f), 0)
    try:
        if os.access(os.path.join(folder, "MANUSKRIPT"), os.R_OK):
            pytest.skip("cannot make files unreadable (running as root, or on Windows)")
        MW.closeProject()
        MW.loadProject(path)
        assert MW.currentProject is None
        assert quit(MW, monkeypatch)
    finally:
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                os.chmod(os.path.join(dirpath, f), 0o644)
    assert snapshot(folder) == before


def test_open_project_with_unreadable_scenes(MW, tmp_path, monkeypatch):
    """Scenes and folders that cannot be read are reported and not loaded, the project
    opens. Saving it never overwrites nor removes them."""
    path = copySample(tmp_path)
    folder = path[:-4]
    chapter = os.path.join(folder, "outline", "0-Jerusalem", "0-Chapter_1")
    scene = os.path.join(chapter, "0-Introduction.md")
    otherChapter = os.path.join(folder, "outline", "0-Jerusalem", "1-Chapter_2")
    try:
        os.symlink(os.path.join(str(tmp_path), "nonexistent.md"),
                   os.path.join(folder, "outline", "dangling.md"))
    except (OSError, NotImplementedError):
        pass  # symlinks are not available (e.g. Windows without privileges)
    before = snapshot(folder)
    shown = shownDialogs(monkeypatch)
    failReading(monkeypatch, [scene, os.path.join(otherChapter, "folder.txt")],
                OSError(5, "Input/output error"))

    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject == path
    try:
        assert len(shown) == 1 and shown[0][0] == "Files not loaded"
        assert any(i.startswith(scene + " (") for i in shown[0][2])
        root = MW.mdlOutline.rootItem
        titles = [c.title() for c in root.child(0).children()]
        assert "Chapter 2" not in titles
        assert [c.title() for c in root.child(0).child(0).children()] == \
            ["Jesus taken up into heaven", "Matthias chosen to replace Judas"]

        # A new scene has the same path as the scene that could not be read
        addItem(MW, root.child(0).child(0), "Introduction", "New text", row=0)
        # A new chapter has the same path as the chapter that could not be read
        newChapter = addItem(MW, root.child(0), "Chapter 2", folder=True, row=1)
        addItem(MW, newChapter, "Scene", "New scene")
        assert not loadSave.saveProject()

        # The project can still be saved, the other changes are saved
        MW.mdlOutline.removeIndex(root.child(0).child(0).child(0).index())
        MW.mdlOutline.removeIndex(newChapter.index())
        MW.mdlOutline.setData(root.child(0).child(0).child(0).index(Outline.text), "Today")
        assert loadSave.saveProject()
    finally:
        monkeypatch.undo()
        MW.closeProject()

    after = snapshot(folder)
    for f in before:
        if f.startswith(os.path.relpath(scene, folder)) or \
                f.startswith(os.path.relpath(otherChapter, folder) + os.sep):
            assert after[f] == before[f]
    MW.loadProject(path)
    try:
        chapter1 = MW.mdlOutline.rootItem.child(0).child(0)
        assert [c.title() for c in chapter1.children()] == \
            ["Introduction", "Jesus taken up into heaven", "Matthias chosen to replace Judas"]
        assert chapter1.child(1).data(Outline.text) == "Today"
        assert MW.mdlOutline.rootItem.child(0).child(1).title() == "Chapter 2"
    finally:
        MW.closeProject()


@pytest.mark.parametrize("unreadable", ["", "outline", "characters"])
def test_open_project_with_unreadable_main_folder(MW, tmp_path, monkeypatch, unreadable):
    """The project is not opened if its folder, or its outline or characters folder, cannot
    be listed."""
    path = copySample(tmp_path)
    folder = path[:-4]
    before = snapshot(folder)
    os.chmod(os.path.join(folder, unreadable), 0o300)
    try:
        if os.access(os.path.join(folder, unreadable), os.R_OK):
            pytest.skip("cannot make a folder unreadable (running as root, or on Windows)")
        MW.closeProject()
        MW.loadProject(path)
        assert MW.currentProject is None
        assert quit(MW, monkeypatch)
    finally:
        os.chmod(os.path.join(folder, unreadable), 0o755)
    assert snapshot(folder) == before


def test_open_project_with_missing_folder(MW, tmp_path):
    """Only the project file is there (e.g. a sync tool has not downloaded the folder yet):
    the project is not opened as an empty project, that would be saved over the folder."""
    path = copySample(tmp_path)
    shutil.rmtree(path[:-4])
    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject is None


def test_open_project_with_unreadable_folder(MW, tmp_path):
    """A chapter folder that cannot be listed is not loaded, and left untouched."""
    path = copySample(tmp_path)
    folder = path[:-4]
    chapter = os.path.join(folder, "outline", "0-Jerusalem", "1-Chapter_2")
    before = snapshot(folder)
    os.chmod(chapter, 0o300)
    try:
        if os.access(chapter, os.R_OK):
            pytest.skip("cannot make a folder unreadable (running as root, or on Windows)")
        MW.closeProject()
        MW.loadProject(path)
        assert MW.currentProject == path
        root = MW.mdlOutline.rootItem
        assert "Chapter 2" not in [c.title() for c in root.child(0).children()]
        # A new chapter has the same path as the folder that could not be read
        newChapter = addItem(MW, root.child(0), "Chapter 2", folder=True, row=1)
        addItem(MW, newChapter, "Scene", "New scene")
        assert not loadSave.saveProject()
        MW.mdlOutline.removeIndex(newChapter.index())
        MW.mdlOutline.setData(root.child(0).child(0).child(0).index(Outline.text), "Today")
        assert loadSave.saveProject()
        MW.closeProject()
    finally:
        os.chmod(chapter, 0o755)
    after = snapshot(folder)
    rel = os.path.relpath(chapter, folder) + os.sep
    assert {f: c for f, c in after.items() if f.startswith(rel)} == \
        {f: c for f, c in before.items() if f.startswith(rel)}


def test_new_project_after_failed_load(MW, tmp_path, monkeypatch):
    """Nothing of a project that failed to load is used when another project is saved."""
    path = copySample(tmp_path)
    failReading(monkeypatch, [os.path.join(path[:-4], "plots.xml")])
    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject is None
    monkeypatch.undo()

    from manuskript.load_save import version_1
    assert version_1.cache == {} and version_1.unreadable == {} and version_1.freshTarget
    MW.welcome.createFile(os.path.join(str(tmp_path), "new.msk"), overwrite=True)
    try:
        assert MW.currentProject
        assert loadSave.saveProject()
    finally:
        MW.closeProject()
    assert os.path.isfile(os.path.join(str(tmp_path), "new", "plots.xml"))


def makeUnreadable(filename, how):
    """Makes a file unreadable: no read permission ("chmod"), or not valid UTF-8 ("encoding",
    e.g. saved as cp1252 by another editor). Returns the function that makes the file (at the
    path given to it) readable again."""
    if how == "chmod":
        os.chmod(filename, 0)
        if os.access(filename, os.R_OK):
            os.chmod(filename, 0o644)
            pytest.skip("cannot make a file unreadable (running as root, or on Windows)")
        return lambda f: os.chmod(f, 0o644)

    with open(filename, "ab") as f:
        f.write(b"\nCaf\xe9\n")

    def restore(f):
        with open(f, "rb") as fo:
            data = fo.read()
        with open(f, "wb") as fo:
            fo.write(data.replace(b"\xe9", "\xe9".encode("utf8")))

    return restore


def outline(MW):
    """Outline items by ID: (depth, title, type, text)."""
    return {i[1]: (i[0],) + i[2:] for i in tree(MW)}


@pytest.mark.parametrize("how", ["chmod", "encoding"])
@pytest.mark.parametrize("change", ["rename", "insert"])
def test_unreadable_scene_moves_with_its_folder(MW, tmp_path, how, change):
    """A scene that could not be read stays in its chapter when the chapter's folder is
    renamed or renumbered (the chapter is renamed, or a chapter is inserted, moved or removed
    above it). Left alone in the old folder, without folder.txt, it would no longer be loaded
    once it can be read again."""
    from manuskript.load_save import version_1
    path = copySample(tmp_path)
    folder = path[:-4]
    MW.closeProject()
    MW.loadProject(path)
    before = outline(MW)
    MW.closeProject()

    scene = os.path.join(folder, "outline", "0-Jerusalem", "0-Chapter_1",
                         "1-Jesus_taken_up_into_heaven.md")
    restore = makeUnreadable(scene, how)
    MW.loadProject(path)
    try:
        assert MW.currentProject == path
        part = MW.mdlOutline.rootItem.child(0)
        chapter = part.child(0)
        assert "Jesus taken up into heaven" not in [c.title() for c in chapter.children()]
        if change == "rename":
            MW.mdlOutline.setData(chapter.index(Outline.title), "Prologue")
        else:
            addItem(MW, part, "New chapter", folder=True, row=0)
        assert loadSave.saveProject()
        assert loadSave.saveProject()
        newScene = os.path.join(folder, *version_1.outlineItemPath(chapter) +
                                [os.path.basename(scene)])
        chapterID = chapter.ID()
    finally:
        MW.closeProject()

    assert not os.path.exists(os.path.dirname(scene))
    restore(newScene)
    MW.loadProject(path)
    try:
        after = outline(MW)
        sceneID = [ID for ID, i in before.items() if i[1] == "Jesus taken up into heaven"][0]
        expected = dict(before)
        if change == "rename":
            expected[chapterID] = (1, "Prologue") + before[chapterID][2:]
        if how == "encoding":
            expected[sceneID] = before[sceneID][:3] + (before[sceneID][3] + "\nCaf\xe9\n",)
        assert {ID: after.get(ID) for ID in expected} == expected
        chapter = [c for c in MW.mdlOutline.rootItem.child(0).children() if c.ID() == chapterID]
        assert [c.title() for c in chapter[0].children()] == \
            ["Introduction", "Jesus taken up into heaven", "Matthias chosen to replace Judas"]
    finally:
        MW.closeProject()


def test_unreadable_folder_moves_with_its_parent(MW, tmp_path):
    """Same with a chapter whose folder.txt could not be read, when its part is renamed."""
    path = copySample(tmp_path)
    folder = path[:-4]
    MW.closeProject()
    MW.loadProject(path)
    before = outline(MW)
    MW.closeProject()

    chapter = os.path.join(folder, "outline", "0-Jerusalem", "1-Chapter_2")
    restore = makeUnreadable(os.path.join(chapter, "folder.txt"), "encoding")
    MW.loadProject(path)
    try:
        assert MW.currentProject == path
        part = MW.mdlOutline.rootItem.child(0)
        assert "Chapter 2" not in [c.title() for c in part.children()]
        MW.mdlOutline.setData(part.index(Outline.title), "Holy city")
        assert loadSave.saveProject()
        assert loadSave.saveProject()
        partID = part.ID()
    finally:
        MW.closeProject()

    newChapter = os.path.join(folder, "outline", "0-Holy_city", "1-Chapter_2")
    assert not os.path.exists(os.path.join(folder, "outline", "0-Jerusalem"))
    restore(os.path.join(newChapter, "folder.txt"))
    MW.loadProject(path)
    try:
        after = outline(MW)
        expected = dict(before)
        expected[partID] = (0, "Holy city") + before[partID][2:]
        assert {ID: after.get(ID) for ID in expected} == expected
        assert [c.title() for c in MW.mdlOutline.rootItem.child(0).children()][:3] == \
            ["Chapter 1", "Chapter 2", "Chapter 3"]
    finally:
        MW.closeProject()


def test_unreadable_scene_that_cannot_be_moved(MW, tmp_path, monkeypatch):
    """If a scene that could not be read cannot be moved with its renamed chapter, the old
    folder keeps its folder.txt: the old chapter is loaded again, with that scene, next to
    the renamed one."""
    path = copySample(tmp_path)
    folder = path[:-4]
    scene = os.path.join(folder, "outline", "0-Jerusalem", "0-Chapter_1",
                         "1-Jesus_taken_up_into_heaven.md")
    MW.closeProject()
    MW.loadProject(path)
    text = MW.mdlOutline.rootItem.child(0).child(0).child(1).data(Outline.text)
    MW.closeProject()

    restore = makeUnreadable(scene, "encoding")
    MW.loadProject(path)
    realReplace = os.replace

    def replace(src, dst, *args, **kwargs):
        if os.path.abspath(src) == os.path.abspath(scene):
            raise PermissionError(13, "Permission denied", src)
        return realReplace(src, dst, *args, **kwargs)

    try:
        assert MW.currentProject == path
        chapter = MW.mdlOutline.rootItem.child(0).child(0)
        MW.mdlOutline.setData(chapter.index(Outline.title), "Prologue")
        monkeypatch.setattr(os, "replace", replace)
        assert loadSave.saveProject()
        assert loadSave.saveProject()
        monkeypatch.undo()
    finally:
        MW.closeProject()

    assert os.path.isfile(os.path.join(os.path.dirname(scene), "folder.txt"))
    restore(scene)
    MW.loadProject(path)
    try:
        chapters = {c.title(): c for c in MW.mdlOutline.rootItem.child(0).children()}
        assert [c.title() for c in chapters["Prologue"].children()] == \
            ["Introduction", "Matthias chosen to replace Judas"]
        assert [(c.title(), c.data(Outline.text)) for c in chapters["Chapter 1"].children()] == \
            [("Jesus taken up into heaven", text + "\nCaf\xe9\n")]
    finally:
        MW.closeProject()
