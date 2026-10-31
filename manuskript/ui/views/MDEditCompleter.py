#!/usr/bin/env python
# --!-- coding: utf8 --!--
import re

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QFont, QFontMetrics
from PyQt5.QtWidgets import QAction, qApp, QToolTip, QTextEdit

from manuskript.ui.editors.completer import completer
from manuskript.ui.views.MDEditView import MDEditView
from manuskript.models import references as Ref


class MDEditCompleter(MDEditView):
    def __init__(self, parent=None, index=None, html=None, spellcheck=True, highlighting=False, dict="",
                 autoResize=False):
        MDEditView.__init__(self, parent=parent, index=index, html=html, spellcheck=spellcheck, highlighting=True,
                              dict=dict, autoResize=autoResize)

        self.completer = None
        self.setMouseTracking(True)
        self.refRects = []
        self._noFocusMode = True

        # Like the clickable things (see MDEditView.getClickRects), the
        # references are scanned once text changes have settled.
        self._refRectsTimer = QTimer(self)
        self._refRectsTimer.setSingleShot(True)
        self._refRectsTimer.setInterval(100)
        self._refRectsTimer.timeout.connect(self.computeRefRects)
        self.textChanged.connect(self.getRefRects)
        self.document().documentLayoutChanged.connect(self.getRefRects)

    def setCurrentModelIndex(self, index):
        MDEditView.setCurrentModelIndex(self, index)
        if self._index and not self.completer:
            self.setCompleter(completer())

    def setCompleter(self, completer):
        self.completer = completer
        self.completer.activated.connect(self.insertCompletion)

    def insertCompletion(self, txt):
        tc = self.textCursor()
        tc.insertText(txt)
        self.setTextCursor(tc)

    def textUnderCursor(self, select=False):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        if select:
            self.setTextCursor(tc)
        return tc.selectedText()

    def refUnderCursor(self, cursor):
        pos = cursor.position()
        cursor.select(QTextCursor.BlockUnderCursor)
        text = cursor.selectedText()
        pos -= cursor.selectionStart()
        match = re.findall(Ref.RegExNonCapturing, text)
        for m in match:
            if text.find(m) <= pos <= text.find(m) + len(m):
                return m

                # def event(self, event):
                # if event.type() == QEvent.ToolTip:
                # cursor = self.cursorForPosition(event.pos())
                # ref = self.refUnderCursor(cursor)
                # if ref:
                # QToolTip.showText(self.mapToGlobal(event.pos()), infoForRef(ref))
                # else:
                # QToolTip.hideText()
                # return True
                # return MDEditView.event(self, event)

    def createStandardContextMenu(self):
        menu = MDEditView.createStandardContextMenu(self)

        a = QAction(self.tr("Insert reference"), menu)
        a.triggered.connect(self.popupCompleter)
        menu.insertSeparator(menu.actions()[0])
        menu.insertAction(menu.actions()[0], a)
        return menu

    def keyPressEvent(self, event):
        if self.completer.isVisible():
            if event.key() in (
                    Qt.Key_Enter,
                    Qt.Key_Return,
                    Qt.Key_Escape,
                    Qt.Key_Tab,
                    Qt.Key_Backtab):
                event.ignore()
                return

        isShortcut = (event.modifiers() == Qt.ControlModifier and \
                      event.key() == Qt.Key_Space)

        if not self.completer or not isShortcut:
            self.completer.setVisible(False)
            MDEditView.keyPressEvent(self, event)
            return

        self.popupCompleter()

    def popupCompleter(self):
        if self.completer:
            cr = self.cursorRect()
            cr.moveTopLeft(self.mapToGlobal(cr.bottomLeft()))
            cr.setWidth(self.completer.sizeHint().width())
            self.completer.setGeometry(cr)
            self.completer.popup(self.textUnderCursor(select=True))

    def mouseMoveEvent(self, event):
        """
        When mouse moves, we show tooltip when appropriate.
        """
        self.beginTooltipMoveEvent()
        MDEditView.mouseMoveEvent(self, event)
        self.endTooltipMoveEvent()

        self.computePendingRefRects()
        onRef = [r for r in self.refRects if r.contains(event.pos())]

        if not onRef:
            qApp.restoreOverrideCursor()
            self.hideTooltip()
            return

        cursor = self.cursorForPosition(event.pos())
        ref = self.refUnderCursor(cursor)
        if ref:
            if not qApp.overrideCursor():
                qApp.setOverrideCursor(Qt.PointingHandCursor)

            self.showTooltip(self.mapToGlobal(event.pos()), Ref.tooltip(ref))

    def mouseReleaseEvent(self, event):
        MDEditView.mouseReleaseEvent(self, event)
        self.computePendingRefRects()
        onRef = [r for r in self.refRects if r.contains(event.pos())]
        if onRef:
            cursor = self.cursorForPosition(event.pos())
            ref = self.refUnderCursor(cursor)
            if ref:
                Ref.open(ref)
                qApp.restoreOverrideCursor()

    def resizeEvent(self, event):
        MDEditView.resizeEvent(self, event)
        self.getRefRects()

    def getRefRects(self):
        """
        Schedules an update of the references' rects (see computeRefRects).
        Called on every text change and highlighter pass, so the actual
        computation is debounced.
        """
        # Can be called by MDEditView.__init__, before the timer exists.
        timer = getattr(self, "_refRectsTimer", None)
        if timer is not None:
            timer.start()

    def computePendingRefRects(self):
        """
        Computes the references' rects right away if an update is pending.
        """
        if self._refRectsTimer.isActive():
            self._refRectsTimer.stop()
            self.computeRefRects()

    def computeRefRects(self):
        cursor = self.textCursor()
        f = self.font()
        f.setFixedPitch(True)
        f.setWeight(QFont.DemiBold)
        fm = QFontMetrics(f)
        refs = []
        for txt in re.finditer(Ref.RegEx, self.toPlainText()):
            cursor.setPosition(txt.start())
            r = self.cursorRect(cursor)
            r.setWidth(fm.width(txt.group(0)))
            refs.append(r)
        self.refRects = refs

    def paintEvent(self, event):
        QTextEdit.paintEvent(self, event)

        # Debug: paint rects
        # painter = QPainter(self.viewport())
        # painter.setPen(Qt.gray)
        # for r in self.refRects:
        # painter.drawRect(r)
