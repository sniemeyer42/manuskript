#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the preview of the pandoc PDF export, which opens the PDF in
the system's PDF viewer."""

import importlib
import os
import shutil
import subprocess
import sys
import types

import pytest

from PyQt5.QtCore import QUrl

from manuskript.enums import Outline
from manuskript.functions import appPath


def pdfModule():
    # manuskript.exporter.pandoc exports the PDF class under the name of
    # the module.
    return importlib.import_module("manuskript.exporter.pandoc.PDF")


# The preview only calls writeSettings() on the settings widget, output()
# is replaced by the tests.
settingsWidget = types.SimpleNamespace(writeSettings=lambda: None)

# The note when pandoc made no PDF.
NO_PDF = "No PDF has been produced, so none has been opened."


class Opened(list):
    """The URLs given to QDesktopServices.openUrl, which returns `result`."""
    result = True


@pytest.fixture
def opened(monkeypatch):
    """Records the URLs given to QDesktopServices.openUrl instead of opening
    them."""
    P = pdfModule()
    urls = Opened()

    def openUrl(url):
        urls.append(url)
        return urls.result
    monkeypatch.setattr(P.QDesktopServices, "openUrl", openUrl)
    return urls


@pytest.fixture
def pdf(opened, monkeypatch, tmp_path):
    """The pandoc PDF format, writing its preview in tmp_path."""
    P = pdfModule()
    from manuskript.exporter.pandoc import pandocExporter
    monkeypatch.setattr(P, "tempFile", lambda name: str(tmp_path / name))
    return pandocExporter().getFormatByName("PDF")


def fakeOutput(F, monkeypatch, produce=True, result=""):
    """Replaces pandoc: writes a PDF if `produce`, returns `result` (None
    when pandoc failed). Returns the list of output files asked for."""
    files = []

    def output(settingsWidget, outputfile=None):
        files.append(outputfile)
        if produce:
            with open(outputfile, "wb") as f:
                f.write(b"%PDF-1.5\n")
        return result
    monkeypatch.setattr(F, "output", output)
    return files


def test_previewOpensPDF(pdf, opened, monkeypatch, tmp_path):
    files = fakeOutput(pdf, monkeypatch)
    w = pdf.previewWidget()
    note = w.text()
    assert note

    pdf.preview(settingsWidget, w)

    assert files == [str(tmp_path / "msk_pdfpreview.pdf")]
    assert opened == [QUrl.fromLocalFile(files[0])]
    assert files[0] in w.text()
    assert w.text() != note


def test_previewPathWithSpecialCharacters(pdf, opened, monkeypatch, tmp_path):
    """The old pdf.js viewer built its URL by hand, which broke on these."""
    P = pdfModule()
    # Windows does not allow "?" in file names
    name = "a #b&c d %20 é" if sys.platform == "win32" else "a #b&c?d %20 é"
    folder = tmp_path / name
    folder.mkdir()
    monkeypatch.setattr(P, "tempFile", lambda name: str(folder / name))
    files = fakeOutput(pdf, monkeypatch)

    pdf.preview(settingsWidget, pdf.previewWidget())

    assert len(opened) == 1
    assert opened[0].isLocalFile()
    # toLocalFile() gives "/" on Windows too
    assert os.path.normpath(opened[0].toLocalFile()) == os.path.normpath(files[0])


def test_failedExportOpensNothing(pdf, opened, monkeypatch, tmp_path):
    """pandoc failed (it shows the error): the PDF of the last preview must
    not be opened again."""
    old = tmp_path / "msk_pdfpreview.pdf"
    old.write_bytes(b"%PDF-1.5\nold preview\n")
    fakeOutput(pdf, monkeypatch, produce=False, result=None)
    w = pdf.previewWidget()

    pdf.preview(settingsWidget, w)

    assert opened == []
    assert not old.exists()
    assert w.text() == NO_PDF


def test_failureAfterSuccessUpdatesNote(pdf, opened, monkeypatch, tmp_path):
    """After a preview that worked, a failed one must not leave the note
    saying the PDF (removed by now) has been opened."""
    files = fakeOutput(pdf, monkeypatch)
    w = pdf.previewWidget()
    pdf.preview(settingsWidget, w)
    assert files[0] in w.text()

    fakeOutput(pdf, monkeypatch, produce=False, result=None)
    pdf.preview(settingsWidget, w)

    assert opened == [QUrl.fromLocalFile(files[0])]
    assert not os.path.exists(files[0])
    assert w.text() == NO_PDF


def test_noPDFProducedOpensNothing(pdf, opened, monkeypatch):
    fakeOutput(pdf, monkeypatch, produce=False, result="")
    w = pdf.previewWidget()
    pdf.preview(settingsWidget, w)
    assert opened == []
    assert w.text() == NO_PDF


