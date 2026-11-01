#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for loading and saving projects from the MainWindow."""

import os

from manuskript import loadSave
from manuskript.load_save import version_1
from manuskript.tests.load_save.helpers import copySample


def test_load_damaged_project_does_not_raise(MWNoProject, tmp_path, monkeypatch):
    """An exception while loading must not escape (startup crash loop, #1356)."""
    MW = MWNoProject
    path = copySample(tmp_path)

    def loadProject(project):
        version_1.cache = {"infos.txt": "stale"}
        raise ValueError("damaged project")

    monkeypatch.setattr(loadSave, "loadProject", loadProject)
    MW.loadProject(path)
    assert MW.currentProject is None
    assert version_1.cache == {}


def test_load_project_with_truncated_settings(MWNoProject, tmp_path):
    """A truncated settings.txt is reported, the project opens with default settings."""
    MW = MWNoProject
    path = copySample(tmp_path)
    settingsFile = os.path.join(path[:-4], "settings.txt")
    with open(settingsFile) as f:
        content = f.read()
    with open(settingsFile, "w") as f:
        f.write(content[:len(content) // 2])

    MW.loadProject(path)
    try:
        assert MW.currentProject == path
    finally:
        MW.closeProject()


def openDirtyProject(MW, tmp_path):
    path = copySample(tmp_path)
    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject == path
    MW.projectDirty = True
    return path


def test_failed_save_on_close_asks_user(MW, tmp_path, monkeypatch):
    """If the project cannot be saved, closing it asks before losing the changes."""
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtGui import QCloseEvent
    from manuskript import settings

    answers = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: answers.pop(0))
    monkeypatch.setattr(loadSave, "saveProject", lambda: False)
    path = openDirtyProject(MW, tmp_path)
    try:
        monkeypatch.setattr(settings, "saveOnQuit", True)

        # File > Close project
        answers.append(QMessageBox.Cancel)
        MW.closeProject()
        assert MW.currentProject == path
        assert answers == []

        # Quit
        answers.append(QMessageBox.Cancel)
        event = QCloseEvent()
        MW.closeEvent(event)
        assert not event.isAccepted()
        assert answers == []

        answers.append(QMessageBox.Discard)
        event = QCloseEvent()
        MW.closeEvent(event)
        assert event.isAccepted()
        assert answers == []

        # "Save changes?" > Save, without save on quit
        monkeypatch.setattr(settings, "saveOnQuit", False)
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Save)
        answers.append(QMessageBox.Cancel)
        MW.closeProject()
        assert MW.currentProject == path
        assert answers == []

        answers.append(QMessageBox.Discard)
        MW.closeProject()
        assert MW.currentProject is None
        assert answers == []
    finally:
        answers[:] = [QMessageBox.Discard] * 3
        MW.closeProject()


def test_quit_unchanged_project_that_cannot_be_saved(MW, tmp_path, monkeypatch):
    """A project that has not been changed, but cannot be saved (e.g. it has been opened
    from a read-only location to read it), is closed without asking."""
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtGui import QCloseEvent
    from manuskript import settings

    asked = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args: asked.append(args) or QMessageBox.Cancel)
    monkeypatch.setattr(loadSave, "saveProject", lambda: False)
    monkeypatch.setattr(settings, "saveOnQuit", True)
    openDirtyProject(MW, tmp_path)
    MW.projectDirty = False
    try:
        event = QCloseEvent()
        MW.closeEvent(event)
        assert event.isAccepted()
        assert asked == []
    finally:
        MW.closeProject()


def test_saveDatas_returns_result(MW, tmp_path, monkeypatch):
    openDirtyProject(MW, tmp_path)
    try:
        assert MW.saveDatas() is True
        monkeypatch.setattr(loadSave, "saveProject", lambda: False)
        assert MW.saveDatas() is False
        monkeypatch.undo()
    finally:
        MW.closeProject()
