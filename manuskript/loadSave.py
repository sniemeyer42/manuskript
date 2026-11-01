#!/usr/bin/env python
# --!-- coding: utf8 --!--

# The loadSave file calls the proper functions to load and save file
# trying to detect the proper file format if it comes from an older version
import os
import zipfile

import manuskript.load_save.version_0 as v0
import manuskript.load_save.version_1 as v1

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
