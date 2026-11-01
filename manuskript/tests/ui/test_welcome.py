#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the welcome widget."""

def test_autoLoad(MWNoProject):
    """
    Tests for the welcome widget using MainWindow with no open project.
    """
    MW = MWNoProject
    from PyQt5.QtCore import QSettings

    # Testing when no autoLoad
    QSettings().remove("autoLoad")
    autoLoad, path = MW.welcome.getAutoLoadValues()
    assert type(autoLoad) == bool
    assert autoLoad == False

    for v in [True, False, 42, "42", None, True]:
        MW.welcome.setAutoLoad(v)
        autoLoad, path = MW.welcome.getAutoLoadValues()
        assert type(autoLoad) == bool


def test_demo_project_is_a_copy(MWNoProject, tmp_path, monkeypatch):
    """Opening a demo project opens a copy: the installed one is never modified."""
    import os
    import shutil
    from PyQt5.QtCore import Qt
    from manuskript import functions as F
    from manuskript import loadSave
    from manuskript.enums import Outline
    from manuskript.ui import welcome
    MW = MWNoProject

    # The "installed" demo projects (a copy, so that the repository is not touched)
    installed = tmp_path / "app"
    shutil.copytree(F.appPath("sample-projects"), str(installed / "sample-projects"))
    monkeypatch.setattr(welcome, "appPath", lambda suffix: os.path.join(str(installed), suffix))
    data = tmp_path / "data"

    def writablePath(suffix):
        path = str(data / suffix)
        os.makedirs(path, exist_ok=True)
        return path

    monkeypatch.setattr(welcome, "writablePath", writablePath, raising=False)

    def demoItem():
        tree = MW.welcome.tree
        for i in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).data(0, Qt.UserRole) == "book-of-acts.msk":
                    return top.child(j)

    def snapshot(folder):
        files = {}
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                with open(os.path.join(dirpath, f), "rb") as fo:
                    files[os.path.relpath(os.path.join(dirpath, f), folder)] = fo.read()
        return files

    before = snapshot(str(installed))
    MW.welcome.changeTemplate(demoItem(), 0)
    copy = os.path.join(str(data), "sample-projects", "book-of-acts.msk")
    try:
        assert MW.currentProject == copy
        MW.mdlOutline.setData(MW.mdlOutline.rootItem.child(0).index(Outline.title), "Changed")
        assert loadSave.saveProject()
    finally:
        MW.closeProject()

    assert snapshot(str(installed)) == before
    assert "Changed" in snapshot(copy[:-4])[os.path.join("outline", "0-Changed", "folder.txt")].decode()

    # The next time, the user's copy (with the changes) is opened again
    MW.welcome.changeTemplate(demoItem(), 0)
    try:
        assert MW.currentProject == copy
        assert MW.mdlOutline.rootItem.child(0).title() == "Changed"
    finally:
        MW.closeProject()
