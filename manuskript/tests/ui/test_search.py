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
