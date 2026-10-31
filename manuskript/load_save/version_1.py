#!/usr/bin/env python
# --!-- coding: utf8 --!--

# Version 1 of file saving format.
# Aims at providing a plain-text way of saving a project
# (except for some elements), allowing collaborative work
# versioning and third-party editing.

import errno
import io
import os
import re
import shutil
import string
import zipfile
from collections import OrderedDict

from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtGui import QColor, QStandardItem
from PyQt5.QtWidgets import QListWidgetItem

from manuskript import settings
from manuskript.enums import Character, World, Plot, PlotStep, Outline
from manuskript.functions import mainWindow, iconColor, iconFromColorString
from manuskript.converters import HTML2PlainText
from lxml import etree as ET

from manuskript.load_save.version_0 import loadFilesFromZip
from manuskript.models.characterModel import CharacterInfo
from manuskript.models import outlineItem
from manuskript.ui.listDialog import ListDialog

import logging
LOGGER = logging.getLogger(__name__)
_parser = ET.XMLParser(huge_tree=True)

try:
    import zlib  # Used with zipfile for compression

    compression = zipfile.ZIP_DEFLATED
except:
    compression = zipfile.ZIP_STORED

cache = {}

# True when the cache does not describe the project folder on disk (new project, "Save as...",
# project loaded from a single file): the next save in folder mode writes the whole project,
# after removing what an older project in that folder might have left. A project loaded from
# its folder is never a fresh target, even if nothing could be loaded from it.
freshTarget = True

# Files and folders of the project folder that could not be read when the project was loaded
# (path relative to the project folder: reason). Their content is not in the project, so
# saveProject() never overwrites or removes them.
unreadable = {}

# Files that saveProject() writes at the root of a project folder (besides the
# "outline" and "characters" folders).
projectFiles = ["MANUSKRIPT", "infos.txt", "summary.txt", "labels.txt", "status.txt",
                "settings.txt", "plots.xml", "world.opml", "revisions.xml"]


characterMap = OrderedDict([
    (Character.name, "Name"),
    (Character.ID,   "ID"),
    (Character.importance, "Importance"),
    (Character.pov, "POV"),
    (Character.motivation, "Motivation"),
    (Character.goal, "Goal"),
    (Character.conflict, "Conflict"),
    (Character.epiphany, "Epiphany"),
    (Character.summarySentence, "Phrase Summary"),
    (Character.summaryPara, "Paragraph Summary"),
    (Character.summaryFull, "Full Summary"),
    (Character.notes, "Notes")
])


def formatMetaData(name, value, tabLength=10):

    # Multiline formatting
    if len(value.split("\n")) > 1:
        value = "\n".join([" " * (tabLength + 1) + l for l in value.split("\n")])[tabLength + 1:]

    # Avoid empty description (don't know how much MMD loves that)
    if name == "":
        name = "None"

    # Escapes ":" in name
    name = name.replace(":", "_.._")

    return "{name}:{spaces}{value}\n".format(
        name=name,
        spaces=" " * (tabLength - len(name)),
        value=value
    )


# File names are made from titles. They are truncated to stay below the file system
# limit of 255 bytes per file name, and to keep paths short (Windows limits paths to
# 260 characters, see #313). They stay unique because they start with the item's row
# (or the character's ID).
maxSlugLength = 64


def slugify(name):
    """
    A basic slug function, that escapes all spaces to "_" and all non letters/digits to "-".
    @param name: name to slugify (str)
    @return: str
    """
    valid = string.ascii_letters + string.digits
    newName = ""
    for c in name:
        if c in valid:
            newName += c
        elif c in string.whitespace:
            newName += "_"
        else:
            newName += "-"
    return newName


def writeFile(filename, content, sync=False):
    """
    Writes content (str or bytes) to filename, through a temporary file that replaces it only
    once it has been written completely: if writing fails (disk full, quota...), the previous
    version of the file is left untouched, and no truncated file is left behind.
    A symbolic link is written through (its target is replaced), and the mode of an existing
    file is kept. A file that is not writable is not replaced.
    @param sync: if True, the new content is flushed to the disk before it replaces the file.
    @raise OSError: if the file cannot be written.
    """
    filename = os.path.realpath(filename)
    if os.path.exists(filename) and not os.access(filename, os.W_OK):
        raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), filename)

    # Hidden, so that a temporary file left by a crash is not loaded as part of the project
    tmp = os.path.join(os.path.dirname(filename), "." + os.path.basename(filename) + ".tmp")
    try:
        if type(content) == bytes:
            f = open(tmp, "wb")
        else:
            f = open(tmp, "wt", encoding="utf8", newline="\n")
        with f:
            f.write(content)
            if sync:
                f.flush()
                os.fsync(f.fileno())
        if os.path.exists(filename):
            # Best effort: some file systems do not support chmod (network or FUSE mounts...)
            try:
                shutil.copymode(filename, tmp)
            except OSError as e:
                LOGGER.debug("Cannot keep the mode of %s: %s", filename, e)
        os.replace(tmp, filename)

    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def isUnreadable(path):
    """
    Returns True if path (relative to the project folder) is, is in, or contains a file or
    folder that could not be read when the project was loaded.
    """
    return any(path == u or path.startswith(u + os.sep) or u.startswith(path + os.sep)
               for u in unreadable)


