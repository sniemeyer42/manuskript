#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the frequency analyzer."""

from types import SimpleNamespace

import pytest

from manuskript import settings
from manuskript.ui.tools.frequencyAnalyzer import frequencyAnalyzer


@pytest.fixture(autouse=True)
def keepSettings(monkeypatch):
    """The analyzer writes its options into the global settings."""
    monkeypatch.setattr(settings, "frequencyAnalyzer",
                        dict(settings.frequencyAnalyzer))


class fakeItem:
    def __init__(self, text, children=()):
        self._text = text
        self._children = list(children)

    def text(self):
        return self._text

    def children(self):
        return self._children


def analyzer(text):
    root = fakeItem("", [fakeItem(text)])
    mw = SimpleNamespace(mdlOutline=SimpleNamespace(rootItem=root))
    fa = frequencyAnalyzer(mw)
    fa.spnWordMin.setValue(1)
    fa.txtWordExclude.setPlainText("")
    fa.spnPhraseMin.setValue(2)
    fa.spnPhraseMax.setValue(2)
    return fa


def column(model, col=0):
    return [model.item(r, col).text() for r in range(model.rowCount())]


def test_analyzeWord_typographicApostrophe():
    """Contractions with ’ are counted as one word (#997)."""
    fa = analyzer("I couldn’t go, they couldn't stay.")
    fa.analyzeWord()
    words = column(fa.tblWord.model())
    assert "couldn’t" in words
    assert "couldn't" in words
    assert "couldn" not in words
    assert "t" not in words


def test_analyzePhrase_typographicApostrophe():
    """Phrases are not split at ’ (#997)."""
    fa = analyzer("I couldn’t go. I couldn’t go.")
    fa.analyzePhrase()
    phrases = column(fa.tblPhrase.model())
    assert "I couldn’t" in phrases
    assert "couldn’t go" in phrases
    assert "couldn t" not in phrases


@pytest.mark.parametrize("text", [
    "‘Go away,’ she said. ‘I know.’ He couldn’t. I know.",
    "'Go away,' she said. 'I know.' He couldn't. I know.",
])
def test_analyzeWord_quotes(text):
    """Quotation marks around dialogue are neither words nor parts of words."""
    fa = analyzer(text)
    fa.analyzeWord()
    words = column(fa.tblWord.model())
    assert "know" in words
    assert all(w[0] not in "'’" and w[-1] not in "'’" for w in words), words
    assert "couldn’t" in words or "couldn't" in words


def test_analyzePhrase_quotes():
    """Closing quotes do not end up in the phrases."""
    fa = analyzer("‘Go away,’ she said. ‘Go away,’ she cried.")
    fa.analyzePhrase()
    phrases = column(fa.tblPhrase.model())
    assert "away she" in phrases
    assert all("’" not in p for p in phrases), phrases
