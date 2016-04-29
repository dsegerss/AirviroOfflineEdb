# -*- coding: utf-8 -*-

from qgis.core import QgsMessageLog
from PyQt4 import QtCore, QtGui
from functools import partial
from os import path

from AirviroOfflineEdb.form_utils import (
    BaseFeatureForm,
    set_widget_style,
    init_default,
    validate_in_range,
    validate_is_not_empty,
    validate_of_type,
    validate_max_len,
    ValidationError,
    reconnect
)

from pyAirviro.edb.sqliteapi import (
    insert_sql,
    NO_TRAFFIC_SITUATION_COLS
)

from pyAirviro.edb.rsrc import Rsrc

INVALID_STYLE = "background-color: rgba(255, 107, 107, 150);"
VALID_STYLE = ''
INACTIVE_COLOR = QtGui.QColor(100, 100, 100)
INVALID_TAB_COLOR = QtGui.QColor(255, 0, 0)

TIMEVAR_COL = 1
VEHICLE_COL = 0
FRACTION_COL = 2
ISHEAVY_COL = 3
ISTRAFFIC_COL = 4
MAX_NO_CODES = 6
MAX_CODE_LEVELS = 8


def is_list(val_type, nvalues, widget):
    value_string = widget.text()
    try:
        values = map(val_type, value_string.split(' '))
    except:
        raise ValidationError('value is not a list of integers')

    if nvalues is not None:
        if len(values) != nvalues:
            raise ValidationError('should be %i values in list' % nvalues)

    return values


