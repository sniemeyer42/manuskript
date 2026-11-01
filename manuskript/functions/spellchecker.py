#!/usr/bin/env python
# --!-- coding: utf8 --!--

import os, gzip, json, glob, re, shutil
from PyQt5.QtCore import QLocale
from collections import OrderedDict
from manuskript.functions import writablePath

import logging
LOGGER = logging.getLogger(__name__)

try:
    import enchant
except ImportError:
    enchant = None

try:
    import spellchecker as pyspellchecker
except ImportError:
    pyspellchecker = None

def getPackageVersion(module, distribution):
    # Recent releases of some packages (symspellpy for example) have no
    # __version__ anymore, so ask the metadata of the installed package first.
    try:
        from importlib.metadata import version
        return version(distribution)
    except Exception:
        return getattr(module, "__version__", None)

def isVersionAtLeast(version, minimum):
    # distutils.version was removed in Python 3.12, and comparing the strings
    # gets "6.10.1" < "6.3.8" wrong, so compare the numbers.
    def numbers(v):
        return tuple(int(n) for n in re.findall(r"\d+", str(v))[:3])
    return bool(version) and numbers(version) >= numbers(minimum)

SYMSPELLPY_MIN_VERSION = "6.3.8"

def isSymspellpyUsable(module):
    version = getPackageVersion(module, "symspellpy")
    if version is None:
        # Neither package metadata (a frozen application might have none) nor
        # __version__: look for the API added in the minimum version.
        return hasattr(getattr(module, "SymSpell", None), "delete_dictionary_entry")
    return isVersionAtLeast(version, SYMSPELLPY_MIN_VERSION)

try:
    import symspellpy

    if not isSymspellpyUsable(symspellpy):
        symspellpy = None

except ImportError:
    symspellpy = None


use_language_check = False

try:
    try:
        import language_tool_python as languagetool
    except:
        import language_check as languagetool
        use_language_check = True
except:
    languagetool = None

def pickDictionary(available, preferred, fallback=(), strict=False):
    """
    Returns the name in `available` matching the first possible name in
    `preferred`: the same name (en-US is the same as en_US), else the same
    language in another region (en_GB matches en_US). Unless strict, then
    tries `fallback` the same way, and finally takes the first available
    dictionary. Returns None if no dictionary was found.
    """
    available = list(available)

    def normalized(name):
        return name.replace("-", "_").lower()

    def language(name):
        return normalized(name).split("_")[0]

    def find(names, key):
        for name in names:
            if name:
                for a in available:
                    if key(a) == key(name):
                        return a
        return None

    for names in [preferred] if strict else [preferred, fallback]:
        dictionary = find(names, normalized) or find(names, language)
        if dictionary:
            return dictionary

    return available[0] if available and not strict else None

