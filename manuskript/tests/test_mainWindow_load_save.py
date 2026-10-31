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
