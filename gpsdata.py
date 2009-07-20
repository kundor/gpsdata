# Created by Nick Matteo <kundor@kundor.org> June 9, 2009
'''
Store observation data from a GPS Receiver

Stores data as provided in RINEX files or other data logs.
Specifically, store GPS Time, Pseudorange, Phase, Doppler Frequency, and SNR
for each satellite, and each frequency, observed.
.iter() allows iteration over these values as:
    -a dictionary of dictionaries of all satellites and fields, per epoch
    -a dictionary, for a given satellite, for each epoch
    -a number, for a given satellite, frequency, and field, per epoch
It also holds header information such as satellite system, observer name,
marker position, times of first and last observations, no. of leap seconds,
and so forth.

'''
# TODO: 
# Hold auxiliary satellite information such as ephemerides (either almanac,
# broadcast, or precise) to allow satellite position calculation for each
# epoch.
# Do something with event flags (power failure, antenna moves, cycle slips)
# Create a less RINEX-specific format

from gpstime import datetime, leapseconds, gpsdatetime, gpstz, utctz, taitz, timedelta
from textwrap import wrap
import sys, warnings
from warnings import warn

def showwarn(message, category, filename, lineno, file=sys.stderr): 
    file.write('\n  * '.join(wrap('  * ' + str(message))) + '\n')
warnings.showwarning = showwarn

class value(float):
    '''
    A single value, as included in RINEX observation files.
    
    Acts as a float, but can have fields for extra information encoded in RINEX
    such as signal strength, loss of lock, wave factor, antispoofing.
    '''
    pass

class listvalue(dict):
    '''
    Store values as specified in a RINEX header which have validity
    for a range of records, but may be replaced.
    Allows accessing by record number, eg marker[456] returns
    the marker information which was valid for record 456.
    For convenience, listvalue[0] always returns the first definition
    and listvalue[-1] always returns the last.
    '''
    def add(self, value, recnum):
        self[recnum] = value
    
    def __getitem__(self, index):
        if index == 0:
            index = min(self)
        elif index == -1:
            index = max(self)
        else:
            index = max([k for k in self if k <= index])
        return dict.__getitem__(self, index)
    
    def __contains__(self, index):
        if index in (0, -1):
            return True
        return isinstance(index, (int, float)) and index > 0
    
class record(dict):
    '''
    A record of observations (many satellites, many channels) at a given epoch.

    Has fields epoch, powerfail (indicating whether a power failure preceded
    this record) in addition to a dictionary (by PRN code)
    of dictionaries (by RINEX observation code, e.g. C1, L2) of values.
    Can access as record.epoch, record[13], record['G17'], or iteration.
    '''
    def __init__(self, epoch=gpsdatetime(), powerfail=False, clockoffset=0.):
        self.epoch = epoch
        self.powerfail = powerfail
        self.clockoffset = clockoffset

    def __getitem__(self, index):
        '''
        Allows you to access GPS satellites, eg record['G13'], as
        simply record[13].  For GLONASS or Galileo, you must use the full code.
        '''
        if isinstance(index, (int, long, float)):
            return dict.__getitem__(self, 'G%02d' % index)
        return dict.__getitem__(self, index)

    def __contains__(self, index):
        '''
        Allows containment tests (eg if 13 in record:) for abbreviated GPS PRNs.
        '''
        if isinstance(index, (int, long, float)):
            return dict.__contains__(self, 'G%02d' % index)
        return dict.__contains__(self, index)


