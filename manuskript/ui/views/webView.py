#!/usr/bin/env python
# --!-- coding: utf8 --!--
import PyQt5
import os

# The HTML export previews render with QtWebEngine if it is installed, and
# with a QTextEdit (basic HTML only) otherwise. QT_WEB=qtwebengine forces
# QtWebEngine, any other value of QT_WEB the QTextEdit.
features = {'qtwebengine': False}

if 'QT_WEB' in os.environ:
    features[os.environ['QT_WEB']] = True
else:
    try:
        import PyQt5.QtWebEngineWidgets
        features['qtwebengine'] = True
    except:
        features['qtwebengine'] = False

if features['qtwebengine']:
    from PyQt5 import QtWebEngineWidgets
    webEngine = "QtWebEngine"
    webView = QtWebEngineWidgets.QWebEngineView
else:
    from PyQt5.QtWidgets import QTextEdit
    webEngine = "QTextEdit"
    webView = QTextEdit