def saveProject(zip=None):
    """
    Saves the project. If zip is False, the project is saved as a multitude of plain-text files for the most parts
    and some XML or zip? for settings and stuff.
    If zip is True, everything is saved as a single zipped file. Easier to carry around, but does not allow
    collaborative work, versioning, or third-party editing.
    @param zip: if True, saves as a single file. If False, saves as plain-text. If None, tries to determine based on
    settings.
    @return: True if successful, False otherwise.
    """
    if zip == None:
        zip = settings.saveToZip

    LOGGER.info("Saving to: %s", "zip" if zip else "folder")

    # List of files to be written
    files = []
    # List of files to be removed
    removes = []
    # List of files to be moved
    moves = []

    # MainWindow interaction things.
    mw = mainWindow()
    project = mw.currentProject

    # Sanity check (see PR-583): make sure we actually have a current project.
    if project == None:
        LOGGER.error("Cannot save project because there is no current project in the UI.")
        return False

    # File format version
    files.append(("MANUSKRIPT", "1"))

    # General infos (book and author)
    # Saved in plain text, in infos.txt

    path = "infos.txt"
    content = ""
    for name, col in [
            ("Title", 0),
            ("Subtitle", 1),
            ("Serie", 2),
            ("Volume", 3),
            ("Genre", 4),
            ("License", 5),
            ("Author", 6),
            ("Email", 7),
            ]:
        item = mw.mdlFlatData.item(0, col)
        if item:
            val = item.text().strip()
        else:
            val = ""

        if val:
            content += "{name}:{spaces}{value}\n".format(
                name=name,
                spaces=" " * (15 - len(name)),
                value=val
            )
    files.append((path, content))

    ####################################################################################################################
    # Summary
    # In plain text, in summary.txt

    path = "summary.txt"
    content = ""
    for name, col in [
            ("Situation", 0),
            ("Sentence", 1),
            ("Paragraph", 2),
            ("Page", 3),
            ("Full", 4),
            ]:
        item = mw.mdlFlatData.item(1, col)
        if item:
            val = item.text().strip()
        else:
            val = ""

        if val:
            content += formatMetaData(name, val, 12)

    files.append((path, content))

    ####################################################################################################################
    # Label & Status
    # In plain text

    for mdl, path in [
        (mw.mdlStatus, "status.txt"),
        (mw.mdlLabels, "labels.txt")
    ]:

        content = ""

        # We skip the first row, which is empty and transparent
        for i in range(1, mdl.rowCount()):
            color = ""
            if mdl.data(mdl.index(i, 0), Qt.DecorationRole) != None:
                color = iconColor(mdl.data(mdl.index(i, 0), Qt.DecorationRole)).name(QColor.HexRgb)
                color = color if color != "#ff000000" else "#00000000"

            text = mdl.data(mdl.index(i, 0))

            if text:
                content += "{name}{color}\n".format(
                    name=text,
                    color="" if color == "" else ":" + " " * (20 - len(text)) + color
                )

        files.append((path, content))

    ####################################################################################################################
    # Characters
    # In a character folder

    path = os.path.join("characters", "{name}.txt")
    mdl = mw.mdlCharacter

    # Review characters
    for c in mdl.characters:

        # Generates file's content
        content = ""
        for m in characterMap:
            val = mdl.data(c.index(m.value)).strip()
            if val:
                content += formatMetaData(characterMap[m], val, 20)

        # Character's color:
        content += formatMetaData("Color", c.color().name(QColor.HexRgb), 20)

        # Character's infos
        for info in c.infos:
            content += formatMetaData(info.description, info.value, 20)

        # generate file's path
        cpath = path.format(name="{ID}-{slugName}".format(
            ID=c.ID(),
            slugName=slugify(c.name())[:maxSlugLength]
        ))

        # Has the character been renamed?
        if c.lastPath and cpath != c.lastPath:
            moves.append((c.lastPath, cpath))

        # Update character's path
        c.lastPath = cpath

        files.append((cpath, content))

    ####################################################################################################################
    # Texts
    # In an outline folder

    mdl = mw.mdlOutline

    # Go through the tree
    f, m, r = exportOutlineItem(mdl.rootItem)
    files += f
    moves += m
    removes += r

    # Writes revisions (if asked for)
    if settings.revisions["keep"]:
        files.append(("revisions.xml", mdl.saveToXML()))

    ####################################################################################################################
    # World
    # Either in an XML file, or in lots of plain texts?
    # More probably text, since there might be writing done in third-party.

    path = "world.opml"
    mdl = mw.mdlWorld

    root = ET.Element("opml")
    root.attrib["version"] = "1.0"
    body = ET.SubElement(root, "body")
    addWorldItem(body, mdl)
    content = ET.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    files.append((path, content))

    ####################################################################################################################
    # Plots (mw.mdlPlots)
    # Either in XML or lots of plain texts?
    # More probably XML since there is not really a lot if writing to do (third-party)

    path = "plots.xml"
    mdl = mw.mdlPlots

    root = ET.Element("root")
    addPlotItem(root, mdl)
    content = ET.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    files.append((path, content))

    ####################################################################################################################
    # Settings
    # Saved in readable text (json) for easier versioning. But they mustn't be shared, it seems.
    # Maybe include them only if zipped?
    # Well, for now, we keep them here...

    files.append(("settings.txt", settings.save(protocol=0)))

    # We check if the file exist and we have write access. If the file does
    # not exist, we check the parent folder, because it might be a new project.
    if os.path.exists(project) and not os.access(project, os.W_OK) or \
       not os.path.exists(project) and not os.access(os.path.dirname(project), os.W_OK):
        LOGGER.error("You don't have write access to save this project there.")
        return False

    ####################################################################################################################
    # Save to zip

    if zip:
        # project = os.path.join(
        #     os.path.dirname(project),
        #     "_" + os.path.basename(project)
        # )

        # The project file is replaced only once the new version is complete (and on disk):
        # an interrupted save (disk full, removed drive...) must not destroy the previous
        # version of the project, which is the only copy.
        try:
            data = io.BytesIO()
            with zipfile.ZipFile(data, mode="w") as zf:
                for filename, content in files:
                    zf.writestr(filename, content, compress_type=compression)

            writeFile(project, data.getvalue(), sync=True)

        except OSError as e:
            LOGGER.error("Cannot save project %s: %s", project, e)
            return False

        return True

    ####################################################################################################################
    # Save to plain text

    else:
        filesWithPermissionErrors = list()

        # Project path
        dir = os.path.dirname(project)

        # Folder containing file: name of the project file (without .msk extension)
        folder = os.path.splitext(os.path.basename(project))[0]

        # Debug
        LOGGER.debug("Saving to folder %s", folder)

        # If the project has not been loaded from this folder (new project, "Save as..."),
        # we remove what an older project in that folder might have left, just to be sure.
        # Only if the folder is a Manuskript project, and only the files Manuskript writes:
        # never wipe a folder of the user that happens to have the project's name.
        global freshTarget
        if freshTarget:
            target = os.path.join(dir, folder)
            try:
                # Hidden files (.DS_Store...) do not count
                notEmpty = os.path.isdir(target) and \
                    [f for f in os.listdir(target) if f[:1] != "."]
            except OSError:
                notEmpty = True
            if notEmpty:
                if not os.path.isfile(os.path.join(target, "MANUSKRIPT")):
                    LOGGER.error("Cannot save project: the folder %s already exists and is not "
                                 "a Manuskript project.", target)
                    dlg = ListDialog(mw)
                    dlg.setModal(True)
                    dlg.setWindowTitle(dlg.tr("Project not saved"))
                    dlg.label.setText(dlg.tr(
                        "The project is saved in a folder named like the project file. This folder "
                        "already exists and is not a Manuskript project, so the project cannot be "
                        "saved there. Use \"Save as...\" to save it under another name."))
                    QListWidgetItem(target, dlg.listWidget)
                    dlg.open()
                    return False

                for sub in ["outline", "characters"]:
                    if os.path.isdir(os.path.join(target, sub)):
                        shutil.rmtree(os.path.join(target, sub))
                for f in projectFiles:
                    if os.path.isfile(os.path.join(target, f)):
                        os.remove(os.path.join(target, f))

            # From now on, the cache describes what is in the folder.
            freshTarget = False

        # Renamed / moved items are NOT moved on disk. Their new path is not in the cache,
        # so they are written below, and their old file is then removed as a phantom.
        # Moving files in place one by one is not safe: an item's new path can be the old
        # path of another item that has not been moved yet (its file gets overwritten,
        # see #1320), the destination folder may not exist yet (#1306), and renaming the
        # cache keys by substring corrupted the cache (#1216, #761).
        for old, new in moves:
            LOGGER.debug("* %s has been renamed/moved to %s, it will be rewritten", old, new)

        # Writing files
        for path, content in files:
            filename = os.path.join(dir, folder, path)

            # A file that could not be read when the project was loaded is not overwritten
            # (it is not in the cache, but its content is not in the project either).
            if isUnreadable(path):
                LOGGER.error("Cannot write file %s: it could not be read when the project was "
                             "loaded.", filename)
                filesWithPermissionErrors.append("{} ({})".format(
                    filename, unreadable.get(path, "could not be read")))
                continue

            # Check if content is in cache, and write if necessary
            # (also if the file has disappeared from disk since it was cached)
            if path not in cache or cache[path] != content or not os.path.exists(filename):
                LOGGER.debug("* Writing file {} ({})".format(path, "not in cache" if path not in cache else "different"))
                # Any error (permission, name too long, disk full...) is reported, and must not
                # stop the other files from being written.
                try:
                    os.makedirs(os.path.dirname(filename), exist_ok=True)
                    writeFile(filename, content)
                    cache[path] = content

                except OSError as e:
                    LOGGER.error("Cannot write file %s: %s", filename, e)
                    filesWithPermissionErrors.append("{} ({})".format(filename, e.strerror or e))
                    # The file on disk is not up to date: it must be written next time.
                    if path in cache:
                        cache[path] = None

        # Removing phantoms (files of items that have been removed, renamed or moved)
        written = {p.lower(): p for p, c in files}
        phantoms = [p for p in cache if p not in [p for p, c in files]]

        # The old files of a renamed or moved item are not removed if its new files could not
        # all be written: they are then the only copy of its content. They stay on disk and in
        # the cache, and the item keeps its old path, so that the next save handles it as
        # moved again (and removes the old files once the new ones have been written).
        # The old files of removed items, and of the items written at their new place, are
        # removed even if other files could not be written.
        failed = [p for p, c in files if cache.get(p) != c]
        # A folder whose folder.txt could not be written is not loaded, nor anything in it:
        # the items written into it have not been written either.
        unloadable = [os.path.dirname(f) for f in failed if os.path.basename(f) == "folder.txt"
                      and not os.path.exists(os.path.join(dir, folder, f))]
        notMoved = {new: old for old, new in moves
                    if any(f == new or f.startswith(new + os.sep) for f in failed)
                    or any(new.startswith(u + os.sep) for u in unloadable)}
        if notMoved:
            LOGGER.warning("Some files could not be written, the old files of %d renamed or "
                           "moved items are not removed.", len(notMoved))
            phantoms = [p for p in phantoms if not any(
                p == old or p.startswith(old + os.sep) for old in notMoved.values())]

            for c in mw.mdlCharacter.characters:
                c.lastPath = notMoved.get(c.lastPath, c.lastPath)

            def keepOldPath(item):
                for child in item.children():
                    child._lastPath = notMoved.get(child._lastPath, child._lastPath)
                    keepOldPath(child)

            keepOldPath(mw.mdlOutline.rootItem)

        # Files and folders that could not be read when the project was loaded are not part of
        # the project, so they are not written with the other files of a renamed or moved
        # folder. They are moved to its new place once it has been written: left in the old
        # folder, they would no longer be loaded once its folder.txt has been removed.
        entries = list(unreadable)
        for old, new in moves:
            if new in notMoved or not os.path.isdir(os.path.join(dir, folder, new)):
                continue
            for u in [u for u in entries if u in unreadable and os.path.dirname(u) == old]:
                target = os.path.join(new, os.path.basename(u))
                try:
                    if target.lower() in written or \
                            os.path.lexists(os.path.join(dir, folder, target)):
                        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), target)
                    os.replace(os.path.join(dir, folder, u), os.path.join(dir, folder, target))
                except OSError as e:
                    # The old folder then keeps its folder.txt (see below)
                    LOGGER.error("Cannot move %s to %s: %s", u, target, e)
                    continue
                LOGGER.debug("* Moved %s to %s", u, target)
                for k in [k for k in unreadable if k == u or k.startswith(u + os.sep)]:
                    unreadable[target + k[len(u):]] = unreadable.pop(k)

        for path in phantoms:
            filename = os.path.join(dir, folder, path)

            # On a case-insensitive file system (Windows, macOS), the old file of an item
            # whose name only changed in case is the file that has just been written.
            same = written.get(path.lower())
            try:
                isWrittenFile = same is not None and \
                    os.path.samefile(filename, os.path.join(dir, folder, same))
            except OSError:
                isWrittenFile = False

            try:
                if isWrittenFile:
                    LOGGER.debug("* Not removing %s: it is the same file as %s", path, same)

                elif isUnreadable(path):
                    LOGGER.debug("* Not removing %s: it could not be read when loading", path)

                elif os.path.basename(path) == "folder.txt" and any(
                        u.startswith(os.path.dirname(path) + os.sep)
                        for u in list(unreadable) + list(notMoved.values())):
                    # Without it, the files of its folder that could not be read when loading
                    # (and could not be moved with it), and the old files kept above, would no
                    # longer be loaded.
                    LOGGER.warning("* Not removing %s: its folder holds files that could not be "
                                   "read when loading, or that could not be moved", path)
                    continue

                elif os.path.isdir(filename):
                    LOGGER.debug("* Removing %s", path)
                    shutil.rmtree(filename)

                elif os.path.exists(filename):
                    LOGGER.debug("* Removing %s", path)
                    os.remove(filename)

            except OSError as e:
                # Keep it in the cache, so that we try again next time.
                LOGGER.error("Cannot remove file %s: %s", filename, e)
                continue

            # Clear cache
            cache.pop(path, 0)

        # Removing empty directories
        for root, dirs, files in os.walk(os.path.join(dir, folder, "outline")):
            for dir in dirs:
                newDir = os.path.join(root, dir)
                try:
                    os.removedirs(newDir)
                    LOGGER.debug("* Removing empty directory: %s", newDir)
                except:
                    # Directory not empty, we don't remove.
                    pass

        # Write the project file's content
        try:
            writeFile(project, "1")  # Format number
        except OSError as e:
            LOGGER.error("Cannot write file %s: %s", project, e)
            filesWithPermissionErrors.append("{} ({})".format(project, e.strerror or e))

        if len(filesWithPermissionErrors) > 0:
            dlg = ListDialog(mw)
            dlg.setModal(True)
            dlg.setWindowTitle(dlg.tr("Files not saved"))
            dlg.label.setText(dlg.tr("The following files could not be saved:"))
            for f in filesWithPermissionErrors:
                QListWidgetItem(f, dlg.listWidget)
            dlg.open()

        # Some files have not been written: the project is not (completely) saved.
        if filesWithPermissionErrors:
            return False
        return True


