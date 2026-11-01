#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the spellchecker backends, using fakes instead of real libraries."""

import gzip
import importlib.util
import json
import string
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
                              "it", "true", "are", "here", "viele", "grüße",
                              "café", "geht", "gut", "s", "he")):
        self._lang = "fake"
        self._customDict = set()
        self._words = set(words)

    # Like enchant, which raises ValueError for an empty word
    def _isMisspelled(self, word):
        if not word:
            raise ValueError("can't check spelling of empty string")
        return word.lower() not in self._words

    def _getSuggestions(self, word):
        if not word:
            raise ValueError("can't suggest spellings for empty string")
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
    """MainWindow whose dictionary menu lists fake libraries."""
    from PyQt5.QtWidgets import QMenu, QActionGroup
    from PyQt5.QtCore import Qt
    from manuskript import functions as F
    from manuskript import settings

    def availableDictionaries():
        return OrderedDict([("Fake", ["aa_AA", "bb_BB"]),
                            ("Other", ["bb_BB", "cc_CC"])])

    monkeypatch.setattr(S.Spellchecker, "isInstalled", staticmethod(lambda: True))
    monkeypatch.setattr(S.Spellchecker, "availableDictionaries",
                        staticmethod(availableDictionaries))
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


###############################################################################
# LanguageTool dictionaries of older versions
###############################################################################

# LanguageTool is no longer supported. Versions that supported it stored its
# dictionaries like the others, as "dict" in the settings.txt of the project:
# "LanguageTool:en-US". Such a project is treated like one whose dictionary
# is not installed.

def test_languageToolDictionaryIsNotAvailable(resources):
    assert "LanguageTool" not in S.Spellchecker.supportedLibraries()
    assert "LanguageTool" not in S.Spellchecker.availableDictionaries()
    assert S.Spellchecker.getDictionary("LanguageTool:en-US") is None
    assert S.Spellchecker.dictionaries == {}


@pytest.mark.parametrize("dictionary", ["LanguageTool:en-US", "LanguageTool:auto"])
def test_dictionaryMenuReplacesLanguageToolDictionary(dictionaryMenu, dictionary):
    from manuskript import settings
    MW = dictionaryMenu

    settings.dict = dictionary
    MW.updateMenuDict()
    assert settings.dict == "Fake:aa_AA"
    assert checkedDictionaries(MW) == [("Fake", "aa_AA")]
    assert not [a.text() for a in MW.menuDict.actions()
                if "LanguageTool" in a.text()]


def test_projectWithLanguageToolDictionaryOpens(MWNoProject, dictionaryMenu,
                                                tmp_path, monkeypatch, caplog):
    import os
    from PyQt5.QtWidgets import QMessageBox
    from manuskript import settings
    from manuskript.tests.load_save.helpers import copySample
    MW = dictionaryMenu

    path = copySample(tmp_path)
    settingsFile = os.path.join(path[:-4], "settings.txt")
    with open(settingsFile, encoding="utf-8") as f:
        projectSettings = json.load(f)
    projectSettings["dict"] = "LanguageTool:en-US"
    with open(settingsFile, "w", encoding="utf-8") as f:
        json.dump(projectSettings, f, indent=4, sort_keys=True)

    dialogs = []
    for name in ["critical", "warning", "information", "question"]:
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda *args, name=name: dialogs.append(name) or QMessageBox.Ok))
    caplog.set_level("WARNING")

    try:
        # Opened twice: no error the second time either
        for i in range(2):
            MW.loadProject(path)
            assert MW.currentProject == path
            assert settings.dict == "Fake:aa_AA"
            assert checkedDictionaries(MW) == [("Fake", "aa_AA")]
            assert MW.saveDatas() is True
            with open(settingsFile, encoding="utf-8") as f:
                assert json.load(f)["dict"] == "Fake:aa_AA"
            MW.projectDirty = False
            MW.closeProject()

            with open(settingsFile, "w", encoding="utf-8") as f:
                json.dump(projectSettings, f, indent=4, sort_keys=True)

        assert dialogs == []
        assert [r.getMessage() for r in caplog.records
                if r.levelname in ("ERROR", "CRITICAL") or r.exc_info] == []
    finally:
        MW.projectDirty = False
        MW.closeProject()


