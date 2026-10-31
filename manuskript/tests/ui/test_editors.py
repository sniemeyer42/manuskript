#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the text editors (textEditView, MDEditView)."""

import pytest

from PyQt5.QtCore import QEvent
from PyQt5.QtGui import QSyntaxHighlighter, QTextCursor
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import qApp

from manuskript import settings
from manuskript.enums import Outline
from manuskript.ui.highlighters import MarkdownHighlighter
from manuskript.ui.views.MDEditView import MDEditView
from manuskript.ui.views.textEditView import textEditView


def pump():
    """Processes pending (queued) events."""
    for i in range(20):
        qApp.processEvents()


@pytest.fixture
def textItem(MWEmptyProject):
    """Returns a function creating a text item with the given text."""
    from manuskript.models import outlineItem

    def create(text):
        item = outlineItem(title="Text", _type="md",
                           parent=MWEmptyProject.mdlOutline.rootItem)
        item.setData(Outline.text, text)
        return item

    return create


def editorFor(item):
    """Returns a shown MDEditView editing the item's text."""
    ed = MDEditView(None)
    ed.resize(400, 300)
    ed.show()
    ed.setCurrentModelIndex(item.index())
    pump()
    return ed


def test_MDEditView_clickRectsAreDebounced(monkeypatch):
    """
    Clickable things are computed once changes have settled, and only for
    the visible part of the text, but every visible link gets its rect.
    """
    calls = []
    compute = MDEditView.computeClickRects

    def countingCompute(self):
        if self is ed:
            calls.append(self)
        compute(self)

    monkeypatch.setattr(MDEditView, "computeClickRects", countingCompute)

    ed = MDEditView(None)
    ed.resize(400, 300)
    ed.show()
    cursor = ed.textCursor()
    for i in range(200):
        cursor.insertText("Line {i} [link {i}](http://example.org/{i})\n"
                          .format(i=i))
    assert calls == []  # Nothing is computed while typing

    QTest.qWait(300)
    assert len(calls) == 1

    def hasRect(n):
        """Is the n-th link clickable, at the right place?"""
        c = QTextCursor(ed.document().findBlockByNumber(n))
        c.movePosition(QTextCursor.NextCharacter, n=len("Line {} ".format(n)))
        r = ed.cursorRect(c)
        return any(ct.rect.contains(r.center()) and
                   ct.texts[2] == "http://example.org/{}".format(n)
                   for ct in ed.clickRects)

    ed.verticalScrollBar().setValue(0)
    QTest.qWait(300)
    assert hasRect(0)
    assert hasRect(1)
    assert not hasRect(199)  # Not visible

    ed.verticalScrollBar().setValue(ed.verticalScrollBar().maximum())
    QTest.qWait(300)
    assert hasRect(199)
    assert not hasRect(0)
    ed.close()


def test_MDEditView_ctrlClickRightAfterScrolling(monkeypatch):
    """
    Ctrl+click right after scrolling opens the link under the mouse, not
    the one that was there before (the click rects are only recomputed
    some time after the last scroll step).
    """
    from PyQt5.QtCore import Qt
    from manuskript import functions as F
    opened = []
    monkeypatch.setattr(F, "openURL", opened.append)

    ed = MDEditView(None)
    ed.setEnabled(True)  # Disabled until an index is set
    ed.resize(400, 300)
    ed.show()
    ed.setPlainText("\n".join(
        "Line {i} [link {i}](http://example.org/{i})".format(i=i)
        for i in range(200)))
    QTest.qWait(300)
    scrollBar = ed.verticalScrollBar()
    scrollBar.setValue(scrollBar.value() + 10 * scrollBar.singleStep())
    n = ed.cursorForPosition(ed.viewport().rect().topLeft()).blockNumber() + 1
    assert n > 1
    cursor = QTextCursor(ed.document().findBlockByNumber(n))
    cursor.movePosition(QTextCursor.NextCharacter,
                        n=len("Line {} [".format(n)))
    QTest.mouseClick(ed.viewport(), Qt.LeftButton, Qt.ControlModifier,
                     ed.cursorRect(cursor).center())
    assert opened == ["http://example.org/{}".format(n)]
    ed.close()