def addWorldItem(root, mdl, parent=QModelIndex()):
    """
    Lists elements in a world model and create an OPML xml file.
    @param root: an Etree element
    @param mdl:  a worldModel
    @param parent: the parent index in the world model
    @return: root, to which sub element have been added
    """
    # List every row (every world item)
    for x in range(mdl.rowCount(parent)):

        # For each row, create an outline item.
        outline = ET.SubElement(root, "outline")
        for y in range(mdl.columnCount(parent)):

            val = mdl.data(mdl.index(x, y, parent))

            if not val:
                continue

            for w in World:
                if y == w.value:
                    outline.attrib[w.name] = val

        # Sub-items, even if this item has an empty name (which is skipped above)
        if mdl.hasChildren(mdl.index(x, 0, parent)):
            addWorldItem(outline, mdl, mdl.index(x, 0, parent))

    return root


def addPlotItem(root, mdl, parent=QModelIndex()):
    """
    Lists elements in a plot model and create an xml file.
    @param root: an Etree element
    @param mdl:  a plotModel
    @param parent: the parent index in the plot model
    @return: root, to which sub element have been added
    """

    # List every row (every plot item)
    for x in range(mdl.rowCount(parent)):

        # For each row, create an outline item.
        outline = ET.SubElement(root, "plot")
        for y in range(mdl.columnCount(parent)):

            index = mdl.index(x, y, parent)
            val = mdl.data(index)
            #
            # if not val:
            #     continue

            for w in Plot:
                if y == w.value and val:
                    outline.attrib[w.name] = val

            # List characters as attrib
            if y == Plot.characters:
                if mdl.hasChildren(index):
                    characters = []
                    for cX in range(mdl.rowCount(index)):
                        for cY in range(mdl.columnCount(index)):
                            cIndex = mdl.index(cX, cY, index)
                            characters.append(mdl.data(cIndex))
                    outline.attrib[Plot.characters.name] = ",".join(characters)

                elif Plot.characters.name in outline.attrib:
                    outline.attrib.pop(Plot.characters.name)

            # List resolution steps as sub items
            elif y == Plot.steps:
                if mdl.hasChildren(index):
                    for cX in range(mdl.rowCount(index)):
                        step = ET.SubElement(outline, "step")
                        for cY in range(mdl.columnCount(index)):
                            cIndex = mdl.index(cX, cY, index)
                            # If empty, returns None, which creates trouble later with lxml, so default to ""
                            val = mdl.data(cIndex) or ""

                            for w in PlotStep:
                                if cY == w.value and w.name:
                                    step.attrib[w.name] = val

                elif Plot.steps.name in outline.attrib:
                    outline.attrib.pop(Plot.steps.name)

    return root


