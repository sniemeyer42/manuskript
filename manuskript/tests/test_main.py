#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for main.py"""

import pytest

from PyQt5.QtCore import QTranslator

from manuskript import main
from manuskript.functions import appPath


@pytest.mark.parametrize("languageCode, expected", [
    ("de-DE", "manuskript_de_DE.qm"),
    ("pt-BR", "manuskript_pt_BR.qm"),
    ("zh-CN", "manuskript_zh_CN.qm"),
    ("zh-Hans-CN", "manuskript_zh_Hans_CN.qm"),
    ("zh-TW", "manuskript_zh_HANT.qm"),
    ("zh-HK", "manuskript_zh_HANT.qm"),
    ("zh-Hant-TW", "manuskript_zh_HANT.qm"),
])
def test_translationFileName(languageCode, expected):
    assert main.translationFileName(languageCode) == expected


@pytest.mark.parametrize("languageCode, expected", [
    ("de-DE", "manuskript_de.qm"),
    ("zh-CN", "manuskript_zh_CN.qm"),
    ("zh-TW", "manuskript_zh_HANT.qm"),
    ("zh-Hant-HK", "manuskript_zh_HANT.qm"),
])
def test_translationAutoDetection(languageCode, expected):
    """The shipped translation is found for the UI language (APP-17)."""
    translator = QTranslator()
    assert translator.load(main.translationFileName(languageCode),
                           appPath("i18n"))
    if hasattr(translator, "filePath"):  # Qt >= 5.15
        assert translator.filePath().endswith(expected)
