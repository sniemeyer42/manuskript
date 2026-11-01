#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Regression tests: moving / renaming / duplicating outline items must not lose data
when the project is saved as a folder (loadSave version_1)."""

import pytest

from manuskript import loadSave
from manuskript.enums import Outline

from manuskript.tests.load_save.helpers import addItem, drag, duplicate, reload, tree


def test_reorder_titles_with_same_slug(emptyProject):
    """Titles that only differ in non-ASCII letters have the same file name (#1320)."""
    MW = emptyProject
    root = MW.mdlOutline.rootItem
    chapter = addItem(MW, root, "Kapitel", folder=True)
    for title in ["Grüße", "Größe", "Später"]:
        addItem(MW, chapter, title, "Text of " + title)
    assert loadSave.saveProject()

    # Move the last scene to the top
    drag(MW, chapter.child(2), chapter, 0)
    assert [c.title() for c in chapter.children()] == ["Später", "Grüße", "Größe"]

    before, after = reload(MW)
    assert after == before
    texts = [c.data(Outline.text) for c in MW.mdlOutline.rootItem.child(0).children()]
    assert texts == ["Text of Später", "Text of Grüße", "Text of Größe"]


def test_duplicate_saved_folder_and_save_twice(sampleProject):
    """Duplicating a folder that is already on disk made every later save crash (#761, #1216)."""
    MW = sampleProject
    root = MW.mdlOutline.rootItem
    duplicate(MW, root.child(0))
    copy = root.child(root.childCount() - 1)
    assert copy.title() == root.child(0).title()
    assert copy._lastPath == ""

    assert loadSave.saveProject()
    assert loadSave.saveProject()
    before, after = reload(MW)
    assert after == before


def test_chapter_10_moved_above_chapter_1(emptyProject):
    """outline/00-Chapter_1 is a prefix of outline/00-Chapter_10 (#719)."""
    MW = emptyProject
    root = MW.mdlOutline.rootItem
    for i in range(1, 13):
        chapter = addItem(MW, root, "Chapter %d" % i, folder=True)
        addItem(MW, chapter, "Scene", "Text of chapter %d" % i)
    assert loadSave.saveProject()

    drag(MW, root.child(9), root, 0)
    assert loadSave.saveProject()
    assert loadSave.saveProject()

    # Delete "Chapter 12": it must not come back
    MW.mdlOutline.removeIndex(root.child(11).index())
    before, after = reload(MW)
    assert after == before
    assert [c.title() for c in MW.mdlOutline.rootItem.children()][:3] == \
        ["Chapter 10", "Chapter 1", "Chapter 2"]
    assert "Chapter 12" not in [c.title() for c in MW.mdlOutline.rootItem.children()]


def test_scenes_moved_into_new_unsaved_folder(sampleProject):
    """Destination folder does not exist on disk yet (#1306)."""
    MW = sampleProject
    root = MW.mdlOutline.rootItem
    chapter1 = root.child(0).child(0)
    scenes = [chapter1.child(0), chapter1.child(1)]
    titles = [s.title() for s in scenes]
    newFolder = addItem(MW, root, "New Part", folder=True)
    for row, scene in enumerate(scenes):
        drag(MW, scene, newFolder, row)

    before, after = reload(MW)
    assert after == before
    root = MW.mdlOutline.rootItem
    newFolder = [c for c in root.children() if c.title() == "New Part"][0]
    assert [c.title() for c in newFolder.children()] == titles
    assert not set(titles) & set(c.title() for c in root.child(0).child(0).children())


def test_rename_only_case(sampleProject):
    """The old file of an item renamed only in case is removed (case-sensitive file system)."""
    MW = sampleProject
    scene = MW.mdlOutline.rootItem.child(0).child(0).child(0)
    MW.mdlOutline.setData(scene.index(Outline.title), scene.title().upper())

    before, after = reload(MW)
    assert after == before


def test_copied_item_has_no_lastPath(sampleProject):
    folder = sampleProject.mdlOutline.rootItem.child(0)
    assert folder._lastPath
    copy = folder.copy()
    assert copy._lastPath == ""
    assert all(c._lastPath == "" for c in copy.children())


def test_rename_only_case_insensitive_fs(sampleProject, monkeypatch):
    """On a case-insensitive file system, the old file of an item renamed only in case is
    the file that has just been written: it must not be removed."""
    import os
    from manuskript.load_save import version_1
    MW = sampleProject
    folder = MW.currentProject[:-4]
    scene = MW.mdlOutline.rootItem.child(0).child(0).child(0)
    old = os.path.join(folder, scene._lastPath)
    MW.mdlOutline.setData(scene.index(Outline.title), scene.title().upper())
    new = os.path.join(folder, *version_1.outlineItemPath(scene))
    assert new != old and new.lower() == old.lower()

    # Emulates a case-insensitive file system: names that only differ in case are the
    # same file, removing one of them removes the other.
    realRemove = os.remove

    def remove(path, *args, **kwargs):
        d, name = os.path.split(path)
        for n in [n for n in os.listdir(d) if n.lower() == name.lower()] or [name]:
            realRemove(os.path.join(d, n), *args, **kwargs)

    monkeypatch.setattr(os.path, "samefile",
                        lambda a, b: os.path.realpath(a).lower() == os.path.realpath(b).lower())
    monkeypatch.setattr(os, "remove", remove)
    assert loadSave.saveProject()
    monkeypatch.undo()

    with open(new, encoding="utf8") as f:
        assert "title:          " + scene.title() + "\n" in f.read()


def test_failed_write_keeps_old_files_of_renamed_folder(sampleProject, monkeypatch):
    """A renamed folder is written at its new place, then its old files are removed. When
    writing the new files fails, the old ones are the only copy: they must be kept."""
    import os
    from manuskript.load_save import version_1
    MW = sampleProject
    folder = MW.currentProject[:-4]
    chapter = MW.mdlOutline.rootItem.child(0).child(0)
    oldFolder = os.path.join(folder, chapter._lastPath)
    oldFiles = {}
    for f in os.listdir(oldFolder):
        with open(os.path.join(oldFolder, f), encoding="utf8") as fo:
            oldFiles[f] = fo.read()

    MW.mdlOutline.setData(chapter.index(Outline.title), "Prologue")
    newFolder = os.path.realpath(os.path.join(folder, *version_1.outlineItemPath(chapter)))
    realOpen = open

    def failingOpen(file, mode="r", *args, **kwargs):
        if "w" in mode and os.path.realpath(file).startswith(newFolder + os.sep):
            raise PermissionError(13, "Permission denied", file)
        return realOpen(file, mode, *args, **kwargs)

    monkeypatch.setattr(version_1, "open", failingOpen, raising=False)
    loadSave.saveProject()
    loadSave.saveProject()
    monkeypatch.undo()

    for f, content in oldFiles.items():
        with open(os.path.join(oldFolder, f), encoding="utf8") as fo:
            assert fo.read() == content

    # Once the files can be written, the next save moves the folder
    before, after = reload(MW)
    assert after == before
    assert not os.path.exists(oldFolder)


def test_failed_write_removes_other_old_files(sampleProject, monkeypatch):
    """When some files cannot be written, only the old files of the items that could not be
    written at their new place are kept. The old files of removed items, and of renamed items
    that have been written, are removed: they must not come back (as duplicates) when the
    project is closed without saving, or after a crash."""
    import os
    from manuskript.load_save import version_1
    MW = sampleProject
    path = MW.currentProject
    folder = path[:-4]
    root = MW.mdlOutline.rootItem
    part1, part2 = root.child(0), root.child(1)
    chapters1 = [c.title() for c in part1.children()]
    chapters2 = [c.title() for c in part2.children()]

    # A renamed chapter and a removed chapter, which are written
    MW.mdlOutline.setData(part1.child(0).index(Outline.title), "Prologue")
    MW.mdlOutline.removeIndex(part1.child(part1.childCount() - 1).index())
    # A renamed chapter whose new files cannot be written
    chapter = part2.child(0)
    MW.mdlOutline.setData(chapter.index(Outline.title), "Not written")
    oldFolder = os.path.join(folder, chapter._lastPath)
    newFolder = os.path.realpath(os.path.join(folder, *version_1.outlineItemPath(chapter)))
    realOpen = open

    def failingOpen(file, mode="r", *args, **kwargs):
        if "w" in mode and os.path.realpath(file).startswith(newFolder + os.sep):
            raise PermissionError(13, "Permission denied", file)
        return realOpen(file, mode, *args, **kwargs)

    monkeypatch.setattr(version_1, "open", failingOpen, raising=False)
    assert not loadSave.saveProject()
    # Its old files are still kept by the next save
    assert not loadSave.saveProject()
    monkeypatch.undo()
    assert os.path.isfile(os.path.join(oldFolder, "folder.txt"))

    # Closed without saving
    MW.projectDirty = False
    MW.closeProject()
    MW.loadProject(path)
    root = MW.mdlOutline.rootItem
    assert [c.title() for c in root.child(0).children()] == ["Prologue"] + chapters1[1:-1]
    assert [c.title() for c in root.child(1).children()] == chapters2


def _ids(item):
    out = [item.ID()]
    for c in item.children():
        out += _ids(c)
    return out


def _reopenWithoutSaving(MW):
    """Like 'Discard' (or a crash) after a failed save, then opening the project again."""
    path = MW.currentProject
    MW.projectDirty = False
    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject == path
    return set(i[1] for i in tree(MW))


def _failWritesUnder(monkeypatch, newFolder):
    import os
    from manuskript.load_save import version_1
    realWrite = version_1.writeFile

    def failingWrite(filename, content, *args, **kwargs):
        if os.path.realpath(filename).startswith(newFolder + os.sep):
            raise OSError(28, "No space left on device", filename)
        return realWrite(filename, content, *args, **kwargs)

    monkeypatch.setattr(version_1, "writeFile", failingWrite)


@pytest.mark.parametrize("action", ["delete", "rename"])
def test_failed_write_keeps_items_moved_out_of_a_changed_parent(sampleProject, monkeypatch,
                                                                action):
    """A chapter is dragged out of a part, and the part is deleted (or renamed). When the new
    files of the chapter cannot be written, its old files are kept: the folder.txt of its old
    part must be kept too, or the old files are no longer loaded (the loader skips folders
    without folder.txt), and the chapter is lost when the project is closed without saving."""
    import os
    from manuskript.load_save import version_1
    MW = sampleProject
    folder = MW.currentProject[:-4]
    root = MW.mdlOutline.rootItem
    source, target = root.child(0), root.child(1)
    chapter = source.child(0)
    movedIDs = _ids(chapter)
    oldFolder = os.path.join(folder, chapter._lastPath)

    drag(MW, chapter, target, target.childCount())
    if action == "delete":
        MW.mdlOutline.removeIndex(source.index())
    else:
        MW.mdlOutline.setData(source.index(Outline.title), "Holy city")
    chapter = target.child(target.childCount() - 1)
    newFolder = os.path.realpath(os.path.join(folder, *version_1.outlineItemPath(chapter)))

    _failWritesUnder(monkeypatch, newFolder)
    assert not loadSave.saveProject()
    monkeypatch.undo()
    assert os.path.isfile(os.path.join(oldFolder, "folder.txt"))
    assert os.path.isfile(os.path.join(os.path.dirname(oldFolder), "folder.txt"))

    found = _reopenWithoutSaving(MW)
    assert set(movedIDs) <= found


def test_failed_folder_txt_keeps_items_moved_into_it(sampleProject, monkeypatch):
    """A scene is dragged into another chapter, and that chapter is renamed. When only the
    new folder.txt of the chapter cannot be written, the scene's new file is in a folder that
    is not loaded: its old file must be kept, or the scene is lost when the project is closed
    without saving."""
    import os
    from manuskript.load_save import version_1
    MW = sampleProject
    folder = MW.currentProject[:-4]
    part = MW.mdlOutline.rootItem.child(0)
    chapter1, chapter2 = part.child(0), part.child(1)
    scene = chapter1.child(1)
    sceneID, text = scene.ID(), scene.data(Outline.text)

    drag(MW, scene, chapter2, 0)
    MW.mdlOutline.setData(chapter2.index(Outline.title), "Pentecost")
    newFolderTxt = os.path.realpath(os.path.join(
        folder, *version_1.outlineItemPath(chapter2), "folder.txt"))
    realWrite = version_1.writeFile

    def failingWrite(filename, content, *args, **kwargs):
        if os.path.realpath(filename) == newFolderTxt:
            raise OSError(13, "Permission denied", filename)
        return realWrite(filename, content, *args, **kwargs)

    monkeypatch.setattr(version_1, "writeFile", failingWrite)
    assert not loadSave.saveProject()
    monkeypatch.undo()

    _reopenWithoutSaving(MW)
    texts = {i[1]: i[4] for i in tree(MW)}
    assert texts.get(sceneID) == text
