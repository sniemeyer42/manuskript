#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Fixtures for exporters."""

import pytest


@pytest.fixture
def exporterSettingsPath(monkeypatch, tmp_path):
    """Keeps exporter.ini out of the user's data folder."""
    from manuskript.ui.exporters.manuskript.plainTextSettings import exporterSettings
    path = str(tmp_path / "exporter.ini")
    monkeypatch.setattr(exporterSettings, "getSettingsPath", lambda self: path)
    return path
