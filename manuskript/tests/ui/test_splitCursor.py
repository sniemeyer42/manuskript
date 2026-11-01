#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for Organize > Split at cursor (Ctrl+K) in the main editor."""

import pytest

from PyQt5.QtGui import QTextCursor
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import qApp

from manuskript.enums import Outline


def pump():
    for i in range(10):
        qApp.processEvents()


@pytest.fixture
def openText(MWEmptyProject):
    """
    A text in a folder, open in the main editor. Returns the main window,
    the folder, the text item and the text editor.
    """
    from manuskript.models import outlineItem
    MW = MWEmptyProject
    folder = outlineItem(title="Chapter", _type="folder")
    MW.mdlOutline.appendItem(folder)
    text = outlineItem(title="Scene", _type="md")
    MW.mdlOutline.appendItem(text, folder.index())
    text.setData(Outline.text, "First half. Title Second half.")

    MW.mainEditor.setCurrentModelIndex(text.index())
    pump()
    editor = MW.mainEditor.currentEditor()
    assert editor.currentIndex == text.index()
    assert editor.getCurrentItemView() is editor.txtRedacText
    return MW, folder, text, editor.txtRedacText


def typeAt(textEdit, position, text):
    """
    Types text at position, without a space: the editor keeps it until
    500 ms later (or the next space, or focus-out).
    """
    c = textEdit.textCursor()
    c.setPosition(position)
    textEdit.setTextCursor(c)
    QTest.keyClicks(textEdit, text)
    assert textEdit.updateTimer.isActive()


def test_splitCursorKeepsTextJustTyped(openText):
    MW, folder, text, textEdit = openText
    typeAt(textEdit, len("First half."), "xyz")
    assert text.text() == "First half. Title Second half."  # Not yet

    MW.mainEditor.splitCursor()
    pump()

    assert [c.title() for c in folder.children()] == ["Scene", "Scene_2"]
    assert [c.text() for c in folder.children()] == [
        "First half.xyz", " Title Second half."]
    assert textEdit.toPlainText() == "First half.xyz"

    # The delayed submit, still due, does not change anything either
    QTest.qWait(textEdit.updateTimer.interval() + 200)
    assert [c.text() for c in folder.children()] == [
        "First half.xyz", " Title Second half."]


def test_splitCursorSelectionAfterTextJustTyped(openText):
    """The selected text becomes the new item's title."""
    MW, folder, text, textEdit = openText
    typeAt(textEdit, len("First half."), "xyz")

    c = textEdit.textCursor()
    c.setPosition(len("First half.xyz "))
    c.setPosition(len("First half.xyz Title"), QTextCursor.KeepAnchor)
    textEdit.setTextCursor(c)
    MW.mainEditor.splitCursor()
    pump()

    assert [c.title() for c in folder.children()] == ["Scene", "Title"]
    assert [c.text() for c in folder.children()] == [
        "First half.xyz ", " Second half."]
