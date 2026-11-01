#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""
Tests for the main editor's scroll bar, which editorWidget takes out of the
text edit to put it at the editor's right edge.
"""

import pytest

from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QTextCursor, QWheelEvent
from PyQt5.QtWidgets import QAbstractScrollArea, qApp

from manuskript.enums import Outline


def pump():
    for i in range(20):
        qApp.processEvents()


def scrollBarsShownOutside(area):
    """
    Returns the scroll bars that area may show (their policy is not
    ScrollBarAlwaysOff) but that are not inside it. Some styles (Breeze,
    Adwaita-qt) map positions from a scroll area to such scroll bars,
    which crashes when the bar is elsewhere (#450, #601, #1435).
    """
    bars = []
    if area.horizontalScrollBarPolicy() != Qt.ScrollBarAlwaysOff:
        bars.append(area.horizontalScrollBar())
    if area.verticalScrollBarPolicy() != Qt.ScrollBarAlwaysOff:
        bars.append(area.verticalScrollBar())
    return [b for b in bars if b is not None and not area.isAncestorOf(b)]


def longText(paragraphs):
    return "\n\n".join("Paragraph {} with a few words.".format(i)
                       for i in range(paragraphs))


@pytest.fixture
def mainEditor(MWEmptyProject):
    """
    The main window, shown, with a folder and a long text in it, the text
    open in the main editor. Returns the main window, the folder, the text
    item and the editorWidget.
    """
    from manuskript.models import outlineItem
    MW = MWEmptyProject
    folder = outlineItem(title="Chapter", _type="folder")
    MW.mdlOutline.appendItem(folder)
    text = outlineItem(title="Scene", _type="md")
    MW.mdlOutline.appendItem(text, folder.index())
    text.setData(Outline.text, longText(200))

    MW.tabMain.setCurrentIndex(MW.TabRedac)
    MW.mainEditor.setCurrentModelIndex(text.index())
    MW.show()
    MW.resize(1000, 700)
    pump()
    editor = MW.mainEditor.currentEditor()
    assert editor.currentIndex == text.index()
    yield MW, folder, text, editor
    MW.hide()
    # Delete the editors now: closing the project later does not, and an
    # editor left over with this project's folder in its outline view can
    # crash the next project load (seen with the test of the folder views).
    MW.mainEditor.closeAllTabs()
    qApp.sendPostedEvents(None, QEvent.DeferredDelete)


def test_editorScrollBarNotShownByTheTextEdit(mainEditor):
    """The text edit does not show the bar it no longer contains."""
    MW, folder, text, editor = mainEditor
    bar = editor.txtEditScrollBar
    assert bar is editor.txtRedacText.verticalScrollBar()
    assert bar.parent() is editor
    assert scrollBarsShownOutside(editor.txtRedacText) == []

    # Same for every scroll area of the main window, including the editor
    # of a second tab
    MW.mainEditor.setCurrentModelIndex(folder.index(), newTab=True)
    pump()
    assert MW.mainEditor.currentEditor() is not editor
    for area in MW.findChildren(QAbstractScrollArea):
        assert scrollBarsShownOutside(area) == [], area.objectName()


def firstVisibleBlock(textEdit):
    return textEdit.cursorForPosition(QPoint(0, 0)).blockNumber()


def test_editorScrollBarFollowsTheText(mainEditor):
    MW, folder, text, editor = mainEditor
    textEdit = editor.txtRedacText
    bar = editor.txtEditScrollBar
    assert bar.isVisible()
    assert bar.minimum() == 0 and bar.maximum() > 0

    # Moving the bar scrolls the text
    bar.setValue(0)
    pump()
    assert firstVisibleBlock(textEdit) == 0
    bar.setValue(bar.maximum())
    pump()
    assert firstVisibleBlock(textEdit) > 0

    # Moving the cursor or the wheel scrolls the text and moves the bar
    textEdit.moveCursor(QTextCursor.Start)
    pump()
    assert bar.value() == 0
    textEdit.moveCursor(QTextCursor.End)
    pump()
    assert bar.value() == bar.maximum()
    pos = QPointF(textEdit.viewport().rect().center())
    wheel = QWheelEvent(pos, QPointF(textEdit.viewport().mapToGlobal(
        pos.toPoint())), QPoint(), QPoint(0, 120), Qt.NoButton,
        Qt.NoModifier, Qt.NoScrollPhase, False)
    value = bar.value()
    qApp.sendEvent(textEdit.viewport(), wheel)
    pump()
    assert bar.value() < value

    # The range follows the length of the text
    maximum = bar.maximum()
    text.setData(Outline.text, longText(400))
    pump()
    assert bar.maximum() > maximum
    text.setData(Outline.text, "Short.")
    pump()
    assert bar.maximum() == 0


def test_editorScrollBarHiddenOutsideTheTextView(mainEditor, monkeypatch):
    """setScrollBarVisibility(): the bar is only shown with a single text."""
    from manuskript import settings
    monkeypatch.setattr(settings, "folderView", settings.folderView)
    MW, folder, text, editor = mainEditor
    bar = editor.txtEditScrollBar
    assert bar.isVisible()

    for view in ("cork", "outline", "text"):
        editor.setFolderView(view)
        MW.mainEditor.setCurrentModelIndex(folder.index())
        pump()
        assert editor.stack.currentIndex() != 0
        assert not bar.isVisible()

        MW.mainEditor.setCurrentModelIndex(text.index())
        pump()
        assert editor.stack.currentIndex() == 0
        assert bar.isVisible()
