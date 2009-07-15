'''
Store observation data from a GPS Receiver

Stores data as provided in RINEX files or other data logs.
Specifically, store GPS Time, Pseudorange, Phase, Doppler Frequency, and SNR
for each satellite, and each frequency, observed.
Allows iteration over these values as:
    -a dictionary of dictionaries of all satellites and fields, per epoch
It also holds header information such as satellite system, observer name,
marker position, times of first and last observations, no. of leap seconds,
and so forth.

'''
# TODO: Read Rinex versions 2-2.11; read RINEX 3/ CRINEX 2; read novatel logs;
# read NMEA.
# Allow iteration as
#    -a dictionary, for a given satellite, for each epoch
#    -a number, for a given satellite, frequency, and field, per epoch
# Hold auxiliary satellite information such as ephemerides (either almanac,
# broadcast, or precise) to allow satellite position calculation for each
# epoch.
# Do something with event flags (power failure, antenna moves, cycle slips)
# Support other RINEX file types (navigation message, meteorological data, 
# clock date file)
# Create a less RINEX-specific format
# Make timestruct less terrible

from gpstime import datetime, leapseconds, gpsdatetime, gpstz, utctz, taitz
from textwrap import wrap

def warn(msg):
    print '\n  * '.join(wrap('  * ' + msg))

class value(float):
    '''A single value, as included in RINEX observation files.
    Acts as a float, but can have fields for extra information encoded in RINEX
    such as signal strength, loss of lock, wave factor, antispoofing.'''
    pass

class record(dict):
    '''A record of data, from various satellites, on various channels,
    at a given epoch.
    Has epoch and powerfail fields (indicates whether a power failure
    preceded this record) in addition to a dictionary (by PRN code)
    of dictionaries (by RINEX observation code, e.g. C1, L2) of values.
    Can access as record.epoch, record[13], record['G17'], or iteration.
    '''
    def __init__(self, epoch=gpsdatetime(), powerfail=False, clockoffset=0.):
        self.epoch = epoch
        self.powerfail = powerfail
        self.clockoffset = clockoffset

    def __getitem__(self, index):
        if isinstance(index, (int, long, float)):
            return dict.__getitem__(self, 'G%02d' % index)
        else:
            return dict.__getitem__(self, index)


class GPSData(list):
    '''A GPSData object is primarily a list of records, one for each epoch,
    in chronological order; each record is a dictionary by satellite id
    of dictionaries by observation code of values.
    GPSData.rnx['name'] also gives access to RINEX header values.'''
    
    def __init__(self, tzinfo=None, satsystem=None):
        self.rnx = {}
        list.__init__(self)
        self.tzinfo = tzinfo
        self.satsystem = satsystem

    def timesetup(self):
        '''
        After parsing initial header of a RINEX file,
        timesetup figures out the time system to use (GPS, UTC, or TAI)
        based on satellite system, TIME OF FIRST OBS, or TIME OF LAST OBS.
        It also sets this time system in the datetime objects
        recorded in rnx['firsttime'] and rnx['lasttime'], if any,
        and returns a `base year' for the purpose of disambiguating
        the observation records (which have 2-digit year.)
        '''
        if self.satsystem is None and 'satsystem' in self.rnx:
            self.satsystem = self.rnx['satsystem']
        if self.satsystem == 'R': # GLONASS uses UTC
            self.tzinfo = utctz
        elif self.satsystem == 'E': # Galileo uses TAI
            self.tzinfo = taitz
        else:  # RINEX says default for blank, GPS, GEO files is GPS time
            self.tzinfo = gpstz
        ts = None
        # Time system specified in TIME OF FIRST OBS overrides satsystem
        if 'firsttimesys' in self.rnx and self.rnx['firsttimesys'].strip():
            ts = self.rnx['firsttimesys'].strip().upper()
        if 'endtimesys' in self.rnx and self.rnx['endtimesys'].strip():
            if ts is not None and ts != self.rnx['endtimesys'].strip().upper():
                raise ValueError('Time systems in FIRST OBS and LAST OBS' +
                    'headers do not match.')
            ts = self.rnx['endtimesys'].strip().upper()
        if ts == 'GPS':
            self.tzinfo = gpstz
        elif ts == 'GLO':
            self.tzinfo = utctz
        elif ts == 'GAL':
            self.tzinfo = taitz
        baseyear = None
        if 'firsttime' in self.rnx:
            self.rnx['firsttime'] = self.rnx['firsttime'].replace(tzinfo=self.tzinfo)
            baseyear = self.rnx['firsttime'].year
        if 'endtime' in self.rnx:
            self.rnx['endtime'] = self.rnx['endtime'].replace(tzinfo=self.tzinfo)
            if baseyear is None:
                baseyear = self.rnx['endtime'].year
        return 1900 if baseyear is None else baseyear

    def obscodes(self, which=-1):
        '''
        Return (current) list of observation codes stored in this GPSData
        object.
        '''
        if 'obscodes' not in self.rnx:
            raise RuntimeError('RINEX file did not define data records')
        elif type(self.rnx['obscodes'][0]) is tuple:
            return self.rnx['obscodes'][which][0]
        else:
            return self.rnx['obscodes']
 
    def append(self, epoch, *args):
        '''
        Appends a new record with given args to the GPSData list,
        using correct time system.
        '''
        if not isinstance(epoch, gpsdatetime):
            if isinstance(epoch, datetime):
                epoch = gpsdatetime.copydt(epoch, self.tzinfo)
            else:
                raise ValueError('First argument must be gpsdatetime epoch of record')
        else:
            epoch = epoch.replace(tzinfo = self.tzinfo)
        list.append(self, record(epoch, *args))

    def check(self, obspersat):
        '''
        Checks RINEX header information, if supplied, against information
        obtained from reading the file.  Fills in the header information
        if it wasn't supplied.
        '''
