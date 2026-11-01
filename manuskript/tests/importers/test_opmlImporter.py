#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the OPML importer."""

from manuskript.importer.opmlImporter import opmlImporter


def test_parentTextIsKept(runImporter):
    """Pandoc puts the text before the first sub-heading in the parent's
    _note (e.g. DocX imported via OPML)."""
    items = runImporter(opmlImporter, fromString="""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Book</title></head>
  <body>
    <outline text="Chapter 1" _note="Intro paragraph of the chapter.">
      <outline text="Scene 1" _note="Scene text." />
    </outline>
    <outline text="Chapter 2">
      <outline text="Scene 2" _note="More text." />
    </outline>
  </body>
</opml>""")
    assert [(i.title(), i.type(), i.text()) for i in items] == [
        ("Chapter 1", "folder", ""),
        ("Chapter 1", "md", "Intro paragraph of the chapter."),
        ("Scene 1", "md", "Scene text."),
        ("Chapter 2", "folder", ""),
        ("Scene 2", "md", "More text."),
    ]
    assert [c.title() for c in items[0].children()] == ["Chapter 1", "Scene 1"]