def test_projectWithLanguageToolDictionaryOpensWithoutLibrary(MWNoProject,
                                                              tmp_path,
                                                              monkeypatch, caplog):
    import os
    from PyQt5.QtWidgets import QMessageBox
    from manuskript import settings
    from manuskript.tests.load_save.helpers import copySample
    from manuskript.ui.views.textEditView import textEditView
    MW = MWNoProject

    # No spellcheck library is installed
    monkeypatch.setattr(S.Spellchecker, "implementations", [])
    monkeypatch.setattr(S.Spellchecker, "dictionaries", {})
    monkeypatch.setattr(settings, "dict", settings.dict)
    monkeypatch.setattr(settings, "spellcheck", settings.spellcheck)

    path = copySample(tmp_path)
    settingsFile = os.path.join(path[:-4], "settings.txt")
    with open(settingsFile, encoding="utf-8") as f:
        projectSettings = json.load(f)
    projectSettings["dict"] = "LanguageTool:en-US"
    projectSettings["spellcheck"] = True
    with open(settingsFile, "w", encoding="utf-8") as f:
        json.dump(projectSettings, f, indent=4, sort_keys=True)

    dialogs = []
    for name in ["critical", "warning", "information", "question"]:
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda *args, name=name: dialogs.append(name) or QMessageBox.Ok))
    caplog.set_level("WARNING")

    def firstText(item):
        for child in item.children():
            if child.isText():
                return child
            found = firstText(child)
            if found:
                return found

    try:
        # Opened twice: no error the second time either
        for i in range(2):
            MW.loadProject(path)
            assert MW.currentProject == path
            # The setting is kept, but no editor checks the spelling
            assert settings.dict == "LanguageTool:en-US"
            MW.tabMain.setCurrentIndex(MW.TabRedac)
            MW.mainEditor.setCurrentModelIndex(firstText(MW.mdlOutline.rootItem).index())
            editors = MW.findChildren(textEditView)
            assert MW.mainEditor.currentEditor().txtRedacText in editors
            assert [w for w in editors if w.spellcheck] == []
            assert MW.saveDatas() is True
            with open(settingsFile, encoding="utf-8") as f:
                saved = json.load(f)
            assert (saved["dict"], saved["spellcheck"]) == ("LanguageTool:en-US", True)
            MW.mainEditor.closeAllTabs()
            MW.projectDirty = False
            MW.closeProject()

        assert dialogs == []
        assert [r.getMessage() for r in caplog.records
                if r.levelname in ("ERROR", "CRITICAL") or r.exc_info] == []
    finally:
        MW.mainEditor.closeAllTabs()
        MW.projectDirty = False
        MW.closeProject()


###############################################################################
# Words
###############################################################################

@pytest.mark.parametrize("text, misspelled", [
    ("the dgo is here. ", ["dgo"]),
    ("a b teh. ", ["teh"]),                        # single letters are not checked
    ("He said 'hello world' to me. ", []),         # single quotes
    ("He said ‘hello world’ to me. ", []),
    ("the dogs' bones are here. ", []),            # plural possessive
    ("'teh' dog ", ["teh"]),
    ("It isn’t true. ", []),                       # dictionary only knows isn't
    ("teh's dog ", ["teh's"]),
    ("geht’s gut? ", []),                          # dictionary knows no geht's
    ("geht's gut? ", []),
    ("Viele Grüße ", []),
    ("Viele Grüsse ", ["Grüsse"]),
    ("Viele Grüße", []),                           # being typed: not checked
    ("Viele Grüsse", []),
    ("a café", []),
    ("snake_case dgo ", ["snake", "case", "dgo"]),
])
def test_checkText(text, misspelled):
    d = FakeDictionary()
    assert [m.getWord(text) for m in d.checkText(text)] == misspelled