class Spellchecker:
    dictionaries = {}
    # In order of priority
    implementations = []

    def __init__(self):
        pass

    @staticmethod
    def registerImplementation(impl):
        Spellchecker.implementations.append(impl)

    @staticmethod
    def isInstalled():
        for impl in Spellchecker.implementations:
            if impl.isInstalled():
                return True
        return False

    @staticmethod
    def supportedLibraries():
        libs = OrderedDict()
        for impl in Spellchecker.implementations:
            libs[impl.getLibraryName()] = impl.getLibraryRequirement()
        return libs

    @staticmethod
    def availableLibraries():
        ret = []
        for impl in Spellchecker.implementations:
            if impl.isInstalled():
                ret.append(impl.getLibraryName())
        return ret

    @staticmethod
    def availableDictionaries():
        """
        Returns the dictionaries of every installed library. They are None for
        a library that has to be started first (see startLibrary).
        """
        dictionaries = OrderedDict()
        for impl in Spellchecker.implementations:
            if impl.isInstalled():
                if impl.isStarted():
                    dictionaries[impl.getLibraryName()] = impl.availableDictionaries()
                else:
                    dictionaries[impl.getLibraryName()] = None
        return dictionaries

    @staticmethod
    def startLibrary(lib):
        """Starts the library named lib, which can take a while."""
        for impl in Spellchecker.implementations:
            if impl.isInstalled() and impl.getLibraryName() == lib:
                impl.start()

    @staticmethod
    def normalizeDictName(lib, dictionary):
        return "{}:{}".format(lib, dictionary)

    @staticmethod
    def getDefaultDictionary():
        # A dictionary in the language of the system is better than one in
        # another language from a library of higher priority. A library that
        # is not started is only started if no other one has a dictionary.
        for strict in [True, False]:
            for impl in Spellchecker.implementations:
                if strict and not impl.isStarted():
                    continue
                default = impl.getDefaultDictionary(strict)
                if default:
                    return Spellchecker.normalizeDictName(impl.getLibraryName(), default)
        return None

    @staticmethod
    def getLibraryURL(lib=None):
        urls = {}
        for impl in Spellchecker.implementations:
            urls[impl.getLibraryName()] = impl.getLibraryURL()
        if lib:
            return urls.get(lib, None)
        return urls

    @staticmethod
    def getDictionary(dictionary):
        if not dictionary:
            dictionary = Spellchecker.getDefaultDictionary()
        if not dictionary:
            return None

        values = dictionary.split(":", 1)
        if len(values) == 1:
            (lib, name) = (Spellchecker.implementations[0].getLibraryName(), dictionary)
            dictionary = Spellchecker.normalizeDictName(lib, name)
        else:
            (lib, name) = values
        try:
            d = Spellchecker.dictionaries.get(dictionary, None)
            if d == None:
                for impl in Spellchecker.implementations:
                    if impl.isInstalled() and lib == impl.getLibraryName():
                        d = impl(name)
                        Spellchecker.dictionaries[dictionary] = d
                        break
            return d
        except Exception as e:
            pass
        return None

class BasicMatch:
    def __init__(self, startIndex, endIndex):
        self.start = startIndex
        self.end = endIndex
        self.locqualityissuetype = 'misspelling'
        self.replacements = []
        self.msg = ''

    def getWord(self, text):
        return text[self.start:self.end]

# Apostrophes can be part of a word: isn't, isn’t
APOSTROPHES = "'\u2019"

# Endings after an apostrophe that dictionaries might not know as part of a
# word: the possessive 's, and colloquial German (geht's, so'n, hab'n, auf'm,
# so'ne)
CLITICS = {"s", "n", "m", "ne", "nen", "nem"}

# Based on http://john.nachtimwald.com/2009/08/22/qplaintextedit-with-in-line-spell-check/
# Letters, digits and apostrophes, not preceded or followed by any of them. A
# word at the very end of the text is not matched, so that a word is not
# checked while it is being typed (see BasicHighlighter.highlightBlockAfter).
WORDS = re.compile(r"(?<![^\W_]|['\u2019])((?:[^\W_]|['\u2019])+)(?=[^\w'\u2019]|_)")

