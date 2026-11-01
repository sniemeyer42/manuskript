#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""
Tests for the full summary editor of the Outline tab when several items are
selected: it shows "Various" (an empty text) when their summaries differ,
and must not write that empty text into them unless the user edits it.
"""

import pytest

from PyQt5.QtCore import QEvent, QItemSelectionModel, Qt
from PyQt5.QtGui import QFocusEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import qApp

from manuskript.enums import Outline


def pump():
    for i in range(10):
        qApp.processEvents()


def waitForDelayedSubmit(editor):
    """Lets the editor's "submit after the last change" timer expire."""
    QTest.qWait(editor.updateTimer.interval() + 200)
    pump()


# The editor submits 500 ms after the last change. The tests shorten that
# while they run, so that waiting for it does not slow down the suite.
FAST_SUBMIT_INTERVAL = 50


def focusInAndOut(editor):
    qApp.sendEvent(editor, QFocusEvent(QEvent.FocusIn, Qt.MouseFocusReason))
    pump()
    qApp.sendEvent(editor, QFocusEvent(QEvent.FocusOut, Qt.MouseFocusReason))
    pump()


@pytest.fixture
def outlineTab(MWEmptyProject):
    """
    Two items with different full summaries in the outline, the first one
    selected in the Outline tab.
    """
    from manuskript.models import outlineItem
    MW = MWEmptyProject
    items = []
    for title in ("A", "B"):
        item = outlineItem(title=title, _type="md")
        MW.mdlOutline.appendItem(item)
        item.setData(Outline.summaryFull, "Summary {}".format(title))
        items.append(item)

    timer = MW.outlineItemEditor.txtSummaryFull.updateTimer
    interval = timer.interval()
    timer.setInterval(FAST_SUBMIT_INTERVAL)

    # A click on the first item
    view = MW.treeOutlineOutline
    view.selectionModel().setCurrentIndex(
        items[0].index(),
        QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
    pump()
    yield MW, view, items

    # The main window is shared by all tests
    timer.setInterval(interval)


def selectBoth(view, items):
    """Adds the second item to the selection, like a ctrl+click."""
    view.selectionModel().setCurrentIndex(
        items[1].index(),
        QItemSelectionModel.Select | QItemSelectionModel.Rows)
    pump()
    assert len(view.selectionModel().selectedRows()) == 2
    editor = view.window().outlineItemEditor.txtSummaryFull
    assert editor.toPlainText() == ""
    assert editor.placeholderText() == "Various"
    return editor


def summaries(items):
    return [item.data(Outline.summaryFull) for item in items]


def test_multiSelectionFocusInOutKeepsSummaries(outlineTab):
    """Clicking into the "Various" field and out again changes nothing."""
    MW, view, items = outlineTab
    editor = selectBoth(view, items)

    focusInAndOut(editor)
    assert summaries(items) == ["Summary A", "Summary B"]

    waitForDelayedSubmit(editor)
    assert summaries(items) == ["Summary A", "Summary B"]


@pytest.mark.parametrize("rehighlight", [
    lambda MW: MW.outlineItemEditor.toggleSpellcheck(True),
    lambda MW: MW.outlineItemEditor.toggleSpellcheck(False),
    lambda MW: MW.outlineItemEditor.setDict(
        MW.outlineItemEditor.txtSummaryFull.currentDict),
    lambda MW: MW.outlineItemEditor.txtSummaryFull.highlighter.rehighlight(),
], ids=["spellcheckOn", "spellcheckOff", "setDict", "rehighlight"])
def test_multiSelectionRehighlightKeepsSummaries(outlineTab, rehighlight):
    """
    Re-highlighting (switching spellcheck, changing the dictionary) is not
    an edit, neither right away nor once the delayed submit is due, nor
    when the field loses the focus afterwards.
    """
    MW, view, items = outlineTab
    editor = selectBoth(view, items)

    rehighlight(MW)
    pump()
    waitForDelayedSubmit(editor)
    assert summaries(items) == ["Summary A", "Summary B"]

    focusInAndOut(editor)
    assert summaries(items) == ["Summary A", "Summary B"]


def typeText(editor, text):
    QTest.keyClicks(editor, text)


def pasteText(editor, text):
    qApp.clipboard().setText(text)
    QTest.keyClick(editor, Qt.Key_V, Qt.ControlModifier)


def correctSpelling(editor, text):
    # What the spelling suggestions of the context menu do
    editor.correctWord(text)


def complete(editor, text):
    # What choosing an entry of the completer (Ctrl+Space) does
    editor.insertCompletion(text)


def undoRedo(editor, text):
    QTest.keyClicks(editor, text)
    editor.undo()
    assert editor.toPlainText() == ""
    editor.redo()


@pytest.mark.parametrize("edit", [
    typeText, pasteText, correctSpelling, complete, undoRedo])
def test_multiSelectionEditReachesAllItems(outlineTab, edit):
    """What the user puts into the "Various" field goes to every item."""
    MW, view, items = outlineTab
    editor = selectBoth(view, items)

    edit(editor, "Common")
    assert editor.toPlainText() == "Common"
    waitForDelayedSubmit(editor)
    assert summaries(items) == ["Common", "Common"]

    # And on focus-out, without waiting
    editor.selectAll()
    QTest.keyClicks(editor, "Other")
    focusInAndOut(editor)
    assert summaries(items) == ["Other", "Other"]


def test_multiSelectionTypedTextWithSpaces(outlineTab):
    """A space submits right away; the rest of the text follows."""
    MW, view, items = outlineTab
    editor = selectBoth(view, items)

    QTest.keyClicks(editor, "Two words")
    assert summaries(items) == ["Two ", "Two "]
    focusInAndOut(editor)
    assert summaries(items) == ["Two words", "Two words"]


def test_multiSelectionUndoneEditIsNoEdit(outlineTab):
    """A change undone before it was submitted leaves the items alone."""
    MW, view, items = outlineTab
    editor = selectBoth(view, items)

    QTest.keyClicks(editor, "Typo")
    editor.undo()
    focusInAndOut(editor)
    waitForDelayedSubmit(editor)
    assert summaries(items) == ["Summary A", "Summary B"]

    # Typed, then deleted again by hand: the field still says "Various".
    QTest.keyClicks(editor, "x")
    QTest.keyClick(editor, Qt.Key_Backspace)
    focusInAndOut(editor)
    waitForDelayedSubmit(editor)
    assert summaries(items) == ["Summary A", "Summary B"]


def test_multiSelectionNoEditAfterSubmit(outlineTab):
    """Once the user's text is written, a re-highlight does not write again."""
    MW, view, items = outlineTab
    editor = selectBoth(view, items)

    QTest.keyClicks(editor, "Common")
    focusInAndOut(editor)
    assert summaries(items) == ["Common", "Common"]

    # Another view changes one of them: the field shows "Various" again.
    MW.mdlOutline.setData(
        items[1].index().sibling(items[1].index().row(), Outline.summaryFull),
        "Changed elsewhere")
    pump()
    assert editor.toPlainText() == ""
    editor.highlighter.rehighlight()
    waitForDelayedSubmit(editor)
    focusInAndOut(editor)
    assert summaries(items) == ["Common", "Changed elsewhere"]


def test_singleSelectionUnchanged(outlineTab):
    """With one item selected, edits are submitted as before."""
    MW, view, items = outlineTab
    editor = MW.outlineItemEditor.txtSummaryFull
    assert editor.toPlainText() == "Summary A"

    focusInAndOut(editor)
    editor.highlighter.rehighlight()
    waitForDelayedSubmit(editor)
    assert summaries(items) == ["Summary A", "Summary B"]

    editor.moveCursor(editor.textCursor().End)
    QTest.keyClicks(editor, "!")
    waitForDelayedSubmit(editor)
    assert summaries(items) == ["Summary A!", "Summary B"]

    # Not tied to Qt's "modified" flag of the document
    editor.document().setModified(False)
    editor.moveCursor(editor.textCursor().End)
    QTest.keyClicks(editor, "?")
    editor.document().setModified(False)
    focusInAndOut(editor)
    assert summaries(items) == ["Summary A!?", "Summary B"]
