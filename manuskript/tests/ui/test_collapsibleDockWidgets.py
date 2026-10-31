#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the collapsible dock widgets toolbar."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QWidget

from manuskript.ui.collapsibleDockWidgets import collapsibleDockWidgets


def makeToolbar(label):
    mw = QMainWindow()
    widget = QWidget(mw)
    widget.setObjectName("redacMetadata")
    toolbar = collapsibleDockWidgets(Qt.RightDockWidgetArea, mw)
    toolbar.addCustomWidget(label, widget, 1, False)
    button = toolbar.otherWidgets[0][0]
    return mw, toolbar, widget, button


def test_stateSurvivesLanguageChange():
    """The visibility is restored even if the button label is translated."""
    mw, toolbar, widget, button = makeToolbar("Metadata")
    button.defaultAction().setChecked(True)
    state = toolbar.saveState()

    mw2, toolbar2, widget2, button2 = makeToolbar("Métadonnées")
    assert not button2.isChecked()
    toolbar2.restoreState(state)
    assert button2.isChecked()
    assert not widget2.isHidden()


def test_restoreOldState():
    """States saved by older versions (keyed on the label) still work."""
    mw, toolbar, widget, button = makeToolbar("&Metadata")
    toolbar.restoreState([(1, "Metadata", True)])
    assert button.isChecked()
    assert not widget.isHidden()
