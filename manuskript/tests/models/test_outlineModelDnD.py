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

    # The same XML from another application (without Manuskript's mark) is
    # parsed with libxml2's default limits
    from PyQt5.QtCore import QMimeData
    foreign = QMimeData()
    foreign.setData("application/xml", mimeData.data("application/xml"))
    assert model.decodeMimeData(foreign) is None


@pytest.mark.parametrize("payload", [
    b"<outlineItems><outlineItem title='x'",        # malformed
    b"\xff\xfe<x/>",                                # not UTF-8
    b"<?xml version='1.0' encoding='UTF-8'?><outlineItems/>",
    b"<svg xmlns='http://www.w3.org/2000/svg'/>",   # foreign XML
    b"",
])
def test_decodeForeignMimeData(outlineModelStandalone, payload):
    """
    'application/xml' data from other applications (or garbage) must be
    ignored, not crash the app.
    """
    from PyQt5.QtCore import QMimeData
    model = outlineModelStandalone
    IDsBefore = model.rootItem.listAllIDs()
    folder = model.indexFromItem(model.rootItem.child(0))

    mimeData = QMimeData()
    mimeData.setData("application/xml", payload)
    assert not model.decodeMimeData(mimeData)
    assert not model.canDropMimeData(mimeData, Qt.MoveAction, -1, 0, folder)
    for action in [Qt.CopyAction, Qt.MoveAction]:
        assert not model.dropMimeData(mimeData, action, -1, 0, folder)
        assert not model.dropMimeData(mimeData, action, -1, 0, QModelIndex())
    assert model.rootItem.listAllIDs() == IDsBefore


def test_emptyClipboard(MWSampleProject, monkeypatch):
    """
    QClipboard.mimeData() can return None (empty clipboard on some
    platforms): context menu and paste must not crash.
    """
    from PyQt5.QtGui import QClipboard
    monkeypatch.setattr(QClipboard, "mimeData", lambda *args: None)
    MW = MWSampleProject
    model = MW.mdlOutline
    view = MW.treeRedacOutline
    IDsBefore = model.rootItem.listAllIDs()
    selectRows(view, ["40"])

    view.makePopupMenu()
    assert not view.actPaste.isEnabled()
    view.paste()
    assert model.rootItem.listAllIDs() == IDsBefore


def test_pasteFolderWithCollidingChildIDs(outlineModelStandalone):
    """
    Pasting a folder whose own ID is free, but whose children's IDs are
    already used, must not create duplicate IDs.
    (Remaining part of https://github.com/olivierkes/manuskript/issues/324)
    """
    from manuskript.models.outlineModel import outlineModel
    from manuskript.models import outlineItem
    source = outlineModelStandalone
    # Folder (ID 1) with Text A (ID 2) and Text B (ID 3)
    mimeData = source.mimeData([source.indexFromItem(source.rootItem.child(0))])

    # Other project, with IDs 2, 3 and 4 used, but not 1
    model = outlineModel(None)
    for title in ["x", "y", "z", "w"]:
        outlineItem(title=title, _type="md", parent=model.rootItem)
    model.removeRow(0)
    assert model.rootItem.listAllIDs() == ["0", "2", "3", "4"]

    assert model.dropMimeData(mimeData, Qt.CopyAction, -1, 0, QModelIndex())
    assert duplicateIDs(model) == []
    pasted = model.rootItem.child(3)
    assert pasted.title() == "Folder"
    assert [c.title() for c in pasted.children()] == ["Text A", "Text B"]
    assert len(model.rootItem.listAllIDs()) == 7


def test_pasteKeepsFreeIDsUnique(outlineModelStandalone):
    """An unused ID kept by a pasted item must not be given to another
    pasted item."""
    from PyQt5.QtCore import QMimeData
    model = outlineModelStandalone
    assert model.nextAvailableID == 5
    mimeData = QMimeData()
    mimeData.setData("application/xml",
        b'<outlineItems>'
        b'<outlineItem ID="1" title="F" type="folder">'
        b'<outlineItem ID="2" title="A" type="md"/>'
        b'<outlineItem ID="5" title="B" type="md"/>'
        b'</outlineItem>'
        b'<outlineItem ID="6" title="C" type="md"/>'
        b'</outlineItems>')

    assert model.dropMimeData(mimeData, Qt.CopyAction, -1, 0, QModelIndex())
    assert duplicateIDs(model) == []
    assert len(model.rootItem.listAllIDs()) == 9


