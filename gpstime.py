# Created by Nick Matteo <kundor@kundor.org> June 9, 2009
'''
Defines timezones (tzinfo inheritors) useful for GPS work.

UTCOffset(timedelta offset) is a time zone at a constant offset from UTC.
`utctz' is an instantiation of UTCOffset with no offset.
TAIOffset(timedelta offset) is a time zone at a constant offset from TAI.
`gpstz' is an instantation of TAIOffset with offset = 19 s.
LeapSeconds is a class providing a dictionary of UTC datetimes and
corresponding leapsecond offsets from TAI.
LeapSeconds.update() is a class method to update the leap seconds information.
`leapseconds' is an instantiation of the leap second dictionary.

NB: Standard Python datetime objects are only precise to 1 microsecond.
'''
# These classes do NOT account for:
#  - Difference in GPS time vs. UTC(USNO) (Currently sync'd once per day.)
#  - Difference in UTC(USNO) vs. UTC (sync'd about once a month.)
#  - Difference in UTC vs. GLONASS
#  - Difference in TAI vs. Galileo
# I don't know about UTC vs. GLONASS, but the other errors remain on the order
# of a few nanoseconds.  The sum of all such errors should remain well below a
# microsecond (the limit of Python's datetime precision.)

import re
import os
from os import path
from urllib.request import urlopen
from urllib.error import URLError
from datetime import datetime, timedelta, timezone, tzinfo as TZInfo
import time
from warnings import warn
from collections.abc import Sequence
from numbers import Number


URL1 = 'http://maia.usno.navy.mil/ser7/tai-utc.dat'
URL2 = 'http://hpiers.obspm.fr/iers/bul/bulc/UTC-TAI.history'

GPSepoch = datetime(1980, 1, 6, 0, 0, 0, 0, timezone.utc)

def isnaive(dt):
    '''Return true if input is a naive datetime.'''
    return isinstance(dt, datetime) and (dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None)

def dhours(hrs):
    '''Convenience function: returns timedelta of given # of hours.'''
    return timedelta(hours=hrs)

def getutctime(dt=None, dtclass=datetime, tz=timezone.utc):
    """Convert datetime, struct_time, tuple (Y,M,D,[H,M,S,μS]), or POSIX timestamp
    to UTC aware datetime object. Assumed to already be UTC unless the timezone
    is included (aware datetime objects and struct_times).
    """
    if dt is None:
        return dtclass.now(tz)
    elif isinstance(dt, time.struct_time):
        return dtclass.fromtimestamp(time.mktime(dt), tz)
    elif isinstance(dt, Sequence) and len(dt) == 2: # list or tuple: GPS Week, GPS second of week
        gt = gpsdatetime() + timedelta(weeks=dt[0], seconds=dt[1])
        return gt.astimezone(tz)
    elif isinstance(dt, Sequence): # list or tuple: Year, Month, Day, H, M, S, μS
        return dtclass(*dt, tzinfo=tz)
    elif isinstance(dt, Number):
        return dtclass.fromtimestamp(dt, tz)
    elif isnaive(dt):
        return dt.replace(tzinfo=tz)
    elif isinstance(dt, dtclass):
        return dt.astimezone(tz)
    raise ValueError("Don't know how to interpret this as time")

def gpsweek(dt):
    """Given UTC datetime, return GPS week number."""
    return int((dt + timedelta(seconds=gpsleapsecsutc(dt)) - GPSepoch) / timedelta(weeks=1))

def gpsdow(dt):
    """Given UTC datetime, return GPS Day of Week."""
    return (dt + timedelta(seconds=gpsleapsecsutc(dt))).isoweekday() % 7