@pytest.mark.parametrize("text, misspelled", [
    ("geht's gut? ", []),
    ("So'n Hund. ", []),
    ("hab'n wir ", []),
    ("the dog's bones ", []),                      # possessive
    ("your'e ", ["your'e"]),
    ("I'am ", ["I'am"]),
    ("they'r ", ["they'r"]),
    ("you’r ", ["you’r"]),
    ("could'of ", ["could'of"]),
    ("I'l ", ["I'l"]),
    ("does't ", ["does't"]),
    ("your're ", ["your're"]),
    ("Hund'e ", ["Hund'e"]),
    ("a'b'c'd'e ", ["a'b'c'd'e"]),
    ("a'b's ", ["a'b's"]),
    # A clitic without a word before it, which the dictionary does not know
    ("Hast du 'ne Ahnung? ", ["ne"]),
    ("’nen Moment ", ["nen"]),
    ("''ne ", ["ne"]),
])
def test_checkTextContractions(text, misspelled):
    # Like Hunspell, the dictionary knows single letters and parts of words
    d = FakeDictionary(words=("geht", "gut", "so", "hund", "hab", "wir",
                              "the", "dog", "bones", "your", "you", "they",
                              "could", "does", "am", "of", "re", "ll",
                              "hast", "du", "ahnung", "moment")
                       + tuple(string.ascii_lowercase))
    assert [m.getWord(text) for m in d.checkText(text)] == misspelled


@pytest.mark.parametrize("clitic", ["'s", "’s"])
def test_findSuggestionsForAClitic(clitic):
    # The selection is only a clitic: there is no word before it to check
    d = FakeDictionary()
    text = "the dog" + clitic + " bones"
    [match] = d.findSuggestions(text, 7, 9)
    assert (match.start, match.end, match.replacements) == (7, 9, ["the"])


def test_findSuggestionsForApostrophes():
    d = FakeDictionary()
    text = "the '' ’ dog"
    assert d.findSuggestions(text, 4, 6) == []         # ''
    assert d.findSuggestions(text, 7, 8) == []         # ’


class UnusedLibrary:
    """Records what a dictionary asks its library, which then fails."""
    def __init__(self):
        self.asked = []

    def __getattr__(self, name):
        self.asked.append(name)
        raise AssertionError("asked the library: " + name)


@pytest.mark.parametrize("cls", [S.EnchantDictionary, S.PySpellcheckerDictionary,
                                 S.SymSpellDictionary])
def test_wordsWithoutLettersAreNotChecked(monkeypatch, cls):
    # enchant raises ValueError for an empty word, which would close the
    # application while highlighting
    library = UnusedLibrary()
    d = cls.__new__(cls)
    d._lang = "fake"
    d._customDict = set()
    d._dict = library
    for word in ["", "'", "''", "’", "'’"]:
        assert not d.isMisspelled(word)
        assert d.getSuggestions(word) == []
        assert not d.isWordMisspelled(word)
        assert d.findSuggestions("a " + word + " b", 2, 2 + len(word)) == []
    assert library.asked == []


###############################################################################
# Elisions
###############################################################################

class ElisionDictionary(FakeDictionary):
    """Like the word lists of pyspellchecker and symspellpy, knows neither
    l’homme nor l'homme."""
    def __init__(self, lang, suggestions=None):
        FakeDictionary.__init__(self, words=(
            "homme", "est", "là", "ai", "il", "vienne", "à", "demain",
            "aujourd'hui", "aime", "dit", "pas", "une", "hôtel", "état", "y",
            "chat", "suis", "anno", "amico", "amica", "un'amica", "libro",
            "800", "home", "aigua", "the", "dog", "quick", "a", "ou", "où",
            "e", "è", "due"))
        self._lang = lang
        self._suggestions = suggestions or {}

    def _getSuggestions(self, word):
        return self._suggestions.get(word, [])


