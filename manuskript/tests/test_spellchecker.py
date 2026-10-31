#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the spellchecker backends, using fakes instead of real libraries."""

import gzip
import importlib.util
import json
import sys
import types
from collections import OrderedDict

import pytest

from manuskript.functions import spellchecker as S
from manuskript.functions.spellchecker import BasicDictionary


class FakeDictionary(BasicDictionary):
    """Dictionary with a fixed list of known words."""
    def __init__(self, words=("the", "a", "is", "dog", "dogs", "bones",
                              "said", "hello", "world", "to", "me", "isn't",
                              "it", "true")):
        self._lang = "fake"
        self._customDict = set()
        self._words = set(words)

    def isMisspelled(self, word):
        return word.lower() not in self._words

    def getSuggestions(self, word):
        return ["the"]

    def _saveCustomDict(self):
        pass


def underlinedWords(editor):
    block = editor.document().firstBlock()
    text = block.text()
    return [text[r.start:r.start + r.length] for r in block.layout().formats()
            if r.format.underlineStyle() != 0]


@pytest.fixture
def resources(monkeypatch, tmp_path):
    """Keeps custom dictionaries and caches out of the user's data folder,
    and starts with an empty cache of loaded dictionaries."""
    monkeypatch.setattr(S, "writablePath", lambda: str(tmp_path / "data"))
    monkeypatch.setattr(S.Spellchecker, "dictionaries", {})
    return tmp_path


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


###############################################################################
# symspellpy detection
###############################################################################