def test_MDEditCompleter_refRectsAreDebounced(monkeypatch):
    """
    References are also scanned once changes have settled, but right away
    when the mouse needs them.
    """
    from PyQt5.QtCore import Qt
    from manuskript.models import references as Ref
    from manuskript.ui.views.MDEditCompleter import MDEditCompleter
    calls = []
    compute = MDEditCompleter.computeRefRects

    def countingCompute(self):
        if self is ed:
            calls.append(self)
        compute(self)

    monkeypatch.setattr(MDEditCompleter, "computeRefRects", countingCompute)
    opened = []
    monkeypatch.setattr(Ref, "open", opened.append)

    ed = MDEditCompleter(None)
    ed.setEnabled(True)  # Disabled until an index is set
    ed.resize(400, 300)
    ed.show()
    cursor = ed.textCursor()
    for i in range(200):
        cursor.insertText("Line {}\n".format(i))
    assert calls == []  # Nothing is computed while typing
    QTest.qWait(300)
    assert len(calls) == 1

    ed.moveCursor(QTextCursor.Start)  # Scrolls to the top
    cursor.setPosition(0)
    cursor.insertText("{T:1:Text} ")
    cursor.setPosition(3)
    QTest.mouseClick(ed.viewport(), Qt.LeftButton, Qt.NoModifier,
                     ed.cursorRect(cursor).center())
    assert len(calls) == 2
    assert opened == ["{T:1:Text}"]
    ed.close()


def test_MDEditView_clickRectsAfterEmojis():
    """
    Clickable things get the right rects after characters outside the BMP,
    which take two positions in the document.
    """
    ed = MDEditView(None)
    ed.resize(400, 300)
    ed.show()
    ed.setPlainText("\n".join(
        "\U0001F600 Line {i} [link {i}](http://example.org/{i})".format(i=i)
        for i in range(100)))
    ed.verticalScrollBar().setValue(ed.verticalScrollBar().maximum())
    QTest.qWait(300)

    block = ed.document().lastBlock()
    linkStart = block.text().index("[")
    cursor = QTextCursor(block)
    # + 1 for the emoji's second position, + 1 to be inside the link
    cursor.setPosition(block.position() + linkStart + 2)
    r = ed.cursorRect(cursor)
    assert any(ct.rect.contains(r.center()) and
               ct.texts[2] == "http://example.org/99"
               for ct in ed.clickRects)
    ed.close()


def test_MarkdownHighlighter_typingDoesNotRehighlightPreviousParagraphs(
        textItem, monkeypatch):
    """
    Typing in the last of many single-newline-separated paragraphs only
    highlights the changed paragraph, not all the previous ones (#1376).
    """
    ed = editorFor(textItem("\n".join(["A paragraph of prose."] * 30)))
    assert isinstance(ed.highlighter, MarkdownHighlighter)

    highlighted = []
    doHighlightBlock = MarkdownHighlighter.doHighlightBlock

    def countingDoHighlightBlock(self, text):
        if self is ed.highlighter:
            highlighted.append(self.currentBlock().blockNumber())
        doHighlightBlock(self, text)

    monkeypatch.setattr(MarkdownHighlighter, "doHighlightBlock",
                        countingDoHighlightBlock)

    cursor = ed.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText("x")
    pump()
    assert highlighted == [29]
    ed.close()


def hasLineBreakMarker(block):
    return any(r.start == len(block.text()) - 1 and r.length == 1 and
               r.format.background().style() != 0
               for r in block.layout().formats())