def test_moveFromOtherModel(outlineModelStandalone):
    """Items moved (drag and drop) from another model, e.g. from another
    Manuskript window, get new IDs if theirs are already used."""
    from manuskript.models.outlineModel import outlineModel
    from manuskript.models import outlineItem
    source = outlineModelStandalone
    # Folder (ID 1) with Text A (ID 2) and Text B (ID 3)
    mimeData = source.mimeData([source.indexFromItem(source.rootItem.child(0))])

    model = outlineModel(None)
    for title in ["x", "y", "z"]:
        outlineItem(title=title, _type="md", parent=model.rootItem)
    assert model.rootItem.listAllIDs() == ["0", "1", "2", "3"]

    assert model.canDropMimeData(mimeData, Qt.MoveAction, -1, 0, QModelIndex())
    assert model.dropMimeData(mimeData, Qt.MoveAction, -1, 0, QModelIndex())
    assert duplicateIDs(model) == []
    moved = model.rootItem.child(3)
    assert [c.title() for c in moved.children()] == ["Text A", "Text B"]
    assert len(model.rootItem.listAllIDs()) == 7


def test_copyPasteAndDuplicateInSameProject(MWSampleProject):
    """Copy / paste and duplicate of a folder in the same project give new
    IDs to all copied items."""
    MW = MWSampleProject
    model = MW.mdlOutline
    view = MW.treeRedacOutline
    count = len(model.rootItem.listAllIDs())

    # Chapter 10 (3 texts), pasted into Chapter 12
    selectRows(view, ["29"])
    view.copy()
    selectRows(view, ["31"])
    view.paste()
    assert [c.title() for c in model.getItemByID("31").children()][-1] \
           == "Chapter 10"
    assert duplicateIDs(model) == []
    assert len(model.rootItem.listAllIDs()) == count + 4

    selectRows(view, ["29"])
    view.duplicate()
    assert duplicateIDs(model) == []
    assert len(model.rootItem.listAllIDs()) == count + 8


def test_dropOnFolderSignalsInsertedRows(outlineModelStandalone):
    """
    Dropping or pasting on a folder (row == -1) appends the items, and the
    model must signal the rows where they are really inserted.
    """
    from manuskript.enums import Outline
    model = outlineModelStandalone
    folder = model.indexFromItem(model.rootItem.child(0))
    other = model.indexFromItem(model.rootItem.child(1))
    textA = model.index(0, 0, folder)
    # Dropped or pasted on another cell of the folder's row (outline view)
    folderPOV = folder.sibling(folder.row(), Outline.POV)

    signaled = []
    def rowsAboutToBeInserted(parent, first, last):
        signaled.append((parent.internalPointer().title()
                         if parent.isValid() else "Root",
                         first, last, model.rowCount(parent)))
    model.rowsAboutToBeInserted.connect(rowsAboutToBeInserted)

    for parent, expected in [(other, ("Other folder", 0, 0, 0)),
                             (folder, ("Folder", 2, 2, 2)),
                             (folderPOV, ("Folder", 3, 3, 3)),
                             (QModelIndex(), ("Root", 2, 2, 2))]:
        signaled.clear()
        mimeData = model.mimeData([textA])
        assert model.dropMimeData(mimeData, Qt.CopyAction, -1, 0, parent)
        assert signaled == [expected]
        if parent.isValid():
            parent = parent.sibling(parent.row(), 0)
        row = expected[1]
        assert model.index(row, 0, parent).internalPointer().title() == "Text A"
        assert model.rowCount(parent) == row + 1


def selectedIDs(view):
    return sorted(set(i.internalPointer().ID() for i in view.getSelection()))


@pytest.mark.parametrize("viewName, columns", [("treeRedacOutline", 1),
                                               ("treeOutlineOutline", 1),
                                               ("treeOutlineOutline", 2),
                                               ("treeOutlineOutline", 7),
                                               ("treeOutlineOutline", 8)])
def test_moveUpAndDown(MWSampleProject, monkeypatch, viewName, columns):
    """
    Move up / down (Ctrl+Shift+Up / Down) moves each selected item by one
    row, whatever the number of visible columns (selectedIndexes() has one
    index per column), and does nothing for an item that is already first /
    last.
    """
    from manuskript import settings
    from manuskript.enums import Outline
    MW = MWSampleProject
    model = MW.mdlOutline
    view = getattr(MW, viewName)
    if viewName == "treeOutlineOutline":
        allColumns = [Outline.title, Outline.POV, Outline.status,
                      Outline.compile, Outline.wordCount, Outline.goal,
                      Outline.goalPercentage, Outline.label]
        monkeypatch.setattr(settings, "outlineViewColumns",
                            allColumns[:columns])
        view.hideColumns()
    # Chapter 9: 37, 38, 39
    selectRows(view, ["37"])
    assert len(view.selectedIndexes()) == columns

    view.moveUp()
    assert childIDs(model, "28") == ["37", "38", "39"]

    MW.projectDirty = False
    view.moveDown()
    assert childIDs(model, "28") == ["38", "37", "39"]
    assert selectedIDs(view) == ["37"]
    assert view.currentIndex().internalPointer().ID() == "37"
    assert MW.projectDirty

    view.moveDown()
    view.moveDown()
    assert childIDs(model, "28") == ["38", "39", "37"]
    assert view.currentIndex().row() == 2

    # Several items
    selectRows(view, ["39", "37"])
    view.moveUp()
    assert childIDs(model, "28") == ["39", "37", "38"]
    view.moveUp()
    assert childIDs(model, "28") == ["39", "37", "38"]
    assert selectedIDs(view) == ["37", "39"]
    view.moveDown()
    assert childIDs(model, "28") == ["38", "39", "37"]

    # Top-level items
    selectRows(view, ["35"])
    MW.projectDirty = False
    view.moveDown()
    assert [c.ID() for c in model.rootItem.children()] == ["34", "35", "60"]
    assert MW.projectDirty


