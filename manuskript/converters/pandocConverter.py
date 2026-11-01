#!/usr/bin/env python
# --!-- coding: utf8 --!--
import os
import shutil
import subprocess

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtWidgets import qApp
from PyQt5.QtGui import QCursor

from manuskript.converters import abstractConverter

import logging
LOGGER = logging.getLogger(__name__)

class pandocConverter(abstractConverter):

    name = "pandoc"
    cmd = "pandoc"

    @classmethod
    def isValid(self):
        if self.path() != None:
            return 2

        customPath = self.customPath()
        if customPath and os.path.isfile(customPath) and \
                os.access(customPath, os.X_OK):
            return 1
        else:
            return 0

    @classmethod
    def customPath(self):
        # Path set in the exporters manager for the pandoc exporter
        # (manuskript.exporter.pandoc.pandocExporter.name is "Pandoc")
        settings = QSettings()
        return settings.value("Exporters/Pandoc_customPath", "")

    @classmethod
    def path(self):
        return shutil.which(self.cmd)

    @classmethod
    def convert(self, src, _from="markdown", to="html", args=None, outputfile=None):
        if not self.isValid():
            LOGGER.error("pandocConverter is called but not valid.")
            return None

        cmd = [self.runCmd()]

        cmd += ["--from={}".format(_from)]
        cmd += ["--to={}".format(to)]

        if args:
            cmd += args

        if outputfile:
            cmd.append("--output={}".format(outputfile))

        qApp.setOverrideCursor(QCursor(Qt.WaitCursor))

        try:
            p = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except OSError as e:
            qApp.restoreOverrideCursor()
            LOGGER.error("Could not run pandoc: %s", e)
            return None

        if not type(src) == bytes:
            src = src.encode("utf-8")  # assumes utf-8

        stdout, stderr = p.communicate(src)

        qApp.restoreOverrideCursor()

        if stderr or p.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            if p.returncode != 0:
                # No message box: this also runs while loading a project
                LOGGER.error("pandoc returned %d: %s", p.returncode, err)
                return None
            LOGGER.warning(err)

        return stdout.decode("utf-8")

    @classmethod
    def runCmd(self):
        if self.isValid() == 2:
            return self.cmd
        elif self.isValid() == 1:
            return self.customPath()
