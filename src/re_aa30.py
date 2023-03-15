#!/usr/bin/env python
"""
RigExpertAA30.py
Talk to RE AA-30 and do some standard chores.
version using pyqtgraph

Commands:
FQx
OK
set center frequency (in Hz) to x

SWx
OK
set sweep range to x Hz

FRXn
response: fq, r, x
...
OK
Output frquencey (MHz, R, and X at n+1 steps (does sweep)

VER
AA_X y

ON
OK
Turns RF board on

OFF
OK
Turns RF board off

Requires Python3.8+
"""

import sys
import time
from collections import OrderedDict
from typing import Union

import numpy as np
import pyqtgraph as pg
import serial
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from serial_device2 import SerialDevice, find_serial_device_ports

font = QtGui.QFont()
font.setFamily('Arial')
font.setFixedPitch(False)
font.setPointSize(11)


class REAA30():
    """ Class to control and display data from RigExpert AA30
    build the UI and instantiate buttons and actions """
    def __init__(self):
        self.re_sp = None # Serial port associated with teh AA30
        self.find_port()

        self.done = True
        self.re_version()
        self.re_off() # first turn off the rf board
        
        # defaults for any test scan
        self.start_freq = 3.50
        self.end_freq = 28.0
        self.nfreqs = 100
        
        # parameters for "band" scans
        # bands are defined by a name, and a list with the cf, span, and nfreq parameters
        self.bands = OrderedDict([
                             ('Full', [2.00, 30.0, 200]),
                             ('80cw', [3.480, 3.620, 30]), ('75ph', [3.700, 4.000, 30]), ('80', [3.50, 4.0, 50]),
                             ('60', [5.00, 5.2, 10]),
                             ('40cw', [6.980, 7.150, 50]), ('40ph', [7.100, 7.300, 51]), ('40', [7.000, 7.300, 50]),
                             ('30', [10.080, 10.170, 25]),
                             ('20cw', [13.980, 14.120, 25]), ('20ph', [14.100, 14.350, 50]), ('20', [14.000, 14.350, 50]),
                             ('17', [18.060, 18.180, 20]), ('15', [20.980, 21.470, 50]), ('12', [24.87, 24.960, 20]),
                             ('10cw', [27.980, 29.720, 25]), ('10ph', [28.5, 29.7, 25]), ('10', [28.0, 29.7, 100]),
                             ('all', None), ('cw', None), ('ph', None),
                             ])
        self.band_select = '80cw'
        self.stopscan = False
        self.color_index = 0
        self.in_sampling = False
        self.build_ui()
        self.win.show()

    def find_port(self):
        """Find the port that the AA30 is connected to. 
        This is set up for a mac; may have to be modified for Windows.

        Raises
        ------
        ConnectionError
            Exception is raised when port connection fails (no device)
        """
        ports = find_serial_device_ports() # Returns list of available serial ports
        # signature for AA-30: '/dev/cu.usbserial-2230'
        aa_30_port = '/dev/cu.usbserial-2230'
        if aa_30_port in ports:

            try:
                self.re_sp = serial.Serial(aa_30_port,  # when plugged into the right side port
                    bytesize=8, parity='N', stopbits=1, baudrate=38400, timeout=3)
            except:
                raise ConnectionError('Did not find a serial port connected to an AA-30')

        
    def build_ui(self):
        """
        Create user interface with plots.
        """

        self.app = pg.mkQApp()
        self.app.setStyle("fusion")
        self.win = pg.GraphicsView() # title="AA-30 RF Analyzer")
        self.layout = QtWidgets.QGridLayout()
        self.win.setLayout(self.layout)
        self.win.resize(1024,800)

        # Define parameters (pyqtgraph ptree) that control aquisition and buttons...
        params = [
           {'name': 'Acquisition Parameters', 'type': 'group', 'children': [
                {'name': 'Presets', 'type': 'list', 'values': self.bands.keys(), 'default': self.band_select},
                {'name': 'Start Preset Scans', 'type': 'action'},
                {'name': 'Reset/Clear plots', 'type': 'action'},
                {'name': 'Low F', 'type': 'float', 'value': self.start_freq, 'limits': [2.0, 30.0],
                    'suffix': 'MHz', 'default': self.start_freq, 'fontsize': 9},
                {'name': 'High F', 'type': 'float', 'value': self.end_freq, 'limits': [2.0, 28.0],
                    'suffix': 'MHz', 'default': self.end_freq},
                {'name': 'NFreqs', 'type': 'int', 'value': self.nfreqs, 'default': self.nfreqs,
                    'limits': [1, 10000]},
                {'name': 'Start Single Scan', 'type': 'action'},
                {'name': 'Start Repeated Scans', 'type': 'action'},
                {'name': 'Stop Scans', 'type': 'action'},
                {'name': 'Filename', 'type': 'str', 'value': 'test.p', 'default': 'test.p'},
                {'name': 'New Filename', 'type': 'action'},
                {'name': 'Save Scan', 'type': 'action'},
                {'name': 'Load Scan', 'type': 'action'},
                {'name': 'Info', 'type': 'text', 'value': ''},
                {'name': 'Reset AA-30', 'type': 'action'},
                {'name': "Quit", 'type': 'action'},
            ]
            }]
        ptree = ParameterTree()
        ptree.setMaximumWidth(200)
        ptree.setFont(font)
        ptree.sizeHintForRow(24)
