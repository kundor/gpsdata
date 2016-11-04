# Created by Nick Matteo <kundor@kundor.org> June 9, 2009
"""Store observation data from a GPS Receiver

Stores data as provided in RINEX files or other data logs.
Specifically, store GPS Time, Pseudorange, Phase, Doppler Frequency, and SNR
for each satellite, and each frequency, observed.
.iterdict() allows iteration over these values as:
    -a dictionary of dictionaries of all satellites and fields, per epoch
    -a dictionary, for a given satellite, for each epoch
    -a number, for a given satellite, frequency, and field, per epoch
The GPSData object also holds header information such as satellite system, observer name,
marker position, times of first and last observations, no. of leap seconds,
and so forth.
"""
# TODO:
# Hold auxiliary satellite information such as ephemerides (either almanac,
# broadcast, or precise) to allow satellite position calculation for each
# epoch.
# Create a less RINEX-specific format

import sys
import warnings
from warnings import warn
from textwrap import wrap

from utility import listvalue, metadict
from gpstime import leapseconds, gpstz, utctz, taitz, getgpstime
from gpsazel import gpsazel2, satcoeffs_between


TECUns = 2.854  # TECU/ns according to GPS-Scinda, Charles Carrano, 4-7-08
# TECUns = 2.852  # TECU/ns according to TECalc_rinex, Pat Doherty, 2-21-94
F1 = 1.57542  # L1 Frequency (GHz)
F2 = 1.22760  # L2 Frequency (GHz)
C = 0.299792458  # speed of light in meters/nanosecond
MINGOOD = 16  # Minimum number of usable records we need to use an arc

GNSSYS = {'G' : 'GPS',
          'R' : 'GLONASS',
          'E' : 'Galileo',
          'C' : 'BeiDou',
          'S' : 'Geostationary',
          'M' : 'Mixed'}

def showwarn(message, category, filename, lineno, file=sys.stderr, line=None):
    """Output pretty warnings."""
    file.write('\n  * '.join(wrap('*** ' + str(message))) + '\n')

warnings.showwarning = showwarn

class Record(dict):
    """A record of observations (many satellites, many channels) at a given epoch.

    Has fields epoch, powerfail (indicating whether a power failure preceded
    this record) in addition to a dictionary (by PRN code)
    of dictionaries (by RINEX observation code, e.g. C1, L2) of values.
    Can access as record.epoch, record[13], record['G17'], or iteration.
    """ 
    def __init__(self, epoch, **kwargs):
        """Set arbitrary fields by keyword arguments, e.g. motion, powerfail, clockoffset."""
        dict.__init__(self)
        self.epoch = epoch
        self.__dict__.update(kwargs)

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

    def ptec(self, prn):
        """Phase (carrier) TEC, if observations are available.

        Convert cycles of L1, L2 to ns (divide by frequency)
        Then TEC_P (TECU) = (L1(ns) - L2(ns)) * TECU/ns
        1 TECU = 10*16 el / m**2
        Suffers from integer ambiguity (`constant' offset which changes after
        each cycle slip.)  Should be dealt with in `arcs' between cycle slips.
        """
        l1ns = self[prn]['L1']/F1
        l2ns = self[prn]['L2']/F2
        return (l1ns - l2ns) * TECUns

    def ctec(self, prn):
        """Code (pseudorange) TEC, if observations are available.

        p(ns) = p(m) / .3; TEC_C (TECU) = (p2(ns) - p1(ns) - HWCAL) * TECU/ns
        HWCAL is the hardware calibration in ns
        Suffers from satellite bias, receiver bias, multipath and noise.
        """
        if 'P1' in self[prn] and 'P2' in self[prn]:
            return (self[prn]['P2'] - self[prn]['P1']) * TECUns/C
        if 'C1' in self[prn] and 'C2' in self[prn]:
            return (self[prn]['C2'] - self[prn]['C1']) * TECUns/C
        if 'C1' in self[prn] and 'P2' in self[prn]:
            return (self[prn]['P2'] - self[prn]['C1']) * TECUns/C

    def badness(self, prn):
        """Compute a number indicating how `bad' this record is for TEC

        Larger numbers indicate that these measurements are less trustworthy
        and shouldn't be used for the phase vs. carrier averaging computation.
        """
        bad = 0
        if prn not in self:
            return 1000  # Very bad!
        elif 'L1' not in self[prn] or 'L2' not in self[prn]:
            return 1000
        elif 'C1' not in self[prn] and 'P1' not in self[prn]:
            return 1000
        elif 'C2' not in self[prn] and 'P2' not in self[prn]:
            return 1000
        if self.motion:
            bad += 4
        if 'P2' not in self[prn]:
            bad += 1
        for val in self[prn].values():
            if val.antispoofing:
                bad += 1
            if val.wavefactor == 2:
                bad += 1
            if val.strength and val.strength < 4:
                bad += 4 - val.strength
        return bad
        # TODO: Check for 'S1', 'S2' in obs and compare to averages thereof
        # TODO: Get satellite position and increase bad for lower elevations


