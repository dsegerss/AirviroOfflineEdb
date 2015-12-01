# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AirviroOfflineEdbDockWidget
                                 A QGIS plugin
 Editing Airviro emission databases offline
                             -------------------
        begin                : 2015-11-10
        git sha              : $Format:%H$
        copyright            : (C) 2015 by David Segersson
        email                : david.segersson@smhi.se
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from __future__ import unicode_literals
from __future__ import division

import os

# import qgis first to ensure sip.api is set for QString and QVariant
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsDataSourceURI,
    QgsMapLayerRegistry,
    QgsMapLayer,
    QgsRelation,
    QgsCoordinateReferenceSystem,
    QgsMessageLog
)

from qgis.gui import QgsMessageBar
from qgis.utils import iface

from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QFileDialog, QDockWidget

from pyAirviro.edb.edb import Edb, SerialEdb, is_complete_serial_edb
from pyAirviro.edb.sqliteapi import (
    connect,
    get_epsg,
    get_foreign_keys,
    load_edb,
    initdb,
    create_emission_views,
    create_emission_tables,
    TABLES,
    GEOMETRY_TABLES_COLUMNS,
    table_in_db
)


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qgis_edb_dockwidget_base.ui'))


class AirviroOfflineEdbDockWidget(QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(AirviroOfflineEdbDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.create_db_lineedit.clear()
        self.create_db_browse_btn.clicked.connect(
            self.select_save_db_filename
        )

        self.open_db_lineedit.clear()
        self.open_db_browse_btn.clicked.connect(
            self.select_open_db_filename
        )

        self.open_edb_btn.clicked.connect(
            self.open_db
        )

        self.db_uri = QgsDataSourceURI()
        self.con = None
        self.cur = None
        self.epsg = None
        self.layers = {}

    def select_save_db_filename(self):
        filename = QFileDialog.getSaveFileName(
            self,
            "Select offline edb",
            "",
            '*.sqlite'
        )
        self.create_db_lineedit.setText(filename)

    def select_open_db_filename(self):
        filename = QFileDialog.getOpenFileName(
            self,
            "Select offline edb",
            "",
            '*.sqlite'
        )
        self.open_db_lineedit.setText(filename)

    def open_db(self):
        edb_filename = self.open_db_lineedit.text()
        edb_name, ext = os.path.splitext(os.path.basename(str(edb_filename)))
        QgsMessageLog.logMessage(
            "Loading edb %s" % edb_filename,
            'AirviroOfflineEdb',
            QgsMessageLog.INFO
        )

        self.db_uri.setDatabase(edb_filename)
        self.con, self.cur = connect(str(self.db_uri.database()))
        self.epsg = get_epsg(self.con)

        root = QgsProject.instance().layerTreeRoot()

        edb_increment = 1
        while root.findGroup(edb_name) is not None:
            edb_name = edb_name + unicode(edb_increment)
            edb_increment += 1

        QgsMessageLog.logMessage(
            "Adding edb layers in %s" % edb_name,
            'AirviroOfflineEdb',
            QgsMessageLog.INFO
        )
        edb_group = root.addGroup(edb_name)

        point_group = edb_group.addGroup('Point sources')
        area_group = edb_group.addGroup('Area sources')
        grid_group = edb_group.addGroup('Grid sources')
        road_group = edb_group.addGroup('Road sources')
        subtable_group = edb_group.addGroup('Subtables')
        company_group = edb_group.addGroup('Companies')
        facility_group = edb_group.addGroup('Facilities')
        emis_group = edb_group.addGroup('Emissions')

        point_support_group = point_group.addGroup('Support tables')
        area_support_group = area_group.addGroup('Support tables')
        grid_support_group = grid_group.addGroup('Support tables')
        road_support_group = road_group.addGroup('Support tables')
        facility_support_group = facility_group.addGroup('Support tables')
        company_support_group = company_group.addGroup('Support tables')

        unit_group = subtable_group.addGroup('Units')
        road_vehicle_group = subtable_group.addGroup('Road vehicles')
        road_vehicle_support_group = road_vehicle_group.addGroup(
            'Support tables'
        )
        roadtype_group = subtable_group.addGroup('Roadtypes')
        emis_func_group = subtable_group.addGroup('Emission functions')
        searchkey_group = subtable_group.addGroup('Searchkeys')
        timevar_group = subtable_group.addGroup('Time variations')
        subgrp_group = subtable_group.addGroup('Substance groups')
        
        self.layers = {}
        schema = ''
        geom_table_column_dict = dict(GEOMETRY_TABLES_COLUMNS)
        for table in TABLES:
            if not table_in_db(self.cur, table):
                iface.messageBar().pushMessage(
                    "Warning",
                    "Table %s not found in edb" % table,
                    level=QgsMessageBar.WARNING,
                    duration=3
                )
                continue
            geom_col = geom_table_column_dict.get(table, None)
            self.db_uri.setDataSource(
                schema,
                table,
                geom_col or ''
            )
            layer_uri = self.db_uri.uri()  # + "&crs=EPSG:4326"
            layer = QgsVectorLayer(layer_uri, table, 'spatialite')
            layer.setCrs(QgsCoordinateReferenceSystem(
                self.epsg,
                QgsCoordinateReferenceSystem.EpsgCrsId)
            )
            if not layer.isValid():
                raise ValueError(edb_filename)
            map_layer = QgsMapLayerRegistry.instance().addMapLayer(
                layer, False
            )
                        
            if 'timevar' in table:
                group = timevar_group
            elif 'emission_function' in table:
                group = emis_func_group
            elif 'searchkey' in table:
                group = searchkey_group
            elif 'unit' in table:
                group = unit_group
            elif 'subgrp' in table:
                group = subgrp_group
            elif table == 'substances':
                group = subtable_group
            elif table.endswith('_emis'):
                group = emis_group
            elif table == 'points':
                group = point_group
            elif 'point_' in table:
                group = point_support_group
            elif table == 'areas':
                group = area_group
            elif 'area_' in table:
                group = area_support_group
            elif table == 'roads':
                group = road_group
            elif table in ('road_vehicle_link', 'road_alobs'):
                group = road_support_group
            elif 'road_' in table:
                group = road_vehicle_group
            elif 'roadtype' in table:
                group = roadtype_group
            elif table == 'facilties':
                group = facility_group
            elif 'facility' in table:
                group = facility_support_group
            elif 'companies' == table:
                group = company_group
            elif 'company' in table:
                group = company_support_group
            elif 'traffic_situation' in table:
                group = road_vehicle_support_group

            group.setVisible(False)
            group.setExpanded(False)
            group.addLayer(map_layer)
            self.layers[table] = map_layer.id()

        for table in TABLES:
            foreign_keys = get_foreign_keys(self.con, table)
            referencing_layer = self.layers[table]
            for row in foreign_keys:
                referenced_layer = self.layers[row['table']]
                from_column = row['from']
                to_column = row['to']
                
                rel = QgsRelation()
                rel.setReferencingLayer(referencing_layer)
                rel.setReferencedLayer(referenced_layer)
                rel.addFieldPair(from_column, to_column)
                rel_name = 'fk_%s_%s-%s_%s' % (
                    table, from_column, row['table'], to_column
                )
                rel.setRelationId(rel_name)
                rel.setRelationName(
                    'fk_%s_%s-%s_%s' % (
                        table, from_column, row['table'], to_column)
                )
                
                if not rel.isValid():
                    raise ValueError(
                        'Reference %s is invalid' % rel_name
                    )
                QgsProject.instance().relationManager().addRelation(rel)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
