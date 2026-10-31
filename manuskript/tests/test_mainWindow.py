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
