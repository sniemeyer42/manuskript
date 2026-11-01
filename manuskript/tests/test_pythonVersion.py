#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the Python version check (#1421)."""

import subprocess
import sys

import pytest

from manuskript.functions import appPath


def runWithVersion(version):
    code = ("import sys; sys.version_info = {!r}; "
            "import manuskript; print('imported')").format(version)
    return subprocess.run([sys.executable, "-c", code], cwd=appPath(),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=60)


@pytest.mark.parametrize("version", [(3, 5, 2, "final", 0), (3, 9, 18, "final", 0)])
def test_tooOldPython(version):
    """An old Python gets a clear message instead of a SyntaxError."""
    result = runWithVersion(version)
    assert result.returncode == 1
    assert "requires Python 3.10" in result.stderr
    assert "imported" not in result.stdout


def test_supportedPython():
    result = runWithVersion((3, 10, 0, "final", 0))
    assert result.returncode == 0
    assert "imported" in result.stdout