@pytest.mark.parametrize("apostrophe", ["'", "’"])
@pytest.mark.parametrize("lang, text, misspelled", [
    ("fr_FR", "L'homme est là. ", []),
    ("fr_FR", "j'ai ", []),
    ("fr_FR", "qu'il vienne ", []),
    ("fr_FR", "QU'IL ", []),
    ("fr_FR", "jusqu'à demain ", []),
    ("fr_FR", "quelqu'une ", []),
    ("fr_FR", "l'hôtel, L'ÉTAT, j'y ", []),
    # The rest is checked the same way
    ("fr_FR", "qu'aujourd'hui ", []),
    ("fr_FR", "l'hommme est là ", ["l'hommme"]),
    ("fr_FR", "x'homme ", ["x'homme"]),
    ("fr_FR", "l''homme ", ["l''homme"]),
    # Not before a consonant, not even in colloquial French
    ("fr_FR", "l'chat ", ["l'chat"]),
    ("fr_FR", "j'suis pas là ", ["j'suis"]),
    ("fr_FR", "j't'aime ", ["j't'aime"]),
    ("fr_FR", "dell'anno ", ["dell'anno"]),        # Italian
    # Not without the accent that the word needs after the elision, although
    # it is a word without it
    ("fr_FR", "jusqu'à, d'où, jusqu'où ", []),
    ("fr_FR", "jusqu'a, d'ou, jusqu'ou ", ["jusqu'a", "d'ou", "jusqu'ou"]),
    ("fr_FR", "Jusqu'a, JUSQU'A, D'OU ", ["Jusqu'a", "JUSQU'A", "D'OU"]),
    # Where it can be right without the accent (ce qu'a dit Pierre, d'A à Z)
    ("fr_FR", "qu'a, lorsqu'a, d'a ", []),
    ("it_IT", "dell'anno, nell'800 ", []),
    ("it_IT", "l'amico ", []),
    ("it_IT", "l'libro ", ["l'libro"]),
    # Only before a feminine word: the word list knows these
    ("it_IT", "un'amica ", []),
    ("it_IT", "un'amico ", ["un'amico"]),
    ("it_IT", "dell'annno ", ["dell'annno"]),
    ("it_IT", "c'è, dov'è, s'è ", []),
    ("it_IT", "c'e, dov'e, s'e, quant'e ", ["c'e", "dov'e", "s'e", "quant'e"]),
    ("it_IT", "tutt'e due, dell'e ", []),
    ("it_IT", "jusqu'à ", ["jusqu'à"]),             # French
    ("ca_ES", "l'home, d'aigua ", []),
    ("ca_ES", "jusqu'à ", ["jusqu'à"]),
    ("ca_ES", "d'ou ", []),                         # of an egg
    # English text is not affected
    ("en_US", "the quick dog ", []),
    ("en_US", "the l'homme ", ["l'homme"]),
])
def test_checkTextElisions(lang, text, misspelled, apostrophe):
    d = ElisionDictionary(lang)
    text = text.replace("'", apostrophe)
    misspelled = [w.replace("'", apostrophe) for w in misspelled]
    assert [m.getWord(text) for m in d.checkText(text)] == misspelled


@pytest.mark.parametrize("lang, elisions", [
    ("fr", True), ("fr_FR", True), ("fr-FR", True), ("fr_CA", True),
    ("fr-classique", True), ("FR_fr", True),
    ("it", True), ("it_IT", True), ("it-CH", True),
    ("ca", True), ("ca_ES", True), ("ca-ES-valencia", True),
    ("ca_ES@valencia", True),
    ("en", False), ("en_US", False), ("de_DE", False), ("frr", False),
    ("fake", False), ("", False), (None, False),
])
def test_elisionsInTheLanguageOfTheDictionary(lang, elisions):
    d = ElisionDictionary(lang)
    assert d.isWordMisspelled("l’homme") != elisions
    assert d.isWordMisspelled("l'homme") != elisions
    assert d.isWordMisspelled("l’hommme")


