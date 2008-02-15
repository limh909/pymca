#!/usr/bin/env python
#/*##########################################################################
# Copyright (C) 2004-2008 European Synchrotron Radiation Facility
#
# This file is part of the PyMCA X-ray Fluorescence Toolkit developed at
# the ESRF by the Beamline Instrumentation Software Support (BLISS) group.
#
# This toolkit is free software; you can redistribute it and/or modify it 
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option) 
# any later version.
#
# PyMCA is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# PyMCA; if not, write to the Free Software Foundation, Inc., 59 Temple Place,
# Suite 330, Boston, MA 02111-1307, USA.
#
# PyMCA follows the dual licensing model of Trolltech's Qt and Riverbank's PyQt
# and cannot be used as a free plugin for a non-free program. 
#
# Please contact the ESRF industrial unit (industry@esrf.fr) if this license 
# is a problem for you.
#############################################################################*/
import sys
import McaWindow
qt = McaWindow.qt
QTVERSION = qt.qVersion()
if QTVERSION > '4.0.0':
    import RGBCorrelator
    from RGBCorrelatorWidget import ImageShapeDialog
import RGBCorrelatorGraph
from PyMca_Icons import IconDict
import DataObject
import EDFStack
import SpecFileStack
import numpy.oldnumeric as Numeric
import numpy
import ColormapDialog
import spslut
import os
import PyMcaDirs
import SpecfitFuns
import time
try:
    import QPyMcaMatplotlibSave
    MATPLOTLIB = True
except ImportError:
    MATPLOTLIB = False
import OmnicMap
import LuciaMap

COLORMAPLIST = [spslut.GREYSCALE, spslut.REVERSEGREY, spslut.TEMP,
                spslut.RED, spslut.GREEN, spslut.BLUE, spslut.MANY]
QWTVERSION4 = RGBCorrelatorGraph.QtBlissGraph.QWTVERSION4

if QWTVERSION4:
    raise "ImportError","QEDFStackWidget needs Qwt5"

if QTVERSION > '4.0.0':
    import PyQt4.Qwt5 as Qwt
else:
    import Qwt5 as Qwt


DEBUG = 0

class MyPicker(Qwt.QwtPlotPicker):
    def __init__(self, *var):
        Qwt.QwtPlotPicker.__init__(self, *var)
        self.__text = Qwt.QwtText()
        self.data = None

    def trackerText(self, var):
        d=self.invTransform(var)
        if self.data is None:
            self.__text.setText("%g, %g" % (d.x(), d.y()))
        else:
            limits = self.data.shape
            x = round(d.y())
            y = round(d.x())
            if x < 0: x = 0
            if y < 0: y = 0
            x = min(int(x), limits[0]-1)
            y = min(int(y), limits[1]-1)
            z = self.data[x, y]
            self.__text.setText("%d, %d, %.4g" % (y, x, z))
        return self.__text

class SimpleThread(qt.QThread):
    def __init__(self, function, *var, **kw):
        if kw is None:kw={}
        qt.QThread.__init__(self)
        self._function = function
        self._var      = var
        self._kw       = kw
        self._result   = None
    
    def run(self):
        if DEBUG:
            self._result = self._function(*self._var, **self._kw )
        else:
            try:
                self._result = self._function(*self._var, **self._kw )
            except:
                self._result = ("Exception",) + sys.exc_info()

class QSpecFileStack(SpecFileStack.SpecFileStack):
    def onBegin(self, nfiles):
        self.bars =qt.QWidget()
        if QTVERSION < '4.0.0':
            self.bars.setCaption("Reading progress")
            self.barsLayout = qt.QGridLayout(self.bars,2,3)
        else:
            self.bars.setWindowTitle("Reading progress")
            self.barsLayout = qt.QGridLayout(self.bars)
            self.barsLayout.setMargin(2)
            self.barsLayout.setSpacing(3)
        self.progressBar   = qt.QProgressBar(self.bars)
        self.progressLabel = qt.QLabel(self.bars)
        self.progressLabel.setText('Mca Progress:')
        self.barsLayout.addWidget(self.progressLabel,0,0)        
        self.barsLayout.addWidget(self.progressBar,0,1)
        if QTVERSION < '4.0.0':
            self.progressBar.setTotalSteps(nfiles)
            self.progressBar.setProgress(0)
        else:
            self.progressBar.setMaximum(nfiles)
            self.progressBar.setValue(0)
        self.bars.show()

    def onProgress(self,index):
        if QTVERSION < '4.0.0':
            self.progressBar.setProgress(index)
        else:
            self.progressBar.setValue(index)

    def onEnd(self):
        self.bars.hide()
        del self.bars

class QStack(EDFStack.EDFStack):
    def onBegin(self, nfiles):
        self.bars =qt.QWidget()
        if QTVERSION < '4.0.0':
            self.bars.setCaption("Reading progress")
            self.barsLayout = qt.QGridLayout(self.bars,2,3)
        else:
            self.bars.setWindowTitle("Reading progress")
            self.barsLayout = qt.QGridLayout(self.bars)
            self.barsLayout.setMargin(2)
            self.barsLayout.setSpacing(3)
        self.progressBar   = qt.QProgressBar(self.bars)
        self.progressLabel = qt.QLabel(self.bars)
        self.progressLabel.setText('File Progress:')
        self.barsLayout.addWidget(self.progressLabel,0,0)        
        self.barsLayout.addWidget(self.progressBar,0,1)
        if QTVERSION < '4.0.0':
            self.progressBar.setTotalSteps(nfiles)
            self.progressBar.setProgress(0)
        else:
            self.progressBar.setMaximum(nfiles)
            self.progressBar.setValue(0)
        self.bars.show()

    def onProgress(self,index):
        if QTVERSION < '4.0.0':
            self.progressBar.setProgress(index)
        else:
            self.progressBar.setValue(index)

    def onEnd(self):
        self.bars.hide()
        del self.bars

