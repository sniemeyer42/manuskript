#!/usr/bin/env python
# --!-- coding: utf8 --!--
import os
import random
import shutil
import tempfile

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import qApp, QLabel

from manuskript.exporter.pandoc.abstractOutput import abstractOutput
from manuskript.functions import tempFile, safeTranslate

import logging
LOGGER = logging.getLogger(__name__)


class PDF(abstractOutput):
    """PDF through pandoc and LaTeX. The preview opens the generated PDF in
    the system's default PDF viewer."""

    name = "PDF"
    description = safeTranslate(qApp, "Export", "Needs LaTeX to be installed.")
    InvalidBecause = safeTranslate(qApp, "Export", """a valid LaTeX installation. Pandoc recommendations can be found on:
                     <a href="https://pandoc.org/installing.html">pandoc.org/installing.html</a>. If you want Unicode support, you need XeLaTeX.""")
    icon = "application-pdf"

    exportVarName = "lastPandocPDF"
    toFormat = "pdf"
    exportFilter = "PDF files (*.pdf);; Any files (*)"
    exportDefaultSuffix = ".pdf"
    requires = {
        "Settings": True,
        "Preview": True,
    }

    def isValid(self):
        path = shutil.which("pdflatex") or shutil.which("xelatex")
        return path != None

    def output(self, settingsWidget, outputfile=None):
        args = settingsWidget.runnableSettings()
        args.remove("--to=pdf")
        args.append("--to=latex")
        src = self.src(settingsWidget)
        return self.exporter.convert(src, args, outputfile)

    def previewWidget(self):
        w = QLabel(safeTranslate(qApp, "Export",
                   "The preview opens the PDF in your default PDF viewer."))
        w.setAlignment(Qt.AlignCenter)
        w.setWordWrap(True)
        w.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return w

    @staticmethod
    def previewFilename():
        """Returns the file to write the preview to. The PDFs from earlier
        previews are removed first, so that a failed export does not open
        one of them again."""
        filename = tempFile("msk_pdfpreview.pdf")
        folder = os.path.dirname(filename)

        # The msk_pdfpreview-*.pdf files made below by earlier previews.
        # Those a PDF viewer still has open cannot be removed on Windows,
        # they are removed by a later preview.
        try:
            names = os.listdir(folder)
        except OSError:
            names = []
        for name in names:
            if name.startswith("msk_pdfpreview-") and name.endswith(".pdf"):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass

        try:
            if os.path.exists(filename):
                os.remove(filename)
        except OSError as e:
            # On Windows, the PDF viewer can still have the last preview open.
            LOGGER.info("Cannot replace the last PDF preview (%s), using a new file.", e)
            fd, filename = tempfile.mkstemp(prefix="msk_pdfpreview-", suffix=".pdf",
                                            dir=folder)
            os.close(fd)
            os.remove(filename)
        return filename

    def preview(self, settingsWidget, previewWidget):
        filename = self.previewFilename()

        settingsWidget.writeSettings()
        content = self.output(settingsWidget, outputfile=filename)

        # When pandoc fails, it has already shown the error.
        if content is None or not os.path.isfile(filename):
            previewWidget.setText(safeTranslate(qApp, "Export",
                "No PDF has been produced, so none has been opened."))
            return

        if QDesktopServices.openUrl(QUrl.fromLocalFile(filename)):
            previewWidget.setText(safeTranslate(qApp, "Export",
                "The PDF has been opened in your default PDF viewer:\n{}").format(filename))
        else:
            previewWidget.setText(safeTranslate(qApp, "Export",
                "The PDF could not be opened. It has been saved here:\n{}").format(filename))
