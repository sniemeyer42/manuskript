#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for mainWindow"""

from PyQt5.QtCore import Qt, QItemSelectionModel


def characterItems(lst):
    return [lst.topLevelItem(t).child(i)
            for t in range(lst.topLevelItemCount())
            for i in range(lst.topLevelItem(t).childCount())]


def test_characterMultiSelection(MWSampleProject):
    """Ctrl-/Shift-selecting characters must keep the multi-selection (#1449)."""
    MW = MWSampleProject
    MW.tabMain.setCurrentIndex(MW.TabPersos)
    lst = MW.lstCharacters
    items = characterItems(lst)
    assert len(items) >= 3
    ids = [i.data(0, Qt.UserRole) for i in items]

    # Click first character, then Ctrl-click the next two (the clicked item
    # becomes the current item, as with a real mouse click).
    lst.setCurrentItem(items[0], 0, QItemSelectionModel.ClearAndSelect)
    assert lst.currentCharacterIDs() == ids[:1]
    lst.setCurrentItem(items[1], 0, QItemSelectionModel.Select)
    assert sorted(lst.currentCharacterIDs()) == sorted(ids[:2])
    lst.setCurrentItem(items[2], 0, QItemSelectionModel.Select)
    assert sorted(lst.currentCharacterIDs()) == sorted(ids[:3])

    # Bulk info manager lists all selected characters
    assert MW.BulkManageUi is not None
    assert sorted(MW.bulkAffectedCharacters) == \
        sorted(i.text(0) for i in items[:3])

    # Switching tabs back and forth keeps the selection
    MW.tabMain.setCurrentIndex(MW.TabSummary)
    MW.tabMain.setCurrentIndex(MW.TabPersos)
    assert sorted(lst.currentCharacterIDs()) == sorted(ids[:3])

    # Back to a single selection
    lst.setCurrentItem(items[1], 0, QItemSelectionModel.ClearAndSelect)
    assert lst.currentCharacterIDs() == ids[1:2]
    assert MW.BulkManageUi is None
