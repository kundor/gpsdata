from utility import fileread
from gpstime import gpsdatetime
from numbers import Number
import re
import numpy as np
from math import cos, sin, pi

__all__ = ['readsp3', 'satpos']

sp3head = [(r'#[abc][PV]', 1),
           (r'##', 1),
           (r'\+ ', 5),
           (r'\+\+', 5),
           (r'%c [MG]  cc GPS', 1),
           (r'%c', 1),
           (r'%f', 2), 
           (r'%i', 2),
           (r'/\*', 4)]
"""The leading characters of the 22 header lines. We check that they match
but otherwise ignore the header entirely."""

class posrecord(dict):
    """A record of satellite positions at a given epoch.

    Has field epoch in addition to being a dictionary (by PRN code) of XYZ tuples.
    Can access as record.epoch, record[13], record['G17'], or iteration.
    """
    def __init__(self, epoch):
        self.epoch = epoch

    def __getitem__(self, index):
        """Allow you to access GPS satellites, eg record['G13'], as
        simply record[13].  For GLONASS or Galileo, you must use the full code.
        """
        if index == 'epoch':
            return self.epoch
        if isinstance(index, Number):
            return dict.__getitem__(self, 'G%02d' % index)
        return dict.__getitem__(self, index)

    def __contains__(self, index):
        """Allow containment tests (eg if 13 in record:) for abbreviated GPS PRNs."""
        if isinstance(index, (int, long, float)):
            return dict.__contains__(self, 'G%02d' % index)
        return dict.__contains__(self, index)

def _procheader(fid):        
    for cc, num in sp3head:
        for _ in range(num):
            ll = fid.next()
            if not re.match(cc, ll):
                raise ValueError(fid.name + ' does not have valid sp3 header lines (line '
                        + str(fid.lineno) + ' begins ' + ll[:len(cc)] + '; '
                        'we expected ' + cc + ').')

def _gps_second(epline):
    """Convert an epoch header line to seconds from the gps epoch.
    
    The value is a Python float, which has a resolution of roughly one microsecond
    when the value is around a billion (ca. 2016)"""
    dt = gpsdatetime.strptime(epline[:29], "*  %Y %m %d %H %M %S.%f")
    return (dt - gpsdatetime()).total_seconds()
    
def _addpos(rec, pline):
    prn = pline[1:4]
    x = float(pline[4:18])
    y = float(pline[18:32])
    z = float(pline[32:46])
    rec[prn] = (x, y, z)

def readsp3(filename):
    """List of dictionaries, PRN to (x,y,z) tuple, from the sp3 file.
    
    Each dictionary has an epoch field with the seconds since the GPS epoch.
    """
    with fileread(filename) as fid:
        _procheader(fid)
        poslist = []
# epoch lines begin with '*'. Position lines begin with 'P'.
# Velocity lines begin with 'V' (ignored); correlation lines begin with 'E' (ignored).
# (last line is 'EOF').
        for line in fid:
            if line[0] in ('E', 'V'):
                continue
            elif line[0] == '*':
                poslist.append(posrecord(_gps_second(line)))
            elif line[0] == 'P':
                _addpos(poslist[-1], line)
            else:
                print('Unrecognized line in sp3 file ' + filename + ':\n' + line
                        + '\nIgnoring...')
        return poslist

def _rot3(vector, angle):
    """Rotate vector by angle around z-axis"""
    x =  cos(angle)*vector[0] + sin(angle)*vector[1]
    y = -sin(angle)*vector[0] + cos(angle)*vector[1]
    z = vector[2]
    return x, y, z

def sp3_interpolator(t, tow, xyz):
# This function modified from code by Ryan Hardy
    n = len(tow)
    omega = 2*2*pi/86164.090530833 # 4π/mean sidereal day
    tmed = tow[n//2]

    tinterp = [t - tmed for t in tow]
    jrange = [(j + n//2) % n - n//2 for j in range(n)]
    independent = np.array([[cos(abs(j)*omega*t - (j>0)*pi/2) for t in tinterp] for j in jrange])
    xyzr = [_rot3(xyz[j], omega/2*tinterp[j]) for j in range(n)]
     
    eig =  np.linalg.eig(independent.T)
    iinv  = (eig[1] * 1/eig[0] @ np.linalg.inv(eig[1]))

    coeffs = iinv @ xyzr
    j = np.arange(-(n-1)//2, (n-1)//2 + 1)
    tx = t - tmed
    r_inertial =  np.sum(coeffs[j].T * np.cos(np.abs(j)*omega*tx - (j > 0)*np.pi/2), -1)
    return _rot3(r_inertial, -omega/2*tx)

def satpos(poslist, prn, sec):
    """Compute position of GPS satellite with given prn # at given GPS second.

    Return X, Y, Z cartesian coordinates, in km, Earth-Centered Earth-Fixed.
    GPS second is total seconds since the GPS epoch (float).
    """
# Just a dumb wrapper for sp3_interpolator for now
    idx = int((sec - poslist[0].epoch + 450) // 900)
# We are assuming 15-minute satellite positions here!
    tow = [poslist[k].epoch for k in range(idx-3,idx+4)]
    xyz = [poslist[k][prn] for k in range(idx-3,idx+4)]
    return np.array(sp3_interpolator(sec, tow, xyz))

    
