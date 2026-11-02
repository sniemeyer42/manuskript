#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Fixtures."""

import os
import shutil

import pytest


def closePreviousProject(MW):
    """
    Closes the project that a previous test left open. It is a temporary copy,
    so its changes are dropped: with "save on quit" off, closing a modified
    project would open a modal "Save changes?" dialog, which blocks the tests.
    """
    MW.projectDirty = False
    MW.closeProject()


def removeProject(MW, path):
    """
    Closes the temporary project ``path`` if it is still open, and removes the
    folder that holds its .msk file and its project folder. If the folder
    cannot be removed, pytest removes it with its other old temporary folders.
    """
    if MW.currentProject == os.path.normpath(path):
        closePreviousProject(MW)
    shutil.rmtree(os.path.dirname(path), ignore_errors=True)


@pytest.fixture
def MW():
    """
    Returns the mainWindow
    """
    from manuskript import functions as F
    MW = F.mainWindow()
    assert MW != None
    assert MW == F.MW

    return MW

@pytest.fixture
def MWNoProject(MW):
    """
    Take the MainWindow and close andy possibly open project.
    """
    closePreviousProject(MW)
    assert MW.currentProject == None
    return MW

@pytest.fixture
def MWEmptyProject(MW, tmp_path_factory):
    """
    Creates a MainWindow and load an empty project, in a new temporary folder.
    """
    path = str(tmp_path_factory.mktemp("MWEmptyProject") / "empty.msk")

    closePreviousProject(MW)
    assert MW.currentProject == None
    MW.welcome.createFile(path, overwrite=True)
    assert MW.currentProject != None
    yield MW
    removeProject(MW, path)

@pytest.fixture
def MWSampleProject(MW, tmp_path_factory):
    """
    Creates a MainWindow and load a copy of the Acts sample project, in a new
    temporary folder.
    """

    from manuskript import functions as F
    # Get the path of the first sample project. We assume it is here.
    spDir = F.appPath("sample-projects")
    lst = os.listdir(spDir)
    # We assume it's saved in folder, so there is a `name.msk` file and a
    # `name` folder.
    src = [f for f in lst if f[-4:] == ".msk" and f[:-4] in lst][0]
    path = str(tmp_path_factory.mktemp("MWSampleProject") / src)
    src = os.path.join(spDir, src)
    # Copy to the temp folder
    shutil.copyfile(src, path)
    shutil.copytree(src[:-4], path[:-4])
    closePreviousProject(MW)
    MW.loadProject(path)
    assert MW.currentProject != None

    yield MW
    removeProject(MW, path)
