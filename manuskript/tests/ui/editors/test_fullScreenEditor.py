#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the fullscreen editor."""


def test_fullScreenGoalAndLocker(MWSampleProject):
    """
    The fullscreen editor must cope with a goal set as a string (as the
    properties line edit does) and with a new text without word count.
    """
    from manuskript.enums import Outline
    MW = MWSampleProject
    me = MW.mainEditor

    def firstText(item):
        for c in item.children():
            if c.isText():
                return c
            t = firstText(c)
            if t:
                return t

    text = firstText(MW.mdlOutline.rootItem)
    me.setCurrentModelIndex(text.index())
    goalIndex = text.index().sibling(text.index().row(), Outline.goal)
    MW.mdlOutline.setData(goalIndex, "500")  # Properties > Goal

    me.showFullScreen()
    fs = me._fullScreen
    assert fs is not None
    try:
        assert "500" in fs.lblWC.text()

        # New text: its word count is still "" in the model
        fs.createNewText()
        assert fs._index.internalPointer().data(Outline.wordCount) == ""
        fs.locker.rbtnWordTarget.setChecked(True)
        fs.locker.spnWordTarget.setValue(10)
        fs.locker.lock()
        assert fs.locker.isLocked()
        assert fs.locker._target == 10
        fs.locker.unlock()
    finally:
        fs.leaveFullscreen()
    assert me._fullScreen is None