def ordercheck(maxlen):
    """Return a function to check if a list of (start, stop) pairs is in strict order.

    Check that no index exceeds maxlen."""
    cur = [0]
    def ochk(arc):
        """Check arc[0] is at or past last seen point, and arc[1] is between arc[0] and maxlen."""
        if not isinstance(arc[0], int) or not isinstance(arc[1], int):
            return False
        if not cur[0] <= arc[0] < arc[1] <= maxlen:
            return False
        cur[0] = arc[1]
        return True
    return ochk


class SatData(list):
    """A SatData object is primarily a list of records, one for each epoch.

    The list is in chronological order; each record is a dictionary by satellite id
    of dictionaries by observation code of values.
    SatData.meta['name'] also gives access to some meta information.
    """
    def __init__(self, tzinfo=None, satsystem=None):
        list.__init__(self)
        self.meta = metadict()
        """Metadata about the observations, e.g. header information"""
        self.tzinfo = tzinfo
        """Time system used (GPS, GLONASS/UTC, Galileo/TAI)"""
        self.satsystem = satsystem
        self.prns = set()
        """All satellites included in this GPSData object."""
        self.allobs = set()
        """All observation types seen in this GPSData object."""

    def __str__(self):
        out = self.__class__.__name__ + ' object'
        if 'filename' in self.meta:
            out += ' read from file ' + self.meta.filename
        out += ' with observations ' + ', '.join(self.allobs)
        out += ' from satellites ' + ', '.join(self.prns) + '.'
        out += '{} records, from {} to {}.'.format(len(self),
                                                   self.meta.firsttime,
                                                   self.meta.endtime)
        return out

    __repr__ = object.__repr__ # don't accidentally print out reams of stuff

    def newrecord(self, epoch, **kwargs):
        """Append a new record with given args to the SatData list.

        Use correct time system.
        """
        epoch = getgpstime(epoch, self.tzinfo)
        self.append(Record(epoch, **kwargs))

    def add(self, which, prn, obs, val):
        """Add an observation value to the given record (which)."""
        self.prns.add(prn)
        self.allobs.add(obs)
        self[which].setdefault(prn, {})[obs] = val

    def iterlist(self, sat=None, obscode=None):
        """Return an iterator over the list of records.

        If a PRN is specified for `sat', iterates over lists of values for
        the given satellite, corresponding to the observation codes in "allobs".
        If an observation code is specified for `obscode', iterates over
        lists of values for the given observation type, corresponding to the
        satellites in "prns" (in sorted order).
        If both are specified, iterates over values.
        If an set is provided for either argument, the returned values
        correspond to the sorted order; if a list or tuple is provided, the returned
        values correspond to the given order.
        """
        if isinstance(sat, (list, tuple, set, dict)):
            if not sat:
                sat = None
            elif len(sat) == 1:
                sat = next(iter(sat))
            elif isinstance(sat, (set, dict)):
                sat = sorted(sat)
        if sat is None:
            sat = sorted(self.prns)
        if isinstance(obscode, (list, tuple, set, dict)):
            if not obscode:
                obscode = None
            elif len(obscode) == 1:
                obscode = next(iter(obscode))
            elif isinstance(obscode, (set, dict)):
                obscode = sorted(obscode)
        if obscode is None:
            obscode = sorted(self.allobs)

        def chooser(obs, rec, sat, spec=None):
            """Choose rec[sat][obs], or if it doesn't exist, rec[obs]."""
            if sat in rec and obs in rec[sat]:
                return rec[sat][obs]
            if spec and obs == spec:
                return rec[obs]
            return None

        def hichoose(sat, rec, obscode):
            """A list of values for each entry in "obscode" for the single satellite "sat"."""
            if sat in rec:
                return [chooser(obs, rec, sat) for obs in obscode]
            return None

        for record in self:
            if isinstance(obscode, (list, tuple)) and isinstance(sat, (list, tuple)):
                yield [hichoose(s, record, obscode) for s in sat]
            elif isinstance(obscode, (list, tuple)) and sat in record:
                yield [chooser(obs, record, sat, 'epoch') for obs in obscode]
            elif obscode == 'epoch':
                yield record['epoch']
            elif isinstance(sat, (list, tuple)):
                yield [chooser(obscode, record, s) for s in sat]
            elif sat in record and obscode in record[sat]:
                yield record[sat][obscode]

    def iterdict(self, sat=None, obscode=None):
        """Return an iterator over the list of records.

        If a PRN is specified for `sat', iterates over dictionaries of
        obscode : value for the given satellite.
        If an observation code is specified for `obscode', iterates over
        dictionaries of prn : value for the given observation type.
        If both are specified, iterates over values.
        """
        if isinstance(sat, (list, tuple, set, dict)):
            if not sat:
                sat = None
            elif len(sat) == 1:
                sat = next(iter(sat))
            elif isinstance(sat, (list, tuple, dict)):
                sat = set(sat)
        if isinstance(obscode, (list, tuple, set, dict)):
            if not obscode:
                obscode = None
            elif len(obscode) == 1:
                obscode = next(iter(obscode))
            elif isinstance(obscode, (list, tuple, dict)):
                obscode = set(obscode)

        def epochchoose(rec, sat, obs, spec='epoch'):
            """Choose rec[sat][obs], unless obs matches spec, which must be a field of rec."""
            if obs != spec:
                return rec[sat][obs]
            return rec[obs]

        for record in self:
            if obscode is None and sat is None:
                yield record
            elif obscode is None and isinstance(sat, set):
                yield {s : record[s] for s in sat if s in record}
            elif obscode is None and sat in record:
                yield record[sat]
            elif isinstance(obscode, set) and sat is None:
                yield {s : {obs : epochchoose(record, s, obs)
                            for obs in obscode if obs == 'epoch' or obs in record[s]}
                       for s in record if obscode.intersection(record[s])}
            elif isinstance(obscode, set) and isinstance(sat, set):
                yield {s : {obs : epochchoose(record, s, obs)
                            for obs in obscode if obs == 'epoch' or obs in record[s]}
                       for s in sat if s in record}
            elif isinstance(obscode, set) and sat in record:
                yield {obs : epochchoose(record, sat, obs) for obs in obscode
                       if obs == 'epoch' or obs in record[sat]}
            elif obscode == 'epoch':
                yield record.epoch
            elif sat is None:
                d = {prn : val[obscode] for prn, val in record.items() if obscode in val}
                if d:
                    yield d
            elif isinstance(sat, set):
                d = {s : record[s][obscode] for s in sat
                     if s in record and obscode in record[s]}
                if d:
                    yield d
            elif sat in record and obscode in record[sat]:
                yield record[sat][obscode]

    def obscodes(self, which=-1):
        """Return (current) list of observation codes stored in this SatData."""
        if 'obscodes' not in self.meta:
            raise RuntimeError('File did not define data records')
        return self.meta.obscodes[which]

    def timesetup(self):
        """Prepare time system after headers are parsed.

        After parsing the initial header of a RINEX file,
        timesetup figures out the time system to use (GPS, UTC, or TAI)
        based on satellite system, TIME OF FIRST OBS, or TIME OF LAST OBS.
        It also sets this time system in the datetime objects
        recorded in meta.firsttime and meta.lasttime, if any,
        and returns a `base year' for the purpose of disambiguating
        the observation records (which have 2-digit year.)
        """
        if self.satsystem is None and 'satsystem' in self.meta:
            self.satsystem = self.meta.satsystem
        if self.satsystem == 'R':  # GLONASS uses UTC
            self.tzinfo = utctz
        elif self.satsystem == 'E':  # Galileo uses TAI
            self.tzinfo = taitz
        else:  # RINEX says default for blank, GPS, or GEO files is GPS time
            self.tzinfo = gpstz
        ts = None
        # The time system specified in TIME OF FIRST OBS overrides satsystem
        if 'firsttimesys' in self.meta and self.meta.firsttimesys.strip():
            ts = self.meta.firsttimesys.strip().upper()
        if 'endtimesys' in self.meta and self.meta.endtimesys.strip():
            if ts is not None and ts != self.meta.endtimesys.strip().upper():
                raise ValueError('Time systems in FIRST OBS and LAST OBS '
                                 'headers do not match.')
            ts = self.meta.endtimesys.strip().upper()
        if ts == 'GPS':
            self.tzinfo = gpstz
        elif ts == 'GLO':
            self.tzinfo = utctz
        elif ts == 'GAL':
            self.tzinfo = taitz
        baseyear = None
        if 'firsttime' in self.meta:
            self.meta.firsttime = self.meta.firsttime.replace(tzinfo=self.tzinfo)
            baseyear = self.meta.firsttime.year
        if 'endtime' in self.meta:
            self.meta.endtime = self.meta.endtime.replace(tzinfo=self.tzinfo)
            if baseyear is None:
                baseyear = self.meta.endtime.year
        return baseyear

    def check(self, obspersat, intervals):
        """Validate or supply RINEX headers which the reader can determine.

        Check RINEX header information, if supplied, against information
        obtained from reading the file.  Fill in the header information
        if it wasn't supplied.
        """
        # TODO: check markerpos (APPROX POSITION XYZ) against position solution
        if not len(self):
            warn('Empty GPSData generated')
            return
        if 'firsttime' in self.meta:
            if self.meta.firsttime != self[0].epoch:
                warn('TIME OF FIRST OBS ' + str(self.meta.firsttime) +
                     ' does not match first record epoch ' + str(self[0].epoch))
        else:
            self.meta['firsttime'] = self[0].epoch
        if 'endtime' in self.meta:
            if self.meta.endtime != self[-1].epoch:
                warn('TIME OF LAST OBS ' + str(self.meta.endtime) +
                     ' does not match last record epoch ' + str(self[-1].epoch))
        else:
            self.meta['endtime'] = self[-1].epoch
        if 'leapseconds' in self.meta:
            for recnum, ls in self.meta.leapseconds.items():
                if ls != gpstz.utcoffset(self[recnum].epoch).seconds:
                    wstr = 'Leap seconds in header (' + str(ls) + ') '
                    wstr += 'do not match system leap seconds ('
                    wstr += str(gpstz.utcoffset(self[recnum].epoch)) + ').'
                    if leapseconds.timetoupdate():
                        wstr += '  Try gpstime.LeapSeconds.update().'
                    else:
                        wstr += '  Header appears incorrect!'
                    warn(wstr)
        else:
            self.meta['leapseconds'] = listvalue()
            self.meta['leapseconds'][0] = gpstz.utcoffset(self[0].epoch).seconds
            if self.tzinfo is not None:
                t0 = self[0].epoch.astimezone(utctz).replace(tzinfo=None)
                t1 = self[-1].epoch.astimezone(utctz).replace(tzinfo=None)
            else:
                t0 = self[0].epoch
                t1 = self[-1].epoch
            for leap in leapseconds:
                if t0 < leap < t1:
                    ind = max([k for k in range(len(self))
                               if self[k].epoch <= leap])
                    self.meta['leapseconds'][ind] = gpstz.utcoffset(leap).seconds
        if 'interval' in self.meta:
            if min(self.meta.interval.values()) != min(intervals):
                warn('INTERVAL ' + str(self.meta.interval) + ' does not match '
                     'minimum observation interval ' + str(min(intervals)))
        else:
            self.meta['interval'] = min(intervals)
        if 'numsatellites' in self.meta:
            if self.meta.numsatellites != len(obspersat):
                warn('# OF SATELLITES header ' + str(self.meta.numsatellites) +
                     ' does not matched observed number of satellites ' +
                     str(len(obspersat)) + '.')
        else:
            self.meta['numsatellites'] = len(obspersat)
        if 'obsnumpersatellite' in self.meta:
            rnxprns = set(self.meta.obsnumpersatellite.keys())
            obsprns = set(obspersat.keys())
            if rnxprns.difference(obsprns):
                warn('Satellites ' + ', '.join(rnxprns.difference(obsprns)) +
                     ' listed in header but not seen in file.')
            if obsprns.difference(rnxprns):
                warn('Satellites ' + ', '.join(obsprns.difference(rnxprns)) +
                     ' seen in file but not listed in header.')
            for prn in rnxprns.intersection(obsprns):
                ops = obspersat[prn]
                rns = self.meta.obsnumpersatellite[prn]
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
                    self.meta.obsnumpersatellite[prn] += [obspersat[prn][obs]]
        if self.prns is None:
            self.prns = set(obspersat)

    def header_info(self):
        """Return a string summarizing information from the observation data file headers."""
        if 'filename' in self.meta:
            hstr = 'File:\t\t\t' + self.meta.filename + '\n'
        else:
            hstr = ''
        hstr += 'Satellite system:\t' + GNSSYS[self.satsystem]
        hstr += '\nTime system used:\t' + self.tzinfo.name
        hstr += '\nFirst record time:\t'
        hstr += self.meta.firsttime.strftime('%B %d, %Y %H:%M:%S')
        hstr += '\nLast record time:\t'
        hstr += self.meta.endtime.strftime('%B %d, %Y %H:%M:%S')
        if len(self.meta.leapseconds) > 1:
            hstr += '\nLeap seconds:'
            for recnum, ls in self.meta.leapseconds.items():
                if recnum:
                    hstr += str(recnum) + ')'
                hstr += '\n\t' + str(ls) + '\t(records ' + str(recnum) + ' -- '
            hstr += str(len(self)) + ')'
        else:
            hstr += '\nLeap seconds:\t' + str(self.meta.leapseconds[0])
        hstr += '\nInterval:\t' + str(self.meta.interval) + '\n'
        if 'comment' in self.meta:
            hstr += 'Comments (' + str(len(self.meta.comment)) + '):\n'
            hstr += '-' * 60 + '\n' + '\n'.join(self.meta.comment) + '\n' + \
                    '-' * 60 + '\n'
        hstr += str(self.meta.numsatellites) + ' satellites observed. '
        hstr += 'Number of observations:\n'
        hstr += 'PRN\t' + '\t'.join(['%5s' % s for s in self.obscodes(0)])
        for (prn, counts) in self.meta.obsnumpersatellite.items():
            hstr += '\n' + prn + '\t'
            hstr += '\t'.join(['%5d' % num for num in counts])
        return hstr


