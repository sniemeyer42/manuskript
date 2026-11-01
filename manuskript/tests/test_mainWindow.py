#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for mainWindow"""


def selectCharacters(MW, IDs):
    """Selects the characters with the given IDs in the character list."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QTreeWidgetItemIterator

    tree = MW.lstCharacters
    tree.clearSelection()
    it = QTreeWidgetItemIterator(tree)
    while it.value():
        if it.value().data(0, Qt.UserRole) in IDs:
            it.value().setSelected(True)
        it += 1
    assert sorted(tree.currentCharacterIDs()) == sorted(IDs)


def test_deleteCharactersResetsPOV(MWSampleProject, monkeypatch):
    """
    Deleting one or several characters clears the POV of their scenes.
    """
    from PyQt5.QtWidgets import QMessageBox
    from manuskript.models import references as Ref
    MW = MWSampleProject
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *args: QMessageBox.Yes))

    IDs = [MW.mdlCharacter.ID(0), MW.mdlCharacter.ID(1)]
    sceneIDs = []
    for ID in IDs:
        sceneIDs += MW.mdlOutline.findItemsByPOV(ID)
    assert sceneIDs  # the sample project uses both as POV

    selectCharacters(MW, IDs)
    MW.deleteCharacter()

    for ID in IDs:
        assert MW.mdlCharacter.getCharacterByID(ID) is None
        assert MW.mdlOutline.findItemsByPOV(ID) == []
    for sceneID in sceneIDs:
        assert MW.mdlOutline.getItemByID(sceneID).POV() in ["", None]

    # A POV that points to a non-existent character (e.g. in a project
    # saved by an older version) must not break the reference infos.
    item = MW.mdlOutline.getItemByID(sceneIDs[0])
    item.setData(item.enum.POV, "999")
    assert "<h1>" in Ref.infos(Ref.textReference(sceneIDs[0]))


def test_navigateAfterCloseProject(MWSampleProject, monkeypatch):
    """
    After closing a project, Back and Forward are disabled and do nothing:
    the history must not lead to the items of the closed project.
    """
    import sys
    MW = MWSampleProject
    # Exceptions raised in slots called by Qt end up here
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: errors.append(args))

    MW.tabMain.setCurrentIndex(MW.TabPersos)
    for ID in ["0", "1", "2"]:
        MW.lstCharacters.setCurrentItem(MW.lstCharacters.getItemByID(ID))
    MW.navigateBack()
    assert MW.actBack.isEnabled() and MW.actForward.isEnabled()

    MW.projectDirty = False
    MW.closeProject()
    assert not MW.menuNavigate.isEnabled()
    assert not MW.actBack.isEnabled()
    assert not MW.actForward.isEnabled()

    MW.navigateBack()
    MW.navigateForward()
    assert errors == []
    assert MW.stack.currentIndex() == 0  # still on the welcome screen


def test_closeAndReopenProject(MWNoProject, tmp_path, monkeypatch):
    """
    After closing a project and opening one again in the same session, the
    buttons must only be connected to the new models, and the character
    panel and history navigation must still work.
    """
    import os
    import shutil
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QDialog, QTreeWidgetItemIterator
    from manuskript import functions as F
    from manuskript.enums import Plot
    MW = MWNoProject

    # Copy of the sample project
    spDir = F.appPath("sample-projects")
    path = str(tmp_path / "book-of-acts.msk")
    shutil.copyfile(os.path.join(spDir, "book-of-acts.msk"), path)
    shutil.copytree(os.path.join(spDir, "book-of-acts"), path[:-4])
    MW.loadProject(path)
    assert MW.currentProject

    # The user looked at a character before closing the project
    MW.tabMain.setCurrentIndex(MW.TabPersos)
    MW.lstCharacters.setCurrentItem(MW.lstCharacters.getItemByID("0"))

    MW.closeProject()
    MW.loadProject(path)

    for button in [MW.btnAddPlot, MW.btnRmPlot, MW.btnRmSubPlot,
                   MW.btnAddWorld, MW.btnRmWorld,
                   MW.btnPersoAddInfo, MW.btnPersoRmInfo]:
        assert button.receivers(button.clicked) == 1
    assert MW.history.navigated._methods == [MW.navigated]

    # Character panel (the previous character is selected again)
    character = MW.lstCharacters.currentCharacter()
    assert character.ID() == "0"
    assert MW.tabPersos.isEnabled()
    assert MW.tblPersoInfos.rootIndex() == character.index()
    monkeypatch.setattr(QDialog, "exec_", lambda self: QDialog.Accepted)
    count = len(character.infos)
    MW.btnPersoAddInfo.click()
    assert len(character.infos) == count + 1

    # Back
    MW.lstCharacters.setCurrentItem(MW.lstCharacters.getItemByID("1"))
    MW.lstCharacters.setCurrentItem(MW.lstCharacters.getItemByID("2"))
    MW.navigateBack()
    assert MW.lstCharacters.currentCharacterID() == "1"

    # Remove a plot step
    MW.tabMain.setCurrentIndex(MW.TabPlots)
    it = QTreeWidgetItemIterator(MW.lstPlots)
    while it.value() and it.value().data(0, Qt.UserRole) is None:
        it += 1
    MW.lstPlots.setCurrentItem(it.value())
    assert MW.tabPlot.isEnabled()
    index = MW.lstPlots.currentPlotIndex()
    steps = MW.mdlPlots.item(index.row(), Plot.steps)
    if steps is None or steps.rowCount() == 0:
        MW.btnAddSubPlot.click()
        steps = MW.mdlPlots.item(index.row(), Plot.steps)
    count = steps.rowCount()
    MW.lstSubPlots.setCurrentIndex(
        MW.lstSubPlots.model().index(0, 0, MW.lstSubPlots.rootIndex()))
    MW.btnRmSubPlot.click()
    assert steps.rowCount() == count - 1

    # Remove a world item
    count = MW.mdlWorld.rowCount()
    MW.treeWorld.setCurrentIndex(MW.mdlWorld.index(0, 0))
    MW.btnRmWorld.click()
    assert MW.mdlWorld.rowCount() == count - 1


def test_closeEventClosesOtherWindows(MWNoProject):
    """
    Closing the main window also closes parentless windows like the About
    dialog, which would otherwise keep the application running.
    """
    from PyQt5.QtGui import QCloseEvent
    MW = MWNoProject

    MW.about()
    assert MW.dialog.isVisible()
    # Run what closing the main window does, without closing it
    event = QCloseEvent()
    MW.closeEvent(event)
    assert event.isAccepted()
    assert not MW.dialog.isVisible()
