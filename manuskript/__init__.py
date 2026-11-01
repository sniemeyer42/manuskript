# -*- coding: utf-8 -*-

# Manuskript needs Python 3.10 or newer. Check it before anything else is
# imported, so that users of an older Python get a clear message instead of
# an error further on (#1421). Keep this file compatible with old Python
# versions.
import sys

if sys.version_info < (3, 10):
    sys.stderr.write("Manuskript requires Python 3.10 or newer "
                     "(running Python %s).\n" % sys.version.split()[0])
    sys.exit(1)
