#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the search panel."""

import pytest

from PyQt5.QtWidgets import QListWidgetItem

from manuskript.ui.search import search


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
