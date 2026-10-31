#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the manuskript plain text exporter (base of all exporters)."""

import pytest

from manuskript.enums import Outline


def addItem(parent, title, text=None, compile=True):
    from manuskript.models import outlineItem
    if text is None:
        item = outlineItem(title=title, parent=parent)
    else:
        item = outlineItem(title=title, _type="md", parent=parent)
        item.setData(Outline.text, text)
    if not compile:
        item.setData(Outline.compile, 0)
    return item


@pytest.fixture
def exporterSettingsPath(monkeypatch, tmp_path):
    """Keeps exporter.ini out of the user's data folder."""
    from manuskript.ui.exporters.manuskript.plainTextSettings import exporterSettings
    path = str(tmp_path / "exporter.ini")
    monkeypatch.setattr(exporterSettings, "getSettingsPath", lambda self: path)
    return path


@pytest.fixture
def plainText(MWEmptyProject, exporterSettingsPath):
    from manuskript.exporter.manuskript.plainText import plainText
    f = plainText()
    return f, f.settingsWidget()


@pytest.fixture
def chapter(MWEmptyProject):
    """Chapter 1 with three scenes, the second one excluded from compile."""
    root = MWEmptyProject.mdlOutline.rootItem
    ch = addItem(root, "Chapter 1")
    addItem(ch, "Scene 1", "Text 1.")
    addItem(ch, "Scene 2", "Text 2.", compile=False)
    addItem(ch, "Scene 3", "Text 3.")
    return ch


def test_compileStatusExcludesItems(plainText, chapter):
    f, w = plainText
    out = f.output(w)
    assert "Text 1." in out
    assert "Text 2." not in out
    assert "Text 3." in out


def test_ignoreCompileIncludesEverything(plainText, chapter):
    f, w = plainText
    w.chkContentIgnoreCompile.setChecked(True)
    out = f.output(w)
    assert "Chapter 1" in out
    assert "Text 1." in out
    assert "Text 2." in out
    assert "Text 3." in out


def test_noDoubleSeparatorForExcludedItems(plainText, chapter):
    f, w = plainText
    # Custom scene separator, no text titles
    w.cmbSepTT.setCurrentIndex(1)
    w.txtSepTT.setText("\\n* * *\\n")
    w.tblContent.item(1, 1).setCheckState(0)
    out = f.output(w)
    assert out == "Chapter 1\nText 1.\n\n* * *\nText 3.\n"
    assert out.count("* * *") == 1


def test_quoteTransformationsDoNotGrowSettings(plainText, MWEmptyProject):
    f, w = plainText
    root = MWEmptyProject.mdlOutline.rootItem
    for i in range(5):
        addItem(root, "Scene {}".format(i), "He said \"hi\" and 'bye'.")
    w.chkTransDoubleQuotes.setChecked(True)
    w.chkTransSingleQuote.setChecked(True)
    s = w.getSettings()
    custom = list(s["Transform"]["Custom"])
    out = f.concatenate(root, s)
    assert s["Transform"]["Custom"] == custom
    assert out.count("\"") == 0
    assert out.count("'") == 0


def test_granularSettingsFromShallowerOutline(MWEmptyProject, exporterSettingsPath):
    """Granular content settings saved for another outline depth are
    restored to the matching rows (exporter.ini is not per project)."""
    import json
    from manuskript.exporter.manuskript.plainText import plainText
    root = MWEmptyProject.mdlOutline.rootItem
    part = addItem(root, "Part")
    chapter = addItem(part, "Chapter")
    addItem(chapter, "Scene", "Text.")
    assert MWEmptyProject.mdlOutline.maxLevel() == 3

    # Settings as saved in a project with a single level
    f = plainText()
    s = f.settingsWidget().getSettings()
    s["Content"].update({"More": True, "FolderTitle": [True],
                         "TextTitle": [False], "TextText": [False]})
    with open(exporterSettingsPath, "w", encoding="utf-8") as fp:
        json.dump(s, fp)

    content = f.settingsWidget().getSettings()["Content"]
    assert content["More"]
    assert content["FolderTitle"] == [True, True, True]
    assert content["TextTitle"] == [False, False, False]
    assert content["TextText"] == [False, True, True]


def test_granularSettingsOutlineGotDeeper(MWEmptyProject, exporterSettingsPath):
    """The outline can get deeper while the export dialog is open."""
    from PyQt5.QtCore import Qt
    from manuskript.exporter.manuskript.plainText import plainText
    root = MWEmptyProject.mdlOutline.rootItem
    addItem(root, "Scene 0", "Text 0.")
    f = plainText()
    w = f.settingsWidget()
    w.chkContentMore.setChecked(True)
    w.tblContent.item(3, 1).setCheckState(Qt.Unchecked)  # Level 1 text title
    assert w.getSettings()["Content"]["TextTitle"] == [False]

    part = addItem(root, "Part")
    addItem(addItem(part, "Chapter"), "Scene", "Text.")
    out = f.output(w)
    # Deeper levels use the settings of the deepest known level
    assert out == "Text 0.\n\nPart\nChapter\nText.\n"