class BasicDictionary:
    def __init__(self, name):
        self._lang = name
        if not self._lang:
            self._lang = self.getDefaultDictionary()

        self._customDict = set()
        customPath = self.getCustomDictionaryPath()
        try:
            with gzip.open(customPath, 'rt', encoding='utf-8') as f:
                self._customDict = set(json.loads(f.read()))
                for word in self._customDict:
                    self._dict.create_dictionary_entry(word, self.CUSTOM_COUNT)
        except:
            # If error loading the file, overwrite with empty dictionary
            self._saveCustomDict()

    @property
    def name(self):
        return self._lang

    @staticmethod
    def getLibraryName():
        raise NotImplementedError

    @staticmethod
    def getLibraryRequirement():
        return None

    @staticmethod
    def getLibraryURL():
        raise NotImplementedError

    @staticmethod
    def isInstalled():
        raise NotImplementedError

    @staticmethod
    def isStarted():
        """
        Returns False if the library has to be started (see start) before it
        can list its dictionaries, because starting it is slow.
        """
        return True

    @staticmethod
    def start():
        pass

    @staticmethod
    def getDefaultDictionary(strict=False):
        """
        Returns the dictionary for the language of the system. Unless strict,
        returns another one if there is none (see pickDictionary).
        """
        raise NotImplementedError

    @staticmethod
    def availableDictionaries():
        raise NotImplementedError

    def checkText(self, text):
        matches = []

        for word_object in WORDS.finditer(text):
            start, end = word_object.span(1)
            token = text[start:end]

            # Apostrophes around a word are usually quotes ('hello world') or
            # the possessive of a plural (dogs')
            while start < end and text[start] in APOSTROPHES:
                start += 1
            while end > start and text[end - 1] in APOSTROPHES:
                end -= 1

            # Single letters are not checked
            if end - start < 2:
                continue

            word = text[start:end]
            if self.isWordMisspelled(word) and (word == token or self.isWordMisspelled(token)):
                matches.append(BasicMatch(start, end))

        return matches

    def isWordMisspelled(self, word):
        """
        Like isMisspelled, but also accepts custom words, and words that the
        dictionary only knows with an ASCII apostrophe (isn’t) or without a
        clitic (geht's).
        """
        if not self.isMisspelled(word) or self.isCustomWord(word):
            return False

        # Some dictionaries only know the ASCII apostrophe: isn’t -> isn't
        if "\u2019" in word and not self.isMisspelled(word.replace("\u2019", "'")):
            return False

        # Some dictionaries know no contractions: geht's -> geht + 's. Only
        # for known clitics, since dictionaries know most parts of words
        # (your'e is not your + e), and only after a word ('ne has none).
        parts = re.split("[" + APOSTROPHES + "]", word)
        clitic = parts[-1]
        head = word[:-len(clitic) - 1]
        if len(parts) > 1 and clitic.lower() in CLITICS and head.strip(APOSTROPHES):
            if not self.isMisspelled(head):
                return False

        return True

    def isMisspelled(self, word):
        # A word without letters (empty or only apostrophes) is not asked:
        # enchant raises ValueError for an empty one, which would close the
        # application while highlighting.
        if not word.strip(APOSTROPHES):
            return False
        return self._isMisspelled(word)

    def getSuggestions(self, word):
        if not word.strip(APOSTROPHES):
            return []
        return self._getSuggestions(word)

    def _isMisspelled(self, word):
        """Asks the library whether word is misspelled."""
        raise NotImplementedError

    def _getSuggestions(self, word):
        """Asks the library for the spellings it suggests for word."""
        raise NotImplementedError

    def findSuggestions(self, text, start, end):
        if start < end:
            word = text[start:end]

            # A selection of several words is not a misspelled word
            if not any(c.isspace() for c in word) and self.isWordMisspelled(word):
                match = BasicMatch(start, end)
                match.replacements = self.getSuggestions(word)

                return [ match ]

        return []

    def isCustomWord(self, word):
        return word.lower() in self._customDict

    def addWord(self, word):
        word = word.lower()
        if not word in self._customDict:
            self._customDict.add(word)
            self._saveCustomDict()

    def removeWord(self, word):
        word = word.lower()
        if word in self._customDict:
            self._customDict.remove(word)
            self._saveCustomDict()

    @classmethod
    def getResourcesPath(cls):
        path = os.path.join(writablePath(), "resources", "dictionaries", cls.getLibraryName())
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def getCustomDictionaryPath(self):
        return os.path.join(self.getResourcesPath(), "{}.json.gz".format(self._lang))

    def _saveCustomDict(self):
        customPath = self.getCustomDictionaryPath()
        with gzip.open(customPath, "wt", newline="\n") as f:
            f.write(json.dumps(list(self._customDict)))


class EnchantDictionary(BasicDictionary):

    def __init__(self, name):
        self._lang = name
        if not (self._lang and enchant.dict_exists(self._lang)):
            self._lang = self.getDefaultDictionary()

        self._dict = enchant.DictWithPWL(self._lang, self.getCustomDictionaryPath())

    @staticmethod
    def getLibraryName():
        return "PyEnchant"

    @staticmethod
    def getLibraryURL():
        return "https://pypi.org/project/pyenchant/"

    @staticmethod
    def isInstalled():
        return enchant != None

    @staticmethod
    def availableDictionaries():
        if EnchantDictionary.isInstalled():
            return list(map(lambda i: str(i[0]), enchant.list_dicts()))
        return []

    @staticmethod
    def getDefaultDictionary(strict=False):
        if not EnchantDictionary.isInstalled():
            return None

        return pickDictionary(EnchantDictionary.availableDictionaries(),
                              [enchant.get_default_language(), QLocale.system().name()],
                              ["en_US"], strict)

    def _isMisspelled(self, word):
        return not self._dict.check(word)

    def _getSuggestions(self, word):
        return self._dict.suggest(word)

    def isCustomWord(self, word):
        return self._dict.is_added(word)

    def addWord(self, word):
        self._dict.add(word)

    def removeWord(self, word):
        self._dict.remove(word)

    def getCustomDictionaryPath(self):
        return os.path.join(self.getResourcesPath(), "{}.txt".format(self.name))

