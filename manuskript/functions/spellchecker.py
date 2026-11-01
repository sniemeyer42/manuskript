#!/usr/bin/env python
# --!-- coding: utf8 --!--

import os, gzip, json, glob, re, unicodedata, zlib
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
        """Returns the dictionaries of every installed library."""
        dictionaries = OrderedDict()
        for impl in Spellchecker.implementations:
            if impl.isInstalled():
                dictionaries[impl.getLibraryName()] = impl.availableDictionaries()
        return dictionaries

    @staticmethod
    def normalizeDictName(lib, dictionary):
        return "{}:{}".format(lib, dictionary)

    @staticmethod
    def getDefaultDictionary():
        # A dictionary in the language of the system is better than one in
        # another language from a library of higher priority.
        for strict in [True, False]:
            for impl in Spellchecker.implementations:
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

# Elisions, by language of the dictionary (see dictionaryLanguage): words
# that drop their last vowel and are joined to the next word by an apostrophe
# (French l’homme, qu’il, jusqu’à). Word lists such as the dictionaries of
# pyspellchecker know few of these forms.
ELISIONS = {
    # French
    "fr": {"c", "ç", "d", "j", "l", "m", "n", "s", "t",
           "qu", "jusqu", "lorsqu", "puisqu", "quoiqu", "quelqu"},
    # Italian (dell’anno, c’è, quest’anno, senz’altro). Not un, buon and
    # nessun: they are elided only before a feminine word (un’amica, but
    # un amico). The word lists know most of these forms, not all of them
    # (un’estate).
    "it": {"l", "dell", "all", "dall", "nell", "sull", "coll",
           "c", "ch", "d", "m", "n", "s", "t", "v",
           "quest", "quell", "bell", "sant", "tutt", "pover",
           "anch", "com", "cos", "dov", "quand", "quant", "senz", "nient",
           "mezz"},
    # Catalan (l’home, d’aigua, m’agrada)
    "ca": {"d", "l", "m", "n", "s", "t"},
}

# Words after an elision that need an accent there, by language: the word
# without its accent (lower case), the word with it, and the elisions after
# which only the word with the accent is right: French jusqu’à, d’où and
# jusqu’où, not jusqu’a, d’ou and jusqu’ou; Italian c’è, dov’è and cos’è, not
# c’e, dov’e and cos’e. Without their accent these are words too (French a
# and ou, Italian e), which would be accepted after any elision. Not after
# elisions where they can be right: French qu’a and lorsqu’a (ce qu’a dit
# Pierre, lorsqu’a eu lieu la fête), d’a (d’A à Z), Italian tutt’e (tutt’e
# due) and dell’e (the letter e).
ELISION_ACCENTS = {
    "fr": {"a": ("à", {"jusqu"}),
           "ou": ("où", {"d", "jusqu"})},
    "it": {"e": ("è", {"c", "ch", "m", "n", "s", "t", "v",
                       "com", "cos", "dov", "quand", "quant"})},
}

def dictionaryLanguage(name):
    """Returns the language of a dictionary name: fr for fr, fr_FR or fr-FR."""
    return re.split(r"[-_@.]", name or "")[0].lower()

# Words are only elided before a vowel or h (l’homme, but le chat)
ELISION_FOLLOWERS = set("aeiouyhæœ")

def canFollowElision(word):
    """
    Returns True if word starts with a vowel (with or without accents), y or
    h, or with a digit (Italian dell’800).
    """
    letter = unicodedata.normalize("NFD", word[:1])[:1].lower()
    return letter in ELISION_FOLLOWERS or letter.isdigit()

# Based on http://john.nachtimwald.com/2009/08/22/qplaintextedit-with-in-line-spell-check/
# Letters, digits and apostrophes, not preceded or followed by any of them. A
# word at the very end of the text is not matched, so that a word is not
# checked while it is being typed (see BasicHighlighter.highlightBlockAfter).
WORDS = re.compile(r"(?<![^\W_]|['\u2019])((?:[^\W_]|['\u2019])+)(?=[^\w'\u2019]|_)")

