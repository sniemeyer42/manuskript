#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the pandoc exporter."""

import shutil
import subprocess
import sys
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


@pytest.fixture
def markTranslations(monkeypatch):
    """Marks the texts that go through Qt's translation."""
    from PyQt5.QtWidgets import qApp
    import manuskript.functions
    monkeypatch.setattr(manuskript.functions, "translationCache", {})
    monkeypatch.setattr(qApp, "translate", lambda group, text, *args: "[{}]".format(text))


@pytest.fixture
def customPandoc(MWEmptyProject, monkeypatch, tmp_path):
    """A pandoc exporter not finding pandoc on PATH. Returns a function
    setting the custom path to a file with the given content."""
    from manuskript.exporter.basic import basicExporter
    from manuskript.exporter.pandoc import pandocExporter
    from manuskript.exporter.pandoc.abstractPlainText import pandocSettings as PS
    monkeypatch.setattr(basicExporter, "path", lambda self: None)
    monkeypatch.setattr(PS, "settingsList", dict(PS.settingsList))
    E = pandocExporter()

    def setPath(content, executable):
        path = tmp_path / "pandoc"
        path.write_text(content)
        path.chmod(0o755 if executable else 0o644)
        monkeypatch.setattr(E, "customPath", str(path))
        return E
    return setPath


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permissions")
def test_customPathNotAProgram(customPandoc, exporterSettingsPath):
    E = customPandoc("Not pandoc.", executable=False)
    assert E.isValid() == 0
    assert E.version() == ""
    assert E.run(["--version"]) is None
    # Selecting a pandoc format in the export dialog asks for the version
    E.getFormatByName("Markdown").settingsWidget()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX executables")
def test_customPathCannotRun(customPandoc, MWEmptyProject, monkeypatch, markTranslations):
    from PyQt5.QtWidgets import qApp, QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args))
    monkeypatch.setattr(MWEmptyProject, "dialog", None, raising=False)

    # Executable without shebang: "Exec format error"
    E = customPandoc("echo pandoc 3.1\n", executable=True)
    if E.isValid() != 1:
        pytest.skip("tmp_path does not allow executables (noexec)")
    assert E.version() == ""
    assert E.convert("Text", ["--to=html"]) is None
    assert len(shown) == 1
    assert shown[0][2].startswith("[Could not run pandoc (")
    assert qApp.overrideCursor() is None

    # Program failing
    E = customPandoc("#!/bin/sh\necho 'pandoc: broken' >&2\nexit 3\n", executable=True)
    assert E.run(["--version"]) is None
    assert E.version() == ""
    assert E.lastError == "pandoc: broken"
    E = customPandoc("#!/bin/sh\nexit 3\n", executable=True)
    assert E.run(["--version"]) is None
    assert E.lastError == "[Return code: 3]"


def test_noCommandError(customPandoc, monkeypatch, markTranslations):
    E = customPandoc("", executable=False)
    monkeypatch.setattr(E, "customPath", "")
    assert E.run(["--version"]) is None
    assert E.lastError == "[No command for Pandoc.]"