def test_lockedPreviewUsesNewFile(pdf, opened, monkeypatch, tmp_path):
    """On Windows, the PDF viewer can keep the last preview open, which
    cannot be removed then."""
    P = pdfModule()
    old = tmp_path / "msk_pdfpreview.pdf"
    old.write_bytes(b"%PDF-1.5\nold preview\n")
    remove = os.remove

    def lockedRemove(path):
        if os.path.abspath(path) == str(old):
            raise PermissionError(13, "The process cannot access the file", path)
        remove(path)
    files = fakeOutput(pdf, monkeypatch)
    monkeypatch.setattr(P.os, "remove", lockedRemove)

    pdf.preview(settingsWidget, pdf.previewWidget())

    assert len(files) == 1
    name = os.path.basename(files[0])
    assert os.path.dirname(files[0]) == str(tmp_path)
    assert name.startswith("msk_pdfpreview-") and name.endswith(".pdf")
    assert opened == [QUrl.fromLocalFile(files[0])]


def test_lockedPreviewsDoNotPileUp(pdf, opened, monkeypatch, tmp_path):
    """While the viewer keeps msk_pdfpreview.pdf open, every preview goes
    to a new file. The next preview removes the earlier ones, except those
    still open, and leaves other files alone."""
    P = pdfModule()
    old = tmp_path / "msk_pdfpreview.pdf"
    old.write_bytes(b"%PDF-1.5\nold preview\n")
    stillOpen = tmp_path / "msk_pdfpreview-stillopen.pdf"
    stillOpen.write_bytes(b"%PDF-1.5\n")
    others = [tmp_path / n for n in ("other.pdf", "msk_pdfpreview-x.txt",
                                     "msk_pdfpreview.pdf.bak")]
    for f in others:
        f.write_bytes(b"other\n")
    remove = os.remove

    def lockedRemove(path):
        if os.path.abspath(path) in (str(old), str(stillOpen)):
            raise PermissionError(13, "The process cannot access the file", path)
        remove(path)
    files = fakeOutput(pdf, monkeypatch)
    monkeypatch.setattr(P.os, "remove", lockedRemove)

    pdf.preview(settingsWidget, pdf.previewWidget())
    pdf.preview(settingsWidget, pdf.previewWidget())

    assert len(files) == 2
    assert all(os.path.dirname(f) == str(tmp_path) for f in files)
    assert not os.path.exists(files[0])
    assert os.path.isfile(files[1])
    assert old.exists() and stillOpen.exists()
    assert all(f.exists() for f in others)
    assert opened == [QUrl.fromLocalFile(f) for f in files]


def test_viewerCannotOpen(pdf, opened, monkeypatch):
    files = fakeOutput(pdf, monkeypatch)
    opened.result = False
    w = pdf.previewWidget()

    pdf.preview(settingsWidget, w)

    assert opened == [QUrl.fromLocalFile(files[0])]
    assert files[0] in w.text()
    assert os.path.isfile(files[0])


@pytest.mark.skipif(shutil.which("pandoc") is None
                    or not (shutil.which("pdflatex") or shutil.which("xelatex")),
                    reason="pandoc and LaTeX not installed")
def test_exporterDialogPreview(MWEmptyProject, exporterSettingsPath, opened,
                               monkeypatch, tmp_path):
    """The export dialog runs pandoc and opens the PDF it made."""
    from PyQt5.QtWidgets import QLabel
    P = pdfModule()
    from manuskript.exporter.pandoc.abstractPlainText import pandocSettings as PS
    from manuskript.models import outlineItem
    monkeypatch.setattr(P, "tempFile", lambda name: str(tmp_path / name))
    # The settings widget drops the settings unknown to the installed pandoc
    # version from the class level dict, keep that local to the test.
    monkeypatch.setattr(PS, "settingsList", dict(PS.settingsList))
    MW = MWEmptyProject
    item = outlineItem(title="Scene", _type="md", parent=MW.mdlOutline.rootItem)
    item.setData(Outline.text, "Some *text*.\n")

    MW.doCompile()
    E = MW.dialog
    try:
        i = [j for j in range(E.cmbExporters.count())
             if E.cmbExporters.itemText(j) == "PDF"
             and E.cmbExporters.itemData(j) == "Pandoc"][0]
        E.cmbExporters.setCurrentIndex(i)
        assert isinstance(E.previewWidget, QLabel)
        assert opened == []

        E.preview()
    finally:
        E.close()

    path = str(tmp_path / "msk_pdfpreview.pdf")
    assert opened == [QUrl.fromLocalFile(path)]
    with open(path, "rb") as f:
        assert f.read(5) == b"%PDF-"


@pytest.mark.parametrize("QT_WEB", ["qtwebkit", "none"])
def test_htmlPreviewFallback(QT_WEB):
    """Without QtWebEngine, the HTML previews use a QTextEdit. QtWebKit is
    not used any more."""
    code = ("from manuskript.ui.views.webView import webEngine, webView; "
            "print(webEngine, webView.__name__)")
    env = dict(os.environ, QT_WEB=QT_WEB)
    result = subprocess.run([sys.executable, "-c", code], cwd=appPath(), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["QTextEdit", "QTextEdit"]