class LeapSeconds(dict):
    '''
    Uses data file (leapseco.dat, in same directory as the code)
    to form a dictionary of datetimes : leap second adjustment.
    TAI differs from UTC by the adjustment at the latest datetime
    before the given epoch.
    NB: For dates before 1972, there is secular variation in the
    adjustment, which is NOT accounted for.
    '''
    infofile = path.join(path.dirname(path.abspath(__file__)), 'leapseco.dat')

    def __init__(self):
        '''Load and parse leap seconds data file.'''
        dict.__init__(self)
        try:
            lfile = open(self.infofile)
        except IOError:
            warn('Leap seconds data file not found.  Attempting download.')
            if self.update():
                lfile = open(self.infofile)
            else:
                raise RuntimeError('Leap seconds data file not available.')
        for line in lfile:
            match = re.match('^([0-9:/-]+) : ([0-9.-]+)$', line)
            if match:
                dt = datetime(*(time.strptime(match.group(1), '%Y/%m/%d-%H:%M:%S')[0:6]))
                self[dt] = float(match.group(2))
        lfile.close()

    @classmethod
    def timetoupdate(cls):
        '''
        Attempts to verify whether January 1 or July 1 has passed since
        last update; otherwise, don't bother (new leap seconds only occur
        on those dates.)
        '''
        now = datetime.utcnow()
        if not os.access(cls.infofile, os.R_OK):
            return True  # If file isn't there, try update
        try:
            fid = open(cls.infofile)
        except IOError:
            return True  # ditto
        try:
            updtime = datetime(*(time.strptime(fid.readline(),
                                               'Updated: %Y/%m/%d\n')[0:6]))
        except ValueError:
            warn('Leap second data file in invalid format.')
            return True
        fid.close()
        if updtime > now:
            warn(ValueError, 'Leap second data file is from the future.')
            return False
        elif updtime.month <= 6:
            target = datetime(updtime.year, 7, 1)
        else:
            target = datetime(updtime.year + 1, 1, 1)
        if now <= target:
            return False
        return True

    @classmethod
    def update(cls):
        '''
        Download and parse new leap second information from reliable
        web sources.
        '''
        if not cls.timetoupdate():
            print('No potential leap second has occurred since last update.')
            return False
        if not os.access(path.dirname(cls.infofile), os.W_OK):
            raise IOError('Leap second data file cannot be written.')
        try:
            upd = urlopen(URL1)
            form = 1
        except URLError:
            upd = urlopen(URL2)
            form = 2
        mons = ['', b'JAN', b'FEB', b'MAR', b'APR', b'MAY', b'JUN', b'JUL',
                b'AUG', b'SEP', b'OCT', b'NOV', b'DEC']
        newfile = path.join(path.dirname(__file__), 'leapseco.new')
        lfile = open(newfile, 'w')
        lfile.write('Updated: ' + datetime.utcnow().strftime('%Y/%m/%d\n'))
        year = 1961
        for line in upd:
            if form == 1:
                year = int(line[0:5])
                month = mons.index(line[6:9].upper())
                day = int(line[10:13])
                adjust = float(line[36:48])
            elif form == 2:
                if len(line) < 36 or re.match(b' ?-* ?$| RELATIONSHIP| Limits', line):
                    continue
                if line[0:6].strip() != b'':
                    year = int(line[0:6])
                month = mons.index(line[7:10].upper())
                day = int(line[12:15].rstrip(b'. '))
                adjust = float(line[31:47].replace(b' ', b'').rstrip(b's\t\n'))
            lfile.write(datetime(year, month, day).strftime('%Y/%m/%d-%H:%M:%S')
                        + ' : ' + str(adjust) + '\n')
        upd.close()
        lfile.close()
        if path.exists(cls.infofile):
            os.remove(cls.infofile)
        os.rename(newfile, cls.infofile)
        return True

leapseconds = LeapSeconds()

def leapsecs(dt, cmp):
    '''# of leapseconds at datetime dt.  Whether dt exceeds the UTC time in
    the leapseconds dict is determined by the provided function cmp.'''
    dt = dt.replace(tzinfo=None)
    if dt.year < 1958:
        raise ValueError('TAI vs UTC is unclear before 1958; unsupported.')
    try:
        return leapseconds[max([l for l in leapseconds if cmp(l, dt)])]
    except ValueError:
        return 0 # before 1961-Jan-01, TAI = UTC

def leapsecsutc(utc):
    '''# of TAI-UTC leapseconds at UTC datetime.'''
    return leapsecs(utc, lambda l, dt : l <= dt)

def gpsleapsecsutc(utc):
    '''# of GPS-UTC leapseconds at UTC datetime.'''
    return leapsecs(utc, lambda l, dt : l <= dt) - 19

def leapsecstai(tai):
    '''# of TAI-UTC leapseconds at TAI datetime.'''
    return leapsecs(tai, lambda l, dt : leapseconds[l] <= (dt - l).total_seconds())

class UTCOffset(TZInfo):
    '''UTC: Coordinated Universal Time; with optional constant offset'''

    def __init__(self, offset=timedelta(0), name=None):
        self.offset = offset
        if name is None:
            end = 1
            if offset.seconds % 60:  # not an even minute
                end = 3
            elif offset.seconds % 3600:  # not an even hour
                end = 2
            if offset > timedelta(0):
                name = 'UTC + ' + str(offset).split(':')[0:end].join(':')
            elif offset < timedelta(0):
                name = 'UTC - ' + str(-offset).split(':')[0:end].join(':')
            else:
                name = 'UTC'
        self.name = name

    def utcoffset(self, dt):
        return self.offset
    def dst(self, dt):
        return timedelta(0)
    def tzname(self, dt):
        return self.name
    def __str__(self):
        return self.name + ' (datetime.tzinfo timezone)'

utctz = UTCOffset()

