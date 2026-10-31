#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the search widget."""


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
