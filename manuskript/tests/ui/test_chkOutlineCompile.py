#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the compile check box of the properties view."""

from PyQt5.QtCore import Qt

from manuskript.enums import Outline


def test_compileCheckBoxDoesNotWriteInheritedState():
    """
    Selecting an item that is excluded from compile only because its
    parent is, must not write that state into the item itself. A click by
    the user still does.
    """
    from manuskript.models.outlineModel import outlineModel
    from manuskript.models import outlineItem
    from manuskript.ui.views.chkOutlineCompile import chkOutlineCompile

    model = outlineModel(None)
    folder = outlineItem(title="Folder", _type="folder", parent=model.rootItem)
    child1 = outlineItem(title="Child 1", _type="md", parent=folder)
    child2 = outlineItem(title="Child 2", _type="md", parent=folder)
    other = outlineItem(title="Other", _type="md", parent=model.rootItem)
    folder.setData(Outline.compile, 0)
    assert not child1.compile()

    chk = chkOutlineCompile()
    chk.setModel(model)
    chk.setCurrentModelIndex(model.indexFromItem(other))
    assert chk.checkState() == Qt.Checked

    # One item
    chk.setCurrentModelIndex(model.indexFromItem(child1))
    assert chk.checkState() == Qt.Unchecked
    # Several items
    chk.setCurrentModelIndex(model.indexFromItem(other))
    chk.setCurrentModelIndexes([model.indexFromItem(child1),
                                model.indexFromItem(child2)])
    assert chk.checkState() == Qt.Unchecked

    assert child1.data(Outline.compile) == 2
    assert child2.data(Outline.compile) == 2
    folder.setData(Outline.compile, 2)
    assert child1.compile() and child2.compile()

    # A click still changes the item
    chk.setCurrentModelIndex(model.indexFromItem(child1))
    assert chk.checkState() == Qt.Checked
    chk.click()
    assert chk.checkState() == Qt.Unchecked
    assert not child1.compile()
    assert child2.compile()