# TODO: can check receiverpos (APPROX POSITION XYZ) against position solution
# TODO: check interval, which seems to be wrong in every RINEX file
        if not len(self):
            warn('Empty GPSData generated')
            return
        if 'firsttime' in self.rnx:
            if self.rnx['firsttime'] != self[0].epoch:
                warn('TIME OF FIRST OBS ' + str(self.rnx['firsttime']) +
                     ' does not match first record epoch ' + str(self[0].epoch))
        else:
            self.rnx['firsttime'] = self[0].epoch
        if 'endtime' in self.rnx:
            if self.rnx['endtime'] != self[-1].epoch:
                warn('TIME OF LAST OBS ' + str(self.rnx['endtime']) +
                     ' does not match last record epoch ' + str(self[-1].epoch))
        else:
            self.rnx['endtime'] = self[-1].epoch
        if 'leapseconds' in self.rnx:
            if self.rnx['leapseconds'] != self.tzinfo.utcoffset(self[0].epoch):
                wstr = 'Leap seconds in header (' + str(self.rnx['leapseconds'])
                wstr += ') do not match system leap seconds ('
                wstr += str(self.tzinfo.utcoffset(self[0].epoch)) + ').'
                if leapseconds.timetoupdate():
                    wstr += '  Try gpstime.LeapSeconds.update().'
                else:
                    wstr += '  Header appears incorrect!'
                warn(wstr)
        else:
            self.rnx['leapseconds'] = self.tzinfo.utcoffset(self[0].epoch)
        if 'numsatellites' in self.rnx:
            if self.rnx['numsatellites'] != len(obspersat):
                warn('# OF SATELLITES header ' + str(self.rnx['numsatellites']) +
                     ' does not matched observed number of satellites' +
                     str(len(obspersat)) + '.')
        else:
            self.rnx['numsatellites'] = len(obspersat)
        if 'obsnumpersatellite' in self.rnx:
            rnxprns = set(self.rnx['obsnumpersatellite'].keys())
            obsprns = set(obspersat.keys())
            if rnxprns.difference(obsprns):
                warn('Satellites ' + ', '.join(rnxprns.difference(obsprns)) +
                     ' listed in header but not seen in file.')
            if obsprns.difference(rnxprns):
                warn('Satellites ' + ', '.join(obsprns.difference(rnxprns)) +
                     ' seen in file but not listed in header.')
            for prn in rnxprns.intersection(obsprns):
                ops = obspersat[prn]
                rns = self.rnx['obsnumpersatellite'][prn]
                for (obs, c) in zip(self.obscodes(0), xrange(100)):
                    if ops[obs] != rns[c]:
                        warn(' '.join(('Header claimed', str(rns[c]), obs,
                             'observations for prn', prn, 'but only', 
                             str(ops[obs]), 'observed.')))
        else:
            self.rnx['obsnumpersatellite'] = {}
            for prn in obspersat:
                self.rnx['obsnumpersatellite'][prn] = []
                for obs in self.obscodes(0):
                    self.rnx['obsnumpersatellite'][prn] += [obspersat[prn][obs]]

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
        hstr += self.rnx['firsttime'].strftime('%B %d, %Y %H:%M:%S')
        hstr += '\nLast record time:\t'
        hstr += self.rnx['endtime'].strftime('%B %d, %Y %H:%M:%S')
        hstr += '\n' + str(self.rnx['numsatellites']) + ' satellites observed. '
        hstr += 'Number of observations:\n'
        hstr += 'PRN\t' + '\t'.join(['%5s' % s for s in self.obscodes(0)])
        for (prn, counts) in self.rnx['obsnumpersatellite'].items():
            hstr += '\n' + prn + '\t'
            hstr += '\t'.join(['%5d' % num for num in counts])
        return hstr
