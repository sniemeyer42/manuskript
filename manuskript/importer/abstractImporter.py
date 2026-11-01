#!/usr/bin/env python
# --!-- coding: utf8 --!--
import codecs
import locale
import os
import re
import shutil
import subprocess

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QVBoxLayout, QCheckBox, QHBoxLayout, \
                            QLabel, QSpinBox, QComboBox, QLineEdit, qApp
from manuskript.ui.collapsibleGroupBox2 import collapsibleGroupBox2
from manuskript.ui import style
from manuskript.functions import safeTranslate

import logging
LOGGER = logging.getLogger(__name__)


def readTextFile(filePath):
    """
    Reads a text file of unknown encoding, returns its content with "\\n"
    line endings. Tries UTF-8 (with or without BOM), then the encoding of
    the locale, then Windows-1252 (and Latin-1, which can decode anything).
    A UTF-8 file with a few invalid bytes is read as UTF-8, with these bytes
    replaced by U+FFFD.

    Raises ValueError if the file does not look like a text file.
    """
    with open(filePath, 'rb') as f:
        raw = f.read()

    if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        # Before UTF-16: the UTF-32-LE BOM starts with the UTF-16-LE one
        encodings = ["utf-32"]
    elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encodings = ["utf-16"]
    elif b"\x00" in raw[:8192]:
        raise ValueError(safeTranslate(qApp, "Import",
                                       "This does not appear to be a text file."))
    else:
        encodings = ["utf-8-sig", locale.getpreferredencoding(False), "cp1252"]

    for encoding in encodings + ["latin-1"]:
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            pass

        if encoding == "utf-8-sig":
            # Mostly UTF-8 with a few invalid bytes (e.g. text pasted from
            # another file): only lose these bytes, instead of decoding the
            # whole file as another encoding. Text in other encodings has
            # far fewer valid UTF-8 characters per invalid byte (about one
            # per two in GBK, none in Windows-1252).
            text = raw.decode(encoding, errors="replace")
            invalid = text.count("\ufffd") - raw.count("\ufffd".encode("utf-8"))
            valid = len(re.findall(r"[^\x00-\x7f\ufffd]", text))
            if valid >= 3 * invalid:
                LOGGER.warning("%s is not valid UTF-8: %d invalid bytes replaced.",
                               filePath, invalid)
                break

    return text.replace("\r\n", "\n").replace("\r", "\n")


class abstractImporter:
    """
    abstractImporter is used to import documents into manuskript.

    The startImport function must be subclassed. It takes a filePath (str to
    the document to import), and must return `outlineItem`s.
    """

    name = ""
    description = ""
    fileFormat = ""  # File format accepted. For example: "OPML Files (*.opml)"
                     # For folder, use "<<folder>>"
    icon = ""
    engine = "Internal"

    def __init__(self):
        self.settingsList = []  # Keep the name of the settings in order
        self.settings = {}

    def startImport(self, filePath, parentItem, settingsWidget):
        """
        Takes a str path to the file/folder to import, and the settingsWidget
        returned by `self.settingsWidget()` containing the user set settings,
        and return `outlineItem`s.
        """
        pass

    @classmethod
    def isValid(cls):
        return False


    def settingsWidget(self, widget):
        """
        Takes a QWidget that can be modified and must be returned.
        """
        return widget

    def addGroup(self, parent, title):
        """
        Adds a collapsible group to the given widget.
        """
        g = collapsibleGroupBox2(title=title)
        parent.layout().addWidget(g)
        g.setLayout(QVBoxLayout())
        return g

    def addSetting(self, name, type, label, widget=None,  default=None,
                   tooltip=None, min=None, max=None, vals=None, suffix=""):

        self.settingsList.append(name)
        self.settings[name] = self.setting(name, type, label, widget,  default,
                                         tooltip, min, max, vals, suffix)

    def widget(self, name):
        if name in self.settings:
            return self.settings[name].widget()

    def getSetting(self, name):
        if name in self.settings:
            return self.settings[name]

    def addSettingsTo(self, widget):
        """
        Adds all the settings to the given widget. Assume that the settings
        have not been called yet, so calling `.widget()` will create their
        widgets.
        """
        for name in self.settingsList:
            self.settings[name].widget(widget)


    class setting:
        """
        A class used to store setting, and display a widget for the user to
        modify it.
        """
        def __init__(self, name, type, label, widget=None,  default=None,
                     tooltip=None, min=None, max=None, vals=None, suffix=""):
            self.name = name
            self.type = type
            self.label = label
            self._widget = widget
            self.default = default
            self.min = min
            self.max = max
            self.vals = vals.split("|") if vals else []
            self.suffix = suffix
            self.tooltip = tooltip

        def widget(self, parent=None):
            """
            Returns the widget used, or creates it if not done yet. If parent
            is given, widget is inserted in parent's layout.
            """
            if self._widget:
                return self._widget

            else:

                if "checkbox" in self.type:
                    self._widget = QCheckBox(self.label)
                    if self.default:
                        self._widget.setChecked(True)
                    if parent:
                        parent.layout().addWidget(self._widget)

                elif "number" in self.type:
                    l = QHBoxLayout()
                    label = QLabel(self.label, parent)
                    label.setWordWrap(True)
                    l.addWidget(label, 8)
                    self._widget = QSpinBox()
                    self._widget.setValue(self.default if self.default else 0)
                    if self.min:
                        self._widget.setMinimum(self.min)
                    if self.max:
                        self._widget.setMaximum(self.max)
                    if self.suffix:
                        self._widget.setSuffix(self.suffix)
                    l.addWidget(self._widget, 2)
                    if parent:
                        parent.layout().addLayout(l)

                elif "combo" in self.type:
                    l = QHBoxLayout()
                    label = QLabel(self.label, parent)
                    label.setWordWrap(True)
                    l.addWidget(label, 6)
                    self._widget = QComboBox()
                    self._widget.addItems(self.vals)
                    if self.default:
                        self._widget.setCurrentText(self.default)
                    l.addWidget(self._widget, 2)
                    if parent:
                        parent.layout().addLayout(l)

                elif "text" in self.type:
                    l = QHBoxLayout()
                    label = QLabel(self.label, parent)
                    label.setWordWrap(True)
                    l.addWidget(label, 5)
                    self._widget = QLineEdit()
                    self._widget.setStyleSheet(style.lineEditSS())
                    if self.default:
                        self._widget.setText(self.default)
                    l.addWidget(self._widget, 3)
                    if parent:
                        parent.layout().addLayout(l)

                elif "label" in self.type:
                    self._widget = QLabel(self.label, parent)
                    self._widget.setWordWrap(True)
                    if parent:
                        parent.layout().addWidget(self._widget)

                if self.tooltip:
                    self._widget.setToolTip(self.tooltip)

                return self._widget

        def value(self):
            """
            Return the value contained in the widget.
            """
            if not self._widget:
                return self.default

            else:

                if "checkbox" in self.type:
                    return self._widget.isChecked()

                elif "number" in self.type:
                    return self._widget.value()

                elif "combo" in self.type:
                    return self._widget.currentText()

                elif "text" in self.type:
                    return self._widget.text()



