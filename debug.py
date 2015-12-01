# -*- coding: utf-8 -*-
from PyQt4.QtCore import pyqtRemoveInputHook
import pdb


def trace():
    '''Set a tracepoint in the Python debugger that works with Qt.'''
    # Or for Qt5
    # from PyQt5.QtCore import pyqtRemoveInputHook
    pyqtRemoveInputHook()
    pdb.set_trace()
