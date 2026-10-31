#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the pandoc exporter."""

import shutil
import subprocess
import types

import pytest

from manuskript.enums import Outline


class FakePandoc:
    """Stands in for subprocess.Popen running pandoc."""
    stdout = b""
    stderr = b""
    returncode = 0

    def __init__(self, args, **kwargs):
        self.args = args

    def communicate(self, src):
        return self.stdout, self.stderr


@pytest.fixture
def fakePandoc(MWEmptyProject, monkeypatch):
    import manuskript.exporter.pandoc as P
    monkeypatch.setattr(P.pandocExporter, "isValid", lambda self: 2)
    monkeypatch.setattr(P, "subprocess", types.SimpleNamespace(
        Popen=FakePandoc, PIPE=subprocess.PIPE))
    shown = []
    monkeypatch.setattr(P.QMessageBox, "critical", lambda *args: shown.append(args))
    monkeypatch.setattr(MWEmptyProject, "dialog", None, raising=False)
    return P.pandocExporter(), shown


def test_pandocWarningKeepsOutput(fakePandoc, monkeypatch):
    E, shown = fakePandoc
    monkeypatch.setattr(FakePandoc, "stdout", b"<p>Text</p>\n")
    monkeypatch.setattr(FakePandoc, "stderr", b"[WARNING] Duplicate note reference '1'\n")
    monkeypatch.setattr(FakePandoc, "returncode", 0)
    assert E.convert("Text", ["--to=html"]) == "<p>Text</p>\n"
    assert shown == []


def test_pandocErrorReturnsNone(fakePandoc, monkeypatch):
    E, shown = fakePandoc
    monkeypatch.setattr(FakePandoc, "stdout", b"")
    monkeypatch.setattr(FakePandoc, "stderr", b"pandoc: \xff unknown option\n")
    monkeypatch.setattr(FakePandoc, "returncode", 2)
    assert E.convert("Text", ["--to=html"]) is None
    assert len(shown) == 1


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_duplicateFootnotesExport(MWEmptyProject, exporterSettingsPath, monkeypatch):
    """Every scene numbering its footnotes from 1 makes pandoc warn."""
    from manuskript.models import outlineItem
    from manuskript.exporter.pandoc import pandocExporter
    from manuskript.exporter.pandoc.abstractPlainText import pandocSettings as PS
    monkeypatch.setattr(MWEmptyProject, "dialog", None, raising=False)
    # The settings widget drops the settings unknown to the installed pandoc
    # version from the class level dict, keep that local to the test.
    monkeypatch.setattr(PS, "settingsList", dict(PS.settingsList))
    root = MWEmptyProject.mdlOutline.rootItem
    for i in (1, 2):
        item = outlineItem(title="Scene {}".format(i), _type="md", parent=root)
        item.setData(Outline.text, "Scene {}.[^1]\n\n[^1]: Note {}.\n".format(i, i))
    F = pandocExporter().getFormatByName("HTML")
    r = F.output(F.settingsWidget())
    assert r is not None
    assert "Scene 1." in r and "Scene 2." in r


@pytest.fixture
def pandocSettings(MWEmptyProject, monkeypatch):
    """Returns a function creating the pandoc settings widget for a given
    pandoc version and output format."""
    from manuskript.exporter.pandoc import pandocExporter
    from manuskript.exporter.pandoc.abstractPlainText import pandocSettings as PS
    # The widget drops the settings unknown to the pandoc version from the
    # class level dict, keep that local to the test.
    monkeypatch.setattr(PS, "settingsList", dict(PS.settingsList))

    def make(major, minor, name="Markdown"):
        F = pandocExporter().getFormatByName(name)
        return PS(F, major, minor, toFormat=F.toFormat)
    return make


def test_atxHeadingsArgument(pandocSettings):
    w = pandocSettings("3", "1")
    w.settingsList["atx-heading"].widget.setChecked(True)
    args = w.runnableSettings()
    assert "--markdown-headings=atx" in args


def test_negativeHeadingShift(pandocSettings):
    """Book/Chapter/Scene outlines need chapters promoted to level 1."""
    w = pandocSettings("3", "1")
    spin = w.settingsList["shift-heading"].widget
    assert spin.minimum() < 0
    spin.setValue(-1)
    assert spin.value() == -1
    assert "--shift-heading-level-by=-1" in w.runnableSettings()