class PySpellcheckerDictionary(BasicDictionary):

    def __init__(self, name):
        BasicDictionary.__init__(self, name)

        self._dict = pyspellchecker.SpellChecker(self.name)
        self._dict.word_frequency.load_words(self._customDict)

    @staticmethod
    def getLibraryName():
        return "pyspellchecker"

    @staticmethod
    def getLibraryURL():
        return "https://pyspellchecker.readthedocs.io/en/latest/"

    @staticmethod
    def isInstalled():
        return pyspellchecker != None

    @staticmethod
    def availableDictionaries():
        if PySpellcheckerDictionary.isInstalled():
            dictionaries = []
            files = glob.glob(os.path.join(pyspellchecker.__path__[0], "resources", "*.json.gz"))
            for file in files:
                dictionaries.append(os.path.basename(file)[:-8])
            return dictionaries
        return []

    @staticmethod
    def getDefaultDictionary(strict=False):
        if not PySpellcheckerDictionary.isInstalled():
            return None

        return pickDictionary(PySpellcheckerDictionary.availableDictionaries(),
                              [QLocale.system().name()], ["en"], strict)

    def _isMisspelled(self, word):
        return len(self._dict.unknown([word])) > 0

    def _getSuggestions(self, word):
        candidates = self._dict.candidates(word)
        if candidates and word in candidates:
            candidates.remove(word)
        return candidates

    def addWord(self, word):
        BasicDictionary.addWord(self, word)
        self._dict.word_frequency.add(word.lower())

    def removeWord(self, word):
        BasicDictionary.removeWord(self, word)
        self._dict.word_frequency.remove(word.lower())

