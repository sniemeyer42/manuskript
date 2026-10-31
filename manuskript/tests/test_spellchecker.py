#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the spellchecker backends, using fakes instead of real libraries."""

import pytest

from manuskript.functions import spellchecker as S
from manuskript.functions.spellchecker import BasicDictionary


def test_abstractMethodsRaiseNotImplementedError():
    for method in [BasicDictionary.getLibraryName,
                   BasicDictionary.getLibraryURL,
                   BasicDictionary.isInstalled,
                   BasicDictionary.getDefaultDictionary,
                   BasicDictionary.availableDictionaries]:
        with pytest.raises(NotImplementedError):
            method()

    d = BasicDictionary.__new__(BasicDictionary)
    with pytest.raises(NotImplementedError):
        d.isMisspelled("word")
    with pytest.raises(NotImplementedError):
        d.getSuggestions("word")


###############################################################################
# LanguageTool
###############################################################################

class FakeLTMatch3:
    """Match as returned by language_tool_python >= 3.0 (snake_case)."""
    def __init__(self, offset, length, issueType, message, replacements):
        self.offset = offset
        self.error_length = length
        self.rule_issue_type = issueType
        self.message = message
        self.replacements = replacements


class FakeLTMatch2:
    """Match as returned by language_tool_python < 3.0 (camelCase)."""
    def __init__(self, offset, length, issueType, message, replacements):
        self.offset = offset
        self.errorLength = length
        self.ruleIssueType = issueType
        self.message = message
        self.replacements = replacements


class FakeLTTool:
    def __init__(self, matchClass=FakeLTMatch3, error=None):
        self.matchClass = matchClass
        self.error = error
        self.checked = []

    def check(self, text):
        self.checked.append(text)
        if self.error:
            raise self.error
        matches = []
        start = text.find("teh")
        if start >= 0:
            matches.append(self.matchClass(start, 3, "misspelling",
                                           "Possible spelling mistake found.",
                                           ["the"]))
        return matches


def fakeLanguageToolDictionary(tool):
    d = S.LanguageToolDictionary.__new__(S.LanguageToolDictionary)
    d._lang = "en-US"
    d._customDict = set()
    d.tool = tool
    d._cache = {}
    return d


@pytest.mark.parametrize("matchClass", [FakeLTMatch2, FakeLTMatch3])
def test_languageToolMatchApiVersions(monkeypatch, matchClass):
    monkeypatch.setattr(S, "use_language_check", False)
    d = fakeLanguageToolDictionary(FakeLTTool(matchClass))
    text = "The teh dog."
    matches = d.checkText(text)
    assert [(m.getWord(text), m.locqualityissuetype, m.replacements, m.msg)
            for m in matches] == [("teh", "misspelling", ["the"],
                                   "Possible spelling mistake found.")]


def test_languageToolCheckErrorIsLoggedOnce(monkeypatch, caplog):
    monkeypatch.setattr(S, "use_language_check", False)
    monkeypatch.setattr(S.LanguageToolCache, "_failing", False, raising=False)
    caplog.set_level("DEBUG", logger=S.LOGGER.name)
    tool = FakeLTTool(error=RuntimeError("LanguageTool server died"))
    d = fakeLanguageToolDictionary(tool)

    def warnings():
        return [r for r in caplog.records if r.levelname == "WARNING"]

    # Not for every paragraph
    for i in range(5):
        assert d.checkText("Paragraph {}.".format(i)) == []
    assert len(tool.checked) == 5
    assert len(warnings()) == 1

    # Unless it worked in between
    tool.error = None
    d.checkText("The teh dog.")
    tool.error = RuntimeError("LanguageTool server died again")
    d.checkText("Another paragraph.")
    assert len(warnings()) == 2


def test_languageToolCheckErrorDoesNotRaise(monkeypatch):
    monkeypatch.setattr(S, "use_language_check", False)
    tool = FakeLTTool(error=RuntimeError("LanguageTool server died"))
    d = fakeLanguageToolDictionary(tool)
    assert d.checkText("The teh dog.") == []
    assert d.findSuggestions("The teh dog.", 5, 5) == []
    assert tool.checked