def test_moveUpKeepsEditorIndex(MWSampleProject):
    """The editor showing a moved item still shows it after the move."""
    MW = MWSampleProject
    model = MW.mdlOutline
    view = MW.treeRedacOutline
    selectRows(view, ["42"])
    editor = MW.mainEditor.currentEditor()
    view.moveUp()
    assert childIDs(model, "29") == ["40", "42", "41"]
    assert editor.currentIndex.internalPointer().ID() == "42"
    assert editor.currentIndex.row() == 1


@pytest.fixture
def MWShown(MWSampleProject):
    """The main window with the sample project, shown (so that views have a
    geometry and can be clicked)."""
    from PyQt5.QtCore import QEvent
    from PyQt5.QtWidgets import qApp
    MW = MWSampleProject
    # Fewer editors to show (faster)
    MW.mainEditor.closeAllTabs()
    qApp.sendPostedEvents(None, QEvent.DeferredDelete)
    MW.show()
    MW.resize(1200, 800)
    qApp.processEvents()
    yield MW
    MW.hide()


def clickItem(view, ID, button=Qt.LeftButton, modifier=Qt.NoModifier):
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import qApp
    index = view.model().getIndexByID(ID)
    view.scrollTo(index)
    qApp.processEvents()
    pos = view.visualRect(index).center()
    QTest.mouseClick(view.viewport(), button, modifier, pos)
    qApp.processEvents()


@pytest.mark.parametrize("viewName, tab", [("treeRedacOutline", "TabRedac"),
                                           ("treeOutlineOutline", "TabOutline")])
def test_ctrlClickMultiSelection(MWShown, viewName, tab):
    """Ctrl+click adds an item to / removes it from the selection."""
    from PyQt5.QtWidgets import qApp
    MW = MWShown
    MW.tabMain.setCurrentIndex(getattr(MW, tab))
    view = getattr(MW, viewName)
    view.expandAll()
    qApp.processEvents()

    clickItem(view, "40")
    assert selectedIDs(view) == ["40"]
    clickItem(view, "42", modifier=Qt.ControlModifier)
    assert selectedIDs(view) == ["40", "42"]
    clickItem(view, "37", modifier=Qt.ControlModifier)
    assert selectedIDs(view) == ["37", "40", "42"]
    clickItem(view, "40", modifier=Qt.ControlModifier)
    assert selectedIDs(view) == ["37", "42"]
    clickItem(view, "41")
    assert selectedIDs(view) == ["41"]


def test_editorTabSwitchSelectsItemInTree(MWShown):
    """
    Switching editor tabs selects the tab's item in the editor's tree (only
    it, even if Ctrl is still held), and a Shift+click then selects the range
    from that item.
    """
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import qApp
    MW = MWShown
    MW.tabMain.setCurrentIndex(MW.TabRedac)
    view = MW.treeRedacOutline
    view.expandAll()
    qApp.processEvents()
    tabs = MW.mainEditor.currentTabWidget()

    clickItem(view, "37")
    clickItem(view, "41", modifier=Qt.ControlModifier)  # In a new tab
    clickItem(view, "42")
    assert tabs.count() == 2
    assert selectedIDs(view) == ["42"]

    tabs.setCurrentIndex(0)
    qApp.processEvents()
    assert selectedIDs(view) == ["37"]
    clickItem(view, "38", modifier=Qt.ShiftModifier)
    assert selectedIDs(view) == ["37", "38"]

    # E.g. Ctrl+Tab
    QTest.keyPress(MW.mainEditor, Qt.Key_Control, Qt.ControlModifier)
    tabs.setCurrentIndex(1)
    QTest.keyRelease(MW.mainEditor, Qt.Key_Control)
    qApp.processEvents()
    assert selectedIDs(view) == ["42"]