#        ptree.setUniformRowHeights(True)
        self.ptreedata = Parameter.create(name='params', type='group', children=params)
        ptree.setParameters(self.ptreedata, showTop=False)

        # arrange the window
        self.layout.addWidget(ptree, 0, 0, 6, 1) # Parameter Tree on left

        # add space for the graphs on the right
        view = pg.GraphicsView()
        layout = pg.GraphicsLayout(border=(50,50,50))
        view.setCentralItem(layout)
        self.layout.addWidget(view, 0, 2, 6, 2)  # data plots on right

        # now add plots to the layout
        self.pl = {}  # dictionary access to the plots
        
        self.pl['R'] = layout.addPlot(title="R, X")
        self.pl['R'].showGrid(x=True, y=True)
        self.pl['R'].showAxis('right') # R on left, X on right

        layout.nextCol()
        self.pl['RTL'] = layout.addPlot(title="Return Loss")
        self.pl['RTL'].showGrid(x=True, y=True)

        layout.nextRow()
        self.pl['SWR'] = layout.addPlot(title="SWR")
        self.pl['SWR'].showGrid(x=True, y=True)

        layout.nextCol()
        self.pl['TDR'] = layout.addPlot(title='TDR')
        self.pl['TDR'].showGrid(x=True, y=True)

        self.pl['R'].setYRange(0., 300.)
        self.pl['SWR'].setYRange(1., 10.)
        self.pl['RTL'].setYRange(-50., 0.)

        fmin = (self.start_freq)
        fmax = (self.end_freq)
 
        for p in self.pl.keys():
            if p in ['X', 'TDR']:  # skip plots with different x axis
                continue
            self.pl[p].setXRange(fmin, fmax)
            self.pl[p].getAxis('left').setStyle(stopAxisAtTick=(True, True))
            self.pl[p].getAxis('bottom').setStyle(stopAxisAtTick=(True, False))
            self.pl[p].setLabels(bottom='F (MHz)')
        self.pl['TDR'].setXRange(0., 0.5)
        self.pl['TDR'].setLabels(bottom='T (usec)')

        for plx in ['SWR', 'R', 'RTL']:
            self.pl[plx].setXLink(self.pl['R'])  # link frequency axes
        
        # label axes
        self.pl['R'].setLabels(left='R (Ohms)')
        self.pl['R'].getAxis('right').setLabel('X (Ohms)', color='#0000ff')
        self.pl['SWR'].setLabels(left='SWR')
        self.pl['RTL'].setLabels(left='Return Loss (dB)')

        self.R_label = pg.TextItem(text="F: {} R: {}".format(0, 0))
    # self.pl['R'].setTitle(self.R_label)
        #cross hair
        # R_vLine = pg.InfiniteLine(angle=90, movable=False)
        # R_hLine = pg.InfiniteLine(angle=0, movable=False)
        # self.pl['R'].addItem(R_vLine, ignoreBounds=True)
        # self.pl['R'].addItem(R_hLine, ignoreBounds=True)
        # self.pl['R'].setMouseTracking(True)
        # print(dir(self.pl['R'].scene()))
        self.pl['R'].scene().sigMouseMoved.connect(self.onMouseMoved)
        # print(dir(self.R_label))
        self.R_label.setAnchor((0,0)) # itemPos=(0,0), parentPos=(0,0), offset=(-10,10))
        #
        self.SWR_label = pg.TextItem(text="F: {} \nR: {}".format(0, 0)) # , anchor=(0,0))
        self.pl['SWR'].addItem(self.SWR_label)
        #cross hair
        # SWR_vLine = pg.InfiniteLine(angle=90, movable=False)
        # SWR_hLine = pg.InfiniteLine(angle=0, movable=False)
        # self.pl['SWR'].addItem(SWR_vLine, ignoreBounds=True)
        # self.pl['SWR'].addItem(SWR_hLine, ignoreBounds=True)
        # self.pl['SWR'].setMouseTracking(True)
        # print(dir(self.pl['R'].scene()))
        self.pl['SWR'].scene().sigMouseMoved.connect(self.onMouseMoved)
        self.SWR_label.setAnchor((0,0)) # itemPos=(0,0), parentPos=(0,0), offset=(-10,10))
     
        #
        self.RTL_label = pg.TextItem(text="F: {} \nR: {}".format(0, 0))
        self.pl['RTL'].addItem(self.RTL_label)
        self.RTL_label.setAnchor((0,0)) # itemPos=(0,0), parentPos=(0,0), offset=(-10,10))
        #cross hair
        # RTL_vLine = pg.InfiniteLine(angle=90, movable=False)
        # RTL_hLine = pg.InfiniteLine(angle=0, movable=False)
        # self.pl['RTL'].addItem(RTL_vLine, ignoreBounds=True)
        # self.pl['RTL'].addItem(RTL_hLine, ignoreBounds=True)
        # self.pl['RTL'].setMouseTracking(True)
        # print(dir(self.pl['R'].scene()))
        self.pl['RTL'].scene().sigMouseMoved.connect(self.onMouseMoved)
        self.win.show()

        self.ptreedata.sigTreeStateChanged.connect(self.command_dispatcher)  # connect parameters to their updates

        # Start Qt event loop unless running in interactive mode.
        # Event loop will wait for the GUI to activate the updater and start sampling.
        
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QGuiApplication.instance().exec()

    def command_dispatcher(self, param, changes):
        """
        Respond to changes in the parametertree and update class variables
        Serves to update variables
        Dispatches actions required by button press
        
        Parameters
        ----------
        param : parameter list returned from the parameter tree object
    
        changes : changes as returned from the parameter tree object
    
        Returns
        -------
        Nothing
    
        """
        for param, change, data in changes:
            path = self.ptreedata.childPath(param)

            # if path is not None:
            #     childName = '.'.join(path)
            # else:
            #     childName = param.name()
            #
            # Parameters and user-supplied information
            #
            if path[1] == 'Quit':
                exit()
            if path[1] == 'Filename':
                self.filename = data
            if path[1] == 'Low F':
                self.start_freq = data
            if path[1] == 'High F':
                self.end_freq = data
            if path[1] == 'NFreqs':
                # print(f'nFreqs: {data:d}')
                self.nfreqs = data
            if path[1] == 'Info':
                self.InfoText = data
            if path[1] == 'Presets':
                self.band_select = data
                # print('band select data: ', data)
            #
            # Actions:
            #
            if path[1] == 'Start Single Scan':
                (fr, rx, zx, rtl) = self.re_sample(start_freq=self.start_freq, end_freq=self.end_freq, nfreq=self.nfreqs)
                self.color_index += 1
            if path[1] == 'Start Repeated Scans':
                self.clear_plots()
                self.done = False
                self.repeat_scan()
                
            if path[1] == 'Start Preset Scans':
                if self.band_select in ['cw']:
                    for b in self.bands.keys():
                        if b in self.band_find('ph') or self.bands[b] is None:
                            continue
                        (fr, rx, zx, rtl) = self.re_sample(start_freq=self.bands[b][0], end_freq=self.bands[b][1],
                            nfreq=self.bands[b][2])
                        self.color_index += 1
                elif self.band_select in ['ph']:
                    for b in self.bands.keys():
                        if b in self.band_find('cw') or self.bands[b] is None:
                            continue
                        (fr, rx, zx, rtl) = self.re_sample(start_freq=self.bands[b][0], end_freq=self.bands[b][1],
                            nfreq=self.bands[b][2])
                        self.color_index += 1
                elif self.band_select in ['all']:
                    for b in self.bands.keys():
                        if self.bands[b] is None:  # skip non-specific flags
                            continue
                        (fr, rx, zx, rtl) = self.re_sample(start_freq=self.bands[b][0], end_freq=self.bands[b][1],
                            nfreq=self.bands[b][2])
                        self.color_index += 1
                else:
                    b = self.band_select
                    (fr, rx, zx, rtl) = self.re_sample(start_freq=self.bands[b][0], end_freq=self.bands[b][1],
                        nfreq=self.bands[b][2])
                    self.color_index += 1

            if path[1] == 'Stop Scan':
                self.done = True
                self.stop_scan()
            if path[1] == 'Reset/Clear plots':
                self.clear_plots()
            if path[1] == 'Reset AA-30':
                self.resetAA30()
            # if path[1] == 'Continue':
            #     self.continueRun()
            if path[1] == 'Save Scan':
                pass # self.storeData()
            if path[1] == 'Load Scan':
                pass
                fn = self.getFilename()
                if fn is not None:
                    self.loadData(filename=fn)
            if path[1] == 'New Filename':
                pass
                # self.filename = self.makeFilename()

    def repeat_scan(self):
        """Repeat the last scan, identically
        """        
        while not self.done:
            (fr, rx, zx, rtl) = self.re_sample(start_freq=self.start_freq, end_freq=self.end_freq, nfreq=self.nfreqs)
            self.color_index += 1
        
    def band_find(self, b):
        bl = []
        for k in self.bands.keys():
            if k[-2:] == b:
                bl.append(k)
        return bl

    def compute_swr_and_return_loss(self, re:Union[float, np.ndarray],
                                          im:Union[float, np.ndarray],
                                          z0:float=50.):
        """_summary_

        Parameters
        ----------
        re : float
            Real part of the impedance
        im : float
            reactive (imaginary) part of the impedance
        z0 : float
            nominal load resistance (x = 0), optional
            by default 50.
        """
        rho = np.zeros(len(re))
        for i in range(len(re)):
            z = np.complex(re[i], im[i])
            rho[i] = np.abs((z - z0)/(z + z0))
            if np.abs(rho[i] - 1) < 1e-3:
                rho[i] = 1e-3
        swr = (1.0 + rho)/(1.0 - rho)
        rtl = 20. * np.log10(rho)
        return(swr, rtl)
    
    def compute_tdr(self, fr:np.ndarray, rtl:np.ndarray, z0=50., vf=1.0):
        """Compute the time-domain reflectometry

        Parameters
        ----------
        fr : np.ndarray
            frequency or array of frequencies
        rtl : np.ndarray
            return loss at one frequency or an array of frequencies
        z0 : float, optional
            specified load impedance, by default 50. + 0j
        vf : float, optional
            velocity factor (for cable), by default 1.0
        """
        # print ('rtl: ', rtl)
        tdr = np.fft.ifft(rtl)
        ft = np.mean(np.diff(fr))
        t = 1./fr
        # print('tdr t: ', t)
        # print('tdr rtl: ', tdr.real)
        return(t, tdr.real)

    def clear_plots(self):
        self.color_index = 0
        for k in self.pl.keys():
            self.pl[k].clear()

    def resetAA30(self):
        self.re_off()
        self.re_on()


    
    # def mouseMoved(evt):
    #     pos = evt[0]  ## using signal proxy turns original arguments into a tuple
    #     if self.pl['R'].sceneBoundingRect().contains(pos):
    #         mousePoint = vb.mapSceneToView(pos)
    #         index = int(mousePoint.x())
    #         if index > 0 and index < len(data1):
    #             label.setText("<span style='font-size: 12pt'>x=%0.1f,   <span style='color: red'>y1=%0.1f</span>,   <span style='color: green'>y2=%0.1f</span>" % (mousePoint.x(), data1[index], data2[index]))
    #         vLine.setPos(mousePoint.x())
    #         hLine.setPos(mousePoint.y())

    def onMouseMoved(self, evt):
        pos = evt
        if self.pl['R'].vb.sceneBoundingRect().contains(pos):
            point =self.pl['R'].vb.mapSceneToView(pos)
            self.R_label.setHtml(
                "<p style='color:white'>F： {0} <br> R: {1}</p>".\
                format(f"{point.x():.2f}", f"{point.y():.2f}")
            )
        elif self.pl['SWR'].vb.sceneBoundingRect().contains(pos):
            point =self.pl['SWR'].vb.mapSceneToView(evt)
            self.SWR_label.setHtml(
                "<p style='color:white'>F： {0} <br> R: {1}</p>".\
                format(f"{point.x():.2f}", f"{point.y():.2f}")
            )

        elif self.pl['RTL'].vb.sceneBoundingRect().contains(pos):
            point =self.pl['RTL'].vb.mapSceneToView(evt)
            self.RTL_label.setHtml(
                "<p style='color:white'>F： {0} <br> R: {1}</p>".\
                format(f"{point.x():.2f}", f"{point.y():.2f}")
            )
        else:
            pass
            

    def plot_results(self, freq:np.ndarray, re: np.ndarray, im: np.ndarray,
                    swr: np.ndarray, rtl: np.ndarray, first:bool=True):
        c = pg.intColor(self.color_index, hues=9, values=1, maxValue=255,
            minValue=150, maxHue=360, minHue=0, sat=255, alpha=255)
        p = pg.mkPen(cosmetic=True, width=1.0, color=c)
        p2 = pg.mkPen(cosmetic=True, width=1.0, color='b', 
                style=QtCore.Qt.PenStyle.DashLine)
        
        if first:
            self.curve = {}
            self.curve['R'] = self.pl['R'].plot(freq, re, pen=p)
            self.curve['X'] = self.pl['R'].plot(freq, im, pen=p2) 
            #pg.PlotCurveItem(fr, zx, pen=p2)
            #self.pl['X'].addItem(self.curve['X'])
            self.curve['RTL'] = self.pl['RTL'].plot(freq, rtl, pen=p)
            self.curve['SWR'] = self.pl['SWR'].plot(freq, swr, pen=p)
        else:
            self.curve['R'].setData(freq, re)
            self.curve['X'].setData(freq, im)
            self.curve['RTL'].setData(freq, rtl)
            self.curve['SWR'].setData(freq, swr)
        self.app.processEvents()
        return(p)  # return the pen so we can use it at the end to plot the tdr

    def re_version(self):
        self.re_off()
        self.re_on()
        self.send_re('VER')
        r = self.get_re()
        if r is None:
            print ('RE AA-30 appears to be not responding - is it on?')
            exit()
        print ("RE AA-30 Version = %s" % (r))

    def re_on(self):
        self.send_re('ON')
        r = self.get_re()
        if r != 'OK':
            print ('ON returned: %s' % (r))
        time.sleep(0.2)  # give it time to turn on

    def stop_scan(self):
        self.stopscan = True

    def re_sample(self, start_freq=2., end_freq=30., nfreq=10):
        if self.in_sampling:
            return  # ignore request
        self.in_sampling = True
        self.stopscan=False