def exportOutlineItem(root):
    """
    Takes an outline item, and returns three lists:
    1. of (`filename`, `content`), representing the whole tree of files to be written, in multimarkdown.
    2. of (`filename`, `filename`) listing files to be moved
    3. of `filename`, representing files to be removed.

    @param root: OutlineItem
    @return: [(str, str)], [(str, str)], [str]
    """

    files = []
    moves = []
    removes = []

    k = 0
    for child in root.children():
        spath = os.path.join(*outlineItemPath(child))

        k += 1

        # Has the item been renamed?
        lp = child._lastPath
        if lp and spath != lp:
            moves.append((lp, spath))
            LOGGER.debug("%s has been renamed (%s → %s)", child.title(), lp,  spath)
            LOGGER.debug(" → We mark for moving: %s", lp)

        # Updates item last's path
        child._lastPath = spath

        # Generating content
        if child.type() == "folder":
            fpath = os.path.join(spath, "folder.txt")
            content = outlineToMMD(child)
            files.append((fpath, content))

        elif child.type() == "md":
            content = outlineToMMD(child)
            files.append((spath, content))

        else:
            LOGGER.debug("Unknown type: %s", child.type())

        f, m, r = exportOutlineItem(child)
        files += f
        moves += m
        removes += r

    return files, moves, removes


