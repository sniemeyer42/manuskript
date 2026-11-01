#!/usr/bin/env python
# --!-- coding: utf8 --!--


from manuskript.ui.highlighters.searchResultHighlighters.widgetSelectionHighlighter import widgetSelectionHighlighter


class abstractSearchResultHighlighter():
    def __init__(self):
        self._widgetSelectionHighlighter = widgetSelectionHighlighter()

    def highlightSearchResult(self, searchResult):
        if not self.openView(searchResult):
            # The item does not exist anymore (or is filtered out)
            return
        widgets = self.retrieveWidget(searchResult)
        if not isinstance(widgets, list):
            widgets = [widgets]
        for i in range(len(widgets)):
            if widgets[i] is None:
                continue
            self._widgetSelectionHighlighter.highlight_widget_selection(widgets[i], searchResult.pos()[i][0], searchResult.pos()[i][1], i == len(widgets) - 1)

    def openView(self, searchResult):
        """Opens the view showing searchResult. Returns False if it failed."""
        raise RuntimeError

    def retrieveWidget(self, searchResult):
        raise RuntimeError
