#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the text editors (textEditView, MDEditView)."""

from PyQt5.QtGui import QTextCursor
from PyQt5.QtTest import QTest

from manuskript.ui.views.MDEditView import MDEditView


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