def outlineItemPath(item):
    """
    Returns the outlineItem file path (like the path where it will be written on the disk). As a list of folder's
    name. To be joined by os.path.join.
    @param item: outlineItem
    @return: list of folder's names
    """
    # Root item
    if not item.parent():
        return ["outline"]
    else:
        # Count the number of siblings for padding '0'
        siblings = item.parent().childCount()

        # We check if multiple items have the same name
        # If so, we add "-ID" to their name
        siblingsNames = [s.title() for s in item.parent().children()]
        if siblingsNames.count(item.title()) > 1:
            title = "{}-{}".format(item.title(), item.ID())
        else:
            title = item.title()

        name = "{ID}-{name}{ext}".format(
            ID=str(item.row()).zfill(len(str(siblings))),
            name=slugify(title)[:maxSlugLength],
            ext="" if item.type() == "folder" else ".md"
        )
        return outlineItemPath(item.parent()) + [name]


def outlineToMMD(item):
    content = ""

    # We don't want to write some datas (computed)
    exclude = [Outline.wordCount, Outline.goal, Outline.goalPercentage, Outline.revisions, Outline.text]
    # We want to force some data even if they're empty
    force = [Outline.compile]

    for attrib in Outline:
        if attrib in exclude:
            continue
        val = item.data(attrib.value)
        if val or attrib in force:
            content += formatMetaData(attrib.name, str(val), 15)

    content += "\n\n"
    content += item.data(Outline.text)

    return content

########################################################################################################################
# LOAD
########################################################################################################################

