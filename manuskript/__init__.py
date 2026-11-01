# -*- coding: utf-8 -*-

# Manuskript's code needs Python 3.6 or newer (f-strings). Check it before
# anything else is imported, so that users of an older Python get a clear
# message instead of a SyntaxError (#1421). Keep this file compatible with
# old Python versions.
import sys

if sys.version_info < (3, 6):
    sys.stderr.write("Manuskript requires Python 3.6 or newer "
                     "(running Python %s).\n" % sys.version.split()[0])
    sys.exit(1)
