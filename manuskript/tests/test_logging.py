#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for logging.py"""

import logging
import sys
import threading
from types import SimpleNamespace


def test_threadExceptionHook(caplog):
    """The thread exception hook logs the original exception."""
    from manuskript import logging as ML

    def hookArgs(exc):
        try:
            raise exc
        except BaseException:
            exc_type, exc_value, exc_traceback = sys.exc_info()
        return SimpleNamespace(exc_type=exc_type, exc_value=exc_value,
                               exc_traceback=exc_traceback,
                               thread=threading.current_thread())

    caplog.set_level(logging.DEBUG)
    ML.handle_uncaught_thread_exception(hookArgs(ValueError("thread error")))
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info[0] is ValueError

    caplog.clear()
    ML.handle_uncaught_thread_exception(hookArgs(SystemExit(0)))
    assert caplog.records == []


def test_qtMessageLevels(caplog):
    """Qt message types are logged with the matching level."""
    from PyQt5 import QtCore
    from manuskript import logging as ML

    context = SimpleNamespace(category="manuskript.tests.qt", file=None,
                              line=0, function=None)
    caplog.set_level(logging.DEBUG, logger="manuskript.tests.qt")
    for msgType, level in [
            (QtCore.QtDebugMsg, logging.DEBUG),
            (QtCore.QtInfoMsg, logging.INFO),
            (QtCore.QtWarningMsg, logging.WARNING),
            (QtCore.QtCriticalMsg, logging.ERROR),
            (QtCore.QtFatalMsg, logging.CRITICAL)]:
        caplog.clear()
        ML.qtMessageHandler(msgType, context, "message")
        assert [r.levelno for r in caplog.records] == [level]