class SymSpellDictionary(BasicDictionary):
    CUSTOM_COUNT = 1
    DISTANCE = 2

    def __init__(self, name):
        BasicDictionary.__init__(self, name)

        self._dict = symspellpy.SymSpell(self.DISTANCE)

        cachePath = self.getCachedDictionaryPath()
        try:
            if not self._dict.load_pickle(cachePath, False):
                raise Exception("Can't load cached dictionary. " +
                                "File might be corrupted or incompatible with installed symspellpy version")
        except:
            if pyspellchecker:
                path = os.path.join(pyspellchecker.__path__[0], "resources", "{}.json.gz".format(self.name))
                if os.path.exists(path):
                    with gzip.open(path, 'rt', encoding='utf-8') as f:
                        data = json.loads(f.read())
                        for key in data:
                            self._dict.create_dictionary_entry(key, data[key])
                    self._dict.save_pickle(cachePath, False)

        # Without any dictionary data, every word would be misspelled.
        if self._dict.word_count == 0:
            raise ValueError("No symspellpy dictionary data for '{}'".format(self.name))

        for word in self._customDict:
            self._dict.create_dictionary_entry(word, self.CUSTOM_COUNT)

    def getCachedDictionaryPath(self):
        return os.path.join(self.getResourcesPath(), "{}.sym".format(self.name))

    @staticmethod
    def getLibraryName():
        return "symspellpy"

    @staticmethod
    def getLibraryRequirement():
        return ">= " + SYMSPELLPY_MIN_VERSION

    @staticmethod
    def getLibraryURL():
        return "https://github.com/mammothb/symspellpy"

    @staticmethod
    def isInstalled():
        return symspellpy != None

    @classmethod
    def availableDictionaries(cls):
        if SymSpellDictionary.isInstalled():
            files = glob.glob(os.path.join(cls.getResourcesPath(), "*.sym"))
            dictionaries = []
            for file in files:
                dictionaries.append(os.path.basename(file)[:-4])
            for sp_dict in PySpellcheckerDictionary.availableDictionaries():
                if not sp_dict in dictionaries:
                    dictionaries.append(sp_dict)
            return dictionaries
        return []

    @staticmethod
    def getDefaultDictionary(strict=False):
        if not SymSpellDictionary.isInstalled():
            return None

        return pickDictionary(SymSpellDictionary.availableDictionaries(),
                              [QLocale.system().name()], ["en"], strict)

    def _isMisspelled(self, word):
        suggestions = self._dict.lookup(word.lower(), symspellpy.Verbosity.TOP)
        if len(suggestions) > 0 and suggestions[0].distance == 0:
            return False
        # Try the word as is, since a dictionary might have uppercase letter as part
        # of it's spelling ("I'm" or "January" for example)
        suggestions = self._dict.lookup(word, symspellpy.Verbosity.TOP)
        if len(suggestions) > 0 and suggestions[0].distance == 0:
            return False
        return True

    def _getSuggestions(self, word):
        upper = word.isupper()
        upper1 = word[0].isupper()
        suggestions = self._dict.lookup_compound(word, 2)
        suggestions.extend(self._dict.lookup(word, symspellpy.Verbosity.CLOSEST))
        candidates = []
        for sug in suggestions:
            if upper:
                term = sug.term.upper()
            elif upper1:
                term = sug.term[0].upper() + sug.term[1:]
            else:
                term = sug.term
            if sug.distance > 0 and not term in candidates:
                candidates.append(term)
        return candidates

    def addWord(self, word):
        BasicDictionary.addWord(self, word)
        self._dict.create_dictionary_entry(word.lower(), self.CUSTOM_COUNT)

    def removeWord(self, word):
        BasicDictionary.removeWord(self, word)
        # Since 6.3.8
        self._dict.delete_dictionary_entry(word.lower())

def get_languagetool_match_attribute(match, *names):
    # language_tool_python >= 3.0 uses snake_case names for the attributes of
    # a match (error_length), older releases use camelCase ones (errorLength).
    for name in names:
        try:
            return getattr(match, name)
        except AttributeError:
            pass
    raise AttributeError(names[0])

def get_languagetool_match_errorLength(match):
    if use_language_check:
        return match.errorlength
    else:
        return get_languagetool_match_attribute(match, "error_length", "errorLength")

def get_languagetool_match_ruleIssueType(match):
    if use_language_check:
        return match.locqualityissuetype
    else:
        return get_languagetool_match_attribute(match, "rule_issue_type", "ruleIssueType")

def get_languagetool_match_message(match):
    if use_language_check:
        return match.msg
    else:
        return match.message

class LanguageToolCache:

    # Whether the last check failed: a server that died would otherwise log a
    # warning for every paragraph.
    _failing = False

    def __init__(self, tool, text):
        self._length = len(text)
        self._matches = self._buildMatches(tool, text)

    def getMatches(self):
        return self._matches

    def _buildMatches(self, tool, text):
        matches = []

        # This runs while highlighting, where an exception would terminate
        # the application. If the server fails (or its API changed), only
        # skip the check of this text.
        try:
            for match in tool.check(text):
                start = match.offset
                end = start + get_languagetool_match_errorLength(match)

                basic_match = BasicMatch(start, end)
                basic_match.locqualityissuetype = get_languagetool_match_ruleIssueType(match)
                basic_match.replacements = match.replacements
                basic_match.msg = get_languagetool_match_message(match)

                matches.append(basic_match)
        except Exception as e:
            if LanguageToolCache._failing:
                LOGGER.debug("LanguageTool check failed: %s", e)
            else:
                LOGGER.warning("LanguageTool check failed: %s", e)
                LanguageToolCache._failing = True
            return []

        LanguageToolCache._failing = False
        return matches

    def update(self, tool, text):
        if len(text) != self._length:
            self._matches = self._buildMatches(tool, text)

def get_languagetool_languages(tool):
    if use_language_check:
        return languagetool.get_languages()
    else:
        return tool._get_languages()