class GPSData(list):
    '''
    A GPSData object is primarily a list of records, one for each epoch.

    In chronological order; each record is a dictionary by satellite id
    of dictionaries by observation code of values.
    GPSData.meta['name'] also gives access to RINEX header values.
    '''
    def __init__(self, tzinfo=None, satsystem=None):
        list.__init__(self)
        self.meta = {}
        # Metadata about the observations, e.g. header information
        self.tzinfo = tzinfo
        self.satsystem = satsystem
        self.sats = None

    def append(self, epoch=None, *args):
        '''
        Appends a new record with given args to the GPSData list,
        using correct time system.
        '''
        if isinstance(epoch, gpsdatetime):
            epoch = epoch.replace(tzinfo = self.tzinfo)
        elif isinstance(epoch, datetime):
            epoch = gpsdatetime.copydt(epoch, self.tzinfo)
        elif isinstance(epoch, (tuple, list)):
            epoch = gpsdatetime(*epoch).replace(tzinfo=self.tzinfo)
        elif epoch is None:
            epoch = gpsdatetime(tzinfo = self.tzinfo)
        else:
            raise ValueError('First argument must be gpsdatetime epoch of record')
        list.append(self, record(epoch, *args))

    def iter(self, sat=None, obscode=None):
        '''
        Returns an iterator over the list of records.

        If a PRN is specified for `sat', iterates over dictionaries of 
        obscode : value for the given satellite.
        If an observation code is specified for `obscode', iterates over
        dictionaries of prn : value for the given observation type.
        If both are specified, iterates over values.
        '''
        for record in self:
            if sat is None and obscode is None:
               yield record 
            elif obscode is None and sat in record:
                yield record[sat]
            elif sat is None:
                d = dict([(prn, val[obscode]) for prn, val in 
                    record.iteritems() if obscode in val])
                if len(d):
                    yield d
            elif sat in record and obscode in record[sat]:
                yield record[sat][obscode]
            
    def iterepochs(self):
        '''
        Returns an iterator over the epochs (time values) of each record.
        '''
        for record in self:
            yield record.epoch

    def sats(self):
        '''
        Returns a set of all satellite PRNs which have observations
        in this GPSData object.
        '''
        if self.sats is None:
            self.sats = set()
            for rec in self:
                self.sats.update(rec)
        return self.sats

    def obscodes(self, which=-1):
        '''
        Return (current) list of observation codes stored in this GPSData.
        '''
        if 'obscodes' not in self.meta:
            raise RuntimeError('RINEX file did not define data records')
        return self.meta['obscodes'][which]
 
    def timesetup(self):
        '''
        Prepares time systems after headers are parsed.

        After parsing the initial header of a RINEX file,
        timesetup figures out the time system to use (GPS, UTC, or TAI)
        based on satellite system, TIME OF FIRST OBS, or TIME OF LAST OBS.
        It also sets this time system in the datetime objects
        recorded in meta['firsttime'] and meta['lasttime'], if any,
        and returns a `base year' for the purpose of disambiguating
        the observation records (which have 2-digit year.)
        '''
        if self.satsystem is None and 'satsystem' in self.meta:
            self.satsystem = self.meta['satsystem']
        if self.satsystem == 'R': # GLONASS uses UTC
            self.tzinfo = utctz
        elif self.satsystem == 'E': # Galileo uses TAI
            self.tzinfo = taitz
        else:  # RINEX says default for blank, GPS, GEO files is GPS time
            self.tzinfo = gpstz
        ts = None
        # Time system specified in TIME OF FIRST OBS overrides satsystem
        if 'firsttimesys' in self.meta and self.meta['firsttimesys'].strip():
            ts = self.meta['firsttimesys'].strip().upper()
        if 'endtimesys' in self.meta and self.meta['endtimesys'].strip():
            if ts is not None and ts != self.meta['endtimesys'].strip().upper():
                raise ValueError('Time systems in FIRST OBS and LAST OBS' +
                    'headers do not match.')
            ts = self.meta['endtimesys'].strip().upper()
        if ts == 'GPS':
            self.tzinfo = gpstz
        elif ts == 'GLO':
            self.tzinfo = utctz
        elif ts == 'GAL':
            self.tzinfo = taitz
        baseyear = None
        if 'firsttime' in self.meta:
            self.meta['firsttime'] = self.meta['firsttime'].replace(tzinfo=self.tzinfo)
            baseyear = self.meta['firsttime'].year
        if 'endtime' in self.meta:
            self.meta['endtime'] = self.meta['endtime'].replace(tzinfo=self.tzinfo)
            if baseyear is None:
                baseyear = self.meta['endtime'].year
        return baseyear

    def check(self, obspersat, intervals):
        '''
        Validates or supplies RINEX headers which the reader can determine

        Checks RINEX header information, if supplied, against information
        obtained from reading the file.  Fills in the header information
        if it wasn't supplied.
        '''
