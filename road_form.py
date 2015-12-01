# -*- coding: utf-8 -*-

from qgis.core import QgsMessageLog
from PyQt4 import QtCore, QtGui
from functools import partial

from AirviroOfflineEdb.form_utils import (
    BaseFeatureForm,
    set_widget_style,
    init_default,
    validate_in_range,
    validate_is_not_empty,
    validate_of_type,
    validate_max_len,
    ValidationError
)

from pyAirviro.edb.sqliteapi import insert_sql
from pyAirviro.edb.sqliteapi import (
    NO_TRAFFIC_SITUATION_COLS
)


INVALID_STYLE = "background-color: rgba(255, 107, 107, 150);"
VALID_STYLE = ''
INACTIVE_COLOR = QtGui.QColor(100, 100, 100)

TIMEVAR_COL = 1
VEHICLE_COL = 0
FRACTION_COL = 2
ISHEAVY_COL = 3
ISTRAFFIC_COL = 4


def is_list(val_type, nvalues, widget):
    value_string = widget.text()
    try:
        values = map(val_type, value_string.split(' '))
    except:
        raise ValueError('value is not a list of integers')

    if nvalues is not None:
        if len(values) != nvalues:
            raise ValueError('should be %i values in list' % nvalues)

    return values


class RoadEditForm(BaseFeatureForm):

    def load_data(self):
        self.read_timevars()
        self.read_vehicles()
        self.read_on_road_vehicles()
        self.read_traffic_situations()

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
            on_invalid=partial(set_widget_style, INVALID_STYLE),
            on_valid=partial(set_widget_style, VALID_STYLE)
        )

        self.add_widget(
            'name',
            QtGui.QLineEdit,
            validators=[
                validate_is_not_empty,
                partial(validate_max_len, 47)
            ],
            on_invalid=partial(set_widget_style, INVALID_STYLE),
            on_valid=partial(set_widget_style, VALID_STYLE)
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
            on_invalid=partial(set_widget_style, INVALID_STYLE),
            on_valid=partial(set_widget_style, VALID_STYLE)
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
            init=partial(init_default, '2')
        )

        self.add_widget(
            'width',
            QtGui.QLineEdit,
            validators=[
                partial(validate_in_range, 3, 60),
                partial(validate_of_type, float)
            ],
            on_invalid=partial(set_widget_style, INVALID_STYLE),
            on_valid=partial(set_widget_style, VALID_STYLE)
        )

        self.add_widget(
            'disthouses',
            QtGui.QLineEdit,
            validators=[
                partial(validate_in_range, 3, 60),
                partial(validate_of_type, float)
            ],
            on_invalid=partial(set_widget_style, INVALID_STYLE),
            on_valid=partial(set_widget_style, VALID_STYLE)
        )

        self.add_widget(
            'height',
            QtGui.QLineEdit,
            validators=[
                partial(is_list, int, None)
            ],
            on_invalid=partial(set_widget_style, INVALID_STYLE),
            on_valid=partial(set_widget_style, VALID_STYLE)
        )

        self.add_widget(
            'vehicle_table',
            QtGui.QTableWidget,
            validators=[
                self.validate_vehicle_table
            ],
            on_invalid=self.show_validation_msg,
            on_valid=self.show_validation_msg,
            init=self.init_table
        )

        # self.add_widget(
        #     'ts_layout',
        #     QtGui.QHBoxLayout,
        #     init=self.init_ts_layout
        # )

        self.add_widget('ts_combo_6', QtGui.QComboBox)
        self.add_widget('ts_combo_6_label', QtGui.QLabel)

        self.add_widget(
            'ts_combo_5', QtGui.QComboBox,
            on_action=partial(self.filter_ts_combo, 6)
        )
        self.add_widget('ts_combo_5_label', QtGui.QLabel)

        self.add_widget(
            'ts_combo_4', QtGui.QComboBox,
            on_action=partial(self.filter_ts_combo, 5)
        )
        self.add_widget('ts_combo_4_label', QtGui.QLabel)

        self.add_widget(
            'ts_combo_3', QtGui.QComboBox,
            on_action=partial(self.filter_ts_combo, 4)
        )
        self.add_widget('ts_combo_3_label', QtGui.QLabel)

        self.add_widget(
            'ts_combo_2', QtGui.QComboBox,
            on_action=partial(self.filter_ts_combo, 3)
        )
        self.add_widget('ts_combo_2_label', QtGui.QLabel)

        self.add_widget(
            'ts_combo_1', QtGui.QComboBox,
            init=partial(self.init_ts_combo),
            on_action=partial(self.filter_ts_combo, 2)
        )
        self.add_widget('ts_combo_1_label', QtGui.QLabel)

        self.add_widget(
            'add_vehicle_btn',
            QtGui.QPushButton,
            on_action=self.on_add_vehicle_btn_clicked
        )
        self.add_widget(
            'delete_vehicle_btn',
            QtGui.QPushButton,
            on_action=self.on_delete_vehicle_btn_clicked
        )

        self.add_widget(
            'new_vehicle_combo',
            QtGui.QComboBox,
            init=partial(self.init_combo, self.vehicles)
        )

        self.add_widget(
            'validation_msg_label',
            QtGui.QLabel,
            init=partial(init_default, '')
        )

        self.add_widget(
            'reload_vehicles_btn',
            QtGui.QPushButton,
            on_action=self.on_reload_vehicles_btn_clicked
        )

    def show_validation_msg(self, widget, *args, **kwargs):
        msg = kwargs.get('message', '')
        label = self.widgets['validation_msg_label'].widget
        label.setText(msg)

    def init_widgets(self):
        QgsMessageLog.logMessage(
            'Connected dialog',
            'AirviroOfflineEdb',
            QgsMessageLog.INFO
        )

        super(RoadEditForm, self).init_widgets()

    def on_reload_vehicles_btn_clicked(self, *args, **kwargs):
        table = self.widgets['vehicle_table'].widget
        table.clearContents()
        while table.rowCount() > 0:
            table.removeRow(0)

        self.read_on_road_vehicles()
        self.init_table(table)

    @QtCore.pyqtSlot(QtGui.QTableWidgetItem)
    def validate_cell_item(self):
        self.widgets['vehicle_table'].validate()

    def on_add_vehicle_btn_clicked(self, *args, **kwargs):
        combo = self.widgets['new_vehicle_combo'].widget
        vehicle_name = combo.itemText(combo.currentIndex())
        vehicle_id = combo.itemData(combo.currentIndex())
        self.add_vehicle_to_table(vehicle_id, vehicle_name)

    def on_delete_vehicle_btn_clicked(self, *args, **kwargs):
        table = self.widgets['vehicle_table'].widget
        rows = table.selectionModel().selectedRows()
        for r in rows:
            table.removeRow(r.row())

    def validate_vehicle_table(self, *args, **kwargs):
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

    def load_related(self):
        table = self.widgets['vehicle_table'].widget

        self.con.commit()
        self.con.execute(
            'DELETE FROM road_vehicle_link WHERE road=%i' % self.feature.id()
        )
        self.con.commit()
        
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
    
    def init_ts_combo(self, widget):
        ndims = len(self.traffic_situation_cols)
        ts_indices = self.widgets['traffic_situation'].widget.ts_indices

        for i in range(ndims + 1, NO_TRAFFIC_SITUATION_COLS + 1):
            self.widgets['ts_combo_%i' % i].widget.hide()
            self.widgets['ts_combo_%i_label' % i].widget.hide()
        
        # disconnect not used combos
        self.widgets[
            'ts_combo_%i' % ndims
        ].widget.currentIndexChanged.disconnect()

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
            
            widget.ts_indices = [
                ts_indices[key] for key in ts_indices.keys()
                if key.startswith('situation') and ts_indices[key] is not None
            ]

    def add_vehicle_to_table(self, vehicle_id, vehicle_name, tvar_id=None,
                             fraction=0.0, isheavy=0, istraffic=1):
        table = self.widgets['vehicle_table'].widget
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
        table.itemChanged.connect(self.validate_cell_item)

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

    def init_table(self, table):
        # set column width
        table_width = table.width()
        table.setColumnWidth(VEHICLE_COL, 0.3 * table_width)
        table.setColumnWidth(TIMEVAR_COL, 0.3 * table_width)
        table.setColumnWidth(FRACTION_COL, 0.125 * table_width)
        table.setColumnWidth(ISHEAVY_COL, 0.125 * table_width)
        table.setColumnWidth(ISTRAFFIC_COL, 0.12 * table_width)

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


def formOpen(dialog, layerid, featureid):
    form = RoadEditForm(dialog, layerid, featureid)
    form.load_data()
    form.find_widgets()
    form.init_widgets()
    form.connect_signals()
