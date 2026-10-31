#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Regression tests for saving and loading projects (loadSave version_1)."""

import os

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