class RoadEditForm(BaseFeatureForm):

    def load_data(self):
        self.read_timevars()
        self.read_vehicles()
        self.read_on_road_vehicles()
        self.read_traffic_situations()
        self.read_rsrc()

    def update_fields(self):
        """Update fields given by indirect related fields. """

        # get traffic situation combo indices
        ts_indices = []
        for combo_ind in range(1, len(self.traffic_situation_cols) + 1):
            combo = self.widgets['ts_combo_%i' % combo_ind].widget
            ts_indices.append(combo.itemData(combo.currentIndex()))
            
        # build SQL where-clause for filtering on traffic sit. column id's
        filters = "WHERE situation1=%i" % ts_indices[0]
        for col_ind, ts_ind in enumerate(ts_indices[1:], 2):
            filters += ' AND situation%i=%i' % (col_ind, ts_ind)

        ts_id = self.con.execute(
            """
            SELECT * FROM traffic_situations
            %s
            """ % filters
        ).next()['id']

        self.widgets['traffic_situation'].widget.setText(str(ts_id))

    def find_widgets(self):

        self.add_widget(
            'corrfactor',
            QtGui.QLineEdit,
            validators=[
                validate_is_not_empty,
                partial(validate_in_range, 0, 5.0)
            ],
            init=partial(init_default, '1.0'),
            on_invalid=[partial(set_widget_style, style=INVALID_STYLE)],
            on_valid=[set_widget_style]
        )

        self.add_widget(
            'name',
            QtGui.QLineEdit,
            validators=[
                validate_is_not_empty,
                partial(validate_max_len, 47)
            ],
            on_invalid=[partial(set_widget_style, style=INVALID_STYLE)],
            on_valid=[set_widget_style]
        )

        self.add_widget(
            'vehicles',
            QtGui.QLineEdit,
            validators=[
                validate_is_not_empty,
                partial(validate_in_range, 0, 200000),
                partial(validate_of_type, int)
            ],
            init=partial(init_default, '0'),
            on_invalid=[partial(set_widget_style, style=INVALID_STYLE)],
            on_valid=[set_widget_style]
        )

        self.add_widget(
            'buttonBox',
            QtGui.QDialogButtonBox
        )

        self.add_widget(
            'traffic_situation',
            QtGui.QLineEdit,
            init=self.init_traffic_situation
        )

        self.add_widget(
            'speed',
            QtGui.QComboBox,
            init=partial(init_default, 3)
        )

        self.add_widget(
            'congestionspeed',
            QtGui.QComboBox,
            init=partial(init_default, 3)
        )

        self.add_widget(
            'congestionspeed2',
            QtGui.QComboBox,
            init=partial(init_default, 3)
        )

        self.add_widget(
            'congestionspeed3',
            QtGui.QComboBox,
            init=partial(init_default, 3)
        )

        self.add_widget(
            'nolanes',
            QtGui.QLineEdit,
            validators=[
                partial(validate_in_range, 1, 8),
                partial(validate_of_type, int)
            ],
            init=partial(init_default, '2'),
            on_invalid=[
                partial(set_widget_style, style=INVALID_STYLE)
            ],
            on_valid=[set_widget_style]

        )

        self.add_widget(
            'width',
            QtGui.QLineEdit,
            validators=[
                partial(validate_in_range, 3, 60),
                partial(validate_of_type, float)
            ],
            on_invalid=[
                partial(set_widget_style, style=INVALID_STYLE)
            ],
            on_valid=[set_widget_style]
        )

        self.add_widget(
            'disthouses',
            QtGui.QLineEdit,
            validators=[
                partial(validate_in_range, 3, 1000),
                partial(validate_of_type, float)
            ],
            on_invalid=[partial(set_widget_style, style=INVALID_STYLE)],
            on_valid=[set_widget_style]
        )

        self.add_widget(
            'height',
            QtGui.QLineEdit,
            validators=[
                partial(is_list, int, None)
            ],
            on_invalid=[partial(set_widget_style, style=INVALID_STYLE)],
            on_valid=[set_widget_style]
        )

        self.add_widget(
            'vehicle_table',
            QtGui.QTableWidget,
            validators=[
                self.validate_vehicle_table
            ],
            on_invalid=[self.show_validation_msg],
            on_valid=[self.show_validation_msg],
            init=self.init_table,
            enable_on_edit=True
        )

        # cascading combos for traffic situation
        self.add_widget(
            'ts_combo_6',
            QtGui.QComboBox,
            enable_on_edit=True
        )
        self.add_widget('ts_combo_6_label', QtGui.QLabel)

        for i in range(5, 1, -1):
            
            self.add_widget(
                'ts_combo_%i' % i, QtGui.QComboBox,
                on_action=partial(self.filter_ts_combo, i + 1),
                enable_on_edit=True
            )
            self.add_widget('ts_combo_%i_label' % i, QtGui.QLabel)

        self.add_widget(
            'ts_combo_1', QtGui.QComboBox,
            init=partial(self.init_ts_combo),
            on_action=partial(self.filter_ts_combo, 2),
            enable_on_edit=True
        )
        self.add_widget('ts_combo_1_label', QtGui.QLabel)

        self.add_widget('geocode', QtGui.QLineEdit)

        # cascading combos for geocodes
        for code_index in range(1, MAX_NO_CODES + 1):
            self.add_widget(
                'gc_combo_%i_%i' % (code_index, MAX_CODE_LEVELS),
                QtGui.QComboBox,
                enable_on_edit=True
            )

            for i in range(MAX_CODE_LEVELS, 1, -1):
            
                self.add_widget(
                    'gc_combo_%i_%i' % (code_index, i),
                    QtGui.QComboBox,
                    on_action=partial(self.filter_code_combo, 'gc'),
                    enable_on_edit=True
                )

            self.add_widget('gc_label_%i' % code_index, QtGui.QLabel)
            self.add_widget(
                'gc_combo_%i_%i' % (code_index, 1),
                QtGui.QComboBox,
                init=partial(self.init_code_combo, 'gc'),
                on_action=partial(self.filter_code_combo, 'gc'),
                enable_on_edit=True
            )

        self.add_widget(
            'add_vehicle_btn',
            QtGui.QPushButton,
            on_action=self.add_vehicle_btn_clicked,
            enable_on_edit=True
        )
        self.add_widget(
            'delete_vehicle_btn',
            QtGui.QPushButton,
            on_action=self.delete_vehicle_btn_clicked,
            enable_on_edit=True
        )

        self.add_widget(
            'new_vehicle_combo',
            QtGui.QComboBox,
            init=partial(self.init_combo, self.vehicles),
            enable_on_edit=True
        )

        self.add_widget(
            'validation_msg_label',
            QtGui.QLabel,
            init=partial(init_default, '')
        )

        self.add_widget(
            'form_validation_msg_label',
            QtGui.QLabel,
            init=partial(init_default, '')
        )

        self.add_widget(
            'reload_vehicles_btn',
            QtGui.QPushButton,
            on_action=self.reload_vehicles_btn_clicked,
            enable_on_edit=True
        )

        self.add_widget(
            'save_vehicles_btn',
            QtGui.QPushButton,
            on_action=self.save_vehicles_btn_clicked,
            enable_on_edit=True
        )

    def show_validation_msg(self, widget, *args, **kwargs):
        msg = kwargs.get('message', '')
        label = self.widgets['validation_msg_label'].widget
        label.setText(msg)

    def init_widgets(self):
        super(RoadEditForm, self).init_widgets()

    @QtCore.pyqtSlot()
    def reload_vehicles_btn_clicked(self, *args, **kwargs):
        QgsMessageLog.logMessage(
            'reload vehicles',
            'AirviroOfflineEdb',
            QgsMessageLog.INFO
        )
        table = self.widgets['vehicle_table'].widget
        table.blockSignals(True)
        table.clearContents()
        while table.rowCount() > 0:
            table.removeRow(0)
        table.blockSignals(False)

        self.read_on_road_vehicles()
        self.init_table(table)

    @QtCore.pyqtSlot()
    def save_vehicles_btn_clicked(self, *args, **kwargs):
        table = self.widgets['vehicle_table'].widget

        with self.con:
            self.con.execute(
                """
                DELETE FROM road_vehicle_link
                WHERE road=%i
                """ % self.feature.id()
            )
        
        sql_rows = []
        for row in range(table.rowCount()):
            tvar_combo = table.cellWidget(row, TIMEVAR_COL)
            sql_rows.append(
                (
                    """
                    INSERT INTO road_vehicle_link
                    (road, vehicle, timevar, fraction)
                    VALUES (:road,:veh,:tvar,:frac)
                    """,
                    {
                        'road': self.feature.id(),
                        'veh': table.item(
                            row, VEHICLE_COL).data(QtCore.Qt.UserRole),
                        'tvar': tvar_combo.itemData(tvar_combo.currentIndex()),
                        'frac': float(table.item(row, FRACTION_COL).text())
                    }
                )
            )
        insert_sql(
            self.cur,
            sql_rows,
            'inserting vehicles on road %s' % self.feature.id()
        )
        self.con.commit()

        

    # def set_tab_text_color(self, widget, *args, **kwargs):
    #     color = kwargs.get('color', QtGui.QColor(255, 255, 255))
    #     tab_index = kwargs.get('tab_index', None)
    #     tab_widget = self.widgets['tabs'].widget
    #     tab_widget.setTabTextColor(tab_index, color)

    @QtCore.pyqtSlot(QtGui.QTableWidgetItem)
    def validate_cell_item(self):
        self.widgets['vehicle_table'].validate()

    @QtCore.pyqtSlot()
    def add_vehicle_btn_clicked(self, *args, **kwargs):
        combo = self.widgets['new_vehicle_combo'].widget
        vehicle_name = combo.itemText(combo.currentIndex())
        vehicle_id = combo.itemData(combo.currentIndex())
        self.add_vehicle_to_table(vehicle_id, vehicle_name)

    @QtCore.pyqtSlot()
    def delete_vehicle_btn_clicked(self, *args, **kwargs):
        table = self.widgets['vehicle_table'].widget
        rows = table.selectionModel().selectedRows()
        for r in rows:
            table.removeRow(r.row())

    def validate_vehicle_table(self, *args, **kwargs):
        QgsMessageLog.logMessage(
            'validate vehicle table',
            'AirviroOfflineEdb',
            QgsMessageLog.INFO
        )

        table = self.widgets['vehicle_table'].widget

        if table.rowCount() == 0:
            return True

        frac = 0
        istraffic = 1
        isheavy = 1
        vehicles = set()
        tot_traf = 0
        tot_vehicles = 0
        heavy_traf_proc = 0
        light_traf_proc = 0
        heavy_nontraf_proc = 0
        light_nontraf_proc = 0
        for row in range(table.rowCount()):
            item = table.item(row, VEHICLE_COL)

            # If validation is run before table is filled, items does not exist
            if item is not None:
                veh_id = item.data(QtCore.Qt.UserRole)
                veh_name = item.text()
                if veh_id in vehicles:
                    raise ValidationError(
                        'has duplicate rows for vehicle %s in table' % veh_name
                    )
                else:
                    vehicles.add(veh_id)

            item = table.item(row, FRACTION_COL)
            if item is not None:
                frac = float(item.text())
            
            item = table.item(row, ISTRAFFIC_COL)
            if item is not None:
                istraffic = item.data(QtCore.Qt.UserRole)

            item = table.item(row, ISHEAVY_COL)
            if item is not None:
                isheavy = item.data(QtCore.Qt.UserRole)

            tot_vehicles += frac

            if istraffic:
                tot_traf += frac

            if isheavy and istraffic:
                heavy_traf_proc += frac
            elif istraffic:
                light_traf_proc += frac
            elif isheavy:
                heavy_nontraf_proc += frac
            else:
                light_nontraf_proc += frac
    
        diff = tot_traf - 100.0
        if abs(diff) > 0.01:
            raise ValidationError(
                'has sum of all traffic vehicle ' +
                '{f} != 100 [%]'.format(f=tot_traf)
            )

    def init_ts_combo(self, widget):
        ndims = len(self.traffic_situation_cols)
        ts_indices = self.widgets['traffic_situation'].widget.ts_indices

        for i in range(ndims + 1, NO_TRAFFIC_SITUATION_COLS + 1):
            self.widgets['ts_combo_%i' % i].widget.hide()
            self.widgets['ts_combo_%i_label' % i].widget.hide()
        
        # disconnect not used combos
        try:
            self.widgets[
                'ts_combo_%i' % ndims
            ].widget.currentIndexChanged.disconnect()
        except TypeError:
            pass

        # Set combo labels
        for i, label in enumerate(self.traffic_situation_cols, 1):
            self.widgets['ts_combo_%i_label' % i].widget.setText(
                label
            )

        if ndims == 0:
            self.widgets['ts_combo_%i' % i].show()
            self.widgets['ts_combo_1_label'].widget.setText(
                'Dimensions of traffic situations not defined'
            )
        
        # query to find all labels of dimension 1 of traffic situations
        # for which there are emission factors defined

        query = """
        SELECT tsc.id as id, tsc.label as label
        FROM
        (
            SELECT DISTINCT situation1
            FROM traffic_situations as ts
        ) as ts_filtered
        JOIN traffic_situation_col1 tsc
        ON ts_filtered.situation1=tsc.id
        """

        rows = self.con.execute(query).fetchall()

        # populate first traffic situation combo
        # block signals during initialization
        widget.blockSignals(True)
        for row in rows:
            widget.addItem(row['label'], row['id'])

        # first set to -1, to make sure currentIndexChanged signal is emitted
        # this will trigger initialization of the other combos
        widget.setCurrentIndex(-1)
        widget.blockSignals(False)
        # Each combo filtering is triggered by the previous combo index change
        
        if ts_indices is not None:
            ts_ind = ts_indices[0]
            combo_ind = widget.findData(ts_ind)
            widget.setCurrentIndex(combo_ind)

        # for combo_ind in range(1, ndims + 1):
        #     combo = self.widgets['ts_combo_%i' % combo_ind].widget
        #     if ts_indices is not None:
        #         ts_ind = ts_indices[combo_ind - 1]
        #         combo.setCurrentIndex(combo.findData(ts_ind))
    
    def filter_ts_combo(self, combo_index, *args):
        """Filter specified combo based on previous combo values """
        combo = self.widgets['ts_combo_%i' % combo_index].widget
        current_data = combo.itemData(combo.currentIndex())
        ts_indices = self.widgets['traffic_situation'].widget.ts_indices

        # If combo has not been manually set
        # set it according to ts stored on road (if set)
        if current_data is None and ts_indices is not None:
            current_data = ts_indices[combo_index - 1]

        parent_indices = []
        for i in range(1, combo_index):
            parent_combo = self.widgets['ts_combo_%i' % i].widget
            parent_data = parent_combo.itemData(parent_combo.currentIndex())
            if parent_data is not None:
                parent_indices.append(
                    parent_data
                )
            else:
                # if parent combo is not initialized
                # filtering is based on first item in parent combo
                parent_indices.append(
                    parent_combo.itemData(0)
                )
        
        # build SQL where-clause for filtering on traffic sit. column id's
        if parent_indices == []:
            filters = ''
        else:
            filters = "WHERE ts.situation1=%i" % parent_indices[0]
            for col_ind, ts_ind in enumerate(parent_indices[1:], 2):
                filters += ' AND ts.situation%i=%i' % (col_ind, ts_ind)

        # Build query to get existing traffic situations
        query = """
        SELECT tsc.id as id, tsc.label as label
        FROM
        (
            SELECT DISTINCT situation{current_col}
            FROM traffic_situations as ts
            {filters}
        ) as ts_filtered
        JOIN traffic_situation_col{current_col} tsc
        ON ts_filtered.situation{current_col}=tsc.id
        """.format(
            current_col=len(parent_indices) + 1,
            filters=filters
        )
        rows = self.con.execute(query).fetchall()

        # populate combo
        combo.blockSignals(True)
        combo.clear()
        for row in rows:
            combo.addItem(row['label'], row['id'])
        combo.blockSignals(False)

        data_index = combo.findData(current_data)
        
        if data_index != -1:
            combo.setCurrentIndex(data_index)
            combo.currentIndexChanged.emit(data_index)
        else:
            combo.setCurrentIndex(0)
            combo.currentIndexChanged.emit(0)

    def init_code_combo(self, code_type, widget):
        """Init first combo for code seletion."""

        # name of current combo (e.g. gc_combo_<i>_<j>
        # where i is code index and j is code level
        vals = widget.objectName().split('_')
        code_index = int(vals[-2])

        # get current geocodes from geocode field of road
        current_gc = self.widgets['geocode'].widget.text().strip().split()
        
        # number of codetrees defined in edb.rsrc
        ncodes = len(getattr(self, code_type))

        # get geocode at current code index if specified for road
        try:
            gc = current_gc[code_index - 1]
            if gc.lower() == 'none':
                gc = None
        except IndexError:
            gc = None

        # get codetree and it's depth, if code index of combo is larger
        # than is defined in edb.rsrc, the combo label is hidden
        if code_index <= ncodes:
            codetree = getattr(self, code_type)[code_index - 1]
            nlevels = codetree.depth()
        else:
            self.widgets['gc_label_%i' % code_index].widget.hide()
            nlevels = 0

        # Hide combos for levels > the depth of the code-tree
        for i in range(nlevels + 1, MAX_CODE_LEVELS + 1):
            self.widgets['gc_combo_%i_%i' % (code_index, i)].widget.hide()

        # If no geocodes defined, show info label
        if nlevels == 0:
            if code_index == 1:
                self.widgets['gc_label_1'].widget.setText(
                    'No geocodes defined'
                )
                self.widgets['gc_label_1'].widget.show()
            return

        # disconnect cascading of non used levels
        self.widgets[
            'gc_combo_%i_%i' % (code_index, nlevels)
        ].widget.currentIndexChanged.disconnect()

        # Set combo label
        self.widgets['%s_label_%i' % (code_type, code_index)].widget.setText(
            codetree.name
        )
        
        # populate first traffic situation combo
        # block signals during initialization
        widget.blockSignals(True)

        widget.addItem('.', 'None')
        for node in codetree.root.findall('*'):
            widget.addItem(' '.join([node.tag, node.attrib['name']]), node.tag)

        # first set to -1, to make sure currentIndexChanged signal is emitted
        # this will trigger initialization of the other combos
        widget.setCurrentIndex(-1)
        widget.blockSignals(False)
        # Each combo filtering is triggered by the previous combo index change

        # set index to the gc of the road
        if gc is not None:
            first_level = gc.split('.')[0]
            current_ind = widget.findData(first_level)
            widget.setCurrentIndex(current_ind)
        else:
            widget.setCurrentIndex(0)

    def filter_code_combo(self, code_type, widget):
        """Filter specified combo based on previous combo values """
        vals = widget.objectName().split('_')
        code_index = int(vals[-2])
        code_level = int(vals[-1]) + 1  # next combo for codex
        codetree = getattr(self, code_type)[code_index - 1]

        # get current geocodes from geocode field of road
        current_gc = self.widgets['geocode'].widget.text().strip().split()

        # get geocode at current code index if specified for road
        try:
            gc = current_gc[code_index - 1]
            if gc.lower() == 'none':
                gc = None
        except IndexError:
            gc = None

        if gc is not None:
            try:
                current_data = gc.split('.')[code_level]
            except IndexError:
                current_data = None
        else:
            current_data = None

        combo = self.widgets[
            '%s_combo_%i_%i' % (code_type, code_index, code_level)
        ].widget

        parent_codes = []
        for i in range(1, code_level):
            parent_combo = self.widgets[
                '%s_combo_%i_%i' % (code_type, code_index, i)
            ].widget
            
            parent_data = parent_combo.itemData(parent_combo.currentIndex())
            if parent_data is not None:
                parent_codes.append(
                    parent_data
                )

        # populate combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem('.', 'None')
        if '.' not in parent_codes:
            for node in codetree.root.findall("/".join(parent_codes) + '/*'):
                combo.addItem(
                    ' '.join([node.tag, node.attrib['name']]),
                    node.tag
                )

        if current_data is not None:
            data_index = combo.findData(current_data)
        else:
            data_index = 0
        combo.blockSignals(False)
        combo.setCurrentIndex(data_index)

    def read_traffic_situations(self):
        rows = self.con.execute(
            "SELECT * FROM traffic_situation_columns"
        ).fetchall()
        rows.sort(key=lambda r: r['id'])
        self.traffic_situation_cols = [row['label'] for row in rows]

    def read_on_road_vehicles(self):
        query = """
        SELECT
          rv.name as name,
          rvl.vehicle as vehicle,
          rvl.timevar as timevar,
          rv.isheavy as isheavy,
          rv.istraffic as istraffic,
          rvl.fraction as fraction
        FROM (
           SELECT *
           FROM road_vehicle_link
           WHERE road = %i
        ) rvl
        JOIN road_vehicles rv
        ON rvl.vehicle = rv.id
        """ % self.feature.id()
        self.on_road_vehicles = self.con.execute(query).fetchall()

    def read_vehicles(self):
        self.vehicles = self.con.execute(
            "SELECT id, name FROM road_vehicles"
        ).fetchall()

    def read_timevars(self):
        self.timevars = self.con.execute(
            "SELECT id, name FROM road_timevars"
        ).fetchall()

    def init_combo(self, rows, widget):
        for row in rows:
            widget.addItem(
                row['name'], row['id']
            )

    def init_traffic_situation(self, widget):
        """get traffic situation indices from ts id (or None if new road)."""
        ts = widget.text()
        widget.ts_indices = None
        if len(ts) > 0 and ts is not None:
            ts = int(ts)
            
            ts_indices = self.con.execute(
                """
                SELECT * FROM traffic_situations
                WHERE id=%i
                """ % ts
            ).next()
            index_list = [ts_indices['id']]
            for i in range(1, NO_TRAFFIC_SITUATION_COLS + 1):
                if ts_indices['situation%i' % i] is not None:
                    index_list.append(ts_indices['situation%i' % i])
            widget.ts_indices = index_list

        widget.hide()

    def update_traffic_situation(self, widget):
        ts_indices = []
        for i in range(1, NO_TRAFFIC_SITUATION_COLS):
            combo = self.widgets['ts_combo_%i' % i].widget
            if not combo.isVisible():
                break
            data = combo.itemData(combo.currentIndex())
            if data is not None:
                ts_indices.append(
                    data
                )
            else:
                ts_indices = None
                break
        if ts_indices is not None:
            value = ' '.join(map(unicode, ts_indices))
            self.widgets['traffic_situation'].widget.setText(value)
        else:
            self.widgets['traffic_situation'].widget.setText(None)


    def add_vehicle_to_table(self, vehicle_id, vehicle_name, tvar_id=None,
                             fraction=0.0, isheavy=0, istraffic=1):
        QgsMessageLog.logMessage(
            'add vehicle',
            'AirviroOfflineEdb',
            QgsMessageLog.INFO
        )

        table = self.widgets['vehicle_table'].widget
        table.blockSignals(True)

        table_row = table.rowCount()
        table.insertRow(table_row)

        tvar_id = tvar_id or self.timevars[0]['id']
        tvar_combo = QtGui.QComboBox()
        for tvar in self.timevars:
            tvar_combo.addItem(tvar['name'], tvar['id'])
        tvar_row_index = tvar_combo.findData(tvar_id)
        tvar_combo.setCurrentIndex(tvar_row_index)
        table.setCellWidget(table_row, 1, tvar_combo)

        item = QtGui.QTableWidgetItem(vehicle_name)
        item.setData(QtCore.Qt.UserRole, vehicle_id)
        item.setFlags(QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable)
        table.setItem(table_row, VEHICLE_COL, item)

        item = QtGui.QTableWidgetItem(unicode(fraction))
        table.setItem(
            table_row, FRACTION_COL, item
        )

        if isheavy:
            isheavy_text = 'Heavy'
        else:
            isheavy_text = 'Light'
        item = QtGui.QTableWidgetItem(isheavy_text)
        item.setTextColor(INACTIVE_COLOR)
        item.setData(QtCore.Qt.UserRole, isheavy)
        item.setFlags(QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable)
        table.setItem(table_row, ISHEAVY_COL, item)
        
        if istraffic:
            istraffic_text = 'yes'
        else:
            istraffic_text = 'no'

        item = QtGui.QTableWidgetItem(istraffic_text)
        item.setFlags(QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable)
        item.setTextColor(INACTIVE_COLOR)
        item.setData(QtCore.Qt.UserRole, istraffic)
        table.setItem(table_row, ISTRAFFIC_COL, item)
        self.widgets['vehicle_table'].validate(silent=True)
        table.blockSignals(False)

    def init_table(self, table):
        QgsMessageLog.logMessage(
            'init table',
            'AirviroOfflineEdb',
            QgsMessageLog.INFO
        )
        # clear table
        table.clearContents()
        while table.rowCount() > 0:
            table.removeRow(0)
        
        # set column width
        table_width = table.width()
        table.setColumnWidth(VEHICLE_COL, 0.3 * table_width)
        table.setColumnWidth(TIMEVAR_COL, 0.3 * table_width)
        table.setColumnWidth(FRACTION_COL, 0.125 * table_width)
        table.setColumnWidth(ISHEAVY_COL, 0.125 * table_width)
        table.setColumnWidth(ISTRAFFIC_COL, 0.123 * table_width)

        # add rows
        for ind, row in enumerate(self.on_road_vehicles):
            self.add_vehicle_to_table(
                row['vehicle'],
                row['name'],
                tvar_id=row['timevar'],
                fraction=row['fraction'],
                isheavy=row['isheavy'],
                istraffic=row['istraffic']
            )

        reconnect(table.itemChanged, self.validate_cell_item)

    @QtCore.pyqtSlot(int)
    def set_vehicle_meta(self, value):
        # combo = qApp.focusWidget()
        combo = self.sender()

        veh_id = combo.itemData(combo.currentIndex())
        isheavy, istraffic = self.con.execute(
            'SELECT isheavy, istraffic from road_vehicles WHERE id=%i' % veh_id
        ).next()

        if isheavy:
            isheavy = 'H'
        else:
            isheavy = 'L'

        table = self.widgets['vehicle_table'].widget
        table_index = table.indexAt(combo.parent().pos())
        table.setItem(
            table_index.row(), 3, QtGui.QTableWidgetItem(isheavy)
        )
        table.setItem(
            table_index.row(), 4, QtGui.QTableWidgetItem(unicode(istraffic))
        )

    def read_rsrc(self):
        rsrc_path = path.join(
            path.dirname(self.get_db_file()),
            'edb.rsrc'
        )
        rsrc = Rsrc(rsrc_path)

        self.gc = rsrc.gc
        

def formOpen(dialog, layerid, featureid):
    QgsMessageLog.logMessage(
        'opening form',
        'AirviroOfflineEdb',
        QgsMessageLog.INFO
    )

    form = RoadEditForm(
        dialog, layerid, featureid,
        msg_method='label',
        msg_widget='form_validation_msg_label'
    )
    form.load_data()
    form.find_widgets()
    form.init_widgets()
    form.validate()
    form.connect_signals()
