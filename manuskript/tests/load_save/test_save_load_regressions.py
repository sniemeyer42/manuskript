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
