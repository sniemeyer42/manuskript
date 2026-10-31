#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Regression tests for saving and loading projects (loadSave version_1)."""

import os

from manuskript import loadSave
from manuskript.enums import Outline

from manuskript.tests.load_save.helpers import copySample, addItem, reload


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