def loadProject(project, zip=None):
    """
    Loads a project.
    @param project: the filename of the project to open.
    @param zip: whether the project is a zipped or not.
    @return: an array of errors, empty if None.
    """

    mw = mainWindow()
    errors = list()

    ####################################################################################################################
    # Read and store everything in a dict

    LOGGER.debug("Loading {} ({})".format(project, "zip" if zip else "folder"))
    if zip:
        files = loadFilesFromZip(project)

        # Decode files
        for f in files:
            if f[-4:] not in [".xml", "opml"]:
                files[f] = files[f].decode("utf-8")

    else:
        # Project path
        dir = os.path.dirname(project)

        # Folder containing file: name of the project file (without .msk extension)
        folder = os.path.splitext(os.path.basename(project))[0]

        # The full path towards the folder containing files
        path = os.path.join(dir, folder, "")

        files = {}
        # Files and folders that cannot be read (relative path: reason)
        notRead = OrderedDict()

        def reason(e):
            return getattr(e, "strerror", None) or str(e)

        def walkError(e):
            # A folder that cannot be listed (or the project folder does not exist)
            p = os.path.relpath(e.filename, path) if e.filename else "."
            p = "" if p == "." else p
            # Hidden folders are not loaded anyway
            if not any(c[:1] == "." for c in p.split(os.sep)):
                LOGGER.error("Cannot read folder %s: %s", e.filename, e)
                notRead[p] = reason(e)

        for dirpath, dirnames, filenames in os.walk(path, onerror=walkError):
            p = dirpath.replace(path, "")
            # Skip directories that begin with a period
            if p[:1] == ".":
                continue
            #skip if the basedir of the file starts with an .
            if os.path.basename(p)[:1] == ".":
                continue
            for f in filenames:
                # Skip filenames that begin with a period
                if f[:1] == ".":
                    continue
                # mode = "r" + ("b" if f[-4:] in [".xml", "opml"] else "")
                # A file that cannot be read (permissions, file locked or removed by a sync
                # tool, dangling symlink, path too long, invalid encoding...) is reported.
                filename = os.path.join(dirpath, f)
                try:
                    if f[-4:] in [".xml", "opml"]:
                        with open(filename, "rb") as fo:
                            files[os.path.join(p, f)] = fo.read()
                    else:
                        with open(filename, 'rt', encoding="utf8") as fo:
                            files[os.path.join(p, f)] = fo.read()

                except (UnicodeDecodeError, OSError) as e:
                    LOGGER.error("Cannot read file %s: %s", filename, e)
                    notRead[os.path.join(p, f)] = reason(e)
                    # Without its folder.txt, nothing in a folder is loaded
                    if f == "folder.txt" and p:
                        notRead[p] = reason(e)

        global cache, freshTarget, unreadable
        errors += list(notRead)

        # If the project folder, its main folders or any of the files at its root could not be
        # read, the project is not opened: it would be saved without them (an empty project,
        # or empty plots, world, settings...). Other files that cannot be read are not loaded,
        # and are left untouched when the project is saved.
        failed = [p for p in notRead if p in ["", "outline", "characters"] + projectFiles]
        if failed or (notRead and not files):
            LOGGER.error("Project %s cannot be loaded: some files cannot be read.", project)
            showFilesNotLoaded(mw, path, notRead, failed=True)
            # Nothing of this project must be used by the next save (of another project)
            cache, freshTarget, unreadable = {}, True, {}
            errors.append(project)
            return errors

        if notRead:
            showFilesNotLoaded(mw, path, notRead)

        # Saves to cache (only if we loaded from disk and not zip)
        cache = files
        freshTarget = False
        unreadable = dict(notRead)

        # FIXME: watch directory for changes

    # Sort files by keys
    files = OrderedDict(sorted(files.items()))

    ####################################################################################################################
    # Settings

    if "settings.txt" in files:
        settings.load(files["settings.txt"], fromString=True, protocol=0)
    else:
        errors.append("settings.txt")

    # Just to be sure
    settings.saveToZip = True if zip else False
    settings.defaultTextType = "md"

    ####################################################################################################################
    # Labels

    mdl = mw.mdlLabels
    mdl.appendRow(QStandardItem(""))  # Empty = No labels
    if "labels.txt" in files:
        LOGGER.debug("Reading labels:")
        for s in files["labels.txt"].split("\n"):
            if not s:
                continue

            m = re.search(r"^(.*?):\s*(.*)$", s)
            txt = m.group(1)
            col = m.group(2)
            LOGGER.debug("* Add status: {} ({})".format(txt, col))
            icon = iconFromColorString(col)
            mdl.appendRow(QStandardItem(icon, txt))

    else:
        errors.append("labels.txt")

    ####################################################################################################################
    # Status

    mdl = mw.mdlStatus
    mdl.appendRow(QStandardItem(""))  # Empty = No status
    if "status.txt" in files:
        LOGGER.debug("Reading status:")
        for s in files["status.txt"].split("\n"):
            if not s:
                continue
            LOGGER.debug("* Add status: %s", s)
            mdl.appendRow(QStandardItem(s))
    else:
        errors.append("status.txt")

    ####################################################################################################################
    # Infos

    mdl = mw.mdlFlatData
    if "infos.txt" in files:
        md, body = parseMMDFile(files["infos.txt"], asDict=True)

        row = []
        for name in ["Title", "Subtitle", "Serie", "Volume", "Genre", "License", "Author", "Email"]:
            row.append(QStandardItem(md.get(name, "")))

        mdl.appendRow(row)

    else:
        errors.append("infos.txt")

    ####################################################################################################################
    # Summary

    mdl = mw.mdlFlatData
    if "summary.txt" in files:
        md, body = parseMMDFile(files["summary.txt"], asDict=True)

        row = []
        for name in ["Situation", "Sentence", "Paragraph", "Page", "Full"]:
            row.append(QStandardItem(md.get(name, "")))

        mdl.appendRow(row)

    else:
        errors.append("summary.txt")

    ####################################################################################################################
    # Plots

    mdl = mw.mdlPlots
    if "plots.xml" in files:
        LOGGER.debug("Reading plots:")
        # xml = bytearray(files["plots.xml"], "utf-8")
        root = ET.fromstring(files["plots.xml"])

        for plot in root:
            # Create row
            row = getStandardItemRowFromXMLEnum(plot, Plot)

            # Log
            LOGGER.debug("* Add plot: %s", row[0].text())

            # Characters
            if row[Plot.characters].text():
                IDs = row[Plot.characters].text().split(",")
                item = QStandardItem()
                for ID in IDs:
                    item.appendRow(QStandardItem(ID.strip()))
                row[Plot.characters] = item

            # Subplots
            for step in plot:
                row[Plot.steps].appendRow(
                    getStandardItemRowFromXMLEnum(step, PlotStep)
                )

            # Add row to the model
            mdl.appendRow(row)

    else:
        errors.append("plots.xml")

    ####################################################################################################################
    # World

    mdl = mw.mdlWorld
    if "world.opml" in files:
        LOGGER.debug("Reading World:")
        # xml = bytearray(files["plots.xml"], "utf-8")
        root = ET.fromstring(files["world.opml"])
        body = root.find("body")

        for outline in body:
            row = getOutlineItem(outline, World)
            mdl.appendRow(row)

    else:
        errors.append("world.opml")

    ####################################################################################################################
    # Characters

    mdl = mw.mdlCharacter
    LOGGER.debug("Reading Characters:")
    # Only files in the top-level "characters" folder (not e.g. a scene titled "Main characters")
    for f in [f for f in files if f.split(os.path.sep)[0] == "characters"]:
        md, body = parseMMDFile(files[f])
        c = mdl.addCharacter()
        c.lastPath = f

        color = False
        for desc, val in md:

            # Base infos
            if desc in characterMap.values():
                key = [key for key, value in characterMap.items() if value == desc][0]
                index = c.index(key.value)
                mdl.setData(index, val)

            # Character color
            elif desc == "Color" and not color:
                c.setColor(QColor(val))
                # We remember the first time we found "Color": it is the icon color.
                # If "Color" comes a second time, it is a Character's info.
                color = True

            # Character's infos
            else:
                c.infos.append(CharacterInfo(c, desc, val))

        LOGGER.debug("* Adds {} ({})".format(c.name(), c.ID()))

    ####################################################################################################################
    # Texts
    # We read outline form the outline folder. If revisions are saved, then there's also a revisions.xml which contains
    # everything, but the outline folder takes precedence (in cases it's been edited outside of manuskript.

    mdl = mw.mdlOutline
    LOGGER.debug("Reading outline:")
    # Only files in the top-level "outline" folder (not e.g. a character named "outline")
    paths = [f for f in files if f.split(os.path.sep)[0] == "outline"]
    outline = OrderedDict()

    # We create a structure of imbricated OrderedDict to store the whole tree.
    for f in paths:
        split = f.split(os.path.sep)[1:]
        # LOGGER.debug("* %s", split)

        last = ""
        parent = outline
        parentLastPath = "outline"
        for i in split:
            if last:
                parent = parent[last]
                parentLastPath = os.path.join(parentLastPath, last)
            last = i

            if not i in parent:
                # If not last item, then it is a folder
                if i != split[-1]:
                    parent[i] = OrderedDict()

                # If file, we store it
                else:
                    parent[i] = files[f]

                # We store f to add it later as lastPath
                parent[i + ":lastPath"] = os.path.join(parentLastPath, i)



    # We now just have to recursively add items.
    addTextItems(mdl, outline)

    # Adds revisions
    if "revisions.xml" in files:
        root = ET.fromstring(files["revisions.xml"], parser=_parser)
        appendRevisions(mdl, root)

    # Check IDS
    mdl.rootItem.checkIDs()

    if not zip:
        # saveProject() removes every cached file that it has not written, as the file of a
        # removed item. Files that have not been loaded into the project (unknown files,
        # scenes without ID, folders without folder.txt, ...) must therefore not be in the
        # cache, otherwise they are deleted on the next save. They are left untouched.
        used = set(projectFiles)
        used.update(c.lastPath for c in mw.mdlCharacter.characters)

        def addUsed(item):
            for c in item.children():
                used.add(c._lastPath)
                used.add(os.path.join(c._lastPath, "folder.txt"))
                addUsed(c)

        addUsed(mdl.rootItem)
        for f in [f for f in cache if f not in used]:
            LOGGER.warning("File %s has not been loaded, it will be left untouched.", f)
            cache.pop(f)

    return errors


