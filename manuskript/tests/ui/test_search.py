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
