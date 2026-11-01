#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the markdown and folder importers."""

import pytest

from manuskript.importer.abstractImporter import readTextFile
from manuskript.importer.folderImporter import folderImporter
from manuskript.importer.markdownImporter import markdownImporter

TEXT = "# Grüße aus Köln\n\nÄrger – „Zitat“ …\n"


@pytest.fixture(autouse=True)
def utf8Locale(monkeypatch):
    """The locale's encoding is tried before Windows-1252."""
    monkeypatch.setattr("locale.getpreferredencoding", lambda do_setlocale=True: "UTF-8")


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-32", "cp1252"])
def test_readTextFile(tmp_path, encoding):
    path = tmp_path / "text.md"
    path.write_bytes(TEXT.replace("\n", "\r\n").encode(encoding))
    assert readTextFile(str(path)) == TEXT


def test_readTextFileLatin1(tmp_path):
    path = tmp_path / "text.md"
    path.write_bytes("Grüße aus Köln\n".encode("latin-1"))
    assert readTextFile(str(path)) == "Grüße aus Köln\n"


def test_readTextFileBinary(tmp_path):
    path = tmp_path / "document.odt"
    path.write_bytes(b"PK\x03\x04\x14\x00\x00\x08\x00\x00binary")
    with pytest.raises(ValueError):
        readTextFile(str(path))


def test_readTextFileMostlyUTF8(tmp_path, caplog):
    """A stray byte in a UTF-8 file only loses that byte."""
    path = tmp_path / "text.md"
    path.write_bytes("Grüße aus Köln – café\n".encode("utf-8").replace(b"\xc3\xa9", b"\xe9"))
    assert readTextFile(str(path)) == "Grüße aus Köln – caf\ufffd\n"
    assert "text.md" in caplog.text


def test_folderImportManyUnreadableFiles(runImporter, tmp_path, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: shown.append(args[1:]))
    folder = tmp_path / "folder"
    folder.mkdir()
    for i in range(15):
        (folder / "binary{:02}.txt".format(i)).write_bytes(b"\x00\x01\x02")
    assert runImporter(folderImporter, str(folder)) == []
    lines = shown[0][1].split("\n")
    assert len(lines) == 12 and lines[-1] == "and 5 more"


def test_markdownImportLatin1(runImporter, tmp_path):
    path = tmp_path / "latin1.md"
    path.write_bytes("# Chapter\n\nGrüße aus Köln.\n".encode("latin-1"))
    items = runImporter(markdownImporter, str(path))
    assert [i.title() for i in items] == ["Chapter"]
    assert "Grüße aus Köln." in items[0].text()


def test_folderImportLatin1(runImporter, tmp_path, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: shown.append(args[1:]))
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "latin1.txt").write_bytes("Grüße aus Köln.\n".encode("latin-1"))
    (folder / "utf8.md").write_text("Hello.\n", encoding="utf-8")
    (folder / "binary.txt").write_bytes(b"\x00\x01\x02")
    items = runImporter(folderImporter, str(folder))
    assert sorted((i.title(), i.text()) for i in items) == [
        ("latin1", "Grüße aus Köln.\n"), ("utf8", "Hello.\n")]
    assert len(shown) == 1
    assert "binary.txt" in shown[0][1]


def importMarkdown(runImporter, text):
    items = runImporter(markdownImporter, fromString=text)
    return [(i.title(), i.type(), i.text().strip()) for i in items]


def test_markdownHeaders(runImporter):
    assert importMarkdown(runImporter,
                          "# Part\n\n## Chapter 1 ##\n\nText 1.\n\n"
                          "   ## Chapter 2\n\nText 2.\n") == [
        ("Part", "folder", ""),
        ("Chapter 1", "md", "Text 1."),
        ("Chapter 2", "md", "Text 2."),
    ]


def test_markdownHeadersWithoutSpace(runImporter):
    """Older versions and the editor accept "#Title" as a header."""
    assert importMarkdown(runImporter,
                          "#Chapter 1\n\nText.\n\n##Scene 1\n\nMore.\n") == [
        ("Chapter 1", "folder", ""),
        ("Chapter 1", "md", "Text."),
        ("Scene 1", "md", "More."),
    ]


def test_markdownSceneBreaksAreNotHeaders(runImporter):
    text = ("# Chapter 1\n\nScene one.\n\n###\n\nScene two.\n\n# # #\n\n"
            "Scene three.\n\n#\n\nScene four.\n\n  #  *  *\n\nEnd.\n")
    items = importMarkdown(runImporter, text)
    assert items == [("Chapter 1", "md", text[len("# Chapter 1\n\n"):].strip())]


def test_markdownTildeSceneBreaks(runImporter):
    """"~~~" lines are scene breaks, not code fences."""
    text = ("# Chapter 1\n\nScene one.\n\n~~~\n\nScene two.\n\n"
            "# Chapter 2\n\nScene three.\n\n~~~\n\nScene four.\n\n"
            "# Chapter 3\n\nEnd.\n")
    assert [i[0] for i in importMarkdown(runImporter, text)] == [
        "Chapter 1", "Chapter 2", "Chapter 3"]


def test_markdownUnclosedCodeFence(runImporter):
    text = ("# Chapter 1\n\nScene one.\n\n```\n\nScene two.\n\n"
            "# Chapter 2\n\nEnd.\n")
    assert importMarkdown(runImporter, text) == [
        ("Chapter 1", "md", "Scene one.\n\n```\n\nScene two."),
        ("Chapter 2", "md", "End.")]


def test_markdownLongerCodeFence(runImporter):
    """A fence is only closed by a fence at least as long."""
    text = "# A\n\n````\n```\n# inside\n````\n\n# B\n\nx\n"
    assert importMarkdown(runImporter, text) == [
        ("A", "md", "````\n```\n# inside\n````"), ("B", "md", "x")]


def test_markdownCodeFence(runImporter):
    text = "# Chapter\n\nShe wrote:\n\n```\n# not a header\n~~~\n```\n\nEnd.\n"
    assert importMarkdown(runImporter, text) == [
        ("Chapter", "md", "She wrote:\n\n```\n# not a header\n~~~\n```\n\nEnd.")]


def test_markdownHeadersCRLF(runImporter):
    """pandoc writes CRLF line endings on Windows."""
    text = ("# Chapter 1 #\n\nText 1.\n\nChapter 2\n=========\n\n"
            "```\n# not a header\n```\n\n## Scene 1\n\nEnd.\n")
    assert importMarkdown(runImporter, text.replace("\n", "\r\n")) == [
        ("Chapter 1", "md", "Text 1."),
        ("Chapter 2", "folder", ""),
        ("Chapter 2", "md", "```\n# not a header\n```"),
        ("Scene 1", "md", "End."),
    ]
