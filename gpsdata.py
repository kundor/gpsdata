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

class timestruct(object):
    timesys = 'GPS'
    def __init__(self, year=1980, month=1, day=6, hour=0, minute=0, second=0, timesys=None):
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        if timesys is not None:
            timestruct.timesys = timesys

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
    def __init__(self, epoch=None, powerfail=False, clockoffset=0.):
        if epoch is None:
            self.epoch = struct()
            self.epoch.year = 1980
            self.epoch.month = 1
            self.epoch.day = 6
            self.epoch.hour = self.epoch.minute = self.epoch.second = 0
        else:
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
    def __init__(self):
        self.rnx = {}
        list.__init__(self)
