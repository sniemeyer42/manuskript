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


def test_tooltipStyleIsRestored(MWSampleProject, monkeypatch):
    """Custom tooltip colours are applied again when the project is loaded."""
    from PyQt5.QtWidgets import qApp
    from manuskript import settings

    MW = MWSampleProject
    # Loading the project replaces settings.tooltipStyle: give the module
    # its own tooltip settings back after the test.
    monkeypatch.setattr(settings, "tooltipStyle", dict(settings.tooltipStyle))
    try:
        settings.tooltipStyle["useSystemDefaultsForTooltips"] = False
        settings.tooltipStyle["backgroundColor"] = "#ff0000"
        settings.applyTooltipStyle()
        assert "#ff0000" in qApp.styleSheet()
        MW.saveDatas()

        # Reopen the project, e.g. after restarting Manuskript
        qApp.setStyleSheet("")
        project = MW.currentProject
        MW.closeProject()
        MW.loadProject(project)
        assert settings.tooltipStyle["useSystemDefaultsForTooltips"] is False
        assert "QToolTip" in qApp.styleSheet()
        assert "#ff0000" in qApp.styleSheet()

        # Back to the system defaults
        settings.tooltipStyle["useSystemDefaultsForTooltips"] = True
        settings.applyTooltipStyle()
        assert qApp.styleSheet() == ""
    finally:
        qApp.setStyleSheet("")


def test_styleWithTooltipColours(MWSampleProject, monkeypatch):
    """
    Settings show the active style while custom tooltip colours are used:
    the application style sheet then hides the name of the style.
    """
    from PyQt5.QtWidgets import qApp, QStyleFactory
    from PyQt5.QtCore import QSettings
    from manuskript import settings as S
    from manuskript.settingsWindow import settingsWindow

    style = qApp.style().objectName()
    assert style in [k.lower() for k in QStyleFactory.keys()]
    monkeypatch.setattr(S, "tooltipStyle", dict(S.tooltipStyle))
    S.tooltipStyle["useSystemDefaultsForTooltips"] = False
    qS = QSettings(qApp.organizationName(), qApp.applicationName())
    oldStyle = qS.value("applicationStyle")
    try:
        S.applyTooltipStyle()
        assert qApp.styleSheet()
        SW = settingsWindow(MWSampleProject)
        assert SW.cmbStyle.currentText().lower() == style

        # Also after choosing the style again in the settings
        SW.setStyle(SW.cmbStyle.currentText())
        assert qApp.styleSheet()
        SW = settingsWindow(MWSampleProject)
        assert SW.cmbStyle.currentText().lower() == style
    finally:
        qApp.setStyleSheet("")
        if oldStyle is None:
            qS.remove("applicationStyle")
        else:
            qS.setValue("applicationStyle", oldStyle)
    assert qApp.style().objectName() == style
