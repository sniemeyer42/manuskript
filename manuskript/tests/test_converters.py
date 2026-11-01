#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for converters (HTML to markdown / plain text)."""

import shutil
import sys

import pytest

from manuskript import converters
from manuskript.converters import pandocConverter

PANDOC = shutil.which("pandoc")


@pytest.fixture
def noPandoc(monkeypatch, tmp_path):
    """No pandoc on PATH and no custom path set."""
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(pandocConverter, "customPath", classmethod(lambda cls: ""))
    assert pandocConverter.isValid() == 0


def test_HTML2PlainTextWithoutPandoc(noPandoc):
    assert converters.HTML2PlainText("<p>Hello <b>you</b></p>") == "Hello you"
    # ElementTree.tostring returns bytes (mind map importer)
    assert converters.HTML2PlainText(b"<html><body><p>A note</p></body></html>") == "A note"


def test_HTML2MDWithoutPandoc(noPandoc):
    assert converters.HTML2MD(b"<html><body><p>A <b>note</b></p></body></html>") == "A note"


def test_loadOldHtmlItemWithoutPandoc(noPandoc):
    """Items of type html (old file formats) are converted when loaded."""
    from manuskript.models import outlineItem
    it = outlineItem(xml=b'<outlineItem title="old" type="html" '
                         b'text="&lt;p&gt;hi&lt;/p&gt;" notes=""/>')
    assert it.type() == "md"
    assert it.text() == "hi"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permissions")
def test_customPathNotAProgram(noPandoc, monkeypatch, tmp_path):
    notPandoc = tmp_path / "notpandoc.txt"
    notPandoc.write_text("Not pandoc.")
    notPandoc.chmod(0o644)
    monkeypatch.setattr(pandocConverter, "customPath",
                        classmethod(lambda cls: str(notPandoc)))
    assert pandocConverter.isValid() == 0
    assert converters.HTML2PlainText("<p>Hello</p>") == "Hello"


@pytest.mark.skipif(PANDOC is None, reason="pandoc not installed")
def test_customPandocPath(noPandoc, monkeypatch):
    monkeypatch.setattr(pandocConverter, "customPath", classmethod(lambda cls: PANDOC))
    assert pandocConverter.isValid() == 1
    assert pandocConverter.runCmd() == PANDOC
    assert converters.HTML2MD("<p>A <b>note</b></p>").strip() == "A **note**"
