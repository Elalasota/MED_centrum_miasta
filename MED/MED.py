# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MED
                                 A QGIS plugin
 Wyznaczanie centrum miasta
                              -------------------
        begin                : 2015-01-18
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Ela Lasota
        email                : elcialas@gmail.com
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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QVariant, QDateTime, QPointF, QPoint, Qt 
from PyQt4.QtGui import QAction, QIcon, QColor, QBrush, QImage, QFileDialog, QWidget, QDialog
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from MED_dialog import MEDDialog
import os.path
from pymongo import MongoClient
from qgis.core import *
from qgis.utils import iface
import numpy as np
from decimal import Decimal
from sklearn.cluster import DBSCAN, AffinityPropagation
from sklearn import metrics
from sklearn.datasets.samples_generator import make_blobs
from sklearn.preprocessing import StandardScaler

class MED:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'MED_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = MEDDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Centrum miasta')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'MED')
        self.toolbar.setObjectName(u'MED')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('MED', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/MED/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Wyznacz centrum'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Centrum miasta'),
                action)
            self.iface.removeToolBarIcon(action)


    def run(self):
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.uklady.addItem("WGS84", "EPSG:4326")
        self.dlg.uklady.addItem("PL92", "EPSG:2180")
        self.dlg.uklady.addItem("Mercator", "EPSG:3857")
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
			kolekcja=self.dlg.lista.currentText()
			uklad=self.dlg.uklady.itemData(self.dlg.uklady.currentIndex())
			client=MongoClient()		#połączenie z klientem
			db=client.MED				#połączenie z bazą danych
			collection=db[kolekcja]	#połączenie z kolekcją zawierającą przystanki
			odl=Decimal(self.dlg.liniaodl.displayText())
			print odl
			gest=Decimal(self.dlg.liniag.displayText())
			warstwa=QgsVectorLayer("Point?index=yes&crs="+uklad,"Przystanki","memory")
			#warstwa.setCrs(QgsCoordinateReferenceSystem("EPSG:2180"))
			warstwa.startEditing()
			warstwa.addAttribute(QgsField("X", QVariant.Double))
			warstwa.addAttribute(QgsField("Y", QVariant.Double))
			i=0
			punkty=[]
			newCrs=QgsCoordinateReferenceSystem(uklad) 
			oldCrs=QgsCoordinateReferenceSystem("EPSG:4326")
			transformacja=QgsCoordinateTransform(oldCrs, newCrs)
			
			for el in collection.find():
				obiekt=QgsFeature(warstwa.pendingFields(), i)
				wsp=el['geometry']['coordinates']
				x=wsp[0]
				y=wsp[1]
				punkt_nowy=transformacja.transform(QgsPoint(x,y))
				obiekt.setGeometry(QgsGeometry.fromPoint(punkt_nowy))
				x=punkt_nowy.x()
				y=punkt_nowy.y()
				wsp=[x,y]
				punkty.append(wsp)
				obiekt.setAttribute(warstwa.fieldNameIndex("X"),x)
				obiekt.setAttribute(warstwa.fieldNameIndex("Y"),y)
				warstwa.addFeature(obiekt)
				i=i+1
				#print x	
			warstwa.commitChanges()
			bbox=warstwa.extent()
			if uklad=="EPSG:3857":
				urlWithParams ='crs=EPSG:3857&dpiMode=7&featureCount=10&format=image/png&layers=osm&styles=&url=http://irs.gis-lab.info/?layers%3Dosm%26'
			elif uklad=="EPSG:4326":
				urlWithParams ='crs=EPSG:4326&dpiMode=7&featureCount=10&format=image/png&layers=osm&styles=&url=http://irs.gis-lab.info/?layers%3Dosm%26'
			else:
				urlWithParams ='crs=EPSG:2180&dpiMode=7&featureCount=10&format=image/jpeg&layers=Raster&styles=default&url=http://mapy.geoportal.gov.pl/wss/service/img/guest/ORTO/MapServer/WMSServer'
			rlayer=QgsRasterLayer(urlWithParams, 'Podklad', 'wms')
			QgsMapLayerRegistry.instance().addMapLayer(rlayer)
			if not rlayer.isValid():
				print "Layer failed to load!"
			symbol=QgsSymbolV2.defaultSymbol(warstwa.geometryType())
			styl=QgsSimpleMarkerSymbolLayerV2("circle",QColor("#F8FF8A"))
			symbol.appendSymbolLayer(styl)
			symbol.deleteSymbolLayer(0)
			sr=QgsSingleSymbolRendererV2(symbol)
			warstwa.setRendererV2(sr)
			iface.mapCanvas().refresh()
			QgsMapLayerRegistry.instance().addMapLayer(warstwa)
			warstwa.updateExtents()
			punkty=np.array(punkty)
			print punkty
			db=DBSCAN(eps=odl, min_samples=gest).fit(punkty)
			#db= AffinityPropagation(preference=-50).fit(punkty)
			labels = db.labels_
			
			liczba_klastrow=len(set(labels)) - (1 if -1 in labels else 0)
			print liczba_klastrow
			for i in xrange(0,liczba_klastrow):
				klaster=QgsVectorLayer("Point?index=yes&crs="+warstwa.crs().authid(),"Klaster "+str(i),"memory")
				ajdi=0
				klaster.startEditing()
				klaster.addAttribute(QgsField("X", QVariant.Double))
				klaster.addAttribute(QgsField("Y", QVariant.Double))
				for numer in xrange(0,len(labels)):
					if labels[numer]==i:
						print labels[numer]
						obiekt=QgsFeature(klaster.pendingFields(), ajdi)
						print punkty[numer][0]
						x=punkty[numer][0]
						y=punkty[numer][1]
						obiekt.setGeometry(QgsGeometry.fromPoint(QgsPoint(x,y)))
						obiekt.setAttribute(klaster.fieldNameIndex("X"),x)
						obiekt.setAttribute(klaster.fieldNameIndex("Y"),y)
						klaster.addFeature(obiekt)
						ajdi=ajdi+1
				klaster.commitChanges()
				QgsMapLayerRegistry.instance().addMapLayer(klaster)
				
				klaster.updateExtents()
				iface.mapCanvas().setExtent(bbox)
				



