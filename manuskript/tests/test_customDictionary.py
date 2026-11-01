#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""The custom dictionary of the spellchecker backends: the words added by the user,
saved in <language>.json.gz."""

import gzip
import json
import os

import pytest

from manuskript.functions import spellchecker as S
from manuskript.functions.spellchecker import BasicDictionary


class FakeDictionary(BasicDictionary):
    """Like the real backends, creates its dictionary after BasicDictionary.__init__ has
    loaded the custom words, and adds them to it."""

    def __init__(self, name):
        BasicDictionary.__init__(self, name)
        self._dict = {"the", "dog"} | self._customDict

    @staticmethod
    def getLibraryName():
        return "fake"

    @staticmethod
    def getDefaultDictionary(strict=False):
        return "en"

    def _isMisspelled(self, word):
        return word.lower() not in self._dict


@pytest.fixture
def path(monkeypatch, tmp_path):
    """Keeps the custom dictionaries out of the user's data folder. Returns the path of
    the custom dictionary of FakeDictionary("en")."""
    monkeypatch.setattr(S, "writablePath", lambda: str(tmp_path / "data"))
    monkeypatch.setattr(S.Spellchecker, "dictionaries", {})
    return str(tmp_path / "data" / "resources" / "dictionaries" / "fake" / "en.json.gz")


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(content)


def read(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return f.read()


def readBytes(path):
    with open(path, "rb") as f:
        return f.read()


def test_new_custom_dictionary(path):
    d = FakeDictionary("en")
    assert json.loads(read(path)) == []

    d.addWord("Frodo")
    assert not d.isWordMisspelled("Frodo")
    assert json.loads(read(path)) == ["frodo"]
    assert os.listdir(os.path.dirname(path)) == ["en.json.gz"]  # no temporary file left

    d = FakeDictionary("en")
    assert not d.isWordMisspelled("Frodo")
    d.removeWord("Frodo")
    assert json.loads(read(path)) == []


def test_loading_does_not_rewrite_custom_dictionary(path, monkeypatch):
    write(path, '[ "frodo", "samwise" ]')
    saved = []
    monkeypatch.setattr(FakeDictionary, "_saveCustomDict",
                        lambda self: saved.append(self) or BasicDictionary._saveCustomDict(self))

    d = FakeDictionary("en")

    assert saved == []
    assert read(path) == '[ "frodo", "samwise" ]'
    assert d._customDict == {"frodo", "samwise"}
    assert not d.isWordMisspelled("Samwise")


def gzipBytes(content):
    return gzip.compress(content.encode("utf-8"))


@pytest.mark.parametrize("damaged", [
    gzipBytes('["frodo", "samwise", "gand'),  # truncated JSON
    gzipBytes('["frodo", "samwise"]')[:20],  # truncated file
    gzipBytes('["frodo", "samwise"]')[:12] + b"\xff" * 20,  # damaged data
    b'["frodo", "samwise"]',  # not compressed
    gzipBytes('["frodo"]')[:-8] + b"\0" * 8,  # wrong checksum
    gzipBytes('{"frodo": 1}'),
    gzipBytes('[["frodo"]]'),
    gzipBytes('"frodo"'),
    b"\xff" * 4 + gzipBytes('["frodo"]'),
    gzip.compress(b'["fr\xffdo"]'),
], ids=["truncated JSON", "truncated file", "damaged data", "not compressed",
        "wrong checksum", "not a list", "not words", "a string", "garbage", "encoding"])
def test_damaged_custom_dictionary_is_kept(path, damaged):
    os.makedirs(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(damaged)

    d = FakeDictionary("en")  # does not raise

    # The dictionary starts without custom words, the damaged file is kept aside
    assert d._customDict == set()
    assert not os.path.exists(path)
    assert readBytes(path + ".damaged") == damaged

    d.addWord("Gandalf")
    assert json.loads(read(path)) == ["gandalf"]
    assert readBytes(path + ".damaged") == damaged
    assert not FakeDictionary("en").isWordMisspelled("Gandalf")

    # A second damaged file does not replace the first one
    with open(path, "wb") as f:
        f.write(b"again")
    FakeDictionary("en")
    assert readBytes(path + ".damaged") == damaged
    assert readBytes(path + ".damaged.2") == b"again"


def test_custom_dictionary_is_saved_atomically(path, monkeypatch):
    """If the disk is full, the previous version of the file is kept."""
    write(path, '["frodo"]')
    d = FakeDictionary("en")
    realOpen = open

    class FullDisk:
        def __init__(self, f):
            self._f = f

        def write(self, data):
            raise OSError(28, "No space left on device")

        def __getattr__(self, name):
            return getattr(self._f, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self._f.close()

    def fullDiskOpen(file, mode="r", *args, **kwargs):
        f = realOpen(file, mode, *args, **kwargs)
        if "w" in mode and os.path.dirname(str(file)) == os.path.dirname(path):
            return FullDisk(f)
        return f

    monkeypatch.setattr("builtins.open", fullDiskOpen)
    with pytest.raises(OSError):
        d.addWord("Samwise")
    monkeypatch.undo()

    assert json.loads(read(path)) == ["frodo"]
    assert os.listdir(os.path.dirname(path)) == ["en.json.gz"]


@pytest.mark.parametrize("module, lib", [("spellchecker", "pyspellchecker"),
                                         ("symspellpy", "symspellpy")])
def test_real_backends(path, module, lib):
    pytest.importorskip(module)
    if not getattr(S, "pyspellchecker" if lib == "pyspellchecker" else lib):
        pytest.skip("{} is not usable".format(lib))
    customPath = path.replace(os.sep + "fake" + os.sep, os.sep + lib + os.sep)
    write(customPath, '[ "frodoxyz" ]')

    d = S.Spellchecker.getDictionary("{}:en".format(lib))

    assert d is not None
    assert d.isWordMisspelled("Gandalfxyz")
    assert not d.isWordMisspelled("Frodoxyz")
    assert read(customPath) == '[ "frodoxyz" ]'  # not rewritten

    d.addWord("Gandalfxyz")
    assert not d.isWordMisspelled("Gandalfxyz")
    assert sorted(json.loads(read(customPath))) == ["frodoxyz", "gandalfxyz"]