class GPSData(SatData):
    def __init__(self, tzinfo=None, satsystem=None):
        SatData.__init__(self, tzinfo, satsystem)
        self.inmotion = False
        self.phasearcs = {}
        # a dictionary by PRN of (start, stop) indices delimiting
        # phase-connected arcs

    def newrecord(self, epoch, **kwargs):
        """Append new record with given args to the GPSData list, using correct time system."""
        epoch = getgpstime(epoch, self.tzinfo)
        self.append(Record(epoch, motion=self.inmotion, **kwargs))

    def add(self, which, prn, obs, val):
        """Add observation value to the given record, while helping track phase-connected arcs."""
        super().add(which, prn, obs, val)
        if val.lostlock:
            self.breakphase(prn)

    def endphase(self, prn):
        """End current phase-connected-arc, if any, for satellite prn.

        Ends arc just before the current record.
        """
        if prn in self.phasearcs and self.phasearcs[prn][-1][1] is None:
            self.phasearcs[prn][-1][1] = len(self) - 1

    def breakphase(self, prn):
        """Begin new phase-connected-arc for satellite prn."""
        if isinstance(prn, (list, tuple, set, dict)):
            for p in prn:
                self.breakphase(p)
        elif prn not in self.phasearcs:
            self.phasearcs[prn] = [[len(self) - 1, None]]
        else:
            self.endphase(prn)
            self.phasearcs[prn] += [[len(self) - 1, None]]

    def checkbreak(self):
        """Check whether a cycle slip may have occurred for any satellites.

        Checks at last record added.  This should be called for each record
        inserted, after all its values have been added.
        """
        # TODO: Auto-detect when records have filled all observations for all
        # prns
        if not self:
            return
        if len(self) == 1:
            for prn in self[0]:
                if self[0].badness(prn) < 100 and prn not in self.phasearcs:
                    self.phasearcs[prn] = [[0, None]]
            return
        if self[-1].powerfail:
            self.breakphase(self.prns)
            return
        for prn in set(self[-1]).union(self.phasearcs):
            bad = self[-1].badness(prn)
            if bad < 100 and prn not in self.phasearcs:
                self.phasearcs[prn] = [[len(self) - 1, None]]
                continue
            if bad < 100 and self.phasearcs[prn][-1][1] is not None:
                self.phasearcs[prn] += [[len(self) - 1, None]]
                continue
            if prn not in self.phasearcs or self.phasearcs[prn][-1][1] is not None:
                continue  # It's bad, but nothing to break
            if bad > 100:
                # This satellite missed an observation! Must be slip!
                # print 'whoa imposs', prn, which
                self.phasearcs[prn][-1][1] = len(self) - 1
                continue
            # if `differential carrier phase' ptec changes by more than 8
            # L2 cycles in 30 seconds (our standard interval), there is almost
            # certainly a cycle slip.  (L2 per TECU is 2.3254, Carrano 08)
            # TODO: scale the boundary for different intervals
            if prn in self[len(self) - 2]:
                slip = abs(self[-1].ptec(prn) - self[len(self) - 2].ptec(prn))
                if slip > 8 / 2.3254:
                    # print 'whoa cycle slippage', prn, which, slip
                    self.breakphase(prn)
            elif (prn in self.phasearcs and
                  self.phasearcs[prn][-1][0] < len(self) - 1 and
                  self.phasearcs[prn][-1][1] is None):
                self.phasearcs[prn][-1][1] = len(self) - 2
            # try:
            #     idx = max([k for k in range(len(self.phasearcs[prn])) if
            #               self.phasearcs[prn][k][0] <= which])
            # except ValueError:
            #     continue
            # oldend = self.phasearcs[prn][idx][1]
            # if oldend is None or oldend > which:
            #     self.phasearcs[prn][idx][1] = which

    def sanearcs(self):
        """Ensure that the phase-connected arcs list is in strict order,
        without overlaps or missing measurements.
        """
        for prn, arclist in self.phasearcs.items():
            if not arclist:
                self.phasearcs.pop(prn)
                continue
            if arclist[-1][1] is None:
                arclist[-1][1] = len(self)
            ocheck = ordercheck(len(self))
            self.phasearcs[prn] = arclist = [a for a in arclist if ocheck(a)]
            poplist = []  # indices to remove
            for k, arc in enumerate(arclist):
                good = True
                numgood = [0, 0, 0, 0, 0]
                for rec in range(arc[0], arc[1]):
                    bad = self[rec].badness(prn)
                    if bad > 100 and good:
                        good = False
                        oldend = arc[1]
                        arc[1] = rec
                    elif bad < 100 and not good:
                        arclist.insert(k + 1, [rec, oldend])
                        break  # process this arc in the next step
                    if good and bad < 5:
                        numgood[bad] += 1
                if numgood[0] + numgood[1] < MINGOOD:
                    poplist += [k]
                elif len(arc) > 2:
                    arc[2] = numgood
                else:
                    arc.append(numgood)
            for k in poplist[::-1]:
                arclist.pop(k)

    def calctec(self):
        """Calculate slant uncalibrated TEC and append as observation to records

        TEC from carrier phase (L1, L2) is smooth but ambiguous.
        TEC from code (pseudorange) (C1, C2) or encrypted code (P1, P2) is
        absolute but noisy.  Phase data needs to be fitted to pseudorange data.
        This function calculates the TEC for each PRN in each record, where
        possible.
        """
        self.sanearcs()
        for prn, arclist in self.phasearcs.items():
            for arc in arclist:
                # We examine each value for `badness'.  We want at least 16
                # values with badness < 2 to compute our average.
                # The average does not include:
                #  - Any values with badness > 4
                #  - The worst 20% of the values, if their badness > 1
                targ = (arc[1] - arc[0]) / 5
                # we will omit at most `targ' bad measurements
                leftout = (arc[1] - arc[0]) - sum(arc[2])
                bound = 5
                # we can omit records worse than this without exceeding targ
                while leftout < targ and bound:
                    bound -= 1
                    leftout += arc[2][bound]
                arcavg = 0.  # sum CTEC - PTEC over good members
                arcnum = 0.
                for s in range(arc[0], arc[1]):
                    bad = self[s].badness(prn)
                    if bad <= bound:
                        arcavg += (self[s].ctec(prn) - self[s].ptec(prn))
                        arcnum += 1.
                arcavg = arcavg / arcnum
                for s in range(arc[0], arc[1]):
                    self[s][prn]['TEC'] = self[s].ptec(prn) + arcavg
        # TODO: download and apply satellite corrections from CODE
        #  (ftp://ftp.unibe.ch/aiub/CODE/)
        # Scale to VTEC

    def check(self, *args):
        SatData.check(self, *args)
        self.calctec()