def showFilesNotLoaded(mw, path, notRead, failed=False):
    """
    Tells the user which files of the project folder could not be read.
    @param path: the project folder
    @param notRead: {relative path: reason}
    @param failed: True if the project cannot be opened because of them
    """
    dlg = ListDialog(mw)
    dlg.setModal(True)
    dlg.setWindowTitle(dlg.tr("Files not loaded"))
    if failed:
        dlg.label.setText(dlg.tr("The following files could not be read, so the project "
                                 "cannot be opened:"))
    else:
        dlg.label.setText(dlg.tr("The following files could not be read. They are not loaded, "
                                 "and they are left untouched when the project is saved:"))
    for f, reason in notRead.items():
        QListWidgetItem("{} ({})".format(os.path.normpath(os.path.join(path, f)), reason),
                        dlg.listWidget)
    dlg.open()


def addTextItems(mdl, odict, parent=None):
    """
    Adds a text / outline items from an OrderedDict.
    @param mdl: model to add to
    @param odict: OrderedDict
    @return: nothing
    """
    if parent is None:
        parent = mdl.rootItem

    for k in odict:

        # In case k is a folder:
        if (type(odict[k]) == OrderedDict) and ("folder.txt" in odict[k]):

            # Adds folder
            LOGGER.debug("{}* Adds {} to {} (folder)".format("  " * parent.level(), k, parent.title()))
            item = outlineFromMMD(odict[k]["folder.txt"], parent=parent)
            item._lastPath = odict[k + ":lastPath"]

            # Read content
            addTextItems(mdl, odict[k], parent=item)

        if (":lastPath" in k) or (k == "folder.txt"):
            continue

        # k is not a folder
        if type(odict[k]) == str:
            try:
                LOGGER.debug("{}* Adds {} to {} (file)".format("  " * parent.level(), k, parent.title()))
                item = outlineFromMMD(odict[k], parent=parent)
                item._lastPath = odict[k + ":lastPath"]
            except KeyError:
                LOGGER.error(f"Failed to add file {k}")
        else:
            LOGGER.debug(f"Strange things in file {k}")


