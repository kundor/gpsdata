import os
from collections import namedtuple, UserList
import time
from datetime import datetime, timedelta, timezone
from utility import fileread
from gpsazel import gpsazel, poslist
from gpstime import gpsweek, gpsdow, gpsleapsecsutc

sitelocs = { 'vpr3' : (-1283634.1275, -4726427.8944, 4074798.0304) } # actually p041's location

Record = namedtuple('Record', ['prn', 'el', 'az', 'sod', 'snr'])

def rngcheck(word, name, mn, mx, length, line):
    val = int(word)
    if val < mn or val > mx or len(word) != length:
        raise ValueError(word + ' is not a valid ' + name + ' (in line "' + line + '")')
    return val

def fltcheck(word, name, mn, mx, line):
    val = float(word)
    if val < mn or val > mx:
        raise ValueError(word + ' is not a valid ' + name + ' (in line "' + line + '")')
    return val

def parserec(line):
    words = line.split()
    if len(words) != 7:
        raise ValueError(line + ' is not a valid snr89 record')
    rngcheck(words[4], 'zero', 0, 0, 1, line)
    rngcheck(words[5], 'zero', 0, 0, 1, line)
    return Record(rngcheck(words[0], 'PRN', 1, 32, 2, line),
                  rngcheck(words[1], 'elevation', 0, 90, 2, line),
                  rngcheck(words[2], 'azimuth', 0, 359, 3, line),
                  fltcheck(words[3], 'second of day', 0, 86400, line),
                  fltcheck(words[6], 'SNR', 0, 100, line))

def formrec(prn, el, az, sod, snr):
    return '{:02} {:7.4f} {:8.4f} {} 0 0 {}\n'.format(prn, el, az, sod, snr)

def canread(file):
    """Check if the given path is a readable regular file."""
    return os.path.isfile(file) and os.access(file, os.R_OK)

def fullyear(yr):
    """Convert two-digit year to full year.

    Assumes that two-digit years matching or preceding the current time
    belong to the current century, and that others belong to the previous century.
    This works if the local clock is correct; dates are not in the future; and
    all data is less than a century old.
    """
    yearnow = time.gmtime().tm_year
    return (yearnow - yr) // 100 * 100 + yr


class snr89(UserList):
    """Class holding data from an snr89 file.

    Has fields site (the site code), doy, year, rxloc (with the ECEF location in meters).
    Is a list of named tuples with fields prn, el, az, sod, snr.
    The el (elevation) and az (azimuth) fields are as found in the file,
    and may be 0 or truncated to integers.
    """
    def __init__(self, dir, filename=None):
        UserList.__init__(self)
        if filename is None:
            if not canread(dir):
                raise ValueError('Given path ' + dir + ' does not lead to a readable file.')
            filename = os.path.basename(dir)
            dir = os.path.dirname(dir)
        self.site = filename[:4]
        self.doy = int(filename[4:7])
        self.year = fullyear(int(filename[9:11]))
        try:
            self.rxloc = sitelocs[self.site]
        except KeyError:
            print('First four characters of filename, ' + self.site
                  + ', are not a recognized site name. Receiver location unknown.')
        fid = fileread(os.path.join(dir, filename))
        for l in fid:
            try:
                self.append(parserec(l))
            except ValueError as e:
                print(e)

def _gpssow(year, doy, sod):
    dt = _todatetime(year, doy, sod)
    leaps = gpsleapsecsutc(dt)
    sod = (sod + leaps) % (60*60*24)
    return gpsdow(dt)*60*60*24 + sod

def _todatetime(year, doy, sod):
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days = doy - 1) + timedelta(seconds = sod)

def getazel(snr, index):
    """Given snr89 object and record number, compute azimuth and elevation."""
    dt = _todatetime(snr.year, snr.doy, snr[index].sod)
    return gpsazel(snr.rxloc, snr[index].prn, gpsweek(dt), _gpssow(snr.year, snr.doy, snr[index].sod))

def rewrite(odir, ndir, filename=None, log='/home/xenon/student/nima9589/snr89log'):
    log = open(log, 'at')
    print('--------------------', file=log)
    if filename is None:
        if not canread(odir):
            print('Given path ' + odir + ' does not lead to a readable file.', file=log)
            return
        filename = os.path.basename(odir)
        odir = os.path.dirname(odir)
    print(filename, file=log)
    site = filename[:4]
    doy = int(filename[4:7])
    year = fullyear(int(filename[9:11]))
    week = gpsweek(_todatetime(year, doy, 0))
    sow0 = _gpssow(year, doy, 0)
    try:
        rxloc = sitelocs[site]
    except KeyError:
        print('First four characters of filename, ' + site
              + ', are not a recognized site name. Receiver location unknown.', file=log)
        return
    pl = poslist(week, sow0, sow0 + 60*60*24)
    os.makedirs(ndir, exist_ok = True)
    fid = fileread(os.path.join(odir, filename))
    newfid = open(os.path.join(ndir, filename), 'wt')
    for l in fid:
        try:
            rec = parserec(l)
        except ValueError as e:
            print(e, file=log)
            print('   (on line ' + str(fid.lineno) + ')', file=log)
            continue
        naz, nel = gpsazel(rxloc, rec.prn, week, sow0 + rec.sod, pl)
        if rec.el != 0 or rec.az != 0:
# Compare truncated azimuth and elevation to computed ones
            dazi = abs(naz - rec.az)
            dele = abs(nel - rec.el)
            if dazi > 0.6 or dele > 0.6:
                print('Recorded and computed azimuth, elevation differ by '
                      + str(dazi) + ', ' + str(dele) + ' on line '
                      + str(fid.lineno), file=log)
                print(l, file=log)
        newfid.write(formrec(rec.prn, nel, naz, rec.sod, rec.snr))
    fid.close()
    newfid.close()
    log.close()