class BasicDictionary:
    # Whether a word after an elision (l’homme) is checked apart from it,
    # see splitElision
    SPLIT_ELISIONS = True

    def __init__(self, name):
        self._lang = name
        if not self._lang:
            self._lang = self.getDefaultDictionary()

        # The subclasses add the custom words to their dictionary
        self._customDict = set()
        customPath = self.getCustomDictionaryPath()
        try:
            with gzip.open(customPath, 'rt', encoding='utf-8') as f:
                words = json.loads(f.read())
            if not isinstance(words, list) or \
                    not all(isinstance(w, str) for w in words):
                raise ValueError("not a list of words")
            self._customDict = set(words)

        except FileNotFoundError:
            try:
                self._saveCustomDict()
            except OSError as e:
                LOGGER.warning("Cannot create the custom dictionary %s: %s", customPath, e)

        except (OSError, EOFError, ValueError, zlib.error) as e:
            # Damaged file: it is moved aside, so that the words can be recovered by hand,
            # and the dictionary starts without custom words.
            backup = customPath + ".damaged"
            n = 1
            while os.path.exists(backup):
                n += 1
                backup = "{}.damaged.{}".format(customPath, n)
            try:
                os.replace(customPath, backup)
                LOGGER.error("Cannot read the custom dictionary %s (%s), it has been moved "
                             "to %s.", customPath, e, backup)
            except OSError as e2:
                LOGGER.error("Cannot read the custom dictionary %s: %s (and cannot move it "
                             "aside: %s)", customPath, e, e2)

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
        dictionary only knows with an ASCII apostrophe (isn’t), without a
        clitic (geht's) or without an elision (l’homme).
        """
        if not self._isWordMisspelled(word):
            return False

        # The word after an elision is checked the same way (qu’aujourd’hui),
        # and must have its accent (jusqu’à, not jusqu’a)
        elision = self.splitElision(word)
        if elision is None:
            return True
        prefix, rest = elision
        return (self.missingAccent(prefix, rest) is not None
                or self._isWordMisspelled(rest))

    def _isWordMisspelled(self, word):
        """isWordMisspelled, without looking for an elision."""
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

    def splitElision(self, word):
        """
        Returns (elision, rest) if word starts with an elision of the language
        of the dictionary, followed by a word that can be elided before
        (l’homme -> l’, homme), else None.
        """
        if not self.SPLIT_ELISIONS:
            return None

        parts = re.split("([" + APOSTROPHES + "])", word, maxsplit=1)
        if len(parts) == 3:
            prefix, apostrophe, rest = parts
            if (prefix.lower() in ELISIONS.get(dictionaryLanguage(self.name), ())
                    and canFollowElision(rest)):
                return prefix + apostrophe, rest
        return None

    def missingAccent(self, elision, rest):
        """
        Returns rest with the accent it needs after elision (see
        ELISION_ACCENTS), if it is missing: jusqu’, a -> à. Else None.
        """
        accents = ELISION_ACCENTS.get(dictionaryLanguage(self.name), {})
        accented, elisions = accents.get(rest.lower(), (None, ()))
        if elision[:-1].lower() not in elisions:
            return None
        # In the case of rest: JUSQU’A -> JUSQU’À, Jusqu’a -> Jusqu’à
        return "".join(a.upper() if r.isupper() else a
                       for r, a in zip(rest, accented))

    def getWordSuggestions(self, word):
        """
        Like getSuggestions, but keeps an elision: l’hommme -> l’homme.
        """
        elision = self.splitElision(word)
        if elision is None:
            return self.getSuggestions(word)

        prefix, rest = elision
        accented = self.missingAccent(prefix, rest)
        if accented is not None:
            return [prefix + accented]

        suggestions = []
        for s in self.getSuggestions(rest) or []:
            # With the apostrophe that was typed: qu’aujourd’hiu ->
            # qu’aujourd’hui, although the word list has aujourd'hui
            if "\u2019" in word and "'" not in word:
                s = s.replace("'", "\u2019")
            if canFollowElision(s) and prefix + s not in suggestions:
                suggestions.append(prefix + s)
        return suggestions

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
                match.replacements = self.getWordSuggestions(word)

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
        # Through a temporary file: an interrupted write must not destroy the custom
        # words. Imported here, a module-level import would be circular.
        from manuskript.load_save.version_1 import writeFile
        content = json.dumps(sorted(self._customDict))
        writeFile(self.getCustomDictionaryPath(), gzip.compress(content.encode("utf-8")))


class EnchantDictionary(BasicDictionary):
    # A word with an elision is checked as a whole, as before. Hunspell
    # dictionaries know the elided forms of their language, and some reject
    # wrong ones that a check of the word after the elision would accept
    # (Italian un’amico, l’libro; l’héros in old French dictionaries, current
    # ones accept it).
    SPLIT_ELISIONS = False

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


# Register the implementations in order of priority
Spellchecker.registerImplementation(EnchantDictionary)
Spellchecker.registerImplementation(SymSpellDictionary)
Spellchecker.registerImplementation(PySpellcheckerDictionary)
