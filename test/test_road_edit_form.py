# coding=utf-8
"""DockWidget test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'david.segersson@smhi.se'
__date__ = '2015-11-10'
__copyright__ = 'Copyright 2015, David Segersson'

import qgis_edb
import unittest

from PyQt4.QtGui import QDockWidget
from PyQt4 import QtCore

import road_edit_form

from utilities import get_qgis_app

QGIS_APP = get_qgis_app()


class RoadEditFormTest(unittest.TestCase):
    """Test road_edit_form works."""

    def setUp(self):
        """Runs before each test."""
        self.dockwidget = AirviroOfflineEdbDockWidget(None)

    def tearDown(self):
        """Runs after each test."""
        self.dockwidget = None

    def test_dockwidget_ok(self):
        """Test we can click OK."""
        pass

    def test_dockwidget_open_db(self):
        """Test to load edb from sqlite db in qgis."""
        filename = 'data/test.sqlite'
        self.dockwidget.open_db_lineedit.setText(filename)
        self.dockwidget.open_db()


if __name__ == "__main__":
    suite = unittest.makeSuite(AirviroOfflineEdbDockWidgetTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
