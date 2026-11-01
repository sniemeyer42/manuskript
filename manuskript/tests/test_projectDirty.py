#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""
Tests for the "modified" state of the project (MainWindow.projectDirty). It decides
whether closing the project saves it (or asks), and it starts the autosave after
a change ("autosave if no changes").
"""

import time

import pytest
from PyQt5.QtCore import QModelIndex
from PyQt5.QtGui import QStandardItem
from PyQt5.QtWidgets import qApp, QMessageBox, QTreeWidgetItemIterator

from manuskript import settings
from manuskript.enums import Character
from manuskript.models import outlineItem
from manuskript.tests.conftest import closePreviousProject
from manuskript.tests.load_save.helpers import copySample


def processEvents(seconds=0.1):
    end = time.time() + seconds
    while time.time() < end:
        qApp.processEvents()


def isUnmodified(MW):
    return MW.projectDirty is False and not MW.saveTimerNoChanges.isActive()


def save(MW):
    assert MW.saveDatas()
    assert isUnmodified(MW)


@pytest.fixture
def project(MW, tmp_path):
    """Opens a copy of the sample project, returns its path."""
    closePreviousProject(MW)
    path = copySample(tmp_path)
    MW.loadProject(path)
    assert MW.currentProject == path
    assert settings.autoSaveNoChanges
    yield path
    closePreviousProject(MW)


def characterNotPOV(MW):
    """A character that is the POV of no scene: deleting it changes nothing else."""
    for c in MW.mdlCharacter.characters:
        if not MW.mdlOutline.findItemsByPOV(c.ID()):
            return c


def selectPlot(MW, ID):
    MW.lstPlots.setCurrentItem(MW.lstPlots.getItemByID(ID))
    assert MW.lstPlots.currentPlotID() == ID


###############################################################################
# Changes that add, remove or move rows (and emit no dataChanged)
###############################################################################

def addCharacter(MW):
    MW.btnAddPerso.click()


def removeCharacter(MW):
    MW.mdlCharacter.removeCharacter(characterNotPOV(MW).ID())


def addCharacterInfo(MW):
    MW.mdlCharacter.addCharacterInfo(MW.mdlCharacter.ID(0), "Height", "180 cm")


def removeCharacterInfo(MW):
    ID = MW.mdlCharacter.ID(0)
    MW.mdlCharacter.addCharacterInfo(ID, "Height", "180 cm")
    MW.lstCharacters.setCurrentItem(MW.lstCharacters.getItemByID(ID))
    MW.tblPersoInfos.selectRow(0)
    save(MW)
    MW.btnPersoRmInfo.click()


def addPlot(MW):
    MW.btnAddPlot.click()


def removePlot(MW):
    selectPlot(MW, "2")
    MW.btnRmPlot.click()


def addPlotStep(MW):
    selectPlot(MW, "1")
    MW.btnAddSubPlot.click()


def removePlotStep(MW):
    selectPlot(MW, "1")
    MW.btnAddSubPlot.click()
    save(MW)
    MW.btnRmSubPlot.click()


def addPlotCharacter(MW):
    selectPlot(MW, "0")
    MW.mdlPlots.addPlotPerso(2)


def removePlotCharacter(MW):
    selectPlot(MW, "2")
    MW.lstPlotPerso.setCurrentIndex(MW.mdlPlots.index(0, 0, MW.lstPlotPerso.rootIndex()))
    MW.btnRmPlotPerso.click()


def addWorldItem(MW):
    MW.btnAddWorld.click()


def removeWorldItem(MW):
    MW.treeWorld.setCurrentIndex(MW.mdlWorld.indexByID("5"))
    MW.btnRmWorld.click()


def addLabel(MW):
    MW.mdlLabels.appendRow(QStandardItem("New label"))


def removeLabel(MW):
    MW.mdlLabels.removeRows(MW.mdlLabels.rowCount() - 1, 1)


def addStatus(MW):
    MW.mdlStatus.appendRow(QStandardItem("New status"))


def removeStatus(MW):
    MW.mdlStatus.removeRows(MW.mdlStatus.rowCount() - 1, 1)


# These already marked the project as modified through the word counts
def addOutlineItem(MW):
    MW.mdlOutline.appendItem(outlineItem(title="New", _type="md"))


def removeOutlineItem(MW):
    MW.mdlOutline.removeIndex(MW.mdlOutline.index(0, 0, QModelIndex()))


def moveOutlineItem(MW):
    assert MW.mdlOutline.moveItemRow(0, 1)


@pytest.mark.parametrize("change", [
    addCharacter, removeCharacter, addCharacterInfo, removeCharacterInfo,
    addPlot, removePlot, addPlotStep, removePlotStep, addPlotCharacter, removePlotCharacter,
    addWorldItem, removeWorldItem, addLabel, removeLabel, addStatus, removeStatus,
    addOutlineItem, removeOutlineItem, moveOutlineItem,
], ids=lambda f: f.__name__)
def test_change_marks_project_modified(MW, project, monkeypatch, change):
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.Yes)
    assert isUnmodified(MW)

    change(MW)

    assert MW.projectDirty is True
    assert MW.saveTimerNoChanges.isActive()  # autosave if no changes


def test_reset_or_layout_change_marks_project_modified(MW, project):
    for model in [MW.mdlFlatData, MW.mdlOutline, MW.mdlCharacter, MW.mdlPlots,
                  MW.mdlWorld, MW.mdlStatus, MW.mdlLabels]:
        save(MW)
        model.layoutAboutToBeChanged.emit()
        model.layoutChanged.emit()  # e.g. after an import
        assert MW.projectDirty is True

        save(MW)
        model.beginResetModel()
        model.endResetModel()
        assert MW.projectDirty is True


###############################################################################
# What must not mark the project as modified
###############################################################################

def recordChanges(MW):
    """Returns the list of the changes to the project's models (changed data, added,
    removed or moved rows...) made from now on. Checking only projectDirty could miss
    one: the "no changes" autosave clears it a few seconds later."""
    changes = []
    for model in [MW.mdlFlatData, MW.mdlOutline, MW.mdlCharacter, MW.mdlPlots,
                  MW.mdlWorld, MW.mdlStatus, MW.mdlLabels]:
        for signal in [model.dataChanged, model.rowsInserted, model.rowsRemoved,
                       model.rowsMoved, model.modelReset, model.layoutChanged]:
            signal.connect(lambda *args, name="{!r}: {}".format(signal, signal.signal):
                           changes.append(name))
    return changes


def test_opening_a_project_does_not_modify_it(MW, project):
    changes = recordChanges(MW)
    processEvents(0.5)
    assert isUnmodified(MW)

    # Looking around
    for tab in range(MW.tabMain.count()):
        MW.tabMain.setCurrentIndex(tab)
        processEvents(0.05)

    MW.tabMain.setCurrentIndex(MW.TabPersos)
    for c in MW.mdlCharacter.characters:
        MW.lstCharacters.setCurrentItem(MW.lstCharacters.getItemByID(c.ID()))
        processEvents(0.02)

    MW.tabMain.setCurrentIndex(MW.TabPlots)
    it = QTreeWidgetItemIterator(MW.lstPlots)
    while it.value():
        MW.lstPlots.setCurrentItem(it.value())
        processEvents(0.02)
        it += 1

    MW.tabMain.setCurrentIndex(MW.TabWorld)

    def browse(view, model, parent=QModelIndex()):
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            view.setCurrentIndex(index)
            processEvents(0.02)
            browse(view, model, index)

    browse(MW.treeWorld, MW.mdlWorld)
    MW.tabMain.setCurrentIndex(MW.TabOutline)
    browse(MW.treeOutlineOutline, MW.mdlOutline)
    MW.tabMain.setCurrentIndex(MW.TabRedac)
    browse(MW.treeRedacOutline, MW.mdlOutline)
    processEvents(0.2)
    assert changes == []
    assert isUnmodified(MW)

    # Saving does not modify it (the "no changes" autosave would save again and again)
    save(MW)
    processEvents(0.2)
    assert changes == []
    assert isUnmodified(MW)

    # Nor does opening it again
    MW.closeProject()
    MW.loadProject(project)
    changes = recordChanges(MW)
    processEvents(0.5)
    assert changes == []
    assert isUnmodified(MW)


def test_closed_project_does_not_modify_the_next_one(MW, project):
    """The models of a closed project are not deleted: changes to them must not mark
    the project that is open now as modified."""
    characters, labels = MW.mdlCharacter, MW.mdlLabels
    MW.closeProject()
    MW.loadProject(project)
    assert isUnmodified(MW)

    characters.setData(characters.index(0, Character.name), "Someone else")
    labels.appendRow(QStandardItem("New label"))
    assert isUnmodified(MW)


###############################################################################
# Closing
###############################################################################

@pytest.mark.parametrize("saveOnQuit", [True, False])
def test_close_keeps_deleted_character_deleted(MW, project, monkeypatch, saveOnQuit):
    """File > Close saves (or asks to save) a project in which a character was deleted."""
    asked = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: asked.append(self.text()) or QMessageBox.Save)
    monkeypatch.setattr(settings, "saveOnQuit", saveOnQuit)

    ID = characterNotPOV(MW).ID()
    MW.tabMain.setCurrentIndex(MW.TabPersos)
    MW.lstCharacters.setCurrentItem(MW.lstCharacters.getItemByID(ID))
    MW.btnRmPerso.click()
    assert MW.mdlCharacter.getCharacterByID(ID) is None

    MW.actCloseProject.trigger()
    assert MW.currentProject is None
    # Without "save on quit", "Save changes to project...?"
    assert len(asked) == (0 if saveOnQuit else 1)

    MW.loadProject(project)
    assert MW.currentProject == project
    assert MW.mdlCharacter.getCharacterByID(ID) is None
