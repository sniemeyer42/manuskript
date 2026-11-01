#!/usr/bin/env python
# --!-- coding: utf8 --!--

# The loadSave file calls the proper functions to load and save file
# trying to detect the proper file format if it comes from an older version
import os
import zipfile

import manuskript.load_save.version_0 as v0
import manuskript.load_save.version_1 as v1
from manuskript.functions import mainWindow

import logging
LOGGER = logging.getLogger(__name__)

def saveProject(version=None):

    # While debugging, we don't save the project
    # return

    if version == 0:
        return v0.saveProject()
    else:
        return v1.saveProject()


def clearSaveCache():
    """The project is not saved where it was loaded from (new project, "Save as...")."""
    v1.cache = {}
    v1.freshTarget = True
    v1.unreadable = {}


def saveCacheState():
    """Returns what the save code knows about the current project folder, so that
    restoreSaveCache() can bring it back (e.g. after a failed "Save as..."): the save
    cache, and the paths the characters and outline items were last saved to, which
    saveProject() updates as it goes (it detects renamed and moved items with them)."""
    mw = mainWindow()
    paths = [(c, "lastPath", c.lastPath) for c in mw.mdlCharacter.characters]

    def addItems(item):
        for child in item.children():
            paths.append((child, "_lastPath", child._lastPath))
            addItems(child)

    addItems(mw.mdlOutline.rootItem)
    return dict(v1.cache), v1.freshTarget, dict(v1.unreadable), paths


def restoreSaveCache(state):
    cache, freshTarget, unreadable, paths = state
    v1.cache = dict(cache)
    v1.freshTarget = freshTarget
    v1.unreadable = dict(unreadable)
    for item, attribute, path in paths:
        setattr(item, attribute, path)


def loadProject(project):

    # Detect version
    isZip = False
    version = 0
    errors = []

    # Is it a zip?
    try:
        zf = zipfile.ZipFile(project)
        isZip = True
    except (zipfile.BadZipFile, OSError):
        isZip = False

    # Does it have a VERSION in zip root?
    # Was used in transition between 0.2.0 and 0.3.0
    # So VERSION part can be deleted for manuskript 0.4.0
    if isZip and "VERSION" in zf.namelist():
        s = zf.read("VERSION")

        if s.isdigit():
            version = int(s)
        else:
            errors.append(project)
            errors.append("VERSION")

    # Does it have a MANUSKRIPT in zip root?
    elif isZip and "MANUSKRIPT" in zf.namelist():
        s = zf.read("MANUSKRIPT")
        
        if s.isdigit():
            version = int(s)
        else:
            errors.append(project)
            errors.append("MANUSKRIPT")

    # Zip but no VERSION/MANUSKRIPT: oldest file format
    elif isZip:
        version = 0

    # Not a zip
    else:
        # A damaged file (e.g. a truncated zip) must not crash the app
        try:
            with open(project, 'rt', encoding="utf-8") as f:
                s = f.read().strip()
        except (UnicodeDecodeError, OSError) as e:
            LOGGER.error("Cannot read project file %s: %s", project, e)
            s = ""

        if s.isdigit():
            version = int(s)
        else:
            errors.append(project)

    LOGGER.info("Loading: %s", project)
    LOGGER.info("Detected file format version: {}. Zip: {}.".format(version, isZip))

    if len(errors) > 0:
        return errors

    if version == 0:
        return v0.loadProject(project)
    else:
        return v1.loadProject(project, zip=isZip)
