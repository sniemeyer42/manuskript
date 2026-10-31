#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for drag and drop, copy / paste and moving of outline items."""

import pytest

from PyQt5.QtCore import Qt, QModelIndex, QItemSelectionModel


def duplicateIDs(model):
    IDs = model.rootItem.listAllIDs()
    return sorted(set(i for i in IDs if IDs.count(i) > 1))


def childIDs(model, ID):
    return [c.ID() for c in model.getItemByID(ID).children()]


def selectRows(view, IDs):
    """Selects the items with the given IDs in `view`, the first one being
    the current index (like a click, followed by ctrl+clicks)."""
    model = view.model()
    sm = view.selectionModel()
    sm.clear()
    for k, ID in enumerate(IDs):
        idx = model.getIndexByID(ID)
        if k == 0:
            sm.setCurrentIndex(idx, QItemSelectionModel.ClearAndSelect |
                                    QItemSelectionModel.Rows)
        else:
            sm.select(idx, QItemSelectionModel.Select |
                           QItemSelectionModel.Rows)


def internalMove(view, row, parent):
    """
    Does what Qt does for an internal drag and drop with Qt.MoveAction:
    first QAbstractItemView.dropEvent calls model.dropMimeData, then once
    QDrag.exec() returns, the source view removes the rows that are selected
    at that moment (QAbstractItemViewPrivate::clearOrRemove).
    """
    model = view.model()
    indexes = [i for i in view.selectedIndexes()
               if model.flags(i) & Qt.ItemIsDragEnabled]
    mimeData = model.mimeData(indexes)
    assert model.canDropMimeData(mimeData, Qt.MoveAction, row, 0, parent)
    assert model.dropMimeData(mimeData, Qt.MoveAction, row, 0, parent)

    selection = view.selectionModel().selection()
    for r in [selection[i] for i in range(selection.count())]:
        p = QModelIndex(r.parent())
        if r.left() != 0 or r.right() != model.columnCount(p) - 1:
            continue
        model.removeRows(r.top(), r.bottom() - r.top() + 1, p)


@pytest.mark.parametrize("sources, target, where, parentID, expected", [
    # Scene upwards within a chapter
    (["41"], "40", "above", "29", ["41", "40", "42"]),
    # Scene downwards within a chapter
    (["43"], "44", "below", "30", ["44", "43"]),
    # Folder upwards
    (["31"], "29", "above", "34", ["27", "28", "31", "29", "30"]),
    # Folder downwards
    (["27"], "30", "below", "34", ["28", "29", "30", "27", "31"]),
    # Several items from different folders, dropped on a folder
    (["37", "45"], "49", "on", "49", ["54", "55", "56", "37", "45"]),
    # Several items from another folder, dropped above an item
    (["57", "58"], "54", "above", "49", ["57", "58", "54", "55", "56"]),
])
def test_dragAndDropInEditorTree(MWSampleProject, sources, target, where,
                                 parentID, expected):
    """
    Drag and drop in the editor's tree must move the dragged items, and
    must not delete other items nor leave duplicates behind.
    (https://github.com/olivierkes/manuskript/issues/719, #1264)
    """
    MW = MWSampleProject
    model = MW.mdlOutline
    view = MW.treeRedacOutline
    IDsBefore = sorted(model.rootItem.listAllIDs())

    # Selecting in the tree also opens the (first) item in the editor
    selectRows(view, sources)
    editor = MW.mainEditor.currentEditor()
    assert editor.currentIndex.internalPointer().ID() == sources[0]

    targetIdx = model.getIndexByID(target)
    if where == "on":
        row, parent = -1, targetIdx
    elif where == "above":
        row, parent = targetIdx.row(), targetIdx.parent()
    else:
        row, parent = targetIdx.row() + 1, targetIdx.parent()

    internalMove(view, row, parent)

    assert sorted(model.rootItem.listAllIDs()) == IDsBefore
    assert duplicateIDs(model) == []
    assert childIDs(model, parentID) == expected

    # The editor still shows the moved item, and the one in the model
    # (not the removed original)
    item = editor.currentIndex.internalPointer()
    assert item is model.getItemByID(sources[0])
    assert editor.currentIndex.row() == item.row()


@pytest.fixture
def outlineModelStandalone():
    """Returns an outlineModel (not linked to the main window) with:
      * Folder (ID 1)
        * Text A (ID 2)
        * Text B (ID 3)
      * Other folder (ID 4)
    """
    from manuskript.models.outlineModel import outlineModel
    from manuskript.models import outlineItem
    model = outlineModel(None)
    folder = outlineItem(title="Folder", _type="folder", parent=model.rootItem)
    outlineItem(title="Text A", _type="md", parent=folder)
    outlineItem(title="Text B", _type="md", parent=folder)
    outlineItem(title="Other folder", _type="folder", parent=model.rootItem)
    assert model.rootItem.listAllIDs() == ["0", "1", "2", "3", "4"]
    return model


def test_dragAndCopyHugeItem(outlineModelStandalone):
    """
    Items whose XML is bigger than libxml2's default limit (10 MB) can be
    dragged, copied, pasted and duplicated.
    (https://github.com/olivierkes/manuskript/issues/918, #1193, #1216)
    """
    model = outlineModelStandalone
    folder = model.rootItem.child(0)
    other = model.indexFromItem(model.rootItem.child(1))
    # 10.5 MB in a single attribute (notes, to avoid slow word counts)
    bigText = "word " * 2100000
    notes = folder.enum.notes
    folder.child(0).setData(notes, bigText)

    mimeData = model.mimeData([model.indexFromItem(folder)])
    items = model.decodeMimeData(mimeData)
    assert [i.title() for i in items] == ["Folder"]
    assert items[0].child(0).data(notes) == bigText
    assert model.canDropMimeData(mimeData, Qt.MoveAction, -1, 0, other)
    assert model.dropMimeData(mimeData, Qt.CopyAction, -1, 0, other)
    assert model.rootItem.child(1).child(0).child(0).data(notes) == bigText

    # abstractItem.setFromXML (used by copy(), split, import preview, ...)
    assert folder.copy().child(0).data(notes) == bigText
