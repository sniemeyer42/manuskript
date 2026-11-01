#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Fixtures for the load / save tests."""

import os

import pytest

from manuskript import loadSave
from manuskript.tests.load_save.helpers import copySample


@pytest.fixture
def sampleProject(MW, tmp_path):
    """Loads a copy of the sample project, saved once in the current format."""
    MW.closeProject()
    path = copySample(tmp_path)
    MW.loadProject(path)
    assert MW.currentProject == path
    assert loadSave.saveProject()
    yield MW
    MW.closeProject()


@pytest.fixture
def emptyProject(MW, tmp_path):
    """Creates a new empty project (folder format) in tmp_path."""
    MW.closeProject()
    MW.welcome.createFile(os.path.join(str(tmp_path), "test.msk"), overwrite=True)
    assert MW.currentProject
    yield MW
    MW.closeProject()
