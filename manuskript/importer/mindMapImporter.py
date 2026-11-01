#!/usr/bin/env python
# --!-- coding: utf8 --!--

from PyQt5.QtWidgets import qApp, QMessageBox
from manuskript.models import outlineItem
from manuskript.enums import Outline
from lxml import etree as ET
from manuskript.functions import mainWindow, safeTranslate
from manuskript.importer.abstractImporter import abstractImporter
from manuskript.converters import HTML2MD, HTML2PlainText


class mindMapImporter(abstractImporter):

    name = "Mind Map"
    description = ""
    fileFormat = "Mind map Files (*.mm)"
    icon = "text-x-opml+xml"

    @classmethod
    def isValid(cls):
        return True

    def startImport(self, filePath, parentItem, settingsWidget, fromString=None):
        """
        Import/export outline cards in mind map free plane.
        """
        ret = False

        if filePath != "":
            # We have a filePath, so we read the file
            try:
                with open(filePath, 'rb') as f:
                    content = f.read()
            except:
                return None

        elif fromString == "":
            # We have neither filePath nor fromString, so we leave
            return None

        else:
            # We load from string
            content = bytes(fromString, "utf-8")

        root = ET.fromstring(content)

        node = root.find("node")
        items = []

        if node != None:
            items.extend(self.parseItems(node, parentItem))
            ret = True

        if not ret:
            QMessageBox.critical(
                settingsWidget,
                safeTranslate(qApp, "Import", "Mind Map Import"),
                safeTranslate(qApp, "Import", "This does not appear to be a valid Mind Map file."))

            return None

        return items

    def settingsWidget(self, widget):
        """
        Takes a QWidget that can be modified and must be returned.
        """

        # Add group
        group = self.addGroup(widget.toolBox.widget(0),
                              safeTranslate(qApp, "Import", "Mind Map import"))

        self.addSetting("importTipAs", "combo",
                        safeTranslate(qApp, "Import", "Import tip as:"),
                        vals="Text|Folder",
                       )

        for s in self.settings:
            self.settings[s].widget(group)

        return widget

    def parseItems(self, underElement, parentItem=None):
        items = []

        # Title
        title = underElement.get('TEXT', "").replace("\n", " ")
        if not title:
            title = safeTranslate(qApp, "Import", "Untitled")

        item = outlineItem(parent=parentItem, title=title)
        items.append(item)

        # URL
        url = underElement.get('LINK', None)

        # Rich text content
        notes = []
        for content in underElement.findall("richcontent"):
            # In Freemind, can be note or node
            # Note: it's a note
            # Node: it's the title of the node, in rich text
            content_type = content.get("TYPE", "NOTE")
            html = content.find("html")
            if html is not None:
                html = ET.tostring(html)
            else:
                # Freeplane can store plain text or markdown instead of html
                text = "".join(content.itertext()).strip()
                if not text:
                    continue

            if content_type == "NODE":
                # Content is title
                # convert rich text title (in html) to plain text
                title = HTML2PlainText(html) if html is not None else text
                # Count the number of lines
                lines = [l.strip() for l in title.split("\n") if l.strip()]

                # If there is one line, we use it as title.
                # Otherwise we leave it to be inserted as a note.
                if len(lines) == 1:
                    item.setData(Outline.title, "".join(lines))
                    continue

            notes.append(HTML2MD(html) if html is not None else text)

        if notes:
            # Set the note content as text value
            item.setData(Outline.notes, "\n\n".join(notes))

        if url:
            # Set the url in notes
            item.setData(Outline.notes,
                         item.data(Outline.notes) + "\n\n" + url)

        children = underElement.findall('node')

        # Process children
        if children != None and len(children) > 0:
            for c in children:
                items.extend(self.parseItems(c, item))

        # Process if no children
        elif self.getSetting("importTipAs").value() == "Text":
            # Transform item to text
            item.setData(Outline.type, 'md')
            # Move notes to text
            if item.data(Outline.notes):
                item.setData(Outline.text, item.data(Outline.notes))
                item.setData(Outline.notes, "")

        return items
