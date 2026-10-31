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
