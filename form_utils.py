# -*- coding: utf-8 -*-

import abc
import copy
import re
from functools import partial
from collections import OrderedDict

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


def make_iterable(value):
    value = value or []
    if not hasattr(value, '__iter__'):
        value = [value]
    return value


def connect_db(filename):
    """Connect to database."""
    con = sqlite3.connect(filename)
    # con.enable_load_extension(True)
    # con.execute("select load_extension('libspatialite')")
    # con.enable_load_extension(False)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('PRAGMA foreign_keys = ON')
    return con, cur


def reconnect(signal, callback):
    try:
        signal.disconnect()
    except:
        pass
    signal.connect(callback)
    

class ValidationError(Exception):
    
    """Form validation error."""

    def __init__(self, message, *args, **kwargs):
        message = message.format(*args, **kwargs)
        super(ValidationError, self).__init__(message)


class ValidationWarning(Exception):
    
    """Form validation error."""

    def __init__(self, message, *args, **kwargs):
        message = message.format(*args, **kwargs)
        super(ValidationWarning, self).__init__(message)


class BaseFeatureForm:

    """A container for widgets making form validation more standardized."""

    __metaclass__ = abc.ABCMeta

    def __init__(self, dialog, layer, feature,
                 msg_method=None, msg_widget=None):
        self.layer = layer
        self.feature = feature
        self.dialog = dialog
        self.widgets = OrderedDict()
        self.msg_method = msg_method
        self.msg_widget = msg_widget

        db = self.get_db_file()
        self.con, self.cur = connect_db(db)

    def get_db_file(self):
        db_path = re.compile('dbname=.(.*?). ').match(
            self.layer.source()
        ).group(1)
        return db_path

    def connect_signals(self):
        """Attach validate function to form Ok button."""

        # The bypassing of accept button is deprecated

        # # Disconnect the signal that QGIS has wired up
        # # for the dialog to the button box.
        # self.widgets['buttonBox'].widget.accepted.disconnect(
        #     self.dialog.accept
        # )

        # # Wire up our own signals.
        # self.widgets['buttonBox'].widget.accepted.connect(
        #     self.validate
        # )
        # self.widgets['buttonBox'].widget.rejected.connect(
        #     self.dialog.reject
        # )
    
        reconnect(
            self.dialog.attributeChanged,
            partial(self.validate, self.msg_method, self.msg_widget)
        )
            
        reconnect(
            self.layer.editingStarted,
            partial(self.toggle_enabled, True)
        )
        reconnect(
            self.layer.editingStopped,
            partial(self.toggle_enabled, False)
        )

    def toggle_enabled(self, enabled=True):
        """Toggle widget status."""
        for name, form_widget in self.widgets.iteritems():
            if form_widget.enable_on_edit:
                form_widget.toggle_enabled(enabled)

    def init_widgets(self):
        """Init widgets on custom form."""

        for name, widget in self.widgets.iteritems():
            widget.init(edit=self.layer.isEditable())

    def add_widget(self, name, widget_type,
                   validators=None, init=None,
                   on_invalid=None, on_valid=None, on_action=None,
                   enable_on_edit=False):
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
            on_action=on_action,
            enable_on_edit=enable_on_edit
        )

    def validate(self, msg_method=None, msg_widget=None, widget_name=None):
        """Validate all widgets in form."""
        
        widgets_to_validate = (
            (name, widget) for name, widget in self.widgets.iteritems()
            if widget_name is None or
            name == widget_name
        )

        msg_method = msg_method or self.msg_method
        msg_widget_name = msg_widget or self.msg_widget
        msg_widget = self.widgets[msg_widget_name].widget

        errors = []
        warnings = []
        for name, widget in widgets_to_validate:
            try:
                widget.validate(silent=False)
            except ValidationError, err:
                errors.append((name, widget.widget, err.message))
            except ValidationWarning, err:
                warnings.append((name, widget.widget, err.message))

        if msg_method == 'label':
            widget = self.widgets[msg_widget_name].widget
        elif msg_method == 'dialog':
            widget = QtGui.QMessageBox()
        else:
            raise ValueError('Invalid method for validation: %s' % msg_method)

        show = False
        if errors != []:
            error_msg = "Invalid data in fields: "
            for name, widget, msg in errors:
                error_msg += '%s (%s), ' % (name, msg)
            error_msg = error_msg[:-2]
            msg_widget.setText(error_msg)
            msg_widget.setStyleSheet('color: red')
            show = True

        elif warnings != []:
            warning_msg = "Potential problems in fields: "
            for name, widget, msg in warnings:
                warning_msg += '%s(%s) ' % (name, msg)
            warning_msg = warning_msg[:-2]
            msg_widget.setText(warning_msg)
            msg_widget.setStyleSheet('color: yellow')
            show = True
        else:
            msg_widget.setText('')

        if show:
            if msg_method == 'dialog':
                widget.exec_()

    @abc.abstractmethod
    def find_widgets(self):
        pass

    def load_related(self):
        pass

    def update_fields(self):
        pass


class FormWidget:

    def __init__(self, widget, validators=None, init=None,
                 on_invalid=None, on_valid=None, on_action=None,
                 enable_on_edit=False):
        self.widget = widget
        self._init = init
        self.enable_on_edit = enable_on_edit
        self._validators = make_iterable(validators)
        self._on_action = make_iterable(on_action)
        self._on_invalid = make_iterable(on_invalid)
        self._on_valid = make_iterable(on_valid)

        reconnect(
            self.widget.textChanged,
            partial(
                self.validate,
                silent=True
            )
        )
        if self._on_action is not None:
            for action in self._on_action:
                if isinstance(self.widget, QtGui.QComboBox):
                    reconnect(
                        self.widget.currentIndexChanged,
                        action
                    )
                elif isinstance(self.widget, QtGui.QPushButton):
                    reconnect(
                        self.widget.clicked,
                        action
                    )
                elif isinstance(self.widget, QtGui.QLineEdit):
                    reconnect(
                        self.widget.textChanged,
                        action
                    )

    def init(self, edit=False):
        """run init function."""
        if self.enable_on_edit:
            self.widget.setEnabled(edit)

        if self._init is not None:
            self._init(self.widget)

    def on_action(self):
        if self._on_action is not None:
            self._on_action(self.widget)

    def validate(self, silent=True):
        """run validation function."""
        try:
            for validator in self._validators:
                validator(self.widget)
            for on_valid in self._on_valid:
                on_valid(self.widget, message='')
        except ValidationError, err:
            for on_invalid in self._on_invalid:
                on_invalid(self.widget, message=err.message)
            if not silent:
                raise
        return True

    def toggle_enabled(self, enabled=True):
        """Toggle widget status."""
        self.widget.setEnabled(enabled)


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
            'is non-numeric'
        )

    if value < min_value or value > max_value:
        raise ValidationError(
            'outside range %g - %g' % (min_value, max_value)
        )


def validate_is_not_empty(widget):
    if widget.text() is None or len(widget.text()) == 0:
        raise ValidationError(
            'may not be empty'
        )


def validate_of_type(type_from_str, widget):
    value = widget.text()
    try:
        type_from_str(value)
    except ValueError:
        raise ValidationError(
            ' should be an %s' % str(type_from_str)
        )


def validate_max_len(length, widget):
    value = widget.text()
    if len(value) > length:
        raise ValidationError(
            'more than %i characters' % length
        )


def set_widget_style(widget, *args, **kwargs):
    style = kwargs.get('style', '')
    widget.setStyleSheet(style)


