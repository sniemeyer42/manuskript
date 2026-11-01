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


def test_recentFiles(MWNoProject, tmp_path):
    """
    The same project is listed only once, and projects with the same file
    name can be told apart (#1228).
    """
    import os
    from PyQt5.QtCore import QSettings
    MW = MWNoProject
    welcome = MW.welcome

    real = tmp_path / "real"
    other = tmp_path / "other"
    real.mkdir()
    other.mkdir()
    (real / "book.msk").write_text("")
    (other / "book.msk").write_text("")
    link = tmp_path / "link"
    try:
        os.symlink(str(real), str(link))
    except (OSError, NotImplementedError):
        link = None

    sttgns = QSettings()
    old = sttgns.value("recentFiles")
    try:
        sttgns.remove("recentFiles")
        if link:
            welcome.appendToRecentFiles(str(link / "book.msk"))
        welcome.appendToRecentFiles(str(real / "book.msk"))
        welcome.appendToRecentFiles(str(real) + "/./book.msk")
        assert sttgns.value("recentFiles") == [str(real / "book.msk")]

        welcome.appendToRecentFiles(str(other / "book.msk"))
        assert sttgns.value("recentFiles") == [str(other / "book.msk"),
                                               str(real / "book.msk")]

        # Lists stored by older versions may contain duplicates
        stored = sttgns.value("recentFiles") + [str(real) + "/./book.msk"]
        if link:
            stored.append(str(link / "book.msk"))
        sttgns.setValue("recentFiles", stored)
        welcome.loadRecents()
        actions = MW.menuRecents.actions()
        assert [a.data() for a in actions] == [str(other / "book.msk"),
                                               str(real / "book.msk")]
        labels = [a.text() for a in actions]
        assert len(set(labels)) == 2
        assert all("book.msk" in l for l in labels)
        assert [a.toolTip() for a in actions] == [a.data() for a in actions]
    finally:
        if old is None:
            sttgns.remove("recentFiles")
        else:
            sttgns.setValue("recentFiles", old)
        welcome.loadRecents()