def test_MarkdownHighlighter_lineBreakMarkerIsUpdated(textItem):
    """
    A paragraph ending with two spaces gets its line-break marker as soon
    as a paragraph follows it.
    """
    ed = editorFor(textItem("foo  \nbar\nbaz"))
    assert hasLineBreakMarker(ed.document().firstBlock())
    ed.close()

    ed = editorFor(textItem("foo  \n"))
    assert not hasLineBreakMarker(ed.document().firstBlock())
    cursor = ed.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText("b")
    pump()
    assert hasLineBreakMarker(ed.document().firstBlock())
    ed.close()


@pytest.mark.parametrize("text, n, newText, marker", [
    ("foo  \nbar", 1, "# bar", False),  # The next line becomes a heading,
    ("- one  \n- two", 1, "## two", False),
    ("foo  \nbar\n", 2, "===", False),  # a Setext heading,
    ("foo  \nbar", 1, "", False),  # empty,
    ("foo  \nbar", 1, "***", False),  # a horizontal rule,
    ("foo  \n# bar", 1, "bar", True),  # or a paragraph again.
])
def test_MarkdownHighlighter_lineBreakMarkerFollowsNextLine(
        textItem, text, n, newText, marker):
    """
    The line-break marker of a line ending with two spaces is updated
    when the next line changes, whatever it becomes.
    """
    ed = editorFor(textItem(text))
    assert hasLineBreakMarker(ed.document().firstBlock()) != marker
    cursor = QTextCursor(ed.document().findBlockByNumber(n))
    cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    cursor.insertText(newText)
    pump()
    assert hasLineBreakMarker(ed.document().firstBlock()) == marker
    ed.close()


def test_MarkdownHighlighter_lineBreakMarkerWhenLineIsRemoved(textItem):
    """
    The line-break marker is updated when the line after it is removed.
    """
    ed = editorFor(textItem("foo  \n\nbar"))
    assert not hasLineBreakMarker(ed.document().firstBlock())
    cursor = QTextCursor(ed.document().lastBlock())
    cursor.deletePreviousChar()
    pump()
    assert ed.toPlainText() == "foo  \nbar"
    assert hasLineBreakMarker(ed.document().firstBlock())
    ed.close()


def test_MarkdownHighlighter_openingDoesNotRehighlightParagraphs(
        textItem, monkeypatch):
    """
    Opening a text highlights each paragraph only once, also the ones
    ending with a line break (two spaces), whose highlighting depends on
    the next paragraph.
    """
    rehighlighted = []
    onHighlightBlockAtPosition = MarkdownHighlighter.onHighlightBlockAtPosition

    def countingOnHighlightBlockAtPosition(self, position):
        rehighlighted.append(self.document().findBlock(position).blockNumber())
        onHighlightBlockAtPosition(self, position)

    monkeypatch.setattr(MarkdownHighlighter, "onHighlightBlockAtPosition",
                        countingOnHighlightBlockAtPosition)
    ed = editorFor(textItem("\n".join(["A paragraph of prose."] * 30 +
                                      ["A line break  "] * 30 +
                                      ["Last one."])))
    assert rehighlighted == []
    assert all(hasLineBreakMarker(ed.document().findBlockByNumber(n))
               for n in range(30, 60))
    ed.close()


