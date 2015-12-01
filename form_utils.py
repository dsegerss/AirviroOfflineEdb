# -*- coding: utf-8 -*-

import abc
import copy
import re
from functools import partial

from qgis.core import QgsMessageLog
from PyQt4 import QtGui
from PyQt4 import QtCore

try:
    from pysqlite2 import dbapi2 as sqlite3
except ImportError:
    try:
        import sqlite3
    except:
        pass


def connect(filename):
    """Connect to database."""
    con = sqlite3.connect(filename)
    # con.enable_load_extension(True)
    # con.execute("select load_extension('libspatialite')")
    # con.enable_load_extension(False)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('PRAGMA foreign_keys = ON')
    return con, cur

_oldConnect = QtCore.QObject.connect
_oldDisconnect = QtCore.QObject.disconnect
_oldEmit = QtCore.QObject.emit


class ValidationError(Exception):
    
    """Form validation error."""

    def __init__(self, message, *args, **kwargs):
        message = message.format(*args, **kwargs)
        super(ValidationError, self).__init__(message)


class BaseFeatureForm:

    """A container for widgets making form validation more standardized."""

    __metaclass__ = abc.ABCMeta

    def __init__(self, dialog, layer, feature, widgets=None):
        self.layer = layer
        self.feature = feature
        self.dialog = dialog
        if widgets is None:
            self.widgets = {}
        else:
            self.widgets = copy(widgets)
        db = re.compile('dbname=.(.*?). ').match(self.layer.source()).group(1)
        self.con, self.cur = connect(db)

    def connect_signals(self):
        """Attach validate function to form Ok button."""

        # Disconnect the signal that QGIS has wired up
        # for the dialog to the button box.
        self.widgets['buttonBox'].widget.accepted.disconnect(
            self.dialog.accept
        )

        # Wire up our own signals.
        self.widgets['buttonBox'].widget.accepted.connect(
            self.validate
        )
        self.widgets['buttonBox'].widget.rejected.connect(
            self.dialog.reject
        )

    def init_widgets(self):
        """Init widgets on custom form."""

        for name, widget in self.widgets.iteritems():
            widget.init()

    def add_widget(self, name, widget_type,
                   validators=None, init=None,
                   on_invalid=None, on_valid=None, on_action=None):
        """Add widget to custom form."""

        widget = self.dialog.findChild(widget_type, name)
        if widget is None:
            raise ValueError(
                'Widget with objectName %s not found in ui' % name
            )
        self.widgets[name] = FormWidget(
            widget,
            validators=validators,
            init=init,
            on_invalid=on_invalid,
            on_valid=on_valid,
            on_action=on_action
        )

    def validate(self):
        self.con.commit()
        self.update_fields()
        errors = []
        for name, widget in self.widgets.iteritems():
            try:
                widget.validate(silent=False)
            except ValidationError, err:
                errors.append((name, widget, err.message))
        if errors == []:
            import debug;debug.trace()
            self.load_related()
            # Return the form as accpeted to QGIS.
            self.dialog.accept()
        else:
            error_msg = "Road form contains invalid data:\n"
            for name, widget, msg in errors:
                error_msg += '%s %s\n' % (name, msg)
            widget.widget.setFocus()

            msgBox = QtGui.QMessageBox()
            msgBox.setText(error_msg)
            msgBox.exec_()
            
    @abc.abstractmethod
    def find_widgets(self):
        pass

    def load_related(self):
        pass

    def update_fields(self):
        pass


class FormWidget:

    def __init__(self, widget, validators=None, init=None,
                 on_invalid=None, on_valid=None, on_action=None):
        self.widget = widget
        self._validators = validators
        self._on_action = on_action

        if self._validators is not None:
            if isinstance(self.widget, QtGui.QLineEdit):
                self.widget.textChanged.connect(
                    partial(
                        self.validate,
                        silent=True
                    )
                )
        if self._on_action is not None:
            if isinstance(self.widget, QtGui.QComboBox):
                self.widget.currentIndexChanged.connect(
                    self.on_action
                )
            if isinstance(self.widget, QtGui.QPushButton):
                self.widget.clicked.connect(
                    self.on_action
                )

        self._init = init
        self._on_invalid = on_invalid
        self._on_valid = on_valid

    def init(self):
        """run init function."""
        if self._init is not None:
            self._init(self.widget)

    def on_action(self):
        if self._on_action is not None:
            self._on_action(self.widget)

    def validate(self, silent=True):
        """run validation function."""

        if self._validators is None:
            return True
        try:
            for validator in self._validators:
                validator(self.widget)
            if self._on_valid is not None:
                self._on_valid(self.widget, message='')
        except ValidationError, err:
            if self._on_invalid is not None:
                self._on_invalid(self.widget, message=err.message)
            if not silent:
                raise
        return True


def init_default(value, widget):
    if isinstance(widget, QtGui.QLineEdit):
        if widget.text() is None or len(widget.text()) == 0:
            widget.setText(value)
    elif isinstance(widget, QtGui.QComboBox):
        if widget.currentIndex() == -1:
            widget.setCurrentIndex(value)
    elif isinstance(widget, QtGui.QLabel):
        widget.setText(value)


def validate_in_range(min_value, max_value, widget):
    value = widget.text()
    if value == '' or value is None:
        return

    try:
        value = float(value)
    except ValueError:
        raise ValidationError(
            'field should have a numeric value'
        )

    if value < min_value or value > max_value:
        raise ValidationError(
            'value may not be outside range %f - %f' % (min_value, max_value)
        )


def validate_is_not_empty(widget):
    if widget.text() is None or len(widget.text()) == 0:
        raise ValidationError(
            'field may not be empty'
        )


def validate_of_type(type_from_str, widget):
    value = widget.text()
    try:
        type_from_str(value)
    except ValueError:
        raise ValidationError(
            'value should be of type %s' % str(type_from_str)
        )


def validate_max_len(length, widget):
    value = widget.text()
    if len(value) > length:
        raise ValidationError(
            'field does not allow more than %i characters' % length
        )


def set_widget_style(style, widget, *args, **kwargs):
    widget.setStyleSheet(style)

