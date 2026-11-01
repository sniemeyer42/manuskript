#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the import dialog: invalid files must not close the app."""

import shutil

import pytest


@pytest.fixture
def importDialog(MWEmptyProject, monkeypatch):
    """Opens the import dialog. Returns the dialog, a function selecting an
    importer, and the list of message boxes shown."""
    from PyQt5.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args[1:]))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: shown.append(args[1:]))

    MWEmptyProject.doImport()
    D = MWEmptyProject.dialog

    def select(engine, name):
        for i in range(D.cmbImporters.count()):
            if D.cmbImporters.itemData(i) == "{}:{}".format(engine, name):
                D.cmbImporters.setCurrentIndex(i)
                D.updateSettings()
                return
        raise ValueError(name)

    yield D, select, shown
    D.close()


@pytest.mark.parametrize("topLevelFolder", [False, True])
@pytest.mark.parametrize("content, message", [
    ("<opml version=\"1.0\"><head/></opml>", "valid OPML"),  # no body
    ("<opml version=\"1.0\"><body><outline text=\"A\"", "broken.opml"),  # not XML
])
def test_invalidOPML(importDialog, MWEmptyProject, tmp_path, content, message,
                     topLevelFolder):
    D, select, shown = importDialog
    path = tmp_path / "broken.opml"
    path.write_text(content)
    select("Internal", "OPML")
    D.settingsWidget.chkGeneralTopLevel.setChecked(topLevelFolder)
    D.setFileName(str(path))

    D.preview()
    assert len(shown) == 1
    assert message in shown[0][1]

    root = MWEmptyProject.mdlOutline.rootItem
    D.doImport()
    assert len(shown) == 2
    assert root.childCount() == 0  # no empty top-level folder left
    assert D.isVisible()


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_damagedDocX(importDialog, MWEmptyProject, tmp_path):
    D, select, shown = importDialog
    path = tmp_path / "damaged.docx"
    path.write_bytes(b"PK\x03\x04 not really a docx")
    select("Pandoc", "DocX")
    D.setFileName(str(path))
    D.preview()
    assert len(shown) == 1
    assert "Pandoc could not convert the file" in shown[0][1]
    D.doImport()
    assert MWEmptyProject.mdlOutline.rootItem.childCount() == 0


def test_validOPML(importDialog, MWEmptyProject, tmp_path):
    D, select, shown = importDialog
    path = tmp_path / "ok.opml"
    path.write_text("<opml version=\"1.0\"><body><outline text=\"A\" _note=\"Text A\"/>"
                    "</body></opml>")
    select("Internal", "OPML")
    D.setFileName(str(path))
    D.doImport()
    assert shown == []
    assert [c.title() for c in MWEmptyProject.mdlOutline.rootItem.children()] == ["A"]
    assert not D.isVisible()


@pytest.mark.parametrize("topLevelFolder", [False, True])
def test_wordCountsAfterImport(importDialog, MWEmptyProject, tmp_path, topLevelFolder):
    from manuskript.enums import Outline
    D, select, shown = importDialog
    path = tmp_path / "book.md"
    path.write_text("# Part\n\n## Scene A\n\none two three four five\n\n"
                    "## Scene B\n\nsix seven eight\n")
    select("Internal", "Markdown")
    D.settingsWidget.chkGeneralTopLevel.setChecked(topLevelFolder)
    D.setFileName(str(path))
    D.doImport()
    assert shown == []

    root = MWEmptyProject.mdlOutline.rootItem
    part = root.child(0).child(0) if topLevelFolder else root.child(0)
    assert part.title() == "Part"
    assert [c.data(Outline.wordCount) for c in part.children()] == [5, 3]
    assert part.data(Outline.wordCount) == 8
    assert root.data(Outline.wordCount) == 8