@pytest.mark.parametrize("apostrophe", ["'", "’"])
def test_findSuggestionsForElisions(apostrophe):
    def a(word):
        return word.replace("’", apostrophe)

    d = ElisionDictionary("fr_FR", suggestions={
        "hommme": ["homme", "hommes", "comme"],
        a("aujourd’hiu"): ["aujourd'hui"],
        "hommmmmme": [],
        a("l’hommmmmme"): ["l'homme"],
        a("j’t’l’hommme"): ["je te l'homme"],
        a("x’homme"): ["homme"]})
    text = a("l’homme l’hommme qu’aujourd’hiu j’t’l’hommme l’hommmmmme x’homme ")

    def suggestions(word):
        start = text.index(a(word))
        return d.findSuggestions(text, start, start + len(word))

    # Like the underlines
    misspelled = ["l’hommme", "qu’aujourd’hiu", "j’t’l’hommme", "l’hommmmmme",
                  "x’homme"]
    assert [m.getWord(text) for m in d.checkText(text)] == list(map(a, misspelled))
    assert suggestions("l’homme") == []
    for word in misspelled:
        [match] = suggestions(word)
        assert match.getWord(text) == a(word)

    # The elision is kept, and only valid elisions are suggested (not l’comme)
    [match] = suggestions("l’hommme")
    assert match.replacements == [a("l’homme"), a("l’hommes")]
    # With the apostrophe that was typed
    [match] = suggestions("qu’aujourd’hiu")
    assert match.replacements == [a("qu’aujourd’hui")]
    # Only the word after the elision is looked up
    [match] = suggestions("l’hommmmmme")
    assert match.replacements == []
    # A word that is not an elision is looked up as a whole
    [match] = suggestions("j’t’l’hommme")
    assert match.replacements == ["je te l'homme"]
    [match] = suggestions("x’homme")
    assert match.replacements == ["homme"]


def test_suggestionsAfterAnElisionWithBothApostrophes():
    d = ElisionDictionary("fr_FR", suggestions={
        "aujourd'hiu": ["aujourd'hui"],
        "aujourd’hiu": ["aujourd'hui", "aujourd’hui"]})

    def replacements(word):
        [match] = d.findSuggestions(word + " ", 0, len(word))
        return match.replacements

    # The word list's apostrophe, when both were typed
    assert replacements("qu’aujourd'hiu") == ["qu’aujourd'hui"]
    assert replacements("qu'aujourd’hiu") == ["qu'aujourd'hui", "qu'aujourd’hui"]
    # Only once, if the word list has both
    assert replacements("qu’aujourd’hiu") == ["qu’aujourd’hui"]


@pytest.mark.parametrize("apostrophe", ["'", "’"])
@pytest.mark.parametrize("lang, word, suggestion", [
    ("fr_FR", "jusqu'a", "jusqu'à"),
    ("fr_FR", "Jusqu'a", "Jusqu'à"),
    ("fr_FR", "JUSQU'A", "JUSQU'À"),
    ("fr_FR", "d'ou", "d'où"),
    ("fr_FR", "D'Ou", "D'Où"),
    ("fr_FR", "jusqu'ou", "jusqu'où"),
    ("it_IT", "c'e", "c'è"),
    ("it_IT", "Dov'e", "Dov'è"),
    ("it_IT", "COS'E", "COS'È"),
])
def test_findSuggestionsForMissingAccents(lang, word, suggestion, apostrophe):
    # Only the accented word, not what the word list suggests for a or e
    d = ElisionDictionary(lang, suggestions={"a": ["à", "la"], "e": ["è"]})
    word = word.replace("'", apostrophe)
    [match] = d.findSuggestions(word + " ", 0, len(word))
    assert match.replacements == [suggestion.replace("'", apostrophe)]


def test_missingAccentAfterElisionAsCustomWord():
    d = ElisionDictionary("it_IT")
    assert d.isWordMisspelled("c’e")
    d.addWord("c’e")
    assert not d.isWordMisspelled("c’e")
    assert d.checkText("c’e ") == []


