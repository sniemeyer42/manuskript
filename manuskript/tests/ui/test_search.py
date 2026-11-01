#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the search widget."""

import pytest

from PyQt5.QtWidgets import QListWidgetItem

from manuskript.ui.search import search


def test_searchNewProject(MWEmptyProject):
    """
    Searching in a new project, where the book summary fields have never
    been edited (so their items don't exist yet), must not raise.
    """
    from PyQt5.QtGui import QStandardItem
    from PyQt5.QtWidgets import qApp
    MW = MWEmptyProject
    search = MW.widget

    assert MW.mdlFlatData.item(1, 0) is None
    search.searchTextInput.setText("sentence")
    search.search()
    assert search.result.count() == 0
    assert qApp.overrideCursor() is None

    # Only one summary field edited: it is found, the others are skipped
    MW.mdlFlatData.setItem(1, 1, QStandardItem("A sentence"))
    search.search()
    assert search.result.count() == 1
    assert qApp.overrideCursor() is None


def test_openStaleSearchResult(MWSampleProject):
    """
    Opening a search result whose item was deleted after the search must
    not raise, and results must not survive closing the project.
    """
    from PyQt5.QtCore import Qt
    from manuskript.enums import Model, Outline
    MW = MWSampleProject
    search = MW.widget

    search.searchTextInput.setText("Jesus")
    search.search()
    rows = [r for r in range(search.result.count())
            if search.result.item(r).data(Qt.UserRole).type() == Model.Outline
            and search.result.item(r).data(Qt.UserRole).column() == Outline.text]
    assert rows
    item = search.result.item(rows[0])
    index = MW.mdlOutline.getIndexByID(item.data(Qt.UserRole).id())

    # Delete the text, with no editor tab open
    MW.mainEditor.closeAllTabs()
    MW.mdlOutline.removeRow(index.row(), index.parent())
    search.openItem(item)
    assert MW.mainEditor.currentEditor() is None

    MW.projectDirty = False
    MW.closeProject()
    assert search.result.count() == 0

@pytest.fixture
def searchWidget():
    widget = search()
    widget.opened = []
    widget.openItem = lambda item: widget.opened.append(widget.result.row(item))
    for i in range(3):
        QListWidgetItem("Result {}".format(i), widget.result)
    widget.result.setCurrentRow(-1)
    return widget


def test_nextSearchResult_opensEveryResult(searchWidget):
    """F3 opens each result, including the first one when wrapping around."""
    w = searchWidget
    for i in range(4):
        w.nextSearchResult()
    assert w.opened == [0, 1, 2, 0]


def test_previousSearchResult_opensEveryResult(searchWidget):
    """Shift+F3 opens each result, including the first one."""
    w = searchWidget
    w.result.setCurrentRow(2)
    for i in range(3):
        w.previousSearchResult()
    assert w.opened == [1, 0, 2]


def compileWith(text, regex=False, matchWords=False, caseSensitive=False):
    widget = search()
    widget.searchMenu.options["Regex"][1] = regex
    widget.searchMenu.options["MatchWords"][1] = matchWords
    widget.searchMenu.options["CS"][1] = caseSensitive
    return widget.compileRegex(text)


def matches(regex, text):
    return [m.group() for m in regex.finditer(text)]


def test_compileRegex_matchWords():
    """'Match words' only matches whole words."""
    r = compileWith("cat", matchWords=True)
    assert matches(r, "catalog cat bobcat Cat") == ["cat", "Cat"]

    # Terms starting or ending with punctuation
    r = compileWith("Mr.", matchWords=True)
    assert matches(r, "Hello Mr. Smith") == ["Mr."]
    r = compileWith("e.g.", matchWords=True)
    assert matches(r, "(e.g. this)") == ["e.g."]


def test_compileRegex_regexMatchWords():
    """With 'Regex' and 'Match words', the whole pattern must be a word."""
    r = compileWith("cat|dog", regex=True, matchWords=True)
    assert matches(r, "catalog hotdog cat dog") == ["cat", "dog"]
