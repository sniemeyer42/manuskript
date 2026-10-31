#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for main.py"""

import pytest

from PyQt5.QtCore import QTranslator

from manuskript import main
from manuskript.functions import appPath


@pytest.mark.parametrize("languageCode, expected", [
    ("de-DE", "manuskript_de_DE.qm"),
    ("pt-BR", "manuskript_pt_BR.qm"),
    ("zh-CN", "manuskript_zh_CN.qm"),
    ("zh-Hans-CN", "manuskript_zh_Hans_CN.qm"),
    ("zh-TW", "manuskript_zh_HANT.qm"),
    ("zh-HK", "manuskript_zh_HANT.qm"),
    ("zh-Hant-TW", "manuskript_zh_HANT.qm"),
])
def test_translationFileName(languageCode, expected):
    assert main.translationFileName(languageCode) == expected


@pytest.mark.parametrize("languageCode, expected", [
    ("de-DE", "manuskript_de.qm"),
    ("zh-CN", "manuskript_zh_CN.qm"),
    ("zh-TW", "manuskript_zh_HANT.qm"),
    ("zh-Hant-HK", "manuskript_zh_HANT.qm"),
])
def test_translationAutoDetection(languageCode, expected):
    """The shipped translation is found for the UI language (APP-17)."""
    translator = QTranslator()
    assert translator.load(main.translationFileName(languageCode),
                           appPath("i18n"))
    if hasattr(translator, "filePath"):  # Qt >= 5.15
        assert translator.filePath().endswith(expected)


def catalogue(translation):
    """Returns the manuskript translation `translation`, loaded."""
    translator = QTranslator()
    assert translator.load(translation, appPath("i18n"))
    return translator


@pytest.fixture
def keepLayoutDirection():
    """Removing a translator makes Qt detect the layout direction again."""
    from PyQt5.QtWidgets import qApp
    direction = qApp.layoutDirection()
    yield
    qApp.setLayoutDirection(direction)


def test_loadQtTranslation(keepLayoutDirection):
    """Qt's own strings are translated too (APP-9)."""
    from PyQt5.QtCore import QCoreApplication
    from PyQt5.QtWidgets import qApp

    # Builtin English
    assert main.loadQtTranslation(qApp, "", QTranslator()) is None
    # A catalogue without any translated message gives an English UI
    # (e.g. manuskript_fa.qm): Qt's strings stay in English too.
    assert main.loadQtTranslation(qApp, "manuskript_de.qm", QTranslator()) is None

    translator = main.loadQtTranslation(qApp, "manuskript_de.qm",
                                        catalogue("manuskript_de.qm"))
    if translator is None:
        pytest.skip("Qt's German translation (qtbase_de.qm) is not installed")
    try:
        assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Abbrechen"
    finally:
        qApp.removeTranslator(translator)


@pytest.mark.parametrize("translation", ["manuskript_ar_SA.qm",
                                         "manuskript_he.qm"])
def test_loadQtTranslationKeepsLayoutDirection(translation, keepLayoutDirection):
    """Qt's Arabic and Hebrew translations do not mirror the UI: the layout
    direction stays the one of the manuskript catalogue."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import qApp

    manuskript = catalogue(translation)
    assert manuskript.translate("QGuiApplication", "QT_LAYOUT_DIRECTION") != "RTL"
    qApp.setLayoutDirection(Qt.LeftToRight)

    translator = main.loadQtTranslation(qApp, translation, manuskript)
    if translator is None:
        pytest.skip("Qt's translation for {} is not installed".format(translation))
    try:
        if translator.translate("QGuiApplication", "QT_LAYOUT_DIRECTION") != "RTL":
            pytest.skip("Qt's translation for {} is not right-to-left".format(translation))
        assert qApp.layoutDirection() == Qt.LeftToRight
    finally:
        qApp.removeTranslator(translator)


@pytest.mark.parametrize("argv, style", [
    ([], None),
    (["--style", "Fusion"], "Fusion"),
    (["--style=Windows"], "Windows"),
    (["-style", "Fusion"], "Fusion"),  # Qt's own syntax
])
def test_styleArgument(argv, style):
    assert main.process_commandline(argv).style == style


class fakeSettings(dict):
    def contains(self, key):
        return key in self

    def value(self, key):
        return self[key]


def test_selectStyle(monkeypatch):
    """--style takes precedence over the saved style (#467)."""
    saved = fakeSettings(applicationStyle="Saved")
    noArgs = main.process_commandline([])
    styleArg = main.process_commandline(["--style", "Argument"])

    monkeypatch.delenv("QT_STYLE_OVERRIDE", raising=False)
    assert main.selectStyle(noArgs, fakeSettings()) is None
    assert main.selectStyle(noArgs, saved) == "Saved"
    assert main.selectStyle(styleArg, saved) == "Argument"

    # Many desktops set QT_STYLE_OVERRIDE for all applications: it must not
    # replace the style chosen in the settings, nor the default (Fusion).
    monkeypatch.setenv("QT_STYLE_OVERRIDE", "Environment")
    assert main.selectStyle(noArgs, fakeSettings()) is None
    assert main.selectStyle(noArgs, saved) == "Saved"
    assert main.selectStyle(styleArg, saved) == "Argument"


def test_chooseSessionStyleInSettings(MWSampleProject):
    """
    Started with --style, Settings show the style of the session. Choosing
    it there saves it, although it is already the current entry (#467).
    """
    from PyQt5.QtCore import QSettings
    from PyQt5.QtWidgets import qApp, QStyleFactory
    from manuskript.settingsWindow import settingsWindow

    style = qApp.style().objectName()
    assert style in [k.lower() for k in QStyleFactory.keys()]
    others = [k for k in QStyleFactory.keys() if k.lower() != style]
    if not others:
        pytest.skip("Only one Qt style is available")
    qS = QSettings(qApp.organizationName(), qApp.applicationName())
    oldStyle = qS.value("applicationStyle")
    try:
        # The style of the session (--style) is not the saved one
        qS.setValue("applicationStyle", others[0])
        SW = settingsWindow(MWSampleProject)
        assert SW.cmbStyle.currentText().lower() == style

        # The user chooses the shown entry
        SW.cmbStyle.activated.emit(SW.cmbStyle.currentIndex())
        assert qS.value("applicationStyle") == SW.cmbStyle.currentText()
    finally:
        if oldStyle is None:
            qS.remove("applicationStyle")
        else:
            qS.setValue("applicationStyle", oldStyle)
    assert qApp.style().objectName() == style