# TODO: can check markerpos (APPROX POSITION XYZ) against position solution
        if not len(self):
            warn('Empty GPSData generated')
            return
        if 'firsttime' in self.meta:
            if self.meta['firsttime'] != self[0].epoch:
                warn('TIME OF FIRST OBS ' + str(self.meta['firsttime']) +
                     ' does not match first record epoch ' + str(self[0].epoch))
        else:
            self.meta['firsttime'] = self[0].epoch
        if 'endtime' in self.meta:
            if self.meta['endtime'] != self[-1].epoch:
                warn('TIME OF LAST OBS ' + str(self.meta['endtime']) +
                     ' does not match last record epoch ' + str(self[-1].epoch))
        else:
            self.meta['endtime'] = self[-1].epoch
        if 'leapseconds' in self.meta:
            for recnum, ls in self.meta['leapseconds'].iteritems():
                if ls != gpstz.utcoffset(self[recnum].epoch):
                    wstr = 'Leap seconds in header (' + str(ls)
                    wstr += ') do not match system leap seconds ('
                    wstr += str(gpstz.utcoffset(self[recnum].epoch)) + ').'
                    if leapseconds.timetoupdate():
                        wstr += '  Try gpstime.LeapSeconds.update().'
                    else:
                        wstr += '  Header appears incorrect!'
                    warn(wstr)
        else:
            self.meta['leapseconds'] = listvalue()
            self.meta['leapseconds'].add(gpstz.utcoffset(self[0].epoch), 0)
            if self.tzinfo is not None:
                t0 = self[0].epoch.astimezone(utctz).replace(tzinfo=None)
                t1 = self[-1].epoch.astimezone(utctz).replace(tzinfo=None)
            else:
                t0 = self[0].epoch
                t1 = self[-1].epoch
            for leap in leapseconds:
                if t0 < leap < t1:
                    ind = max([k for k in xrange(len(self)) if self[k].epoch <= leap])
                    self.meta['leapseconds'].add(gpstz.utcoffset(leap), ind)
        if 'interval' in self.meta:
            if self.meta['interval'] != min(intervals):
                warn('INTERVAL ' + str(self.meta['interval']) +
                        ' does not match minimum observation interval ' +
                        str(min(intervals)))
        else:
            self.meta['interval'] = min(intervals)
        if 'numsatellites' in self.meta:
            if self.meta['numsatellites'] != len(obspersat):
                warn('# OF SATELLITES header ' + str(self.meta['numsatellites']) +
                     ' does not matched observed number of satellites' +
                     str(len(obspersat)) + '.')
        else:
            self.meta['numsatellites'] = len(obspersat)
        if 'obsnumpersatellite' in self.meta:
            rnxprns = set(self.meta['obsnumpersatellite'].keys())
            obsprns = set(obspersat.keys())
            if rnxprns.difference(obsprns):
                warn('Satellites ' + ', '.join(rnxprns.difference(obsprns)) +
                     ' listed in header but not seen in file.')
            if obsprns.difference(rnxprns):
                warn('Satellites ' + ', '.join(obsprns.difference(rnxprns)) +
                     ' seen in file but not listed in header.')
            for prn in rnxprns.intersection(obsprns):
                ops = obspersat[prn]
                rns = self.meta['obsnumpersatellite'][prn]
                for (c, obs) in enumerate(self.obscodes(0)):
                    if ops[obs] != rns[c]:
                        warn(' '.join(('Header claimed', str(rns[c]), obs,
                             'observations for prn', prn, 'but only', 
                             str(ops[obs]), 'observed.')))
        else:
            self.meta['obsnumpersatellite'] = {}
            for prn in obspersat:
                self.meta['obsnumpersatellite'][prn] = []
                for obs in self.obscodes(0):
                    self.meta['obsnumpersatellite'][prn] += [obspersat[prn][obs]]
        if self.sats is None:
            self.sats = set(obspersat)

    def header_info(self):
        '''
        Returns a string with some summarizing information from the
        observation data file headers.
        '''
        hstr = 'Satellite system:\t'
        if self.satsystem == 'G':
            hstr += 'GPS'
        elif self.satsystem == 'E':
            hstr += 'Galileo'
        elif self.satsystem == 'R':
            hstr += 'GLONASS'
        elif self.satsystem == 'S':
            hstr += 'Geostationary'
        elif self.satsystem == 'M':
            hstr += 'Mixed'
        hstr += '\nTime system used:\t' + self.tzinfo.name
        hstr += '\nFirst record time:\t'
        hstr += self.meta['firsttime'].strftime('%B %d, %Y %H:%M:%S')
        hstr += '\nLast record time:\t'
        hstr += self.meta['endtime'].strftime('%B %d, %Y %H:%M:%S')
        if 'comment' in self.meta:
            hstr += '\nComments (' + str(len(self.meta['comment'].split('\n'))) + '):\n'
            hstr += '-'*60 + '\n' + self.meta['comment'] + '\n' + '-'*60
        hstr += '\n' + str(self.meta['numsatellites']) + ' satellites observed. '
        hstr += 'Number of observations:\n'
        hstr += 'PRN\t' + '\t'.join(['%5s' % s for s in self.obscodes(0)])
        for (prn, counts) in self.meta['obsnumpersatellite'].items():
            hstr += '\n' + prn + '\t'
            hstr += '\t'.join(['%5d' % num for num in counts])
        return hstr
