#!/usr/bin/env python
_author__ = 'victorzhiyulee'
# Importing QGis API
# Importing OGR & OSR
import os
import sys
import PyQt4.QtCore
import PyQt4.QtGui
import qgis.core
import qgis.gui
from qgis.core import *
from qgis.gui import *
from osgeo import ogr, osr
from PyQt4.QtCore import *

# Supply path to the QGis resources on your PC
# noinspection PyTypeChecker
QgsApplication.setPrefixPath("/home/a001080/usr", True)
# Load providers
QgsApplication.initQgis()
# Show setting of parameters
print QgsApplication.showSettings()


print('Provider List')
print(QgsProviderRegistry.instance().providerList())

r = QgsProviderRegistry.instance()
if not 'ogr' in r.providerList():
    print 'Could not find OGR provider!'
else:
    print 'Providers found ok!'
