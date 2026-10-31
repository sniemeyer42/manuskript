#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for settingsWindow"""

from manuskript import functions as F

def test_general(MWSampleProject, monkeypatch):
    MW = MWSampleProject

    # Loading from mainWindow
    MW.actSettings.triggered.emit()
    assert MW.sw.isVisible()
    MW.sw.close()
    MW.actLabels.triggered.emit()
    assert MW.sw.isVisible()
    MW.sw.close()
    MW.actStatus.triggered.emit()
    assert MW.sw.isVisible()
    MW.sw.hide()
    MW.sw.setTab("General")

    SW = MW.sw

    # Imports
    from PyQt5.QtWidgets import qApp, QStyleFactory
    from PyQt5.QtCore import QSettings, Qt
    qS = QSettings(qApp.organizationName(), qApp.applicationName())
    from manuskript import settings as S

    # Style
    assert SW.cmbStyle.count() == len(list(QStyleFactory.keys()))
    if qS.value("applicationStyle"):
        assert SW.cmbStyle.currentText() == qS.value("applicationStyle")
    ## Seg fault when trying to set the style in tests:
    # for s in styles:
    #     SW.cmbStyle.setCurrentText(s)
        # assert S.value("applicationStyle") == s

    # Translations
    if qS.value("applicationTranslation"):
        assert (SW.cmbTranslation.currentData()
                == qS.value("applicationTranslation"))
    from PyQt5.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *args, **kwargs: QMessageBox.Ok)
    oldTranslation = qS.value("applicationTranslation")
    for name in SW.translations:
        # Choose the language as the user would
        SW.cmbTranslation.setCurrentText(name)
        SW.cmbTranslation.activated.emit(SW.cmbTranslation.currentIndex())
        assert qS.value("applicationTranslation") == SW.translations[name]
    # Do not change the language of the next test runs
    if oldTranslation is None:
        qS.remove("applicationTranslation")
    else:
        qS.setValue("applicationTranslation", oldTranslation)

    def switchCheckBoxAndAssert(chk, settings):
        """
        Asserts that the check state is that of settings, change checkstate
        and asserts settings has been changed.
        Settings is a function that returns the value.
        """
        state = settings()
        assert chk.isChecked() == state
        chk.setChecked(not state)
        assert chk.isChecked() != state

    # Loading and Saving
    SW.txtAutoSave.setText("0")
    SW.txtAutoSaveNoChanges.setText("0")
    switchCheckBoxAndAssert(SW.chkAutoLoad,
                            lambda: qS.value("autoLoad", type=bool))
    switchCheckBoxAndAssert(SW.chkAutoSave,
                            lambda: S.autoSave)
    switchCheckBoxAndAssert(SW.chkAutoSaveNoChanges,
                            lambda: S.autoSaveNoChanges)
    switchCheckBoxAndAssert(SW.chkSaveOnQuit,
                            lambda: S.saveOnQuit)
    switchCheckBoxAndAssert(SW.chkSaveToZip,
                            lambda: S.saveToZip)

    # Revisions
    switchCheckBoxAndAssert(SW.chkRevisionsKeep,
                            lambda: S.revisions["keep"])
    switchCheckBoxAndAssert(SW.chkRevisionRemove,
                            lambda: S.revisions["smartremove"])

    # Views
    # Simple way here, we just call the functions.
    SW.cmbTreeIcon.currentIndexChanged.emit(0)
    SW.cmbOutlineIcon.currentIndexChanged.emit(0)
    SW.cmbCorkIcon.currentIndexChanged.emit(0)
    SW.chkOutlineTitle.setChecked(Qt.Checked)  #outlineColumnsChanged
    SW.chkOutlineTitle.setChecked(Qt.Unchecked)
    SW.chkOutlineTitle.setChecked(Qt.Checked)
    # Can't test because of the dialog
    # assert SW.setCorkColor() == None
    SW.sldTreeIconSize.setValue(SW.sldTreeIconSize.value() + 1)
    SW.rdoCorkNewStyle.toggled.emit(True)
    SW.cmbCorkImage.currentIndexChanged.emit(0)
    SW.cmbCorkImage.currentIndexChanged.emit(1)
    # Test editor: same problem as above
    # choseEditorFontColor
    # choseEditorMisspelledColor
    # choseEditorBackgroundColor
    # Test editor
    switchCheckBoxAndAssert(SW.chkEditorBackgroundTransparent,
                            lambda: S.textEditor["backgroundTransparent"])
    assert SW.restoreEditorColors() == None
    switchCheckBoxAndAssert(SW.chkEditorNoBlinking,
                            lambda: S.textEditor["cursorNotBlinking"])
    # Twice on purpose: set and restore
    switchCheckBoxAndAssert(SW.chkEditorNoBlinking,
                            lambda: S.textEditor["cursorNotBlinking"])
    # Manually call updateAllWidgets, because other wise timer of 250ms
    SW.updateAllWidgets()

    # Labels
    assert SW.updateLabelColor(MW.mdlLabels.item(1).index()) == None
    rc = MW.mdlLabels.rowCount()
    SW.addLabel()
    SW.lstLabels.setCurrentIndex(
        MW.mdlLabels.item(MW.mdlLabels.rowCount() - 1).index())
    SW.removeLabel()
    assert MW.mdlLabels.rowCount() == rc
    # setLabelColor # Same problem as above

    # Status
    rc = MW.mdlStatus.rowCount()
    SW.addStatus()
    SW.lstStatus.setCurrentIndex(
        MW.mdlStatus.item(MW.mdlStatus.rowCount() - 1).index())
    SW.removeStatus()
    assert MW.mdlStatus.rowCount() == rc

    # Fullscreen
    # self.lstThemes.currentItemChanged.connect(self.themeSelected)
    item = SW.lstThemes.item(0)
    SW.lstThemes.currentItemChanged.emit(item, None)
    assert S.fullScreenTheme in item.data(Qt.UserRole)
    SW.lstThemes.currentItemChanged.emit(None, None)
    count = SW.lstThemes.count()
    SW.newTheme()
    assert SW.lstThemes.count() == count + 1
    SW.newTheme() # theme with same name
    item = SW.lstThemes.item(SW.lstThemes.count() - 1)
    SW.lstThemes.setCurrentItem(item)
    SW.removeTheme()
    item = SW.lstThemes.item(count)
    SW.lstThemes.setCurrentItem(item)
    SW.editTheme()
    switchCheckBoxAndAssert(SW.chkThemeIndent,
                            lambda: SW._themeData["Spacings/IndentFirstLine"])
    SW.updateThemeFont(None)
    SW.updateThemeBackground(0)
    SW.updateThemeBackground(1)
    SW.spnThemeLineSpacing.setValue(123)
    for i in range(4):
        SW.updateLineSpacing(i)
        SW.updateUIFromTheme() # No time to wait on timer
    assert SW._editingTheme != None
    SW.resize(SW.geometry().size()) # resizeEvent
    #TODO: other edit test (see SW.loadTheme
    SW.saveTheme()
    item = SW.lstThemes.item(count)
    SW.lstThemes.setCurrentItem(item)
    SW.editTheme()
    SW.cancelEdit()
    item = SW.lstThemes.item(count)
    SW.lstThemes.setCurrentItem(item)
    SW.removeTheme()
    assert SW.lstThemes.count() == count