class TAIOffset(UTCOffset):
    '''
    TAI: International Atomic Time.  utcoffset() is number of leap seconds.
    '''
    # For GPS we deal with TAI(USNO) and UTC(USNO).

    def __init__(self, offset=timedelta(0), name='TAI'):
        self.offset = offset
        self.name = name

    def utcoffset(self, dt):
        if dt.tzinfo in (utctz, timezone.utc):
            off = leapsecsutc(dt)
        else:
            off = leapsecstai(dt - self.offset)
        return timedelta(seconds=off) + self.offset

    def fromutc(self, dt):
        '''Given `dt' in UTC, return the same time in this timezone.'''
        return dt + self.utcoffset(dt.replace(tzinfo=utctz))

taitz = TAIOffset()
gpstz = TAIOffset(timedelta(seconds=-19), 'GPS')

def getgpstime(dt=None, tz=gpstz):
    if isinstance(dt, datetime) and not isinstance(dt, gpsdatetime):
        return gpsdatetime.copydt(dt, tz)
    return getutctime(dt, gpsdatetime, tz)

class gpsdatetime(datetime):
    '''
    gpsdatetime is simply a version of datetime.datetime which allows
    the offset from UTC to not be in whole minutes.
    It also sets tzinfo to gpstz by default, instead of None.
    '''
    def __new__(cls, year=1980, month=1, day=6, hour=0, minute=0, second=0,
                microsecond=0, tzinfo=gpstz):
        if isinstance(year, str) and isinstance(month, TZInfo):
            return datetime.__new__(cls, year, month)
        elif isinstance(year, str):
            return datetime.__new__(cls, year)
        return datetime.__new__(cls, year, month, day, hour, minute, second,
                                int(microsecond), tzinfo)

    @classmethod
    def copydt(cls, other, tzinfo=None):
        '''Copy a standard datetime object into a gpsdatetime,
        optionally replacing tzinfo.
        '''
        if tzinfo is None:
            tzinfo = other.tzinfo
        return cls.__new__(cls, other.year, other.month, other.day, other.hour,
                           other.minute, other.second, other.microsecond, tzinfo)

    def utcoffset(self):
        '''
        Should be identical to datetime.utcoffset() besides allowing
        tzinfo.utcoffset() to not be in whole minutes.
        '''
        if self.tzinfo is None:
            return None
        off = self.tzinfo.utcoffset(self)
        if off is None:
            return off
        elif not isinstance(off, timedelta):
            raise ValueError('tzinfo.utcoffset() must return a timedelta.')
        elif abs(off) >= timedelta(days=1):
            raise ValueError('tzinfo.utcoffset() must be less than one day.')
        return off

    def astimezone(self, tz):
        '''Return equivalent time for timezone tz.'''
        dt = self.replace(tzinfo=None)
        dt = dt - self.utcoffset()
        dt = dt + tz.utcoffset(dt.replace(tzinfo=utctz))
        return dt.replace(tzinfo=tz)

    def __add__(self, other):
        '''Add timedelta to gpsdatetime.'''
        crn = datetime.__add__(self.replace(tzinfo=None), other)
        return self.copydt(crn, self.tzinfo)

    def __sub__(self, other):
        '''Subtract other gpsdatetime or datetime to produce timedelta,
        or subtract timedelta to produce gpsdatetime.
        '''
        if isinstance(other, datetime):
            if self.utcoffset() is None and other.utcoffset() is None:
                return datetime.__sub__(self, other)
            elif isinstance(self.tzinfo, TAIOffset) and isinstance(other.tzinfo, TAIOffset):
                off = datetime.__sub__(self.replace(tzinfo=None), other.replace(tzinfo=None))
                off += other.tzinfo.offset - self.tzinfo.offset
                return off
            elif self.utcoffset() is not None and other.utcoffset() is not None:
                off = datetime.__sub__(self.replace(tzinfo=None),
                                       other.replace(tzinfo=None))
                off += other.utcoffset() - self.utcoffset()
                return off
            else:
                raise TypeError('Cannot subtract naive datetime from '
                                'aware datetime')
        else:
            crn = datetime.__sub__(self.replace(tzinfo=None), other)
            return self.copydt(crn, self.tzinfo)

    def __eq__(self, other):
        if self.utcoffset() is None and other.utcoffset() is None:
            return datetime.__eq__(self, other)
        elif self.utcoffset() is None or other.utcoffset() is None:
            raise TypeError('Cannot compare naive and aware datetimes')
        else:
            us = datetime.__sub__(self.replace(tzinfo=None), self.utcoffset())
            uo = datetime.__sub__(other.replace(tzinfo=None), other.utcoffset())
            return us == uo

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if self.utcoffset() is None and other.utcoffset() is None:
            return datetime.__lt__(self, other)
        elif self.utcoffset() is not None and other.utcoffset() is not None:
            us = datetime.__sub__(self.replace(tzinfo=None), self.utcoffset())
            uo = datetime.__sub__(other.replace(tzinfo=None), other.utcoffset())
            return us < uo
        else:
            raise TypeError("Can't compare naive and aware datetimes")

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return not self < other

    def __gt__(self, other):
        return not self < other and self != other

    def __str__(self):
        return datetime.__str__(self.replace(tzinfo=None))
