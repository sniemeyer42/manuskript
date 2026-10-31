#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Helpers for the load / save tests."""

import os
import shutil

from PyQt5.QtCore import Qt, QModelIndex

from manuskript import loadSave
from manuskript.enums import Outline
from manuskript.functions import appPath
from manuskript.models import outlineItem


def copySample(tmp_path):
    """Copies the sample project to tmp_path, returns the path of the .msk file."""
    src = appPath(os.path.join("sample-projects", "book-of-acts"))
    dst = os.path.join(str(tmp_path), "book-of-acts")
    shutil.copyfile(src + ".msk", dst + ".msk")
    shutil.copytree(src, dst)
    return dst + ".msk"


def addItem(MW, parent, title, text="", folder=False, row=None):
    item = outlineItem(title=title, _type="folder" if folder else "md")
    if not folder:
        item.setData(Outline.text, text)
    mdl = MW.mdlOutline
    parentIndex = QModelIndex() if parent is mdl.rootItem else parent.index()
    MW.mdlOutline.insertItem(item, parent.childCount() if row is None else row, parentIndex)
    return item


def drag(MW, item, parent, row):
    """Moves item to parent at row, like a drag and drop in the outline."""
    mdl = MW.mdlOutline
    parentIndex = QModelIndex() if parent is mdl.rootItem else parent.index()
    assert mdl.dropMimeData(mdl.mimeData([item.index()]), Qt.MoveAction, row, 0, parentIndex)
    mdl.removeIndex(item.index())


def duplicate(MW, item):
    """Like Edit > Duplicate."""
    mdl = MW.mdlOutline
    assert mdl.dropMimeData(mdl.mimeData([item.index()]), Qt.CopyAction, -1, 0, QModelIndex())


def tree(MW):
    """Outline as a list of (depth, ID, title, type, text)."""
    out = []

    def rec(item, depth):
        for c in item.children():
            out.append((depth, c.ID(), c.title(), c.type(), c.data(Outline.text)))
            rec(c, depth + 1)

    rec(MW.mdlOutline.rootItem, 0)
    return out


def reload(MW):
    """Saves, then opens the project again from disk. Returns the outline before and after."""
    assert loadSave.saveProject()
    before = tree(MW)
    path = MW.currentProject
    MW.closeProject()
    MW.loadProject(path)
    assert MW.currentProject == path
    return before, tree(MW)