def test_translationList(MWSampleProject):
    """All shipped translations can be chosen in the settings."""
    import glob
    import os
    from manuskript.settingsWindow import settingsWindow
    SW = settingsWindow(MWSampleProject)

    shipped = sorted(os.path.basename(f) for f in
                     glob.glob(F.appPath(os.path.join("i18n", "manuskript_*.qm"))))
    assert shipped
    names = list(SW.translations)
    assert names[0] == "English"
    assert SW.translations["English"] == ""
    assert sorted(SW.translations.values()) == [""] + shipped
    assert SW.cmbTranslation.count() == len(shipped) + 1
    assert all(names)

    # Languages are named in their own language. The names come from the
    # CLDR data of the Qt build, so only check how the labels are made.
    from PyQt5.QtCore import QLocale
    for name, translation in SW.translations.items():
        locale = F.translationLocale(translation)
        if translation and locale.language() != QLocale.C:
            assert name.casefold().startswith(
                locale.nativeLanguageName().casefold()), (name, translation)
    zh = F.translationLocale("manuskript_zh_HANT.qm")
    assert zh.script() == QLocale.TraditionalChineseScript


def test_translationChoice(MWSampleProject, monkeypatch):
    """
    Without a stored language, the settings show the language detected at
    startup, and choosing English stores it (#1220).
    """
    from PyQt5.QtWidgets import qApp, QMessageBox
    from PyQt5.QtCore import QSettings
    from manuskript.settingsWindow import settingsWindow

    messages = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *args, **kwargs: messages.append(args))
    qS = QSettings(qApp.organizationName(), qApp.applicationName())
    oldTranslation = qS.value("applicationTranslation")
    oldActive = qApp.property("manuskriptTranslation")
    try:
        qS.remove("applicationTranslation")
        qApp.setProperty("manuskriptTranslation", "manuskript_it.qm")
        SW = settingsWindow(MWSampleProject)
        assert SW.cmbTranslation.currentData() == "manuskript_it.qm"

        # Choosing English is stored, with a notice to restart
        SW.cmbTranslation.setCurrentIndex(SW.cmbTranslation.findData(""))
        SW.cmbTranslation.activated.emit(SW.cmbTranslation.currentIndex())
        assert qS.contains("applicationTranslation")
        assert qS.value("applicationTranslation") == ""
        assert len(messages) == 1

        # Choosing the active language needs no restart
        index = SW.cmbTranslation.findData("manuskript_it.qm")
        SW.cmbTranslation.setCurrentIndex(index)
        SW.cmbTranslation.activated.emit(index)
        assert qS.value("applicationTranslation") == "manuskript_it.qm"
        assert len(messages) == 1

        # The notice is shown once per settings window, not for each language
        # passed with the arrow keys (each one is 'activated' and stored)
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        for i in range(3):
            QTest.keyClick(SW.cmbTranslation, Qt.Key_Down)
        assert SW.cmbTranslation.currentIndex() == index + 3
        assert qS.value("applicationTranslation") == SW.cmbTranslation.currentData()
        assert len(messages) == 1

        # A stored language takes precedence
        qS.setValue("applicationTranslation", "manuskript_de.qm")
        SW = settingsWindow(MWSampleProject)
        assert SW.cmbTranslation.currentData() == "manuskript_de.qm"
        SW.cmbTranslation.activated.emit(SW.cmbTranslation.findData(""))
        assert len(messages) == 2
    finally:
        qApp.setProperty("manuskriptTranslation", oldActive)
        if oldTranslation is None:
            qS.remove("applicationTranslation")
        else:
            qS.setValue("applicationTranslation", oldTranslation)
