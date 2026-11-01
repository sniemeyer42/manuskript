#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for the mind map (FreeMind / Freeplane) importer."""

from manuskript.importer.mindMapImporter import mindMapImporter


def test_richContentWithoutHtml(runImporter):
    """Freeplane can store notes as plain text or markdown."""
    items = runImporter(mindMapImporter, fromString="""<map version="freeplane 1.11.5">
<node TEXT="Root">
<node TEXT="Leaf with markdown note">
<richcontent CONTENT-TYPE="plain/markdown" TYPE="NOTE"><text>Some *markdown* note</text></richcontent>
</node>
</node>
</map>""")
    assert [i.title() for i in items] == ["Root", "Leaf with markdown note"]
    assert items[1].text() == "Some *markdown* note"


def test_richTitleAndNote(runImporter):
    """A node can have both a rich text title and a note."""
    items = runImporter(mindMapImporter, fromString="""<map version="1.0.1">
<node TEXT="Root">
<node TEXT="">
<richcontent TYPE="NODE"><html><head></head><body><p>Rich title</p></body></html></richcontent>
<richcontent TYPE="NOTE"><html><head></head><body><p>The note.</p></body></html></richcontent>
</node>
</node>
</map>""")
    assert [i.title() for i in items] == ["Root", "Rich title"]
    assert items[1].text().strip() == "The note."