#        print('cf: %f  span: %f  nfreq: %d', cf, span, nfreq)
        results = []
        freqlist = np.linspace(start_freq, end_freq, num=nfreq+1)
        rx = np.zeros_like(freqlist)
        zx = np.zeros_like(freqlist)
        swr = np.zeros_like(freqlist)
        rtl = np.zeros_like(freqlist)

       
        self.plot_results(freq=freqlist, re=rx, im=zx, swr=swr, rtl=rtl)

        self.re_on()
        fq =start_freq+(end_freq - start_freq)/2.0
        span = end_freq - start_freq
        self.send_re('FQ%d' % int(fq*1e6))
        r = self.get_re()
        if r not in ['OK']:
            print('Response  not "OK", got ""{:s}"" instead'.format(r))
            self.re_off()
            self.in_sampling = False
            raise Exception('Failed to set frequency')
#        print ('FQ command returned: {:s}'.format(r))
        time.sleep(0.01)
        self.send_re('sw%d' % int(span*1e6))
        r = self.get_re()
        if r not in ['OK']:
            # print (r)
            self.re_off()
            self.in_sampling = False
            raise Exception('Failed to set sweep range')
#        print ('Command SW returned: ', r)
        time.sleep(0.01)
        self.send_re('FRX%d' % nfreq)
        r = self.get_re()
        if r not in ['OK']:
            # print (r)
            self.re_off()
            self.in_sampling = False
            raise Exception('Failed to set frx')
        first = True
        # dynamically update the plots - 
        for n in range(len(freqlist)):
            if self.stopscan:
                break
            x = self._readline()
            if x in ['ERROR']:  # oops, not good
                self.re_off()
                self.in_sampling = False
                raise Exception("Processing canceled by user")
            if len(x) == 0 or x[0:2] == 'OK':  # an ok means we are done!
                print ('FRX completed OK')
                done = True
            if len(x) != 2:  # line breaks - just skip them
                results.append(x[:-2])
                (f,rf,zf) = x.split(b',')
