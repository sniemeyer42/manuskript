#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Fixtures for importers."""

import pytest


@pytest.fixture
def runImporter(MWEmptyProject):
    """Returns a function running the given importer class on a file (or a
    string with fromString) and returning the created items."""
    from manuskript.ui.importers.generalSettings import generalSettings

    def run(importerClass, filePath="", fromString=None, setup=None):
        importer = importerClass()
        settingsWidget = importer.settingsWidget(generalSettings())
        if setup:
            setup(importer)
        parent = MWEmptyProject.mdlOutline.rootItem
        if fromString is None:
            return importer.startImport(filePath, parent, settingsWidget)
        return importer.startImport(filePath, parent, settingsWidget,
                                    fromString=fromString)
    return run
