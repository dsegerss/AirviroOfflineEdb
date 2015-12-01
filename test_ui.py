# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
 
nameField = None
myDialog = None

 
def formOpen(dialog, layerid, featureid):
    global myDialog
    myDialog = dialog
    global nameField
    nameField = dialog.findChild(QLineEdit,"name")
    buttonBox = dialog.findChild(QDialogButtonBox,"buttonBox")
 
    # Disconnect the signal that QGIS has wired up for
    # the dialog to the button box.
    buttonBox.accepted.disconnect(myDialog.accept)
 
    # Wire up our own signals.
    buttonBox.accepted.connect(validate)
    buttonBox.rejected.connect(myDialog.reject)

 
def validate():
    # Make sure that the name field isn't empty.
    if not nameField.text().length() > 0:
        msgBox = QMessageBox()
        msgBox.setText("Name field can not be null.")
        msgBox.exec_()
    else:
        # Return the form as accpeted to QGIS.
        myDialog.accept()
