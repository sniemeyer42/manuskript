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
