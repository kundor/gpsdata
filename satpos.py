from utility import fileread
from gpstime import gpsdatetime
import re
import numpy as np
from math import cos, sin, pi
from scipy.interpolate import interp1d

__all__ = ['readsp3', 'satpos', 'mvec', 'coef_fn']

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
        if isinstance(index, (int, float)):
            return dict.__getitem__(self, 'G%02d' % index)
        return dict.__getitem__(self, index)

    def __contains__(self, index):
        """Allow containment tests (eg if 13 in record:) for abbreviated GPS PRNs."""
        if isinstance(index, (int, float)):
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

def satpos(poslist, prn, sec):
    """Compute position of GPS satellite with given prn # at given GPS second.

    Return X, Y, Z cartesian coordinates, in km, Earth-Centered Earth-Fixed.
    GPS second is total seconds since the GPS epoch (float).
    """
    step = poslist[1].epoch - poslist[0].epoch
    idx = int((sec - poslist[0].epoch + (step/2)) // step)
    times = [p.epoch - sec for p in poslist[idx-3:idx+4]]
    xyz = [p[prn] for p in poslist[idx-3:idx+4]]
    return [1, 0, 0, 0, 1, 1, 1] @ coeffs(times, xyz)

def mvec(t, n=5):
    p = 2*pi/86164.090530833*t # 2π/mean sidereal day
    return [1] + [sin(k*p) for k in range(1, n+1)] + [cos(k*p) for k in range(n,0,-1)]

def coeffs(times, xyz):
    n = len(times)//2
    ind = np.array([mvec(t, n) for t in times])
    return np.linalg.solve(ind, xyz)

def allcoeffs(poslist, prn, n=5):
    return [coeffs([p.epoch for p in poslist[idx-n:idx+n+1]],
                   [p[prn] for p in poslist[idx-n:idx+n+1]])
            for idx in range(n,len(poslist)-n)]

def coef_fn(poslist, prn, n=5, type='linear'):
    AC = allcoeffs(poslist, prn, n)
    tint = [p.epoch for p in poslist[n:-n]]
    return interp1d(tint, AC, type, axis=0, assume_sorted=True)
