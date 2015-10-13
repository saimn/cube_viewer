# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function

import numpy as np
import pyqtgraph as pg
from mpdaf.obj import Cube, Spectrum, plt_zscale
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.parametertree import Parameter, ParameterTree


PARAMS = [
    {'name': 'Sky', 'type': 'group', 'children': [
        {'name': 'Show', 'type': 'bool', 'value': True},
        {'name': 'Line Color', 'type': 'str', 'value': 'aaaa'},
    ]},
    {'name': 'Median filter', 'type': 'group', 'children': [
        {'name': 'Show', 'type': 'bool', 'value': False},
        {'name': 'Kernel Size', 'type': 'int', 'value': 5},
        {'name': 'Line Size', 'type': 'int', 'value': 2},
        {'name': 'Line Color', 'type': 'str', 'value': 'r'},
    ]},
]


class MuseApp(object):
    def __init__(self):
        self.img = None
        self.cube = None
        self.sky = Spectrum('sky-ref-spectra.fits')
        self.sky.data /= self.sky.data.max()

        pg.mkQApp()

        self.win = win = QtGui.QWidget()
        win.setWindowTitle('MUSE Cube Viewer')
        # layout = QtGui.QGridLayout()
        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        win.setLayout(layout)

        self.splitter = QtGui.QSplitter()
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        layout.addWidget(self.splitter)

        self.tree = ParameterTree(showHeader=False)
        self.splitter.addWidget(self.tree)
        self.params = Parameter.create(name='params', type='group',
                                       children=PARAMS)
        self.tree.setParameters(self.params, showTop=False)
        self.tree.setWindowTitle('pyqtgraph example: Parameter Tree')

        for p in ('Sky', 'Median filter'):
            self.params.param(p).sigTreeStateChanged.connect(
                self.update_spec_plot)

        self.win_inner = win = pg.GraphicsLayoutWidget()
        self.splitter2 = QtGui.QSplitter()
        self.splitter2.setOrientation(QtCore.Qt.Vertical)
        self.splitter.addWidget(self.win_inner)

        # self.img_label = win.addLabel('Hello !', justify='right')

        # A plot area (ViewBox + axes) for displaying the image
        win.nextRow()
        self.img_plot = win.addPlot(title='Image')
        self.img_plot.setAspectLocked(lock=True, ratio=1)

        # Item for displaying image data
        self.img_item = pg.ImageItem()
        self.img_plot.addItem(self.img_item)

        # pg.SignalProxy(self.img_plot.scene().sigMouseMoved, rateLimit=60,
        #                slot=self.on_mouse_moved)

        # Contrast/color control
        self.hist = hist = pg.HistogramLUTItem()
        hist.setImageItem(self.img_item)
        win.addItem(hist)

        self.add_roi()

        # self.specplot = win.addPlot(row=2, col=0, colspan=2)
        win.nextRow()
        self.specplot = win.addPlot(title='Spectrum', colspan=2)
        self.zoomplot = None

        self.win.resize(800, 800)
        self.win.show()

    def add_zoom_window(self):
        self.win_inner.nextRow()
        self.zoomplot = self.win_inner.addPlot(title='Zoomed Spectrum', colspan=2)
        self.zoomreg = region = pg.LinearRegionItem()
        region.setZValue(10)
        # Add the LinearRegionItem to the ViewBox, but tell the ViewBox to
        # exclude this item when doing auto-range calculations.
        # self.specplot.addItem(self.zoomreg, ignoreBounds=True)
        self.zoomplot.setAutoVisible(y=True)

        def update_spec_with_region():
            region.setZValue(10)
            minX, maxX = region.getRegion()
            print('update_spec_with_region')
            self.zoomplot.setXRange(minX, maxX, padding=0)

        def update_region():
            print('update_region')
            region.setRegion(self.zoomplot.getViewBox().viewRange()[0])

        region.sigRegionChanged.connect(update_spec_with_region)
        self.zoomplot.sigRangeChanged.connect(update_region)
        region.setRegion([1000, 1200])

    def load_cube(self, filename):
        # Generate image data
        print('Loading cube ...', end='')
        self.cube = Cube(filename)
        print('OK')
        print('Creating image ...', end='')
        self.img = self.cube[:100, :, :].mean(axis=0)
        print('OK')
        self.img_item.setImage(self.img.data.data)
        # self.hist.setLevels(self.img.data.min(), self.img.data.max())
        self.hist.setLevels(*plt_zscale.zscale(self.img.data.filled(0)))

        # zoom to fit imageo
        self.img_plot.autoRange()
        self.update_spec_plot()

    def add_roi(self, position=(150, 100), size=(20, 20)):
        # Custom ROI for selecting an image region
        self.roi = roi = pg.ROI(position, size, pen=dict(color='g', size=5))
        roi.addScaleHandle([0.5, 1], [0.5, 0.5])
        roi.addScaleHandle([0, 0.5], [0.5, 0.5])
        roi.addRotateHandle([1, 0], [0.5, 0.5])
        self.img_plot.addItem(roi)
        roi.setZValue(10)  # make sure ROI is drawn above image
        roi.sigRegionChangeFinished.connect(self.update_spec_plot)

    # def on_mouse_moved(self, evt):
    #     # using signal proxy turns original arguments into a tuple
    #     pos = evt[0]
    #     if self.img_plot.sceneBoundingRect().contains(pos):
    #         mousePoint = self.img_plot.vb.mapSceneToView(pos)
    #         pos = list(mousePoint.pos())
    #         if pos[0] > 0 and pos[0] < self.img.shape[0] and \
    #                 pos[1] > 0 and pos[1] < self.img.shape[1]:
    #             self.img_label.setText(
    #                 "<span style='font-size: 12pt'>x=%0.1f, "
    #                 "<span style='color: red'>y1=%0.1f</span>, "
    #                 "<span style='color: green'>y2=%0.1f</span>" % (
    #                     mousePoint.x(), mousePoint.y(), 0))

    def update_spec_plot(self):
        """Callbacks for handling user interaction"""
        print('update_spec_plot')
        if self.img is not None:
            p = self.params
            pos = np.array(self.roi.pos(), dtype=int)
            size = np.array(self.roi.size(), dtype=int)
            imin = np.clip(pos - size, 0, self.cube.shape[1])
            imax = np.clip(pos + size, 0, self.cube.shape[2])
            print('Extract mean spectrum for {}'.format(zip(imin, imax)))
            data = self.cube[:, imin[0]:imax[0], imin[1]:imax[1]]
            spec = data.mean(axis=(1, 2))
            self.specplot.clearPlots()

            if p['Sky', 'Show']:
                sp = self.sky.data.data * (2*spec.data.max()) + spec.data.min()
                print('Sky color:', p['Sky', 'Line Color'])
                self.specplot.plot(sp, pen=p['Sky', 'Line Color'])
                # (200, 200, 200, 100)

            self.specplot.plot(spec.data.data, pen=(255, 255, 255, 200))

            if p['Median filter', 'Show']:
                sp = spec.median_filter(p['Median filter', 'Kernel Size'])
                self.specplot.plot(sp.data.data, pen={
                    'color': p['Median filter', 'Line Color'],
                    'width': p['Median filter', 'Line Size']
                })

            self.specplot.autoRange()
            if self.zoomplot is not None:
                self.zoomplot.plot(spec.data.data, clear=True)
                self.specplot.addItem(self.zoomreg, ignoreBounds=True)
                self.update_spec_with_region()


if __name__ == '__main__':
    import sys
    # Start Qt event loop unless running in interactive mode or using pyside.
    if sys.flags.interactive != 1 or not hasattr(QtCore, 'PYQT_VERSION'):
        app = MuseApp()
        # pg.dbg()
        app.load_cube('/home/simon/muse/UDF/0.21/DATACUBE-ZAP_UDF-10.fits')
        QtGui.QApplication.instance().exec_()