def loadSpellcheckerCopy(monkeypatch, symspellpyVersion=None,
                         metadataVersion=None, api=False):
    """Executes a fresh copy of the spellchecker module with a fake symspellpy
    installed and distutils unavailable (as in Python >= 3.12)."""
    # Python >= 3.8
    metadata = pytest.importorskip("importlib.metadata")

    fake = types.ModuleType("symspellpy")
    if symspellpyVersion:
        fake.__version__ = symspellpyVersion
    if api:
        fake.SymSpell = types.SimpleNamespace(delete_dictionary_entry=None)
    monkeypatch.setitem(sys.modules, "symspellpy", fake)
    monkeypatch.setitem(sys.modules, "distutils", None)
    monkeypatch.setitem(sys.modules, "distutils.version", None)

    def version(distribution):
        if distribution == "symspellpy" and metadataVersion:
            return metadataVersion
        raise metadata.PackageNotFoundError(distribution)
    monkeypatch.setattr(metadata, "version", version)

    spec = importlib.util.spec_from_file_location("spellchecker_copy", S.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("symspellpyVersion, metadataVersion, api, detected", [
    (None, "6.10.1", True, True),   # recent releases have no __version__
    ("6.7.7", None, True, True),    # no package metadata, but __version__
    ("6.3.8", "6.3.8", True, True),
    (None, "6.3.7", True, False),   # too old
    # Unknown version, as in a frozen application without package metadata
    (None, None, True, True),
    (None, None, False, False),
])
def test_symspellpyDetection(monkeypatch, symspellpyVersion, metadataVersion,
                             api, detected):
    module = loadSpellcheckerCopy(monkeypatch, symspellpyVersion,
                                  metadataVersion, api)
    assert (module.symspellpy is not None) == detected
    assert module.SymSpellDictionary.isInstalled() == detected


def test_isVersionAtLeast():
    assert S.isVersionAtLeast("6.10.1", "6.3.8")
    assert S.isVersionAtLeast("6.3.8", "6.3.8")
    assert not S.isVersionAtLeast("6.3.7", "6.3.8")
    assert not S.isVersionAtLeast(None, "6.3.8")


###############################################################################
# symspellpy backend
###############################################################################

class FakeSuggestItem:
    def __init__(self, term, distance):
        self.term = term
        self.distance = distance


class FakeSymSpell:
    """Minimal stand-in for symspellpy.SymSpell."""
    def __init__(self, maxDistance):
        self._words = {}

    @property
    def word_count(self):
        return len(self._words)

    def load_pickle(self, path, compressed):
        return False

    def save_pickle(self, path, compressed):
        pass

    def create_dictionary_entry(self, key, count):
        self._words[key] = count
        return True

    def delete_dictionary_entry(self, key):
        return self._words.pop(key, None) is not None

    def lookup(self, phrase, verbosity, *args, **kwargs):
        if phrase in self._words:
            return [FakeSuggestItem(phrase, 0)]
        return []


@pytest.fixture
def fakeSymspell(monkeypatch, resources):
    """symspellpy, and pyspellchecker resources with only an 'en' word list."""
    monkeypatch.setattr(S, "symspellpy", types.SimpleNamespace(
        SymSpell=FakeSymSpell,
        Verbosity=types.SimpleNamespace(TOP=0, CLOSEST=1, ALL=2)))

    pyspellcheckerPath = resources / "pyspellchecker"
    (pyspellcheckerPath / "resources").mkdir(parents=True)
    with gzip.open(str(pyspellcheckerPath / "resources" / "en.json.gz"), "wt",
                   encoding="utf-8") as f:
        f.write(json.dumps({"the": 100, "quick": 10, "dog": 50}))
    monkeypatch.setattr(S, "pyspellchecker", types.SimpleNamespace(
        __path__=[str(pyspellcheckerPath)]))


def test_symspellUnknownLanguage(fakeSymspell):
    with pytest.raises(ValueError):
        S.SymSpellDictionary("C")
    assert S.Spellchecker.getDictionary("symspellpy:C") is None

    d = S.Spellchecker.getDictionary("symspellpy:en")
    text = "The quick dog teh. "
    assert [m.getWord(text) for m in d.checkText(text)] == ["teh"]


def test_symspellRemoveCustomWord(fakeSymspell):
    d = S.Spellchecker.getDictionary("symspellpy:en")
    text = "The Manuskript dog. "
    assert [m.getWord(text) for m in d.checkText(text)] == ["Manuskript"]

    d.addWord("Manuskript")
    assert d.checkText(text) == []

    d.removeWord("Manuskript")
    assert not d.isCustomWord("Manuskript")
    assert [m.getWord(text) for m in d.checkText(text)] == ["Manuskript"]


###############################################################################
# Default dictionary
###############################################################################

class FakeQLocale:
    localeName = "C"

    @classmethod
    def system(cls):
        return cls()

    def name(self):
        return self.localeName


def fakeEnchant(monkeypatch, available, default):
    monkeypatch.setattr(S, "enchant", types.SimpleNamespace(
        list_dicts=lambda: [(name, None) for name in available],
        dict_exists=lambda name: name in available,
        get_default_language=lambda: default))


def fakeLocale(monkeypatch, name):
    monkeypatch.setattr(FakeQLocale, "localeName", name)
    monkeypatch.setattr(S, "QLocale", FakeQLocale)


@pytest.mark.parametrize("default, locale, available, expected", [
    ("de_DE", "de_DE", ["de_DE", "en_US"], "de_DE"),
    (None, "C", ["de_DE", "en_US"], "en_US"),
    ("fr_FR", "fr_FR", ["de_DE", "en_US"], "en_US"),
    ("en_GB", "en_GB", ["de_DE", "en_US"], "en_US"),
    ("de_AT", "de_AT", ["en_US", "de_DE"], "de_DE"),
    (None, "fr_CA", ["fr_FR", "en_US"], "fr_FR"),
    (None, "C", ["de_DE"], "de_DE"),
    (None, "C", [], None),
])
def test_enchantDefaultDictionaryIsAvailable(monkeypatch, default, locale,
                                             available, expected):
    fakeEnchant(monkeypatch, available, default)
    fakeLocale(monkeypatch, locale)
    assert S.EnchantDictionary.getDefaultDictionary() == expected


@pytest.mark.parametrize("locale, expected", [
    ("de_AT", "de"),
    ("C", "en"),
    ("hu_HU", "en"),
])
def test_pyspellcheckerDefaultDictionaryIsAvailable(monkeypatch, fakeSymspell,
                                                    locale, expected):
    fakeLocale(monkeypatch, locale)
    monkeypatch.setattr(S.PySpellcheckerDictionary, "availableDictionaries",
                        staticmethod(lambda: ["de", "en", "fr"]))
    assert S.PySpellcheckerDictionary.getDefaultDictionary() == expected


def test_symspellDefaultDictionaryIsAvailable(monkeypatch, fakeSymspell):
    # Only an "en" word list is installed (see fakeSymspell)
    fakeLocale(monkeypatch, "C")
    assert S.SymSpellDictionary.getDefaultDictionary() == "en"
    assert S.SymSpellDictionary(S.SymSpellDictionary.getDefaultDictionary())


def test_languageToolDefaultDictionaryIsAvailable(monkeypatch):
    fakeLocale(monkeypatch, "en_GB")
    monkeypatch.setattr(S, "use_language_check", False)
    monkeypatch.setattr(S, "languagetool", types.SimpleNamespace(
        utils=types.SimpleNamespace(get_locale_language=lambda: "en_GB")))
    monkeypatch.setattr(S.LanguageToolDictionary, "isInstalled",
                        staticmethod(lambda: True))
    monkeypatch.setattr(S.LanguageToolDictionary, "availableDictionaries",
                        staticmethod(lambda: ["auto", "de", "de-DE", "en",
                                              "en-GB", "en-US"]))
    assert S.LanguageToolDictionary.getDefaultDictionary() == "en-GB"


@pytest.mark.parametrize("locale, enchantDictionaries, expected", [
    # The language of the system in any library, before English
    ("fr_FR", ["de_DE", "en_US"], "pyspellchecker:fr"),
    ("de_DE", ["en_US"], "pyspellchecker:de"),
    # In the library of highest priority that has the language
    ("de_AT", ["de_DE", "en_US"], "PyEnchant:de_DE"),
    ("en_GB", ["de_DE", "en_US"], "PyEnchant:en_US"),
    # No library has it
    ("hu_HU", ["de_DE", "en_US"], "PyEnchant:en_US"),
    ("hu_HU", [], "pyspellchecker:en"),
])
def test_defaultDictionaryPrefersTheLanguage(monkeypatch, locale,
                                             enchantDictionaries, expected):
    fakeEnchant(monkeypatch, enchantDictionaries, locale)
    fakeLocale(monkeypatch, locale)
    monkeypatch.setattr(S, "pyspellchecker", types.SimpleNamespace())
    monkeypatch.setattr(S.PySpellcheckerDictionary, "availableDictionaries",
                        staticmethod(lambda: ["de", "en", "fr"]))
    monkeypatch.setattr(S.Spellchecker, "implementations",
                        [S.EnchantDictionary, S.PySpellcheckerDictionary])
    assert S.Spellchecker.getDefaultDictionary() == expected


def test_defaultDictionaryFallsBackToNextLibrary(monkeypatch, fakeSymspell):
    fakeEnchant(monkeypatch, [], "en_US")
    fakeLocale(monkeypatch, "en_US")
    monkeypatch.setattr(S.Spellchecker, "implementations",
                        [S.EnchantDictionary, S.SymSpellDictionary])
    assert S.Spellchecker.getDefaultDictionary() == "symspellpy:en"
    assert S.Spellchecker.getDictionary(None) is not None


###############################################################################
# Editor
###############################################################################

def test_setDictEnablesSpellcheckAgain(monkeypatch):
    from manuskript import settings
    from manuskript.ui.views.textEditView import textEditView

    fake = FakeDictionary()
    monkeypatch.setattr(settings, "spellcheck", True)
    monkeypatch.setattr(S.Spellchecker, "getDictionary", staticmethod(
        lambda name: fake if name == "Fake:good" else None))

    # The project dictionary is not installed: spellcheck is switched off
    editor = textEditView(spellcheck=True, highlighting=True, dict="Fake:missing")
    assert not editor.spellcheck

    # The user picks an installed one in Tools > Dictionary
    editor.setDict("Fake:good")
    assert editor.spellcheck
    editor.setPlainText("the dgo is a dog\n")
    editor.highlighter.rehighlight()
    assert underlinedWords(editor) == ["dgo"]

    # But it stays off if the user disabled spellcheck
    monkeypatch.setattr(settings, "spellcheck", False)
    editor = textEditView(spellcheck=False, highlighting=True, dict="Fake:good")
    editor.setDict("Fake:good")
    assert not editor.spellcheck


###############################################################################
# Tools > Dictionary menu
###############################################################################

@pytest.fixture
def dictionaryMenu(MW, monkeypatch):
    """MainWindow whose dictionary menu lists fake dictionaries."""
    from PyQt5.QtWidgets import QMenu, QActionGroup
    from PyQt5.QtCore import Qt
    from manuskript import functions as F
    from manuskript import settings

    available = OrderedDict([("Fake", ["aa_AA", "bb_BB"]),
                             ("Other", ["bb_BB", "cc_CC"])])
    monkeypatch.setattr(S.Spellchecker, "isInstalled", staticmethod(lambda: True))
    monkeypatch.setattr(S.Spellchecker, "availableDictionaries",
                        staticmethod(lambda: available))
    monkeypatch.setattr(S.Spellchecker, "supportedLibraries",
                        staticmethod(lambda: OrderedDict([("Fake", None),
                                                          ("Other", None)])))
    monkeypatch.setattr(S.Spellchecker, "getDefaultDictionary",
                        staticmethod(lambda: "Fake:aa_AA"))
    monkeypatch.setattr(S.Spellchecker, "getDictionary",
                        staticmethod(lambda name: None))
    # Connect as in the application, not as in the other tests (see
    # tests/__init__.py)
    monkeypatch.setattr(F, "AUC", Qt.AutoConnection | Qt.UniqueConnection)
    monkeypatch.setattr(settings, "dict", settings.dict)
    if not hasattr(MW, "menuDict"):
        monkeypatch.setattr(MW, "menuDict", QMenu(), raising=False)
        monkeypatch.setattr(MW, "menuDictGroup", QActionGroup(MW), raising=False)
    yield MW

    # Rebuild the real menu
    monkeypatch.undo()
    if hasattr(MW, "menuDict"):
        MW.updateMenuDict()


def checkedDictionaries(MW):
    return [(a.data, a.text().replace("&", ""))
            for a in MW.menuDictGroup.actions() if a.isChecked()]


def test_dictionaryMenuCanBeRebuilt(dictionaryMenu, monkeypatch):
    from manuskript import settings
    MW = dictionaryMenu

    # The menu is rebuilt at startup and on every project load. Many actions
    # make it likely that new ones get the address of deleted ones, which
    # PyQt still remembers as connected for a while: connecting them with
    # Qt.UniqueConnection then raised "TypeError: connection is not unique".
    available = OrderedDict([("Fake", ["aa_{:02}".format(i) for i in range(30)]),
                             ("Other", ["bb_BB"])])
    monkeypatch.setattr(S.Spellchecker, "availableDictionaries",
                        staticmethod(lambda: available))
    settings.dict = "Fake:aa_00"
    for i in range(20):
        MW.updateMenuDict()
    assert len(MW.menuDictGroup.actions()) == 31
    assert checkedDictionaries(MW) == [("Fake", "aa_00")]

    # The actions still work
    [action] = [a for a in MW.menuDictGroup.actions()
                if a.text().replace("&", "") == "aa_05"]
    action.trigger()
    assert settings.dict == "Fake:aa_05"


def test_dictionaryMenuDoesNotPileUpActions(dictionaryMenu):
    from manuskript import settings
    MW = dictionaryMenu

    settings.dict = "Fake:bb_BB"
    for i in range(3):
        MW.updateMenuDict()
    assert len(MW.menuDictGroup.actions()) == 4
    assert checkedDictionaries(MW) == [("Fake", "bb_BB")]

    settings.dict = "Other:cc_CC"
    MW.updateMenuDict()
    assert len(MW.menuDictGroup.actions()) == 4
    assert checkedDictionaries(MW) == [("Other", "cc_CC")]


def test_dictionaryMenuKeepsLegacyDictionaryName(dictionaryMenu):
    from manuskript import settings
    MW = dictionaryMenu

    # Stored by older versions (and in the sample projects) without library
    settings.dict = "bb_BB"
    MW.updateMenuDict()
    assert settings.dict == "Fake:bb_BB"
    assert checkedDictionaries(MW) == [("Fake", "bb_BB")]

    settings.dict = "cc_CC"
    MW.updateMenuDict()
    assert settings.dict == "Other:cc_CC"

    # Not installed: falls back to the default dictionary
    settings.dict = "zz_ZZ"
    MW.updateMenuDict()
    assert settings.dict == "Fake:aa_AA"