def get_languagetool_locale_language():
    if use_language_check:
        return languagetool.get_locale_language()
    else:
        return languagetool.utils.get_locale_language()

class LanguageToolDictionary(BasicDictionary):

    _tool = None
    _toolFailed = False
    _javaInstalled = None

    def __init__(self, name):
        BasicDictionary.__init__(self, name)

        if not (self._lang and self._lang in get_languagetool_languages(self.getTool())):
            self._lang = self.getDefaultDictionary()

        self.tool = languagetool.LanguageTool(self._lang)
        self._cache = {}

    @staticmethod
    def getTool():
        # Creating the tool starts a LanguageTool server in Java (after
        # downloading LanguageTool the first time), so only try it once.
        if LanguageToolDictionary._tool is None and not LanguageToolDictionary._toolFailed:
            try:
                # The language of this tool does not matter, but the language of
                # the system locale might not be supported by LanguageTool.
                LanguageToolDictionary._tool = languagetool.LanguageTool("en-US")
            except Exception as e:
                LOGGER.warning("Could not start LanguageTool: %s", e)
                LanguageToolDictionary._toolFailed = True

        return LanguageToolDictionary._tool

    @staticmethod
    def getLibraryName():
        return "LanguageTool"

    @staticmethod
    def getLibraryURL():
        if use_language_check:
            return "https://pypi.org/project/language-check/"
        else:
            return "https://pypi.org/project/language-tool-python/"

    @staticmethod
    def isInstalled():
        if languagetool is None or LanguageToolDictionary._toolFailed:
            return False

        # LanguageTool needs Java. Does not start LanguageTool, which is slow
        # (see isStarted).
        if LanguageToolDictionary._javaInstalled is None:
            LanguageToolDictionary._javaInstalled = shutil.which("java") is not None

        return LanguageToolDictionary._javaInstalled

    @staticmethod
    def isStarted():
        return LanguageToolDictionary._tool is not None

    @staticmethod
    def start():
        LanguageToolDictionary.getTool()

    @staticmethod
    def availableDictionaries():
        if LanguageToolDictionary.isInstalled():
            tool = LanguageToolDictionary.getTool()
            if tool:
                languages = list(get_languagetool_languages(tool))
                languages.sort()
                return languages

        return []

    @staticmethod
    def getDefaultDictionary(strict=False):
        if not LanguageToolDictionary.isInstalled():
            return None

        return pickDictionary(LanguageToolDictionary.availableDictionaries(),
                              [get_languagetool_locale_language(), QLocale.system().name()],
                              ["en-US"], strict)

    def checkText(self, text):
        matches = []

        if len(text) == 0:
            return matches

        textId = hash(text)
        cacheEntry = None

        if not textId in self._cache:
            cacheEntry = LanguageToolCache(self.tool, text)

            self._cache[textId] = cacheEntry
        else:
            cacheEntry = self._cache[textId]
            cacheEntry.update(self.tool, text)

        for match in cacheEntry.getMatches():
            word = match.getWord(text)

            if not (match.locqualityissuetype == 'misspelling' and self.isCustomWord(word)):
                matches.append(match)

        return matches

    def _isMisspelled(self, word):
        if self.isCustomWord(word):
            return False

        for match in self.checkText(word):
            if match.locqualityissuetype == 'misspelling':
                return True

        return False

    def _getSuggestions(self, word):
        suggestions = []

        for match in self.checkText(word):
            suggestions += match.replacements

        return suggestions

    def findSuggestions(self, text, start, end):
        matches = []
        checked = self.checkText(text)

        if start == end:
            # Check for containing area:
            for match in checked:
                if (start >= match.start and start <= match.end):
                    matches.append(match)
        else:
            # Check for overlapping area:
            for match in checked:
                if (match.end > start and match.start < end):
                    matches.append(match)

        return matches


# Register the implementations in order of priority
Spellchecker.registerImplementation(EnchantDictionary)
Spellchecker.registerImplementation(SymSpellDictionary)
Spellchecker.registerImplementation(PySpellcheckerDictionary)
Spellchecker.registerImplementation(LanguageToolDictionary)