def outlineFromMMD(text, parent):
    """
    Creates outlineItem from multimarkdown file.
    @param text: content of the file
    @param parent: appends item to parent (outlineItem)
    @return: outlineItem
    """

    md, body = parseMMDFile(text, asDict=True)

    # Assign ID on creation, to avoid generating a new ID for this object
    item = outlineItem(parent=parent, ID=md.pop('ID'))

    # Store metadata
    for k in md:
        if k in Outline.__members__:
            item.setData(Outline.__members__[k], str(md[k]))

    # Store body
    item.setData(Outline.text, str(body))

    # Set file format to "md"
    # (Old version of manuskript had different file formats: text, t2t, html and md)
    # If file format is html, convert to plain text:
    if item.type() == "html":
        item.setData(Outline.text, HTML2PlainText(body))
    if item.type() in ["txt", "t2t", "html"]:
        item.setData(Outline.type, "md")

    return item


def appendRevisions(mdl, root):
    """
    Parse etree item to find outlineItem's with revisions, and adds them to model `mdl`.
    @param mdl: outlineModel
    @param root: etree
    @return: nothing
    """
    for child in root:
        # Recursively go through items
        if child.tag == "outlineItem":
            appendRevisions(mdl, child)

        # Revision found.
        elif child.tag == "revision":
            # Get root's ID
            ID = root.attrib["ID"]
            if not ID:
                LOGGER.debug("* Serious problem: no ID!")
                LOGGER.error("Revision has no ID associated!")
                continue

            # Find outline item in model
            item = mdl.getItemByID(ID)
            if not item:
                LOGGER.debug("* Error: no item whose ID is %s", ID)
                LOGGER.error("Could not identify the item matching the revision ID.")
                continue

            # Store revision
            LOGGER.debug("* Appends revision ({}) to {}".format(child.attrib["timestamp"], item.title()))
            item.appendRevision(child.attrib["timestamp"], child.attrib["text"])


def getOutlineItem(item, enum):
    """
    Reads outline items from an opml file. Returns a row of QStandardItem, easy to add to a QStandardItemModel.
    @param item: etree item
    @param enum: enum to read keys from
    @return: [QStandardItem]
    """
    row = getStandardItemRowFromXMLEnum(item, enum)
    LOGGER.debug("* Add worldItem: %s", row[0].text())
    for child in item:
        sub = getOutlineItem(child, enum)
        row[0].appendRow(sub)

    return row


def getStandardItemRowFromXMLEnum(item, enum):
    """
    Reads and etree item and creates a row of QStandardItems by cross-referencing an enum.
    Returns a list of QStandardItems that can be added to a QStandardItemModel by appendRow.
    @param item: the etree item
    @param enum: the enum
    @return: list of QStandardItems
    """
    row = []
    for i in range(len(enum)):
        row.append(QStandardItem(""))

    for name in item.attrib:
        if name in enum.__members__:
            row[enum[name].value] = QStandardItem(item.attrib[name])
    return row

def parseMMDFile(text, asDict=False):
    """
    Takes the content of a MultiMarkDown file (str) and returns:
    1. A list containing metadatas: (description, value) if asDict is False.
       If asDict is True, returns metadatas as an OrderedDict. Be aware that if multiple metadatas have the same description
       (which is stupid, but hey), they will be lost except the last one.
    2. The body of the file
    @param text: the content of the file
    @return: (list, str) or (OrderedDict, str)
    """
    md = []
    mdd = OrderedDict()
    body = []
    descr = ""
    val = ""
    inBody = False
    for s in text.split("\n"):
        if not inBody:
            m = re.match(r"^([^\s].*?):\s*(.*)$", s)
            if m:
                # Commit last metadata
                if descr:
                    if descr == "None":
                        descr = ""
                    md.append((descr, val))
                    mdd[descr] = val
                descr = ""
                val = ""

                # Store new values
                descr = m.group(1)
                val = m.group(2)

            elif s[:4] == "    ":
                val += "\n" + s.strip()

            elif s == "":
                # End of metadatas
                inBody = True

                # Commit last metadata
                if descr:
                    if descr == "None":
                        descr = ""
                    md.append((descr, val))
                    mdd[descr] = val

        else:
            body.append(s)

    # We remove the second empty line (since we save with two empty lines)
    if body and body[0] == "":
        body = body[1:]

    body = "\n".join(body)

    if not asDict:
        return md, body
    else:
        return mdd, body