@pytest.mark.parametrize("text, misspelled", [
    ("D’aujourd’hui ", []),
    # Only one elision, since the word after it starts with a vowel or h
    ("J’t’l’ai dit ", ["J’t’l’ai"]),
    ("j't’l'ai pas dit ", ["j't’l'ai"]),
    ("l’l’homme ", ["l’l’homme"]),
    # A long word does not take long, and is not checked with a recursion,
    # which would fail while highlighting
    ("l’" * (sys.getrecursionlimit() + 10) + "homme ",
     ["l’" * (sys.getrecursionlimit() + 10) + "homme"]),
])
def test_checkTextElisionChains(text, misspelled):
    d = ElisionDictionary("fr")
    assert [m.getWord(text) for m in d.checkText(text)] == misspelled
    for word in misspelled:
        [match] = d.findSuggestions(text, 0, len(word))
        assert match.getWord(text) == word


@pytest.mark.parametrize("word, follows", [
    ("homme", True), ("Homme", True), ("aime", True), ("à", True),
    ("état", True), ("ÉTAT", True), ("île", True), ("œuvre", True),
    ("Œil", True), ("y", True), ("800", True), ("chat", False),
    ("Pierre", False), ("’homme", False), ("'", False), ("", False),
])
def test_canFollowElision(word, follows):
    assert S.canFollowElision(word) == follows


def test_contextMenuForElisions(monkeypatch):
    from manuskript import settings
    from manuskript.ui.views.textEditView import textEditView

    fake = ElisionDictionary("fr_FR", suggestions={"hommme": ["homme"]})
    monkeypatch.setattr(settings, "spellcheck", True)
    monkeypatch.setattr(S.Spellchecker, "getDictionary",
                        staticmethod(lambda name: fake))
    editor = textEditView(spellcheck=True, highlighting=True, dict="Fake:fr_FR")
    text = "l’homme est là, l’hommme est là jusqu’a demain\n"
    editor.setPlainText(text)
    editor.highlighter.rehighlight()
    assert underlinedWords(editor) == ["l’hommme", "jusqu’a"]

    def spellingSuggestions(position):
        cursor = editor.textCursor()
        cursor.setPosition(position)
        editor.setTextCursor(cursor)
        menu = editor.createStandardContextMenu()
        return [s.text() for a in menu.actions() if a.menu()
                for s in a.menu().actions()
                if isinstance(s, textEditView.SpellAction)]

    # Right-clicking selects the whole word
    assert spellingSuggestions(text.index("l’homme") + 3) == []
    assert spellingSuggestions(text.index("l’hommme") + 3) == ["l’homme"]
    assert editor.textCursor().selectedText() == "l’hommme"
    assert spellingSuggestions(text.index("jusqu’a") + 1) == ["jusqu’à"]
    assert editor.textCursor().selectedText() == "jusqu’a"


class HunspellLibrary:
    """Like a Hunspell dictionary of enchant, knows the elided forms with an
    ASCII apostrophe, and that they are wrong before a consonant, an h
    aspiré (l'héros) or a masculine word (un'amico)."""
    words = {"l'homme", "homme", "le", "héros", "chat", "l'amico", "amico",
             "un", "un'amica", "amica", "libro"}

    def check(self, word):
        return word.lower() in self.words

    def suggest(self, word):
        return {"l'héros": ["le héros"]}.get(word.replace("’", "'"), [])

    def is_added(self, word):
        return False