class QEDFStackWidget(qt.QWidget):
    def __init__(self, parent = None,
                 mcawidget = None,
                 rgbwidget = None,
                 vertical = False,
                 master = True):
        qt.QWidget.__init__(self, parent)
        if QTVERSION < '4.0.0':
            self.setIcon(qt.QPixmap(IconDict['gioconda16']))
            self.setCaption("PyMCA - ROI Imaging Tool")
        else:
            self.setWindowIcon(qt.QIcon(qt.QPixmap(IconDict['gioconda16'])))
            self.setWindowTitle("PyMCA - ROI Imaging Tool")
            screenHeight = qt.QDesktopWidget().height()
            if screenHeight > 0:
                self.setMaximumHeight(int(0.99*screenHeight))
                self.setMinimumHeight(int(0.5*screenHeight))
            screenWidth = qt.QDesktopWidget().width()
            if screenWidth > 0:
                self.setMaximumWidth(int(screenWidth)-5)
                self.setMinimumWidth(min(int(0.5*screenWidth),800))
        self.mainLayout = qt.QVBoxLayout(self)
        self.mainLayout.setMargin(6)
        self.mainLayout.setSpacing(0)
        self._y1AxisInverted = False
        self.__stackImageData = None
        self.__ROIImageData  = None
        self.__ROIImageBackground  = None
        self.__stackBackgroundCounter = 0
        self.__stackBackgroundAnchors = None
        self.__stackColormap = None
        self.__stackColormapDialog = None
        self.__ROIColormap       = None
        self.__ROIColormapDialog = None
        self.mcaWidget = mcawidget
        self.rgbWidget = rgbwidget
        if QTVERSION < '4.0.0':master = False
        self.master = master
        self.slave  = None
        self.tab = None

        self._build(vertical)
        self._buildBottom()
        self.__ROIBrushMenu  = None
        self.__ROIBrushMode  = False
        self.__ROIEraseMode  = False
        self.__ROIConnected = True

        self.__setROIBrush2()
        self._buildConnections()

        self._matplotlibSaveImage = None
        
    def _build(self, vertical = False):
        box = qt.QSplitter(self)
        if vertical:
            box.setOrientation(qt.Qt.Vertical)
        else:
            box.setOrientation(qt.Qt.Horizontal)
        #boxLayout.setMargin(0)
        #boxLayout.setSpacing(6)
        self.stackWindow = qt.QWidget(box)
        self.stackWindow.mainLayout = qt.QVBoxLayout(self.stackWindow)
        self.stackWindow.mainLayout.setMargin(0)
        self.stackWindow.mainLayout.setSpacing(0)
        self.stackGraphWidget = RGBCorrelatorGraph.RGBCorrelatorGraph(self.stackWindow,
                                                            colormap=True)

        infotext  = 'If checked, spectra will be added normalized to the number\n'
        infotext += 'of pixels. Be carefull if you are preparing a batch and you\n'
        infotext += 'fit the normalized spectra because the data in the batch will\n'
        infotext += 'have a different weight because they are not normalized.'
        self.normalizeIcon = qt.QIcon(qt.QPixmap(IconDict["normalize16"]))  
        self.normalizeButton = self.stackGraphWidget._addToolButton(\
                                        self.normalizeIcon,
                                        self.normalizeIconChecked,
                                        infotext,
                                        toggle = True,
                                        state = False,
                                        position = 6)
        infotext  = 'Remove background from current stack using current\n'
        infotext += 'ROI markers as anchors.\n'
        infotext += 'WARNING: Very slow. 0.01 to 0.02 seconds per pixel.\n'
        infotext += 'Not recommended  unless you really need a  better\n'
        infotext += 'contrast to place your ROIs and you know what you\n'
        infotext += 'are doing.\n'
        infotext += 'The ROI background subtraction is more efficient.\n'
        self.backgroundIcon = qt.QIcon(qt.QPixmap(IconDict["subtract"]))  
        self.backgroundButton = self.stackGraphWidget._addToolButton(\
                                        self.backgroundIcon,
                                        self.submitThread,
                                        #self.subtractBackground,
                                        infotext,
                                        position = 7)
        if self.master:
            self.loadIcon = qt.QIcon(qt.QPixmap(IconDict["fileopen"]))  
            self.loadStackButton = self.stackGraphWidget._addToolButton(\
                                        self.loadIcon,
                                        self.loadSlaveStack,
                                        'Load another stack of same size',
                                        position = 8)
        
        self.roiWindow = qt.QWidget(box)
        self.roiWindow.mainLayout = qt.QVBoxLayout(self.roiWindow)
        self.roiWindow.mainLayout.setMargin(0)
        self.roiWindow.mainLayout.setSpacing(0)
        standaloneSaving = True
        if QTVERSION > '4.0.0':
            if MATPLOTLIB:
                standaloneSaving = False
        self.roiGraphWidget = RGBCorrelatorGraph.RGBCorrelatorGraph(self.roiWindow,
                                                                selection = True,
                                                                colormap=True,
                                                                imageicons=True,
                                                                standalonesave=standaloneSaving)
        if not standaloneSaving:
            self.connect(self.roiGraphWidget.saveToolButton,
                         qt.SIGNAL("clicked()"), 
                         self._roiSaveToolButtonSignal)
            self._roiSaveMenu = qt.QMenu()
            self._roiSaveMenu.addAction(qt.QString("Standard"),    self.roiGraphWidget._saveIconSignal)
            self._roiSaveMenu.addAction(qt.QString("Matplotlib") , self._roiSaveMatplotlibImage)

        if QTVERSION > '4.0.0':
            infotext  = 'Toggle background subtraction from current image\n'
            infotext += 'subtracting a straight line between the ROI limits.'
            self.roiBackgroundIcon = qt.QIcon(qt.QPixmap(IconDict["subtract"]))  
            self.roiBackgroundButton = self.roiGraphWidget._addToolButton(\
                                        self.roiBackgroundIcon,
                                        self.roiSubtractBackground,
                                        infotext,
                                        toggle = True,
                                        state = False,
                                        position = 6)
        
        self.roiGraphWidget.picker = MyPicker(Qwt.QwtPlot.xBottom,
                               Qwt.QwtPlot.yLeft,
                               Qwt.QwtPicker.NoSelection,
                               Qwt.QwtPlotPicker.CrossRubberBand,
                               Qwt.QwtPicker.AlwaysOn,
                               self.roiGraphWidget.graph.canvas())
        self.roiGraphWidget.picker.setTrackerPen(qt.Qt.black)
        self.roiGraphWidget.graph.enableSelection(False)
        self.roiGraphWidget.graph.enableZoom(True)
        self.setROISelectionMode(False)
        self._toggleROISelectionMode()
        self.stackWindow.mainLayout.addWidget(self.stackGraphWidget)
        self.roiWindow.mainLayout.addWidget(self.roiGraphWidget)
        if QTVERSION < '4.0.0':
            box.moveToLast(self.stackWindow)
            box.moveToLast(self.roiWindow)
        else:
            box.addWidget(self.stackWindow)
            box.addWidget(self.roiWindow)
        self.mainLayout.addWidget(box)

    def normalizeIconChecked(self):
        pass

    def submitThread(self):
        try:
            threadResult = self._submitThread()
            if type(threadResult) == type((1,)):
                if len(threadResult):
                    if threadResult[0] == "Exception":
                        raise threadResult[1],threadResult[2]
            self.originalPlot()
            #self.mcaWidget.graph.newcurve("background", Numeric.arange(len(self.b)), self.b)
            #self.mcaWidget.graph.replot()
        except:
            msg = qt.QMessageBox(self)
            msg.setIcon(qt.QMessageBox.Critical)
            msg.setText("%s" % sys.exc_info()[1])
            if QTVERSION < '4.0.0':
                msg.exec_loop()
            else:
                msg.exec_()

            
    def _submitThread(self, *var, **kw):
        message = "Please Wait: Calculating background"
        sthread = SimpleThread(self.subtractBackground,
                                *var, **kw)        
        sthread.start()
        if QTVERSION < '3.0.0':
            msg = qt.QDialog(self, "Please Wait", False,qt.Qt.WStyle_NoBorder)            
        elif QTVERSION < '4.0.0':
            msg = qt.QDialog(self, "Please Wait", 1,qt.Qt.WStyle_NoBorder)
        else:
            if 0:
                msg = qt.QDialog(self, qt.Qt.FramelessWindowHint)
                msg.setModal(0)
            else:
                msg = qt.QDialog(self, qt.Qt.FramelessWindowHint)
                msg.setModal(1)
            msg.setWindowTitle("Please Wait")
        layout = qt.QHBoxLayout(msg)
        layout.setMargin(0)
        layout.setSpacing(0)
        l1 = qt.QLabel(msg)
        l1.setFixedWidth(l1.fontMetrics().width('##'))
        l2 = qt.QLabel(msg)
        l2.setText("%s" % message)
        l3 = qt.QLabel(msg)
        l3.setFixedWidth(l3.fontMetrics().width('##'))
        layout.addWidget(l1)
        layout.addWidget(l2)
        layout.addWidget(l3)
        msg.show()
        qt.qApp.processEvents()
        t0 = time.time()
        i = 0
        ticks = ['-','\\', "|", "/","-","\\",'|','/']
        if QTVERSION < '4.0.0':
            while (sthread.running()):
                i = (i+1) % 8
                l1.setText(ticks[i])
                l3.setText(" "+ticks[i])
                qt.qApp.processEvents()
                time.sleep(2)
            msg.close(True)
        else:
            while (sthread.isRunning()):
                i = (i+1) % 8
                l1.setText(ticks[i])
                l3.setText(" "+ticks[i])
                qt.qApp.processEvents()
                time.sleep(2)
            msg.close()
        result = sthread._result
        del sthread
        if QTVERSION < '4.0.0':
            self.raiseW()
        else:
            self.raise_()
        return result

    def _roiSaveToolButtonSignal(self):
        self._roiSaveMenu.exec_(self.cursor().pos())

    def _roiSaveMatplotlibImage(self):
        if self._matplotlibSaveImage is None:
            self._matplotlibSaveImage = QPyMcaMatplotlibSave.SaveImageSetup(None,
                                                            self.__ROIImageData)
            self._matplotlibSaveImage.setWindowTitle("Matplotlib ROI Image")
        else:
            self._matplotlibSaveImage.setImageData(self.__ROIImageData)
        self._matplotlibSaveImage.show()
        self._matplotlibSaveImage.raise_()    

    def subtractBackground(self):
        if 0:
            fitconfig   = self.mcaWidget.advancedfit.mcafit.config
            constant    = fitconfig['fit'].get('stripconstant', 1.0)
            iterations  = int(fitconfig['fit'].get('stripiterations',4000)/2)
            width       = fitconfig['fit'].get('stripwidth', 4)
            filterwidth = fitconfig['fit'].get('stripfilterwidth', 10)
            anchorsflag = fitconfig['fit'].get('stripanchorsflag', 0)
        constant    = 1.0
        iterations  = 1000
        if self.__stackBackgroundCounter == 0:
            width       = 8
        elif self.__stackBackgroundCounter == 1:
            width       = 4
        else:
            width       = 2
        self.__stackBackgroundCounter += 1
        if self.__stackBackgroundAnchors is not None:
            anchorslist = self.__stackBackgroundAnchors
        else:
            anchorslist = []
        shape = self.stack.data.shape

        if DEBUG:t0 = time.time()
        if self.fileIndex == 0:
            if self.mcaIndex == 1:
                for i in range(shape[0]):
                    for j in range(shape[2]):
                        data = self.stack.data[i, :, j]
                        #data = SpecfitFuns.SavitskyGolay(data, filterwidth)
                        data = SpecfitFuns.subacfast(data,
                                                     constant,
                                                     iterations,
                                                     width,
                                                     anchorslist)
                        data = SpecfitFuns.subacfast(data,
                                                     constant,
                                                     500,
                                                     1,
                                                     anchorslist)
                        self.stack.data[i, :, j] -= data
            else:
                #self.b = 0 *  self.stack.data[0, 0, :]
                for i in range(shape[0]):
                    for j in range(shape[1]):
                        data = self.stack.data[i, j, :]
                        #data = SpecfitFuns.SavitskyGolay(data, filterwidth)
                        data = SpecfitFuns.subacfast(data,
                                                     constant,
                                                     iterations,
                                                     width,
                                                     anchorslist)
                        data = SpecfitFuns.subacfast(data,
                                                     constant,
                                                     500,
                                                     1,
                                                     anchorslist)                        
                        self.stack.data[i, j, :] -= data
                        #self.b += data
        else:
            #self.fileIndex = 2
            if self.mcaIndex == 0:
                for i in range(shape[1]):
                    for j in range(shape[2]):
                        data = self.stack.data[:, i, j]
                        #data = SpecfitFuns.SavitskyGolay(data, filterwidth)
                        data = SpecfitFuns.subacfast(data,
                                                     constant,
                                                     iterations,
                                                     width,
                                                     anchorslist)
                        data = SpecfitFuns.subacfast(data,
                                                     constant,
                                                     500,
                                                     1,
                                                     anchorslist)                        
                        self.stack.data[:, i, j] -= data
            else:
                for i in range(shape[0]):
                    for j in range(shape[2]):
                        data = self.stack.data[i, :, j]
                        #data = SpecfitFuns.SavitskyGolay(data, filterwidth)
                        data = SpecfitFuns.subacfast(data,
                                                     constant,
                                                     iterations,
                                                     width,
                                                     anchorslist)
                        data = SpecfitFuns.subacfast(data,
                                                     constant,
                                                     500,
                                                     1,
                                                     anchorslist)
                        self.stack.data[i, :, j] -= data
        if DEBUG:print "elapsed = ", time.time() - t0
        #self.originalPlot()

    def roiSubtractBackground(self):
        if self.__ROIImageData is None: return
        if self.__ROIImageBackground is None: return
        if self.roiBackgroundButton.isChecked():
            self.__ROIImageData =  self.__ROIImageData - self.__ROIImageBackground
            self.roiGraphWidget.graph.setTitle(self.roiGraphWidget.__title + " Net")
        else:
            self.__ROIImageData =  self.__ROIImageData + self.__ROIImageBackground
            self.roiGraphWidget.graph.setTitle(self.roiGraphWidget.__title)
        if self.__ROIColormapDialog is not None:
            minData = self.__ROIImageData.min()
            maxData = self.__ROIImageData.max()
            self.__ROIColormapDialog.setDataMinMax(minData, maxData)
        self.plotROIImage(update = True)

    def loadSlaveStack(self):
        if self.slave is None:
            filelist = self._getStackOfFiles()
            if not(len(filelist)): return
            filelist.sort()
            
            PyMcaDirs.inputDir = os.path.dirname(filelist[0])
            
            self.slave = QEDFStackWidget(rgbwidget=self.rgbWidget,
                                         master=False)
            try:
                self.slave.setStack(QStack(filelist))
            except:
                self.slave.setStack(QSpecFileStack(filelist))
            self._buildConnections(self.slave)
            self.slave._buildConnections(self)

        if self.slave is not None:
            self.loadStackButton.hide()
            self.slave.show()
            return
    
    def _buildBottom(self):
        n = 0
        if self.mcaWidget is None: n += 1
        if (QTVERSION > '4.0.0') and  (self.rgbWidget is None): n += 1
        if n == 1:
            if self.mcaWidget is None:
                self.mcaWidget = McaWindow.McaWidget(self, vertical = False)
                if QTVERSION < '4.0.0':
                    self.mcaWidget.setCaption("PyMCA - Mca Window")
                else:
                    self.mcaWidget.setWindowTitle("PyMCA - Mca Window")
                self.mainLayout.addWidget(self.mcaWidget)
            if self.rgbWidget is None:
                if QTVERSION > '4.0.0':
                    #I have not implemented it for Qt3
                    #self.rgbWidget = RGBCorrelator.RGBCorrelator()
                    self.rgbWidget = RGBCorrelator.RGBCorrelator(self)
                    self.mainLayout.addWidget(self.rgbWidget)
            return
        if n == 2:
            self.tab = qt.QTabWidget(self)
            self.mcaWidget = McaWindow.McaWidget(vertical = False)
            if QTVERSION > '4.0.0':
                self.mcaWidget.graphBox.setMinimumWidth(0.5 * qt.QWidget.sizeHint(self).width())
                self.tab.setMaximumHeight(1.3 * qt.QWidget.sizeHint(self).height())
                self.mcaWidget.setWindowTitle("PyMCA - Mca Window")
            self.tab.addTab(self.mcaWidget, "MCA")
            if QTVERSION > '4.0.0':
                #I have not implemented it for Qt3
                #self.rgbWidget = RGBCorrelator.RGBCorrelator()
                self.rgbWidget = RGBCorrelator.RGBCorrelator()
                self.tab.addTab(self.rgbWidget, "RGB Correlator")
            self.mainLayout.addWidget(self.tab)
        
    def _toggleROISelectionMode(self):
        if self.roiGraphWidget.graph._selecting:
            self.setROISelectionMode(False)
        else:
            self.setROISelectionMode(True)


    def setROISelectionMode(self, mode = None):
        if mode:
            self.roiGraphWidget.graph.enableSelection(True)
            self.__ROIBrushMode  = False
            self.roiGraphWidget.picker.setTrackerMode(Qwt.QwtPicker.AlwaysOn)
            self.roiGraphWidget.graph.enableZoom(False)
            if QTVERSION < '4.0.0':
                self.roiGraphWidget.selectionToolButton.setState(qt.QButton.On)
            else:
                self.roiGraphWidget.selectionToolButton.setChecked(True)
            self.roiGraphWidget.selectionToolButton.setDown(True)
            self.roiGraphWidget.showImageIcons()
            
        else:
            self.roiGraphWidget.graph.enableZoom(True)
            if QTVERSION < '4.0.0':
                self.roiGraphWidget.selectionToolButton.setState(qt.QButton.Off)
            else:
                self.roiGraphWidget.selectionToolButton.setChecked(False)
            self.roiGraphWidget.selectionToolButton.setDown(False)
            self.roiGraphWidget.hideImageIcons()
            #self.plotStackImage(update = True)
            #self.plotROIImage(update = True)
        if self.__stackImageData is None: return
        #do not reset the selection
        #self.__selectionMask = Numeric.zeros(self.__stackImageData.shape, Numeric.UInt8)
            
    def _buildAndConnectButtonBox(self):
        #the MCA selection
        self.mcaButtonBox = qt.QWidget(self.stackWindow)
        self.mcaButtonBoxLayout = qt.QHBoxLayout(self.mcaButtonBox)
        self.mcaButtonBoxLayout.setMargin(0)
        self.mcaButtonBoxLayout.setSpacing(0)
        self.addMcaButton = qt.QPushButton(self.mcaButtonBox)
        self.addMcaButton.setText("ADD MCA")
        self.removeMcaButton = qt.QPushButton(self.mcaButtonBox)
        self.removeMcaButton.setText("REMOVE MCA")
        self.replaceMcaButton = qt.QPushButton(self.mcaButtonBox)
        self.replaceMcaButton.setText("REPLACE MCA")
        self.mcaButtonBoxLayout.addWidget(self.addMcaButton)
        self.mcaButtonBoxLayout.addWidget(self.removeMcaButton)
        self.mcaButtonBoxLayout.addWidget(self.replaceMcaButton)
        
        self.stackWindow.mainLayout.addWidget(self.mcaButtonBox)

        self.connect(self.addMcaButton, qt.SIGNAL("clicked()"), 
                    self._addMcaClicked)
        self.connect(self.removeMcaButton, qt.SIGNAL("clicked()"), 
                    self._removeMcaClicked)
        self.connect(self.replaceMcaButton, qt.SIGNAL("clicked()"), 
                    self._replaceMcaClicked)

        if self.rgbWidget is not None:
            # The IMAGE selection
            self.imageButtonBox = qt.QWidget(self.roiWindow)
            buttonBox = self.imageButtonBox
            self.imageButtonBoxLayout = qt.QHBoxLayout(buttonBox)
            self.imageButtonBoxLayout.setMargin(0)
            self.imageButtonBoxLayout.setSpacing(0)
            self.addImageButton = qt.QPushButton(buttonBox)
            icon = qt.QIcon(qt.QPixmap(IconDict["rgb16"]))
            self.addImageButton.setIcon(icon)
            self.addImageButton.setText("ADD IMAGE")
            self.removeImageButton = qt.QPushButton(buttonBox)
            self.removeImageButton.setIcon(icon)
            self.removeImageButton.setText("REMOVE IMAGE")
            self.replaceImageButton = qt.QPushButton(buttonBox)
            self.replaceImageButton.setIcon(icon)
            self.replaceImageButton.setText("REPLACE IMAGE")
            self.imageButtonBoxLayout.addWidget(self.addImageButton)
            self.imageButtonBoxLayout.addWidget(self.removeImageButton)
            self.imageButtonBoxLayout.addWidget(self.replaceImageButton)
            
            self.roiWindow.mainLayout.addWidget(buttonBox)
            
            self.connect(self.addImageButton, qt.SIGNAL("clicked()"), 
                        self._addImageClicked)
            self.connect(self.removeImageButton, qt.SIGNAL("clicked()"), 
                        self._removeImageClicked)
            self.connect(self.replaceImageButton, qt.SIGNAL("clicked()"), 
                        self._replaceImageClicked)

    def _buildConnections(self, widget = None):
        if widget is None:
            self._buildAndConnectButtonBox()
        else:
            self.connect(self.stackGraphWidget.colormapToolButton,
                     qt.SIGNAL("clicked()"),
                     self.selectStackColormap)

        if widget is None:
            self.connect(self.stackGraphWidget.hFlipToolButton,
                 qt.SIGNAL("clicked()"),
                 self._hFlipIconSignal)
        else:
            self.connect(self.stackGraphWidget.hFlipToolButton,
                 qt.SIGNAL("clicked()"),
                 widget._hFlipIconSignal)

        if widget is None:
            #ROI Image
            self.connect(self.roiGraphWidget.hFlipToolButton,
                     qt.SIGNAL("clicked()"),
                     self._hFlipIconSignal)

            self.connect(self.roiGraphWidget.colormapToolButton,
                         qt.SIGNAL("clicked()"),
                         self.selectROIColormap)

            self.connect(self.roiGraphWidget.selectionToolButton,
                         qt.SIGNAL("clicked()"),
                         self._toggleROISelectionMode)
        else:
            #ROI Image
            self.connect(self.roiGraphWidget.hFlipToolButton,
                     qt.SIGNAL("clicked()"),
                     widget._hFlipIconSignal)

            self.connect(self.roiGraphWidget.selectionToolButton,
                         qt.SIGNAL("clicked()"),
                         widget._toggleROISelectionMode)
        text = "Toggle between Selection\nand Zoom modes"
        if QTVERSION > '4.0.0':
            self.roiGraphWidget.selectionToolButton.setToolTip(text)

        if widget is None:
            self.connect(self.roiGraphWidget.imageToolButton,
                         qt.SIGNAL("clicked()"),
                         self._resetSelection)

            self.connect(self.roiGraphWidget.eraseSelectionToolButton,
                         qt.SIGNAL("clicked()"),
                         self._setROIEraseSelectionMode)

            self.connect(self.roiGraphWidget.rectSelectionToolButton,
                         qt.SIGNAL("clicked()"),
                         self._setROIRectSelectionMode)

            self.connect(self.roiGraphWidget.brushSelectionToolButton,
                         qt.SIGNAL("clicked()"),
                         self._setROIBrushSelectionMode)

            self.connect(self.roiGraphWidget.brushToolButton,
                         qt.SIGNAL("clicked()"),
                         self._setROIBrush)
        else:
            self.connect(self.roiGraphWidget.imageToolButton,
                         qt.SIGNAL("clicked()"),
                         widget._resetSelection)

            self.connect(self.roiGraphWidget.eraseSelectionToolButton,
                         qt.SIGNAL("clicked()"),
                         widget._setROIEraseSelectionMode)

            self.connect(self.roiGraphWidget.rectSelectionToolButton,
                         qt.SIGNAL("clicked()"),
                         widget._setROIRectSelectionMode)

            self.connect(self.roiGraphWidget.brushSelectionToolButton,
                         qt.SIGNAL("clicked()"),
                         widget._setROIBrushSelectionMode)

            self.connect(self.roiGraphWidget.brushToolButton,
                         qt.SIGNAL("clicked()"),
                         widget._setROIBrush)

        if widget is None:
            self.stackGraphWidget.graph.canvas().setMouseTracking(1)
            #self.roiGraphWidget.graph.canvas().setMouseTracking(1)
            self.stackGraphWidget.setInfoText("    X = ???? Y = ???? Z = ????")
            self.stackGraphWidget.showInfo()
        
        if QTVERSION < "4.0.0":
            self.connect(self.stackGraphWidget.graph,
                         qt.PYSIGNAL("QtBlissGraphSignal"),
                         self._stackGraphSignal)
            self.connect(self.roiGraphWidget.graph,
                         qt.PYSIGNAL("QtBlissGraphSignal"),
                         self._roiGraphSignal)
            self.connect(self.mcaWidget,
                         qt.PYSIGNAL("McaWindowSignal"),
                         self._mcaWidgetSignal)
        else:
            if widget is None:
                self.connect(self.stackGraphWidget.graph,
                         qt.SIGNAL("QtBlissGraphSignal"),
                         self._stackGraphSignal)
                self.connect(self.roiGraphWidget.graph,
                         qt.SIGNAL("QtBlissGraphSignal"),
                         self._roiGraphSignal)
                self.connect(self.mcaWidget,
                         qt.SIGNAL("McaWindowSignal"),
                         self._mcaWidgetSignal)
            else:
                self.connect(self.stackGraphWidget.graph,
                         qt.SIGNAL("QtBlissGraphSignal"),
                         widget._stackGraphSignal)
                self.connect(self.roiGraphWidget.graph,
                         qt.SIGNAL("QtBlissGraphSignal"),
                         widget._roiGraphSignal)
                         #widget._otherWidgetRoiGraphSignal)

    def _stackGraphSignal(self, ddict):
        if ddict['event'] == "MouseAt":
            x = round(ddict['y'])
            if x < 0: x = 0
            y = round(ddict['x'])
            if y < 0: y = 0
            limits = self.__stackImageData.shape
            x = min(int(x), limits[0]-1)
            y = min(int(y), limits[1]-1)
            z = self.__stackImageData[x, y]
            self.stackGraphWidget.setInfoText("    X = %d Y = %d Z = %.4g" %\
                                               (y, x, z))

    def _otherWidgetRoiGraphSignal(self, ddict):
        self._roiGraphSignal(ddict, ownsignal = False)

    def _roiGraphSignal(self, ddict, ownsignal = None):
        if ownsignal is None:ownsignal = True
        if ddict['event'] == "MouseSelection":
            if ddict['xmin'] < ddict['xmax']:
                xmin = ddict['xmin']
                xmax = ddict['xmax']
            else:
                xmin = ddict['xmax']
                xmax = ddict['xmin']
            if ddict['ymin'] < ddict['ymax']:
                ymin = ddict['ymin']
                ymax = ddict['ymax']
            else:
                ymin = ddict['ymax']
                ymax = ddict['ymin']
            i1 = max(int(round(xmin)), 0)
            i2 = min(abs(int(round(xmax)))+1, self.__stackImageData.shape[1])
            j1 = max(int(round(ymin)),0)
            j2 = min(abs(int(round(ymax)))+1,self.__stackImageData.shape[0])
            self.__selectionMask[j1:j2, i1:i2] = 1
            #Stack Image
            if self.__stackColormap is None:
                a = Numeric.array(map(int,
                    0.8* Numeric.ravel(self.__stackPixmap0[j1:j2,i1:i2,:]))).astype(Numeric.UInt8)
                a.shape = [j2-j1, i2-i1, 4]
                self.__stackPixmap[j1:j2,i1:i2,:]  = a
            elif int(str(self.__stackColormap[0])) > 1:     #color
                a = Numeric.array(map(int,
                    0.8* Numeric.ravel(self.__stackPixmap0[j1:j2,i1:i2,:]))).astype(Numeric.UInt8)
                a.shape = [j2-j1, i2-i1, 4]
                self.__stackPixmap[j1:j2,i1:i2,:]  = a
            else:
                #self.__stackPixmap[j1:j2,i1:i2,0:2]  = 0    #that changes grey by red but gives the problem that 0
                #                                            #remains 0 and appears as not selected in the image
                self.__stackPixmap[j1:j2,i1:i2,0]    = 0x40
                self.__stackPixmap[j1:j2,i1:i2,2]    = 0x70
                self.__stackPixmap[j1:j2,i1:i2,1]    = self.__stackPixmap0[j1:j2,i1:i2,0]
                self.__stackPixmap[j1:j2,i1:i2,3]    = 0x40
            #ROI Image
            if self.__ROIColormap is None:
                a = Numeric.array(map(int,
                    0.8* Numeric.ravel(self.__ROIPixmap0[j1:j2,i1:i2,:]))).astype(Numeric.UInt8)
                a.shape = [j2-j1, i2-i1, 4]
                self.__ROIPixmap[j1:j2,i1:i2,:]  = a
            elif int(str(self.__ROIColormap[0])) > 1:     #color
                a = Numeric.array(map(int,
                    0.8* Numeric.ravel(self.__ROIPixmap0[j1:j2,i1:i2,:]))).astype(Numeric.UInt8)
                a.shape = [j2-j1, i2-i1, 4]
                self.__ROIPixmap[j1:j2,i1:i2,:]  = a
            else:
                self.__ROIPixmap[j1:j2,i1:i2,0]    = 0x40
                self.__ROIPixmap[j1:j2,i1:i2,2]    = 0x70
                self.__ROIPixmap[j1:j2,i1:i2,1]    = self.__ROIPixmap0[j1:j2,i1:i2,0]
                self.__ROIPixmap[j1:j2,i1:i2,3]    = 0x40
            self.plotROIImage(update = False)
            self.plotStackImage(update = False)
            return

        elif ddict['event'] == "MouseAt":
            if ownsignal:self._stackGraphSignal(ddict)
            if self.__ROIBrushMode:
                if self.roiGraphWidget.graph.isZoomEnabled():
                    return
                #if follow mouse is not activated
                #it only enters here when the mouse is pressed.
                #Therefore is perfect for "brush" selections.
                width = self.__ROIBrushWidth   #in (row, column) units
                r = self.__stackImageData.shape[0]
                c = self.__stackImageData.shape[1]
                xmin = max((ddict['x']-0.5*width), 0)
                xmax = min((ddict['x']+0.5*width), c)
                ymin = max((ddict['y']-0.5*width), 0)
                ymax = min((ddict['y']+0.5*width), r)
                i1 = min(int(round(xmin)), c-1)
                i2 = min(int(round(xmax)), c)
                j1 = min(int(round(ymin)),r-1)
                j2 = min(int(round(ymax)), r)
                if i1 == i2: i2 = i1+1
                if j1 == j2: j2 = j1+1
                if self.__ROIEraseMode:
                    self.__stackPixmap[j1:j2,i1:i2,:]    = self.__stackPixmap0[j1:j2,i1:i2,:]
                    self.__ROIPixmap[j1:j2,i1:i2,:]    = self.__ROIPixmap0[j1:j2,i1:i2,:]
                    self.__selectionMask[i1:i2, j1:j2] = 0
                else:
                    #stack image
                    if self.__stackColormap is None:
                        a = Numeric.array(map(int,
                                        0.8* Numeric.ravel(self.__stackPixmap0[j1:j2,i1:i2,:]))).\
                                        astype(Numeric.UInt8)
                        a.shape = [j2-j1, i2-i1, 4]
                        self.__stackPixmap[j1:j2,i1:i2,:]  = a
                    elif int(str(self.__stackColormap[0])) > 1:     #color
                        a = Numeric.array(map(int,
                                        0.8* Numeric.ravel(self.__stackPixmap0[j1:j2,i1:i2,:]))).\
                                        astype(Numeric.UInt8)
                        a.shape = [j2-j1, i2-i1, 4]
                        self.__stackPixmap[j1:j2,i1:i2,:]  = a
                    else:
                        #self.__stackPixmap[j1:j2,i1:i2,0:2]  = 0    #that changes grey by red but gives the problem that 0
                        #                                            #remains 0 and appears as not selected in the image
                        self.__stackPixmap[j1:j2,i1:i2,0]    = 0x40
                        self.__stackPixmap[j1:j2,i1:i2,2]    = 0x70
                        self.__stackPixmap[j1:j2,i1:i2,1]    = self.__stackPixmap0[j1:j2,i1:i2,0]
                        self.__stackPixmap[j1:j2,i1:i2,3]    = 0x40
                    #ROI image
                    if self.__ROIColormap is None:
                        a = Numeric.array(map(int,
                                        0.8* Numeric.ravel(self.__ROIPixmap0[j1:j2,i1:i2,:]))).\
                                        astype(Numeric.UInt8)
                        a.shape = [j2-j1, i2-i1, 4]
                        self.__ROIPixmap[j1:j2,i1:i2,:]  = a
                    elif int(str(self.__ROIColormap[0])) > 1:     #color
                        a = Numeric.array(map(int,
                                        0.8* Numeric.ravel(self.__ROIPixmap0[j1:j2,i1:i2,:]))).\
                                        astype(Numeric.UInt8)
                        a.shape = [j2-j1, i2-i1, 4]
                        self.__ROIPixmap[j1:j2,i1:i2,:]  = a
                    else:
                        #self.__stackPixmap[j1:j2,i1:i2,0:2]  = 0    #that changes grey by red but gives the problem that 0
                        #                                            #remains 0 and appears as not selected in the image
                        self.__ROIPixmap[j1:j2,i1:i2,0]    = 0x40
                        self.__ROIPixmap[j1:j2,i1:i2,2]    = 0x70
                        self.__ROIPixmap[j1:j2,i1:i2,1]    = self.__ROIPixmap0[j1:j2,i1:i2,0]
                        self.__ROIPixmap[j1:j2,i1:i2,3]    = 0x40
                    self.__selectionMask[j1:j2, i1:i2] = 1
                self.plotROIImage(update = False)
                self.plotStackImage(update = False)

    def setStack(self, stack, mcaindex=1, fileindex = None):
        #stack.data is an XYZ array
        if QTVERSION < '4.0.0':
            title = str(self.caption())+\
                    ": from %s to %s" % (os.path.basename(stack.sourceName[0]),
                                        os.path.basename(stack.sourceName[-1]))                         
            self.setCaption(title)
        else:
            title = str(self.windowTitle())+\
                    ": from %s to %s" % (os.path.basename(stack.sourceName[0]),
                                        os.path.basename(stack.sourceName[-1]))                         
            self.setWindowTitle(title)
        
        if stack.info["SourceType"] == "SpecFileStack" and (QTVERSION > '4.0.0'):
            oldshape = stack.data.shape
            dialog = ImageShapeDialog(self, shape = oldshape[0:2])
            dialog.setModal(True)
            ret = dialog.exec_()
            if ret:
                shape = dialog.getImageShape()
                dialog.close()
                del dialog
                stack.data.shape = [shape[0], shape[1], oldshape[2]]

        self.stack = stack
        shape = self.stack.data.shape
        self.mcaIndex   = mcaindex
        self.otherIndex = 0
        if fileindex is None:
            fileindex      = 2
            if hasattr(self.stack, "info"):
                if self.stack.info.has_key('FileIndex'):
                    fileindex = stack.info['FileIndex']
                if fileindex == 0:
                    self.mcaIndex   = 2
                    self.otherIndex = 1
                else:
                    self.mcaIndex = 1
                    self.otherIndex = 0
                
        self.fileIndex = fileindex
        self.originalPlot()

    def originalPlot(self):        
        #original image
        self.__stackImageData = Numeric.sum(self.stack.data, self.mcaIndex)
        
        #original ICR mca
        i = max(self.otherIndex, self.fileIndex)
        j = min(self.otherIndex, self.fileIndex)                
        mcaData0 = Numeric.sum(Numeric.sum(self.stack.data, i), j) * 1.0

        calib = self.stack.info['McaCalib']
        dataObject = DataObject.DataObject()
        dataObject.info = {"McaCalib": calib,
                           "selectiontype":"1D",
                           "SourceName":"EDF Stack",
                           "Key":"SUM"}
        dataObject.x = [Numeric.arange(len(mcaData0)).astype(Numeric.Float)
                        + self.stack.info['Channel0']]
        dataObject.y = [mcaData0]

        #store the original spectrum
        self.__mcaData0 = dataObject
        
        #add the original image
        self.__addOriginalImage()

        #add the ICR ROI Image
        #self.updateRoiImage(roidict=None)

        #add the mca
        self.sendMcaSelection(dataObject, action = "ADD")

    def __addOriginalImage(self):
        #init the original image
        self.stackGraphWidget.graph.setTitle("Original Stack")
        if self.fileIndex == 2:
            self.stackGraphWidget.graph.x1Label("File")
            if self.mcaIndex == 0:
                self.stackGraphWidget.graph.y1Label('Column')
            else:
                self.stackGraphWidget.graph.y1Label('Row')
        elif self.stack.info["SourceType"] == "SpecFileStack":
            self.stackGraphWidget.graph.y1Label('Row')
            self.stackGraphWidget.graph.x1Label('Column')
        else:
            self.stackGraphWidget.graph.y1Label("File")
            if self.mcaIndex == 1:
                self.stackGraphWidget.graph.x1Label('Row')
            else:
                self.stackGraphWidget.graph.x1Label('Column')

        [ymax, xmax] = self.__stackImageData.shape
        if self._y1AxisInverted:
            self.stackGraphWidget.graph.zoomReset()
            self.stackGraphWidget.graph.setY1AxisInverted(True)
            if 0:   #This is not needed because there are no curves in the graph
                self.stackGraphWidget.graph.setY1AxisLimits(0, ymax, replot=False)
                self.stackGraphWidget.graph.setX1AxisLimits(0, xmax, replot=False)
                self.stackGraphWidget.graph.replot() #I need it to update the canvas
            self.plotStackImage(update=True)
        else:
            self.stackGraphWidget.graph.zoomReset()
            self.stackGraphWidget.graph.setY1AxisInverted(False)
            if 0:#This is not needed because there are no curves in the graph
                self.stackGraphWidget.graph.setY1AxisLimits(0, ymax, replot=False)
                self.stackGraphWidget.graph.setX1AxisLimits(0, xmax, replot=False)
                self.stackGraphWidget.graph.replot() #I need it to update the canvas
            self.plotStackImage(update=True)

        self.__selectionMask = Numeric.zeros(self.__stackImageData.shape, Numeric.UInt8)

        #init the ROI
        self.roiGraphWidget.graph.setTitle("ICR ROI")
        self.roiGraphWidget.graph.y1Label(self.stackGraphWidget.graph.y1Label())
        self.roiGraphWidget.graph.x1Label(self.stackGraphWidget.graph.x1Label())
        self.roiGraphWidget.graph.setY1AxisInverted(self.stackGraphWidget.graph.isY1AxisInverted())
        if 0:#This is not needed because there are no curves in the graph
            self.roiGraphWidget.graph.setX1AxisLimits(0,
                                            self.__stackImageData.shape[0])
            self.roiGraphWidget.graph.setY1AxisLimits(0,
                                            self.__stackImageData.shape[1])
            self.roiGraphWidget.graph.replot()
        self.__ROIImageData = self.__stackImageData.copy()
        self.plotROIImage(update = True)

    def sendMcaSelection(self, mcaObject, key = None, legend = None, action = None):
        if action is None:action = "ADD"
        if key is None: key = "SUM"
        if legend is None:
            legend = "EDF Stack SUM"
            if self.normalizeButton.isChecked():
                npixels = self.__stackImageData.shape[0] * self.__stackImageData.shape[1]
                legend += "/%d" % npixels
        sel = {}
        sel['SourceName'] = "EDF Stack"
        sel['Key']        =  key
        sel['legend']     =  legend
        sel['dataobject'] =  mcaObject
        if action == "ADD":
            self.mcaWidget._addSelection([sel])
        elif action == "REMOVE":
            self.mcaWidget._removeSelection([sel])
        elif action == "REPLACE":
            self.mcaWidget._replaceSelection([sel])
        if self.tab is None:
            self.mcaWidget.show()
            if QTVERSION < '4.0.0':
                self.mcaWidget.raiseW()
            else:
                self.mcaWidget.raise_()
        else:
            if QTVERSION < '4.0.0':
                self.tab.setCurrentPage(self.tab.indexOf(self.mcaWidget))
            else:
                self.tab.setCurrentWidget(self.mcaWidget)

    def _mcaWidgetSignal(self, ddict):
        if not self.__ROIConnected:return
        if ddict['event'] == "ROISignal":
            self.__stackBackgroundAnchors = None
            title = "%s" % ddict["name"]
            self.roiGraphWidget.graph.setTitle(title)
            self.roiGraphWidget.__title = title
            if (ddict["name"] == "ICR"):                
                i1 = 0
                i2 = self.stack.data.shape[self.mcaIndex]
            elif (ddict["type"]).upper() != "CHANNEL":
                #energy roi
                xw =  ddict['calibration'][0] + \
                      ddict['calibration'][1] * self.__mcaData0.x[0] + \
                      ddict['calibration'][2] * self.__mcaData0.x[0] * \
                                                self.__mcaData0.x[0]
                i1 = Numeric.nonzero(ddict['from'] <= xw)
                if len(i1):
                    i1 = min(i1)
                else:
                    return
                i2 = Numeric.nonzero(xw <= ddict['to'])
                if len(i2):
                    i2 = max(i2) + 1
                else:
                    return
            else:
                i1 = Numeric.nonzero(ddict['from'] <= self.__mcaData0.x[0])
                if len(i1):
                    i1 = min(i1)
                else:
                    i1 = 0
                i1 = max(i1, 0)

                i2 = Numeric.nonzero(self.__mcaData0.x[0] <= ddict['to'])
                if len(i2):
                    i2 = max(i2)
                else:
                    i2 = 0
                i2 = min(i2+1, self.stack.data.shape[self.mcaIndex])
            if self.fileIndex == 0:
                if self.mcaIndex == 1:
                    background =  0.5 * (i2-i1) * (self.stack.data[:,i1,:]+self.stack.data[:,i2-1,:])
                    self.__ROIImageData = Numeric.sum(self.stack.data[:,i1:i2,:],1)
                else:
                    background =  0.5 * (i2-i1) * (self.stack.data[:,:,i1]+self.stack.data[:,:,i2-1])
                    self.__ROIImageData = Numeric.sum(self.stack.data[:,:,i1:i2],2)
            else:
                #self.fileIndex = 2
                if self.mcaIndex == 0:
                    background =  0.5 * (i2-i1) * (self.stack.data[i1,:,:]+self.stack.data[i2-1,:,:])
                    self.__ROIImageData = Numeric.sum(self.stack.data[i1:i2,:,:],0)
                else:
                    background =  0.5 * (i2-i1) * (self.stack.data[:,i1,:]+self.stack.data[:,i2-1,:])
                    self.__ROIImageData = Numeric.sum(self.stack.data[:,i1:i2,:],1)
            self.__ROIImageBackground = background
            self.__stackBackgroundAnchors = [i1, i2-1]
            if self.roiBackgroundButton.isChecked():
                self.__ROIImageData =  self.__ROIImageData - self.__ROIImageBackground
                self.roiGraphWidget.graph.setTitle(self.roiGraphWidget.__title + " Net")
            else:
                pass
                #self.__ROIImageData =  self.__ROIImageData
            if self.__ROIColormapDialog is not None:
                minData = self.__ROIImageData.min()
                maxData = self.__ROIImageData.max()
                self.__ROIColormapDialog.setDataMinMax(minData, maxData)
    
            self._resetSelection()
            if self.isHidden():
                self.show()
                if self.tab is not None:
                    if QTVERSION < '4.0.0':
                        self.tab.setCurrentPage(self.tab.indexOf(self.rgbWidget))
                    else:
                        self.tab.setCurrentWidget(self.rgbWidget)


    def plotROIImage(self, update = True):
        if self.__ROIImageData is None:
            self.roiGraphWidget.graph.clear()
            self.roiGraphWidget.picker.data = None
            return
        if update:
            self.__selectionMask = Numeric.zeros(self.__stackImageData.shape, Numeric.UInt8)
            self.getROIPixmapFromData()
            self.__ROIPixmap0 = self.__ROIPixmap.copy()
            self.roiGraphWidget.picker.data = self.__ROIImageData
            if self.__ROIColormap is None:
                self.roiGraphWidget.picker.setTrackerPen(qt.Qt.black)
            elif int(str(self.__ROIColormap[0])) > 1:     #color
                self.roiGraphWidget.picker.setTrackerPen(qt.Qt.black)
            else:
                self.roiGraphWidget.picker.setTrackerPen(qt.Qt.green)
        if not self.roiGraphWidget.graph.yAutoScale:
            ylimits = self.roiGraphWidget.graph.getY1AxisLimits()
        if not self.roiGraphWidget.graph.xAutoScale:
            xlimits = self.roiGraphWidget.graph.getX1AxisLimits()
        self.roiGraphWidget.graph.pixmapPlot(self.__ROIPixmap.tostring(),
            (self.__ROIImageData.shape[1], self.__ROIImageData.shape[0]),
                                        xmirror = 0,
                                        ymirror = not self._y1AxisInverted)
        if not self.roiGraphWidget.graph.yAutoScale:
            self.roiGraphWidget.graph.setY1AxisLimits(ylimits[0], ylimits[1], replot=False)
        if not self.roiGraphWidget.graph.xAutoScale:
            self.roiGraphWidget.graph.setX1AxisLimits(xlimits[0], xlimits[1], replot=False)
        self.roiGraphWidget.graph.replot()

    def getROIPixmapFromData(self):
        #It does not look nice, but I avoid copying data
        colormap = self.__ROIColormap
        if colormap is None:
            (self.__ROIPixmap,size,minmax)= spslut.transform(\
                                self.__ROIImageData,
                                (1,0),
                                (spslut.LINEAR,3.0),
                                "BGRX",
                                spslut.TEMP,
                                1,
                                (0,1),
                                (0, 255), 1)
        else:
            if len(colormap) < 7: colormap.append(spslut.LINEAR)
            (self.__ROIPixmap,size,minmax)= spslut.transform(\
                                self.__ROIImageData,
                                (1,0),
                                (colormap[6],3.0),
                                "BGRX",
                                COLORMAPLIST[int(str(colormap[0]))],
                                colormap[1],
                                (colormap[2],colormap[3]),
                                (0,255), 1)

        self.__ROIPixmap = self.__ROIPixmap.astype(numpy.ubyte)

        self.__ROIPixmap.shape = [self.__ROIImageData.shape[0],
                                    self.__ROIImageData.shape[1],
                                    4]

    def getStackPixmapFromData(self):
        colormap = self.__stackColormap
        if colormap is None:
            (self.__stackPixmap,size,minmax)= spslut.transform(\
                                self.__stackImageData,
                                (1,0),
                                (spslut.LINEAR,3.0),
                                "BGRX",
                                spslut.TEMP,
                                1,
                                (0,1),(0, 255),1)
        else:
            if len(colormap) < 7: colormap.append(spslut.LINEAR)
            (self.__stackPixmap,size,minmax)= spslut.transform(\
                                self.__stackImageData,
                                (1,0),
                                (colormap[6],3.0),
                                "BGRX",
                                COLORMAPLIST[int(str(colormap[0]))],
                                colormap[1],
                                (colormap[2],colormap[3]),(0,255),1)
            
        self.__stackPixmap = self.__stackPixmap.astype(numpy.ubyte)

        self.__stackPixmap.shape = [self.__stackImageData.shape[0],
                                    self.__stackImageData.shape[1],
                                    4]

    def plotStackImage(self, update = True):
        if self.__stackImageData is None:
            self.stackGraphWidget.graph.clear()
            return
        if update:
            self.getStackPixmapFromData()
            self.__stackPixmap0 = self.__stackPixmap.copy()
        if not self.stackGraphWidget.graph.yAutoScale:
            ylimits = self.stackGraphWidget.graph.getY1AxisLimits()
        if not self.stackGraphWidget.graph.xAutoScale:
            xlimits = self.stackGraphWidget.graph.getX1AxisLimits()
        self.stackGraphWidget.graph.pixmapPlot(self.__stackPixmap.tostring(),
            (self.__stackImageData.shape[1], self.__stackImageData.shape[0]),
                    xmirror = 0,
                    ymirror = not self._y1AxisInverted)            
        if not self.stackGraphWidget.graph.yAutoScale:
            self.stackGraphWidget.graph.setY1AxisLimits(ylimits[0], ylimits[1], replot=False)
        if not self.stackGraphWidget.graph.xAutoScale:
            self.stackGraphWidget.graph.setX1AxisLimits(xlimits[0], xlimits[1], replot=False)        
        self.stackGraphWidget.graph.replot()

    def _hFlipIconSignal(self):
        if QWTVERSION4:
            qt.QMessageBox.information(self, "Flip Image", "Not available under PyQwt4")
            return
        if not self.stackGraphWidget.graph.yAutoScale:
            qt.QMessageBox.information(self, "Open",
                    "Please set stack Y Axis to AutoScale first")
            return
        if not self.stackGraphWidget.graph.xAutoScale:
            qt.QMessageBox.information(self, "Open",
                    "Please set stack X Axis to AutoScale first")
            return
        if not self.roiGraphWidget.graph.yAutoScale:
            qt.QMessageBox.information(self, "Open",
                    "Please set ROI image Y Axis to AutoScale first")
            return
        if not self.roiGraphWidget.graph.xAutoScale:
            qt.QMessageBox.information(self, "Open",
                    "Please set ROI image X Axis to AutoScale first")
            return

        if self._y1AxisInverted:
            self._y1AxisInverted = False
        else:
            self._y1AxisInverted = True
        self.stackGraphWidget.graph.zoomReset()
        self.roiGraphWidget.graph.zoomReset()
        self.stackGraphWidget.graph.setY1AxisInverted(self._y1AxisInverted)
        self.roiGraphWidget.graph.setY1AxisInverted(self._y1AxisInverted)
        self.plotStackImage(True)
        self.plotROIImage(True)

    def selectStackColormap(self):
        if self.__stackImageData is None:return
        if self.__stackColormapDialog is None:
            self.__initStackColormapDialog()
        if self.__stackColormapDialog.isHidden():
            self.__stackColormapDialog.show()
        if QTVERSION < '4.0.0':self.__stackColormapDialog.raiseW()
        else:  self.__stackColormapDialog.raise_()          
        self.__stackColormapDialog.show()


    def __initStackColormapDialog(self):
        minData = self.__stackImageData.min()
        maxData = self.__stackImageData.max()
        self.__stackColormapDialog = ColormapDialog.ColormapDialog()
        self.__stackColormapDialog.colormapIndex  = self.__stackColormapDialog.colormapList.index("Temperature")
        self.__stackColormapDialog.colormapString = "Temperature"
        if QTVERSION < '4.0.0':
            self.__stackColormapDialog.setCaption("Stack Colormap Dialog")
            self.connect(self.__stackColormapDialog,
                         qt.PYSIGNAL("ColormapChanged"),
                         self.updateStackColormap)
        else:
            self.__stackColormapDialog.setWindowTitle("Stack Colormap Dialog")
            self.connect(self.__stackColormapDialog,
                         qt.SIGNAL("ColormapChanged"),
                         self.updateStackColormap)
        self.__stackColormapDialog.setDataMinMax(minData, maxData)
        self.__stackColormapDialog.setAutoscale(1)
        self.__stackColormapDialog.setColormap(self.__stackColormapDialog.colormapIndex)
        self.__stackColormap = (self.__stackColormapDialog.colormapIndex,
                              self.__stackColormapDialog.autoscale,
                              self.__stackColormapDialog.minValue, 
                              self.__stackColormapDialog.maxValue,
                              minData, maxData)
        self.__stackColormapDialog._update()

    def updateStackColormap(self, *var):
        if len(var) > 6:
            self.__stackColormap = [var[0],
                             var[1],
                             var[2],
                             var[3],
                             var[4],
                             var[5],
                             var[6]]
        elif len(var) > 5:
            self.__stackColormap = [var[0],
                             var[1],
                             var[2],
                             var[3],
                             var[4],
                             var[5]]
        else:
            self.__stackColormap = [var[0],
                             var[1],
                             var[2],
                             var[3],
                             var[4],
                             var[5]]
        self.plotStackImage(True)

    def selectROIColormap(self):
        if self.__ROIImageData is None:return
        if self.__ROIColormapDialog is None:
            self.__initROIColormapDialog()
        if self.__ROIColormapDialog.isHidden():
            self.__ROIColormapDialog.show()
        if QTVERSION < '4.0.0':self.__ROIColormapDialog.raiseW()
        else:  self.__ROIColormapDialog.raise_()          
        self.__ROIColormapDialog.show()


    def __initROIColormapDialog(self):
        minData = self.__ROIImageData.min()
        maxData = self.__ROIImageData.max()
        self.__ROIColormapDialog = ColormapDialog.ColormapDialog()
        self.__ROIColormapDialog.colormapIndex  = self.__ROIColormapDialog.colormapList.index("Temperature")
        self.__ROIColormapDialog.colormapString = "Temperature"
        if QTVERSION < '4.0.0':
            self.__ROIColormapDialog.setCaption("ROI Colormap Dialog")
            self.connect(self.__ROIColormapDialog,
                         qt.PYSIGNAL("ColormapChanged"),
                         self.updateROIColormap)
        else:
            self.__ROIColormapDialog.setWindowTitle("ROI Colormap Dialog")
            self.connect(self.__ROIColormapDialog,
                         qt.SIGNAL("ColormapChanged"),
                         self.updateROIColormap)
        self.__ROIColormapDialog.setDataMinMax(minData, maxData)
        self.__ROIColormapDialog.setAutoscale(1)
        self.__ROIColormapDialog.setColormap(self.__ROIColormapDialog.colormapIndex)
        self.__ROIColormap = (self.__ROIColormapDialog.colormapIndex,
                              self.__ROIColormapDialog.autoscale,
                              self.__ROIColormapDialog.minValue, 
                              self.__ROIColormapDialog.maxValue,
                              minData, maxData)
        self.__ROIColormapDialog._update()

    def updateROIColormap(self, *var):
        if len(var) > 6:
            self.__ROIColormap = [var[0],
                             var[1],
                             var[2],
                             var[3],
                             var[4],
                             var[5],
                             var[6]]
        elif len(var) > 5:
            self.__ROIColormap = [var[0],
                             var[1],
                             var[2],
                             var[3],
                             var[4],
                             var[5]]
        else:
            self.__ROIColormap = [var[0],
                             var[1],
                             var[2],
                             var[3],
                             var[4],
                             var[5]]
        self.plotROIImage(True)

    def _addImageClicked(self):
        self.rgbWidget.addImage(self.__ROIImageData,
                                str(self.roiGraphWidget.graph.title().text()))
        #if self.rgbWidget.isHidden():
        if 1:
            if self.tab is None:
                if self.master:
                    self.rgbWidget.show()
            else:
                self.tab.setCurrentWidget(self.rgbWidget)


    def _removeImageClicked(self):
        self.rgbWidget.removeImage(str(self.roiGraphWidget.graph.title().text()))

    def _replaceImageClicked(self):
        self.rgbWidget.reset()
        self.rgbWidget.addImage(self.__ROIImageData,
                                str(self.roiGraphWidget.graph.title().text()))
        if self.rgbWidget.isHidden():
            self.rgbWidget.show()
        if self.tab is None:
            self.rgbWidget.show()
            self.rgbWidget.raise_()
        else:
            self.tab.setCurrentWidget(self.rgbWidget)

    def _addMcaClicked(self, action = None):
        if action is None:action = "ADD"
        #original ICR mca
        if self.__stackImageData is None: return
        mcaData = None
        if self.__selectionMask is None:
            if self.normalizeButton.isChecked():
                npixels = self.__stackImageData.shape[0] * self.__stackImageData.shape[1] * 1.0
                dataObject = DataObject.DataObject()
                dataObject.info.update(self.__mcaData0.info)
                dataObject.x  = [self.__mcaData0.x[0]]
                dataObject.y =  [self.__mcaData0.y[0] / npixels];
            else:
                dataObject = self.__mcaData0
            self.sendMcaSelection(dataObject, action = action)
            return
        npixels = len(Numeric.nonzero(Numeric.ravel(self.__selectionMask)>0)) * 1.0
        if npixels == 0:
            if self.normalizeButton.isChecked():
                npixels = self.__stackImageData.shape[0] * self.__stackImageData.shape[1]
                dataObject = DataObject.DataObject()
                dataObject.info.update(self.__mcaData0.info)
                dataObject.x  = [self.__mcaData0.x[0]]
                dataObject.y =  [self.__mcaData0.y[0] / npixels];
            else:
                dataObject = self.__mcaData0
            self.sendMcaSelection(dataObject, action = action)
            return

        mcaData = Numeric.zeros(self.__mcaData0.y[0].shape, Numeric.Float)

        cleanMask = numpy.nonzero(self.__selectionMask > 0)
        if len(cleanMask[0]) and len(cleanMask[1]):
            cleanMask = numpy.array(cleanMask).transpose()
            if self.fileIndex == 2:
                if self.mcaIndex == 0:
                    for r, c in cleanMask:
                        mcaData += self.stack.data[:,r,c]
                else:
                    for r, c in cleanMask:
                        mcaData += self.stack.data[r,:,c]
            else:    
                if self.mcaIndex == 1:
                    for r, c in cleanMask:
                        mcaData += self.stack.data[r,:,c]
                else:
                    for r, c in cleanMask:
                        mcaData += self.stack.data[r,c,:]

        if self.normalizeButton.isChecked():
            mcaData = mcaData/npixels

        calib = self.stack.info['McaCalib']
        dataObject = DataObject.DataObject()
        dataObject.info = {"McaCalib": calib,
                           "selectiontype":"1D",
                           "SourceName":"EDF Stack",
                           "Key":"Selection"}
        dataObject.x = [Numeric.arange(len(mcaData)).astype(Numeric.Float)
                        + self.stack.info['Channel0']]
        dataObject.y = [mcaData]

        legend = self.__getLegend()
        if self.normalizeButton.isChecked():
            legend += "/%d" % npixels
        self.sendMcaSelection(dataObject,
                          key = "Selection",
                          legend =legend,
                          action = action)

    def __getLegend(self):
        title = str(self.roiGraphWidget.graph.title().text())
        return "Stack " + title + " selection"
    
    def _removeMcaClicked(self):
        #remove the mca
        #dataObject = self.__mcaData0
        #send a dummy object
        dataObject = DataObject.DataObject()
        legend = self.__getLegend()
        if self.normalizeButton.isChecked():
            legend += "/"
            curves = self.mcaWidget.graph.curves.keys()
            for curve in curves:
                if curve.startswith(legend):
                    legend = curve
                    break
        self.sendMcaSelection(dataObject, legend = legend, action = "REMOVE")
    
    def _replaceMcaClicked(self):
        #replace the mca
        self.__ROIConnected = False
        self._addMcaClicked(action="REPLACE")
        self.__ROIConnected = True
        
    def closeEvent(self, event):
        ddict = {}
        ddict['event'] = "StackWidgetClosed"
        ddict['id']    = id(self)
        if QTVERSION < '4.0.0':
            self.emit(qt.PYSIGNAL("StackWidgetSignal"), (ddict,))
        else:
            self.emit(qt.SIGNAL("StackWidgetSignal"),ddict)
        if self.__stackColormapDialog is not None:
            self.__stackColormapDialog.close()
        if self.__ROIColormapDialog is not None:
            self.__ROIColormapDialog.close()
        if self._matplotlibSaveImage is not None:
            self._matplotlibSaveImage.close()
        qt.QWidget.closeEvent(self, event)

    def _resetSelection(self):
        if DEBUG:print "_resetSelection"
        self.plotStackImage(update = True)
        self.plotROIImage(update = True)
        if self.__stackImageData is None: return
        self.__selectionMask = Numeric.zeros(self.__stackImageData.shape, Numeric.UInt8)


    def _setROIEraseSelectionMode(self):
        if DEBUG:print "_setROIEraseSelectionMode"
        self.__ROIEraseMode = True
        self.__ROIBrushMode = True
        self.roiGraphWidget.picker.setTrackerMode(Qwt.QwtPicker.ActiveOnly)
        self.roiGraphWidget.graph.enableSelection(False)

    def _setROIRectSelectionMode(self):
        if DEBUG:print "_setROIRectSelectionMode"
        self.__ROIEraseMode = False
        self.__ROIBrushMode = False
        self.roiGraphWidget.picker.setTrackerMode(Qwt.QwtPicker.AlwaysOn)
        self.roiGraphWidget.graph.enableSelection(True)
        
    def _setROIBrushSelectionMode(self):
        if DEBUG:print "_setROIBrushSelectionMode"
        self.__ROIEraseMode = False
        self.__ROIBrushMode = True
        self.roiGraphWidget.picker.setTrackerMode(Qwt.QwtPicker.ActiveOnly)
        self.roiGraphWidget.graph.enableSelection(False)
        
    def _setROIBrush(self):
        if DEBUG:print "_setROIBrush"
        if self.__ROIBrushMenu is None:
            if QTVERSION < '4.0.0':
                self.__ROIBrushMenu = qt.QPopupMenu()
                self.__ROIBrushMenu.insertItem(qt.QString(" 1 Image Pixel Width"),self.__setROIBrush1)
                self.__ROIBrushMenu.insertItem(qt.QString(" 2 Image Pixel Width"),self.__setROIBrush2)
                self.__ROIBrushMenu.insertItem(qt.QString(" 3 Image Pixel Width"),self.__setROIBrush3)
                self.__ROIBrushMenu.insertItem(qt.QString(" 5 Image Pixel Width"),self.__setROIBrush4)
                self.__ROIBrushMenu.insertItem(qt.QString("10 Image Pixel Width"),self.__setROIBrush5)
                self.__ROIBrushMenu.insertItem(qt.QString("20 Image Pixel Width"),self.__setROIBrush6)
            else:
                self.__ROIBrushMenu = qt.QMenu()
                self.__ROIBrushMenu.addAction(qt.QString(" 1 Image Pixel Width"),self.__setROIBrush1)
                self.__ROIBrushMenu.addAction(qt.QString(" 2 Image Pixel Width"),self.__setROIBrush2)
                self.__ROIBrushMenu.addAction(qt.QString(" 3 Image Pixel Width"),self.__setROIBrush3)
                self.__ROIBrushMenu.addAction(qt.QString(" 5 Image Pixel Width"),self.__setROIBrush4)
                self.__ROIBrushMenu.addAction(qt.QString("10 Image Pixel Width"),self.__setROIBrush5)
                self.__ROIBrushMenu.addAction(qt.QString("20 Image Pixel Width"),self.__setROIBrush6)
        if QTVERSION < '4.0.0':
            self.__ROIBrushMenu.exec_loop(self.cursor().pos())
        else:
            self.__ROIBrushMenu.exec_(self.cursor().pos())

    def __setROIBrush1(self):
        self.__ROIBrushWidth = 1

    def __setROIBrush2(self):
        self.__ROIBrushWidth = 2

    def __setROIBrush3(self):
        self.__ROIBrushWidth = 3

    def __setROIBrush4(self):
        self.__ROIBrushWidth = 5

    def __setROIBrush5(self):
        self.__ROIBrushWidth = 10

    def __setROIBrush6(self):
        self.__ROIBrushWidth = 20

    def _getStackOfFiles(self):
        fileTypeList = ["EDF Files (*edf)",
                        "EDF Files (*ccd)",
                        "Specfile Files (*mca)",
                        "Specfile Files (*dat)",
                        "OMNIC Files (*map)",
                        "All Files (*)"]
        message = "Open ONE indexed stack or SEVERAL files"
        wdir = PyMcaDirs.inputDir
        if QTVERSION < '4.0.0':
            if sys.platform != 'darwin':
                filetypes = ""
                for filetype in fileTypeList:
                    filetypes += filetype+"\n"
                filelist = qt.QFileDialog.getOpenFileNames(filetypes,
                            wdir,
                            self,
                            message,
                            message)
                if not len(filelist):return []
        else:
            if (QTVERSION < '4.3.0') and (sys.platform != 'darwin'):
                filetypes = ""
                for filetype in fileTypeList:
                    filetypes += filetype+"\n"
                filelist = qt.QFileDialog.getOpenFileNames(self,
                            message,
                            wdir,
                            filetypes)
                if not len(filelist):return []
            else:
                fdialog = qt.QFileDialog(self)
                fdialog.setModal(True)
                fdialog.setWindowTitle(message)
                strlist = qt.QStringList()
                for filetype in fileTypeList:
                    strlist.append(filetype)
                fdialog.setFilters(strlist)
                fdialog.setFileMode(fdialog.ExistingFiles)
                fdialog.setDirectory(wdir)
                ret = fdialog.exec_()
                if ret == qt.QDialog.Accepted:
                    filelist = fdialog.selectedFiles()
                    fdialog.close()
                    del fdialog                        
                else:
                    fdialog.close()
                    del fdialog
                    return []
        filelist = map(str, filelist)
        if not(len(filelist)): return []
        PyMcaDirs.inputDir = os.path.dirname(filelist[0])
        filelist.sort()
        return filelist

