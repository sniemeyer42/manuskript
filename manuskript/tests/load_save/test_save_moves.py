#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Regression tests: moving / renaming / duplicating outline items must not lose data
when the project is saved as a folder (loadSave version_1)."""

from manuskript import loadSave
from manuskript.enums import Outline

from manuskript.tests.load_save.helpers import addItem, drag, duplicate, reload


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