@pytest.mark.parametrize("apostrophe", ["'", "’"])
@pytest.mark.parametrize("lang, text, misspelled", [
    ("fr_FR", "L'homme, le héros, le chat ", []),
    ("fr_FR", "l'héros, l'chat ", ["l'héros", "l'chat"]),
    ("it_IT", "l'amico, un'amica ", []),
    ("it_IT", "un'amico, l'libro ", ["un'amico", "l'libro"]),
])
def test_enchantChecksElisionsItself(lang, text, misspelled, apostrophe):
    # Hunspell dictionaries know which elisions are wrong, so the word after
    # an elision is not checked apart from it
    d = S.EnchantDictionary.__new__(S.EnchantDictionary)
    d._lang = lang
    d._dict = HunspellLibrary()
    text = text.replace("'", apostrophe)
    misspelled = [w.replace("'", apostrophe) for w in misspelled]
    assert [m.getWord(text) for m in d.checkText(text)] == misspelled
    if lang == "fr_FR" and misspelled:
        [match] = d.findSuggestions(text, 0, len(misspelled[0]))
        assert match.replacements == ["le héros"]


@pytest.mark.parametrize("library", ["pyspellchecker", "symspellpy"])
@pytest.mark.parametrize("lang, correct, misspelled, suggestion, accents", [
    ("fr", "L’homme qu’il a vu jusqu’à aujourd’hui n’est pas d’accord. "
           "L'homme qu'il a vu jusqu'à aujourd'hui n'est pas d'accord. "
           "Qu’aujourd’hui j’ai faim, quelqu’une aussi. "
           "D’où et jusqu’où, d'où et jusqu'où ? Ce qu’a dit Pierre. ",
     ["l’hommme", "x’homme", "l’chat", "l'hommme", "x'homme", "l'chat"],
     "l’homme",
     [("jusqu’a", "jusqu’à"), ("D’ou", "D’où"), ("jusqu'ou", "jusqu'où")]),
    ("it", "M’ama l’amico e un’amica dell’anno, bell’aspetto. Quant’è? "
           "M'ama l'amico e un'amica dell'anno, bell'aspetto. Quant'è? "
           "Dov’è? C’è. Cos'è? Tutt’e due. ",
     ["dell’annno", "l’amicco", "un’amico", "l’libro",
      "dell'annno", "l'amicco", "un'amico", "l'libro"], "dell’anno",
     [("dov’e", "dov’è"), ("C’e", "C’è"), ("cos'e", "cos'è")]),
], ids=["fr", "it"])
def test_elisionsWithWordLists(resources, library, lang, correct, misspelled,
                               suggestion, accents):
    cls = {"pyspellchecker": S.PySpellcheckerDictionary,
           "symspellpy": S.SymSpellDictionary}[library]
    if not cls.isInstalled():
        pytest.skip("{} is not installed".format(library))
    if lang not in cls.availableDictionaries():
        pytest.skip("{} has no '{}' dictionary".format(library, lang))
    d = cls(lang)

    assert [m.getWord(correct) for m in d.checkText(correct)] == []
    # The first word, which the dictionary does not know
    assert d.findSuggestions(correct, 0, correct.index(" ")) == []

    text = " ".join(misspelled) + " "
    assert [m.getWord(text) for m in d.checkText(text)] == misspelled
    for word in misspelled:
        start = text.index(word)
        [match] = d.findSuggestions(text, start, start + len(word))
        assert match.getWord(text) == word
    [match] = d.findSuggestions(text, 0, len(misspelled[0]))
    assert suggestion in match.replacements

    # A word after the elision that misses its accent there
    text = " ".join(word for word, _ in accents) + " "
    assert ([m.getWord(text) for m in d.checkText(text)] ==
            [word for word, _ in accents])
    for word, accented in accents:
        start = text.index(word)
        [match] = d.findSuggestions(text, start, start + len(word))
        assert match.replacements == [accented]