@pytest.mark.parametrize("leave", ["Down", "click"])
def test_MDEditView_spellchecksParagraphWhenCursorLeavesIt(textItem, leave):
    """
    The last word of a paragraph is not spellchecked while the cursor is
    at its end (it may still be typed), but once the cursor leaves the
    paragraph, also with the arrow keys or the mouse.
    """
    from PyQt5.QtCore import Qt
    from manuskript.functions.spellchecker import BasicDictionary

    class Dictionary(BasicDictionary):
        def __init__(self):
            self._customDict = set()

        def isMisspelled(self, word):
            return word == "tehh"

    ed = MDEditView(None)
    ed.spellcheck = True
    ed._dict = Dictionary()
    ed.resize(400, 300)
    ed.show()
    ed.setCurrentModelIndex(
        textItem("First paragraph.\nSecond paragraph.").index())
    pump()

    def misspelled(block):
        return [(r.start, r.length) for r in block.layout().formats()
                if r.format.underlineStyle() != 0]

    cursor = QTextCursor(ed.document().firstBlock())
    cursor.movePosition(QTextCursor.EndOfBlock)
    ed.setTextCursor(cursor)
    QTest.keyClicks(ed, " tehh")
    pump()
    first = ed.document().firstBlock()
    assert misspelled(first) == []
    if leave == "Down":
        QTest.keyClick(ed, Qt.Key_Down)
    else:
        cursor = QTextCursor(ed.document().lastBlock())
        QTest.mouseClick(ed.viewport(), Qt.LeftButton, Qt.NoModifier,
                         ed.cursorRect(cursor).center())
    pump()
    assert ed.textCursor().block() == ed.document().lastBlock()
    assert misspelled(first) == [(17, 4)]
    ed.close()


def test_MDEditView_focusModeFromStartOfText(textItem, monkeypatch):
    """
    In focus mode, leaving the first paragraph from position 0 fades it.
    """
    monkeypatch.setitem(settings.textEditor, "focusMode", "paragraph")
    ed = editorFor(textItem("First paragraph here.\n"
                            "Second paragraph here.\n"
                            "Third paragraph here."))

    def faded(n):
        formats = ed.document().findBlockByNumber(n).layout().formats()
        return bool(formats) and all(
            r.format.foreground().color().alpha() < 255 for r in formats)

    cursor = ed.textCursor()
    cursor.movePosition(QTextCursor.End)
    ed.setTextCursor(cursor)
    pump()
    cursor.movePosition(QTextCursor.Start)
    ed.setTextCursor(cursor)
    pump()
    assert [faded(n) for n in range(3)] == [False, True, True]
    cursor.movePosition(QTextCursor.NextBlock)
    ed.setTextCursor(cursor)
    pump()
    assert [faded(n) for n in range(3)] == [True, False, True]
    ed.close()


def test_MDEditView_keepsOneHighlighter(textItem):
    """
    Changing the edited item does not stack highlighters on the document.
    """
    item1, item2 = textItem("First text."), textItem("Second text.")
    ed = editorFor(item1)
    for item in [item2, item1, item2]:
        ed.setCurrentModelIndex(item.index())
        pump()
    qApp.sendPostedEvents(None, QEvent.DeferredDelete)
    highlighters = ed.document().findChildren(QSyntaxHighlighter)
    assert highlighters == [ed.highlighter]
    assert isinstance(ed.highlighter, MarkdownHighlighter)
    assert ed.toPlainText() == "Second text."
    ed.close()


def test_textEditView_toIdealText():
    """
    Like QTextDocument.toPlainText(), but keeps non-breaking spaces.
    """
    ed = textEditView(None)
    ed.setPlainText("a\u00a0b\nc")
    cursor = ed.textCursor()
    cursor.movePosition(QTextCursor.End)
    cursor.insertText("d\u2028e")
    cursor.insertTable(1, 1)
    cursor.insertText("f")
    assert ed.document().toRawText() == \
        "a\u00a0b\u2029cd\u2028e\ufdd0f\ufdd1"
    assert ed.toIdealText() == "a\u00a0b\ncd\ne\nf\n"
    assert ed.toPlainText() == ed.toIdealText()


def test_lineEditView_submitsOncePerEdit(textItem, monkeypatch):
    """
    Changing the edited item does not connect textEdited to submit once
    more each time (every keystroke was submitted once per item change).
    """
    from manuskript.ui.views.lineEditView import lineEditView

    calls = []
    submit = lineEditView.submit

    def countingSubmit(self):
        calls.append(self)
        submit(self)

    monkeypatch.setattr(lineEditView, "submit", countingSubmit)

    item1, item2 = textItem("First text."), textItem("Second text.")
    item2.setData(Outline.title, "Second")
    edit = lineEditView(None)
    for item in [item1, item2, item1, item2]:
        edit.setCurrentModelIndex(item.index())
    assert edit.text() == "Second"
    QTest.keyClick(edit, "x")
    assert len(calls) == 1
    assert item2.title() == "Secondx"
    assert item1.title() == "Text"