#                print('n, freq; ', n, f)
                if float(f) > 0.0:
                    freqlist[n] = float(f)
                    rx[n] = float(rf)
                    zx[n] = float(zf)
                else:
                    freqlist[n] = np.nan
                    rx[n] = np.nan
                    zx[n] = np.nan
                swr, rtl = self.compute_swr_and_return_loss(re=rx[0:n], im=zx[0:n], z0=50.)
                pen = self.plot_results(freq=freqlist[0:n], re=rx[0:n], im=zx[0:n], 
                                        swr=swr[0:n],
                                        rtl=rtl[0:n], 
                                        first=first)
                first = False
                n += 1
        self.in_sampling = False
        td, tdr = self.compute_tdr(freqlist, rtl)
        self.pl['TDR'].plot(td[1:len(tdr)], tdr[1:], pen=pen)
        self.re_off()
        return(freqlist, rx, zx, tdr.real)

    def re_off(self):
        self.send_re('OFF')
        self.get_re()
        #print( 'OFF returned: %s' % (r))

    def send_re(self, cmd):
        cmd = cmd + '\r'

        self.re_sp.write(cmd.encode())
        
    def get_re(self, verbose = False):
        """
        Read after a command to the AA-30
        Commands are a response consisting of:
        <cr><lf>value<cr><lf>
        optionally followed by
        <cr><lf>OK<cr><lf>
        """
        s = ''  # result string
        string_end_flag = False
        crlf_count = 0
        buf = '' # collect the whole buffer
        while not string_end_flag:
            buf += self.re_sp.read(1).decode() # do this low-level, character at a time.
            if len(buf) == 0:  # no characters, likely the device is not on
                return None
            if verbose:
                print ('ts is: %d' %  ord(buf[-1]), buf[-1])
            if buf[-1] == '\r':  # pop line feeds
                continue
            if buf[-1] == '\n' and buf[-2] == '\r':  # catch newlines
                    crlf_count += 1
                    if crlf_count == 2:
                        string_end_flag = True
                    continue
            if buf[-3:-1] == 'OK':
                string_end_flag = True
            if verbose:
                print ('buffer: ', buf)
            s += buf[-1]
        if verbose: 
            print ('s:[%s] ' % s)
        if len(s) > 0:
            return s
        else:            
            return None

    def _readline(self):
        eol = b'\r\n'
        leneol = len(eol)
        line = bytearray()
        while True:
            c = self.re_sp.read(1)
            if c:
                line += c
                if line[-leneol:] == eol:
                    break
            else:
                break
        return bytes(line)
        
def main():
    app = REAA30()

if __name__ == "__main__":
    main()