@pytest.mark.parametrize("lang, correct, elisions", [
    ("fr_FR", "L’homme qu’il a vu jusqu’à aujourd’hui n’est pas d’accord. "
              "L'homme qu'il a vu jusqu'à aujourd'hui n'est pas d'accord. ",
     ["l’héros", "l’chat", "d’maison", "j’suis", "jusqu’a", "d’ou"]),
    ("it_IT", "Ama l’amico e un’amica dell’anno. "
              "Ama l'amico e un'amica dell'anno. ",
     ["un’amico", "l’libro", "dov’e", "c’e"]),
], ids=["fr_FR", "it_IT"])
def test_elisionsWithEnchant(resources, lang, correct, elisions):
    # A word with an elision is checked as a whole, as the dictionary checks
    # it (with ’ read as '). Which of these words it rejects depends on the
    # dictionary: old French Hunspell dictionaries reject l’héros and l’chat,
    # current ones accept them.
    if S.enchant is None:
        pytest.skip("pyenchant is not installed")
    if not S.enchant.dict_exists(lang):
        pytest.skip("enchant has no '{}' dictionary".format(lang))
    d = S.EnchantDictionary(lang)

    assert [m.getWord(correct) for m in d.checkText(correct)] == []

    words = elisions + [w.replace("’", "'") for w in elisions]
    rejected = [w for w in words if not d._dict.check(w)
                and not d._dict.check(w.replace("’", "'"))]
    text = " ".join(words) + " "
    assert [m.getWord(text) for m in d.checkText(text)] == rejected
    for word in rejected:
        start = text.index(word)
        [match] = d.findSuggestions(text, start, start + len(word))
        assert match.replacements == d._dict.suggest(word)


def test_checkTextCustomWord():
    d = FakeDictionary()
    d.addWord("Manuskript")
    text = "the Manuskript dgo. "
    assert [m.getWord(text) for m in d.checkText(text)] == ["dgo"]


def test_findSuggestionsAgreesWithCheckText():
    d = FakeDictionary()
    text = "It isn’t teh dog. "
    assert d.findSuggestions(text, 3, 8) == []         # isn’t
    [match] = d.findSuggestions(text, 9, 12)           # teh
    assert (match.start, match.end, match.replacements) == (9, 12, ["the"])


def test_wordBeingTypedIsNotUnderlined(monkeypatch):
    from manuskript import settings
    from manuskript.ui.views.textEditView import textEditView

    fake = FakeDictionary()
    monkeypatch.setattr(settings, "spellcheck", True)
    monkeypatch.setattr(S.Spellchecker, "getDictionary",
                        staticmethod(lambda name: fake))
    editor = textEditView(spellcheck=True, highlighting=True, dict="Fake:fake")
    editor.setEnabled(True)
    for character in "viele Grüße":
        cursor = editor.textCursor()
        cursor.insertText(character)
        editor.setTextCursor(cursor)
    assert underlinedWords(editor) == []


def test_findSuggestionsOnlyForOneWord():
    d = FakeDictionary()
    text = "teh dgo\nhello world"
    assert d.findSuggestions(text, 0, 7) == []         # teh dgo
    assert d.findSuggestions(text, 4, 13) == []        # dgo\nhello
    assert d.findSuggestions(text, 8, 19) == []        # hello world
    [match] = d.findSuggestions(text, 4, 7)            # dgo
    assert (match.start, match.end) == (4, 7)


def test_misspelledColorSetting(monkeypatch):
    from PyQt5.QtGui import QColor
    from manuskript import settings
    from manuskript.ui.views.textEditView import textEditView

    fake = FakeDictionary()
    monkeypatch.setattr(settings, "spellcheck", True)
    monkeypatch.setattr(S.Spellchecker, "getDictionary",
                        staticmethod(lambda name: fake))
    editor = textEditView(spellcheck=True, highlighting=True, dict="Fake:fake")
    editor.setPlainText("the dgo is here\n")

    def underlineColor():
        block = editor.document().firstBlock()
        return [r.format.underlineColor().name() for r in block.layout().formats()
                if r.format.underlineStyle() != 0]

    # Settings > Editor
    monkeypatch.setitem(settings.textEditor, "misspelled", "#0000ff")
    editor.highlighter.updateColorScheme()
    assert underlineColor() == ["#0000ff"]

    # Themes
    editor.highlighter.setMisspelledColor(QColor("#00ff00"))
    editor.highlighter.rehighlight()
    assert underlineColor() == ["#00ff00"]
