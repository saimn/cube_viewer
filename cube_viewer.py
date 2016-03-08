# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function

import numpy as np
import os
import pyqtgraph as pg
import sys
from mpdaf.obj import Cube, Spectrum
from mpdaf.tools import zscale
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.parametertree import Parameter, ParameterTree
from six.moves import zip


SKYREF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'udf',
                      'data', 'sky-ref-spectra.fits')

PARAMS = [
    {'name': 'Sky', 'type': 'group', 'children': [
        {'name': 'Show', 'type': 'bool', 'value': True},
        {'name': 'Line Color', 'type': 'str', 'value': 'aaaa'},
    ]},
    {'name': 'Spectrum', 'type': 'group', 'children': [
        {'name': 'Line color', 'type': 'str', 'value': 'fffa'},
        {'name': 'Lambda Min', 'type': 'int', 'value': 0},
        {'name': 'Lambda Max', 'type': 'int', 'value': 100},
        {'name': 'Selection color', 'type': 'str', 'value': '3333'},
        {'name': 'Show Zoom', 'type': 'bool', 'value': False},
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
        self.spec = None
        self.sky = Spectrum(SKYREF)
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

        self.connect(('Median filter', ), self.update_spec_plot)
        self.connect(('Sky', ), self.update_spec_plot)
        self.connect(('Spectrum', 'Lambda Max'), self.show_image)
        self.connect(('Spectrum', 'Lambda Min'), self.show_image)
        self.connect(('Spectrum', 'Line color'), self.update_spec_plot)
        self.connect(('Spectrum', 'Selection color'), self.update_spec_plot)
        self.connect(('Spectrum', 'Show Zoom'), self.add_zoom_window)

        self.win_inner = win = pg.GraphicsLayoutWidget()
        self.splitter2 = QtGui.QSplitter()
        self.splitter2.setOrientation(QtCore.Qt.Vertical)
        self.splitter.addWidget(self.win_inner)

        # self.img_label = win.addLabel('Hello !', justify='right')

        # A plot area (ViewBox + axes) for displaying the  white-light image
        win.nextRow()
        self.white_plot = win.addPlot(title='White-light Image')
        self.white_plot.setAspectLocked(lock=True, ratio=1)
        self.white_item = pg.ImageItem()
        self.white_plot.addItem(self.white_item)

        # A plot area (ViewBox + axes) for displaying the image
        win.nextColumn()
        self.img_plot = win.addPlot(title='Band Image')
        self.img_plot.setAspectLocked(lock=True, ratio=1)
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
        self.specplot = win.addPlot(title='Spectrum', colspan=3)
        self.zoomplot = None
        self.zoomplot_visible = False

        # self.lbdareg = region = pg.LinearRegionItem(movable=False)
        # self.specplot.addItem(region)
        # region.setZValue(10)
        self.zoomreg = region = pg.LinearRegionItem()
        region.setZValue(10)
        self.specplot.addItem(self.zoomreg, ignoreBounds=True)
        region.setRegion([1000, 1200])

        self.win.resize(1000, 800)
        self.win.show()

    def connect(self, names, func):
        self.params.param(*names).sigTreeStateChanged.connect(func)

    def add_zoom_window(self):
        if self.zoomplot_visible:
            return
        else:
            self.zoomplot_visible = True

        self.win_inner.nextRow()
        self.zoomplot = self.win_inner.addPlot(title='Zoomed Spectrum',
                                               colspan=3)
        self.zoomplot.setAutoVisible(y=True)

        def update_region_from_zoom():
            self.zoomreg.setRegion(self.zoomplot.getViewBox().viewRange()[0])

        self.zoomreg.sigRegionChanged.connect(
            self.update_zoom_spec_from_region)
        self.zoomplot.sigRangeChanged.connect(update_region_from_zoom)

    def update_zoom_spec_from_region(self):
        self.zoomplot.plot(self.spec.data.data, clear=True,
                           pen=self.params['Spectrum', 'Line color'])
        # Add the LinearRegionItem to the ViewBox, but tell the ViewBox to
        # exclude this item when doing auto-range calculations.
        self.specplot.addItem(self.zoomreg, ignoreBounds=True)
        self.zoomreg.setZValue(10)
        self.zoomplot.setXRange(*self.zoomreg.getRegion(), padding=0)

    def load_cube(self, filename):
        print('Loading cube {} ... '.format(filename), end='')
        self.cube = Cube(filename, dtype=None, copy=False)
        print('OK')

        # Generate image data
        print('Creating white-light image ... ', end='')
        img = self.cube.mean(axis=0)
        print('OK')
        self.white_item.setImage(img.data.data.T)
        self.white_item.setLevels(zscale(img.data.filled(0)))

        self.show_image()

        # zoom to fit image
        self.white_plot.autoRange()
        self.img_plot.autoRange()
        self.update_spec_plot()

    def show_image(self):
        print('Creating image ... ', end='')
        self.img = self.cube[:100, :, :].mean(axis=0)
        print('OK')
        self.img_item.setImage(self.img.data.data.T)
        # self.hist.setLevels(self.img.data.min(), self.img.data.max())
        self.hist.setLevels(*zscale(self.img.data.filled(0)))

        # self.lbdareg.setBrush(self.params['Spectrum', 'Selection color'])
        # self.lbdareg.setRegion([self.params['Spectrum', 'Lambda Min'],
        #                         self.params['Spectrum', 'Lambda Max']])

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
        if self.img is None:
            return

        p = self.params
        pos = np.array(self.roi.pos(), dtype=int)
        size = np.array(self.roi.size(), dtype=int)
        imin = np.clip(pos - size, 0, self.cube.shape[1])
        imax = np.clip(pos + size, 0, self.cube.shape[2])
        print('Extract mean spectrum for {}'.format(list(zip(imin, imax))))
        data = self.cube[:, imin[0]:imax[0], imin[1]:imax[1]]
        self.spec = spec = data.mean(axis=(1, 2))
        self.specplot.clearPlots()

        if p['Sky', 'Show']:
            sp = self.sky.data.data * (2 * spec.data.max()) + spec.data.min()
            self.specplot.plot(sp, pen=p['Sky', 'Line Color'])

        self.specplot.plot(spec.data.data, pen=p['Spectrum', 'Line color'])

        if p['Median filter', 'Show']:
            sp = spec.median_filter(p['Median filter', 'Kernel Size'])
            self.specplot.plot(sp.data.data, pen={
                'color': p['Median filter', 'Line Color'],
                'width': p['Median filter', 'Line Size']
            })

        # self.specplot.autoRange()
        if self.zoomplot is not None:
            self.update_zoom_spec_from_region()


def main():
    # Start Qt event loop unless running in interactive mode or using pyside.
    if sys.flags.interactive != 1 or not hasattr(QtCore, 'PYQT_VERSION'):
        app = MuseApp()
        # pg.dbg()
        if len(sys.argv) != 2:
            print('No cube filename provided ?')
        app.load_cube(sys.argv[1])
        QtGui.QApplication.instance().exec_()


if __name__ == '__main__':
    main()
