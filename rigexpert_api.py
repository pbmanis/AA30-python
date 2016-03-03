# jon klein, jtklein@alaska.edu
# python API for rigexpert antenna analyzers, see http://www.rigexpert.com/index?f=aa_commands
# mit license

import serial
import numpy as np
import matplotlib.pyplot as plt
import csv
import pdb

RIGPORT = '/dev/ttyUSB0'
VERBOSE = True
RADAR = 'adw'

class rigexpert_analyzer:
    def __init__(self, port = RIGPORT):
        self.ser = serial.Serial(port, 38400, timeout = 5)
        assert self._command_scalar('ON') == 'OK'
        #assert self._command_scalar('VER') == 'AA-30 109'
        self.span_hz = 0
        self.cfreq_hz = 0

    def close(self):
        assert self._command_scalar('OFF') == 'OK'
        self.ser.close()
    
    # set center frequency in hz
    def cfreq(self, freq):
        assert self._command_scalar('FQ{}'.format(str(int(freq)))) == 'OK'
        self.cfreq_hz = freq
    
    # set span in hz
    def span(self, span_hz):
        assert self._command_scalar('SW{}'.format(str(int(span_hz)))) == 'OK'
        self.span_hz = span_hz

    # measure a sweep
    def sweep(self, npoints):
        assert self.cfreq_hz != 0
        assert self.span_hz != 0
        assert npoints > 0

        cmd = 'FRX' + str(int(npoints))

        s = self._command_vector(cmd, npoints)
        f = np.array([si[0] for si in s])
        r = np.array([si[1] for si in s])
        x = np.array([si[2] for si in s])
        
        return (f, r, x)

    def _command_scalar(self, cmd):
        self.ser.write(cmd + '\n')
        r = self.ser.readline()
        while len(r) == 2 : # skip ahead, the aa-30 spits out lots of blank lines..
            r = self.ser.readline()
        if VERBOSE:
            print('command: {}, response: {}'.format(cmd, r))
        return r[:-2]

    def _command_vector(self, cmd, lines):
        self.ser.write(cmd + '\n')

        print('command: ' + cmd)

        r = []
        
        l = self.ser.readline()
        while len(l) == 2 :
            l = self.ser.readline()

        for i in range(lines):
            l = self.ser.readline().split(',')
            l = [float(li) for li in l]
            r.append(l)
            print r[-1]
        
        return r


def main():
    ant = input('enter an antenna number: ')
    ra = rigexpert_analyzer()
    ra.cfreq(13e6)
    ra.span(10e6)
    f, r, x = ra.sweep(10)
    
    z = r + 1j * x
    z0 = 50
    ref = abs((z - z0) / (z + z0))
    vswr = (1 + ref) / (1 - ref)
   
    
    with open('{}_ant{}.csv'.format(RADAR, ant), 'wb') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)

        csvwriter.writerow(['freq (MHz)', 'vswr', 'R (ohms)', 'X (ohms)'])
        for i in range(len(f)):
            csvwriter.writerow([f[i], vswr[i], r[i], x[i]])

    ra.close()
    plt.plot(f, vswr)
    plt.xlabel('frequency (MHz)')
    plt.ylabel('VSWR')
    plt.title('antenna {} VSWR'.format(ant))
    axes = plt.gca()
    axes.set_ylim([0, 10])
    plt.savefig('{}_ant{}.png'.format(RADAR, ant)) 
    plt.show()
    
if __name__ == '__main__':
    main()