def typeAtEnd(ed, text):
    cursor = ed.textCursor()
    cursor.movePosition(QTextCursor.End)
    ed.setTextCursor(cursor)
    QTest.keyClicks(ed, text)


def test_textEditView_submitsPendingTextWhenIndexChanges(textItem):
    """
    What was just typed goes to the item being left, even if the editor
    keeps the focus (e.g. fullscreen editor, Alt+Right).
    """
    item1, item2 = textItem("First text."), textItem("Second text.")
    ed = editorFor(item1)
    typeAtEnd(ed, "x")
    assert ed.updateTimer.isActive()  # Submit is still pending
    ed.setCurrentModelIndex(item2.index())
    assert item1.text() == "First text.x"
    assert item2.text() == "Second text."
    assert ed.toPlainText() == "Second text."
    ed.close()


def test_mainWindow_saveDatasSubmitsPendingText(MWEmptyProject, textItem,
                                                monkeypatch):
    """
    Saving (Ctrl+S, Ctrl+Q) saves what was just typed in the editors.
    """
    from manuskript import loadSave
    item = textItem("Some text.")
    saved = []
    monkeypatch.setattr(loadSave, "saveProject",
                        lambda: saved.append(item.text()) or True)
    ed = editorFor(item)
    typeAtEnd(ed, " More")
    assert ed.updateTimer.isActive()  # Submit is still pending
    MWEmptyProject.saveDatas()
    assert saved == ["Some text. More"]
    ed.close()


def test_textEditView_submitsPendingTextWhenIndexesChange(textItem):
    """
    Same when the editor gets several items at once (outline item editor).
    """
    item1, item2 = textItem("First text."), textItem("Second text.")
    ed = editorFor(item1)
    typeAtEnd(ed, "x")
    assert ed.updateTimer.isActive()  # Submit is still pending
    ed.setCurrentModelIndexes([item1.index(), item2.index()])
    assert not ed.updateTimer.isActive()
    assert item1.text() == "First text.x"
    assert item2.text() == "Second text."
    ed.close()


@pytest.mark.parametrize("close", ["closeProject", "closeEvent"])
def test_mainWindow_closeSubmitsPendingText(MWEmptyProject, textItem,
                                            monkeypatch, close):
    """
    Closing the project or quitting submits what was just typed before
    checking for unsaved changes ("save on quit" off: "Save changes?").
    """
    from PyQt5.QtGui import QCloseEvent
    MW = MWEmptyProject
    item = textItem("Some text.")
    ed = editorFor(item)
    typeAtEnd(ed, " More")
    assert ed.updateTimer.isActive()  # Submit is still pending
    MW.projectDirty = False  # As if just saved
    monkeypatch.setattr(settings, "saveOnQuit", False)
    monkeypatch.setattr(settings, "openIndexes", settings.openIndexes)
    monkeypatch.setattr(settings, "lastTab", settings.lastTab)
    monkeypatch.setattr(MW.mainEditor, "close", lambda: True)
    asked = []

    def handleUnsavedChanges():
        asked.append((MW.projectDirty, item.text()))
        return False  # "Cancel": the project stays open

    monkeypatch.setattr(MW, "handleUnsavedChanges", handleUnsavedChanges)
    if close == "closeProject":
        MW.closeProject()
    else:
        event = QCloseEvent()
        MW.closeEvent(event)
        assert not event.isAccepted()
    assert asked == [(True, "Some text. More")]
    assert MW.currentProject
    ed.close()