if __name__ == "__main__":
    import getopt
    options = ''
    longoptions = ["fileindex=","begin=", "end="]
    try:
        opts, args = getopt.getopt(
                     sys.argv[1:],
                     options,
                     longoptions)
    except getopt.error,msg:
        print msg
        sys.exit(1)
    #import time
    #t0= time.time()
    fileindex = 0   #it is faster with fileindex=0
    begin = None
    end = None
    for opt, arg in opts:
        if opt in '--begin':
            begin = int(arg)
        elif opt in '--end':
            end = int(arg)
        elif opt in '--fileindex':
            fileindex = int(arg)
    app = qt.QApplication([])
    w = QEDFStackWidget(master=True)
    if len(args):
        f = open(args[0])
        #read 10 characters
        line = f.read(10)
        f.close()
        omnicfile = False
        if line[0] == "\n":
            line = line[1:]
        if line[0] == "{":
            stack = QStack()
        elif line.startswith('Spectral'):
            stack = OmnicMap.OmnicMap(args[0])
            omnicfile = True
        elif line.startswith('#\tDate:'):
            stack = LuciaMap.LuciaMap(args[0])
            omnicfile = True
        else:
            stack = QSpecFileStack()
        f.close()
    if len(args) > 1:
        stack.loadFileList(args, fileindex =fileindex)
        PyMcaDirs.inputDir = os.path.dirname(args[0])
    elif len(args) == 1:
        if not omnicfile:
            stack.loadIndexedStack(args, begin, end, fileindex=fileindex)
        try:
            PyMcaDirs.inputDir = os.path.dirname(args[0])
        except ValueError:
            PyMcaDirs.inputDir = os.getcwd()
    else:
        if 1:
            filelist = w._getStackOfFiles()
            if len(filelist):
                PyMcaDirs.inputDir = os.path.dirname(filelist[0])
                f = open(filelist[0])
                #read 10 characters
                line = f.read(10)
                f.close()
                omnicfile = False
                if line[0] == "\n":
                    line = line[1:]
                if line[0] == "{":
                    stack = QStack()
                elif line.startswith('Spectral'):
                    stack = OmnicMap.OmnicMap(filelist[0])
                    omnicfile = True
                elif line.startswith('#\tDate'):
                    stack = LuciaMap.LuciaMap(filelist[0])
                    omnicfile = True
                else:
                    stack = QSpecFileStack()
            if len(filelist) == 1:
                if not omnicfile:
                    stack.loadIndexedStack(filelist[0], begin, end, fileindex=fileindex)
            elif len(filelist):
                stack.loadFileList(filelist, fileindex=fileindex)
            else:
                print "Usage: "
                print "python QEDFStackWidget.py SET_OF_EDF_FILES"
                print "python QEDFStackWidget.py -begin=0 --end=XX INDEXED_EDF_FILE"
                sys.exit(1)
        elif os.path.exists(".\COTTE\ch09\ch09__mca_0005_0000_0070.edf"):
            stack.loadIndexedStack(".\COTTE\ch09\ch09__mca_0005_0000_0070.edf")
        elif os.path.exists("Z:\COTTE\ch09\ch09__mca_0005_0000_0070.edf"):
            stack.loadIndexedStack("Z:\COTTE\ch09\ch09__mca_0005_0000_0070.edf")
        else:
            print "Usage: "
            print "python QEDFStackWidget.py SET_OF_EDF_FILES"
            sys.exit(1)
    shape = stack.data.shape
    qt.QObject.connect(app, qt.SIGNAL("lastWindowClosed()"),
                       app, qt.SLOT("quit()"))

    w.setStack(stack)
    w.show()
    #print "reading elapsed = ", time.time() - t0
    if qt.qVersion() < '4.0.0':
        app.setMainWidget(w)
        app.exec_loop()
    else:
        sys.exit(app.exec_())
