#!/usr/bin/python
# Created by Nick Matteo <kundor@kundor.org> June 9, 2009

'''
Utilities to read RINEX GPS file values.

Mostly you will use read_rinex(URL), where URL can be an http, ftp, or
local file path to a gzipped, compact, or standard RINEX observation file.
A GPSData object is returned.
crx2rnx(filename) will convert to standard RINEX if it is compact RINEX.
Finally, get_data(filename) turns a standard RINEX file into a GPSData object.

'''

import sys
import urllib
import gzip
import tarfile
import re
from cPickle import dump
from string import strip
from warnings import warn
from optparse import OptionParser
from crx2rnx import crx2rnx, CR_VER
from gpsdata import value, record, timestruct, GPSData

RNX_VER = '2.11'
__ver__ = '0.1'

btog = lambda c : 'G' if c in (None, '', ' ') else c.upper()
toint = lambda x : 0 if x is None or x.strip() == '' else int(x)
tofloat = lambda x : 0. if x is None or x.strip() == '' else float(x)
to3float = lambda s : tuple(tofloat(s[k*14:(k+1)*14]) for k in (0,1,2))

def satsystem(c):
    if c.upper() == 'R': # GLONASS
        timestruct.timesys = 'GLO'
    elif c.upper() == 'E': # Galileo
        timestruct.timesys = 'GAL'
    return btog(c)

def versioncheck(ver):
    nums = ver.split('.')
    if not 0 < len(nums) < 3:
        raise ValueError('RINEX Version not parsable')
    elif int(nums[0]) != 2:
        raise IOError('RINEX File not version 2; unsupported')
    elif len(nums) > 1 and int(nums[1]) > 11:
        warn('RINEX minor version more recent than program.')
    return ver.strip()

def iso(c):
    if c.upper() != 'O':
        raise IOError('RINEX File is not observation data')
    return c.upper()

def parsetime(s, tight=False):
    width = 3 if tight else 6
    secwidth = 11 if tight else 13
    year = toint(s[0 : width])
    month = toint(s[width : width * 2])
    day = toint(s[width * 2 : width * 3])
    hour = toint(s[width * 3 : width * 4])
    minute = toint(s[width * 4 : width * 5])
    second = tofloat(s[width * 5 : width * 5 + secwidth])
    if not tight:
        ts = s[48:51].strip()
        timesys = None if ts == '' else ts.upper()
    else:
        timesys = None
    return timestruct(year, month, day, hour, minute, second, timesys)

class wavelength(object):
# if prn list is empty (numsats = 0), L1/2 ambiguity applies to all satellites
# else applies to satellites given in prnlist; many lines allowed
# valid until next 'global' WAVELENGTH FACT, or that prn reset
    def __init__(self):
        self.waveinfo = dict([('G%02d' % prn, (1, 1)) for prn in range(1, 33)]) 
    def __call__(self, s):
        l1amb = toint(s[0:6])
        l2amb = toint(s[6:12])
        numsats = toint(s[12:18])
        if not numsats:
            self.waveinfo = dict([('G%02d' % prn, (l1amb, l2amb)) 
                for prn in range(1, 33)]) 
        else:
            for p in range(numsats):
                prn = btog(s[21 + 6 * p]) + '%02d' % toint(s[22 + 6 * p : 24 + 6 * p])
                self.waveinfo[prn] = (l1amb, l2amb)
        return self.waveinfo.copy()

class obscode(object):
# must be 'numtypes' many observation codes, possibly over two lines
# continuation lines have blank 'numtypes'
    def __init__(self):
        self.numtypes = None
    def __call__(self, s):
        nt = toint(s[0:6])
        if self.numtypes is not None and not nt: # continuing
            if len(self.obstypes) >= self.numtypes:
                raise RuntimeError('Observation code headers seem broken.')
            for ot in range(min(self.numtypes - len(self.obstypes), 9)):
                self.obstypes += [s[6 * ot + 10 : 6 * ot + 12]]
        elif nt:
            self.numtypes = nt
            self.obstypes = []
            for ot in range(min(nt, 9)):
                self.obstypes += [s[6 * ot + 10 : 6 * ot + 12]]
        else:
            raise RuntimeError('Observation type code header without beginning!')
        return self.obstypes[:]

class satnumobs(object):
    def __init__(self):
        self.sno = {}
        self.prn = None
    def __call__(self, s):
        prn = s[0:3]
        if prn.strip() == '' and self.prn is not None: # continuation
            pass
        elif prn.strip() != '':
            prn = btog(prn[0]) + '%02d'% toint(prn[1:])
            self.prn = prn
            if prn in self.sno:
                warn('Repeated # OF OBS for PRN ' + prn + ', why?')
            else:
                self.sno[prn] = []
        else:
            raise RuntimeError('PRN / # OF OBS continuation without beginning!')
        for no in range(9):
            obs = s[no * 6 + 3: no * 6 + 9]
            if obs.strip() == '':
                break
            else:
                self.sno[self.prn] += [toint(obs)]
        return self.sno
# for given sat, number of observations of each type in 'obstypes'
# continuation lines have blank 'prn'

class field(object):
    def __init__(self, name, start, stop, convert=strip):
        self.name = name
        self.start = start
        self.stop = stop
        self.convert = convert
    def read(self, line):
        return self.convert(line[self.start:self.stop])

class fields(object):
    def __init__(self, field_args, multi_act=0):
        self.mems = [field(*fargs) for fargs in field_args]
        self.multi_act = multi_act
        # What to do when encountering this value again
        # 0 : replace and warn
        # 1 : disallow
        # 2 : replace
        # 3 : append to list, with record number
        # 4 : ignore
        # 5 : replace if recordnum hasn't changed
    def __iter__(self):
        return iter(self.mems)
    def __getitem__(self, index):
        return self.mems[index]
    def __len__(self):
        return len(self.mems)

RINEX = {
    'RINEX VERSION / TYPE' : fields((('rnxver', 0, 9, versioncheck),
                              ('filetype', 20, 21, iso),
                              ('satsystem', 40, 41, satsystem))),
    'PGM / RUN BY/ DATE  ' : fields((('rnxprog', 0, 20), # gps-scinda
                              ('agency', 20, 40),
                              ('filedate', 40, 60))),
    'PGM / RUN BY / DATE ' : fields((('rnxprog', 0, 20), 
                              ('agency', 20, 40),
                              ('filedate', 40, 60))),
    'COMMENT             ' : fields((), 4),
    'MARKER NAME         ' : fields((('marker', 0, 60, strip),), 3),
    'MARKER NUMBER       ' : fields((('markernum', 0, 20, strip),), 3),
    'OBSERVER / AGENCY   ' : fields((('observer', 0, 20), 
                              ('obsagency', 20, 60))),
    'REC # / TYPE / VERS ' : fields((('receivernum', 0, 20),
                              ('receivertype', 20, 40),
                              ('receiverver', 40, 60))),
    'ANT # / TYPE        ' : fields((('antennanum', 0, 20),
                              ('antennatype', 20, 40))),
    'APPROX POSITION XYZ ' : fields((('receiverpos', 0, 42, to3float),), 3), # WGS84
    'ANTENNA: DELTA H/E/N' : fields((('antennashift', 0, 42, to3float),), 3), # UEN
    'WAVELENGTH FACT L1/2' : fields((('ambiguity', 0, 53, wavelength()),), 5),
    '# / TYPES OF OBSERV ' : fields((('obscodes', 0, 60, obscode()),), 5),
    'INTERVAL            ' : fields((('obsinterval', 0, 10, tofloat),), 3),
    'TIME OF FIRST OBS   ' : fields((('firsttime', 0, 51, parsetime),), 1),
    'TIME OF LAST OBS    ' : fields((('endtime', 0, 51, parsetime),)),
    # endtime.timesys must agree with firsttime.timesys
    'RCV CLOCK OFFS APPL ' : fields((('receiverclockcorrection', 0, 6, toint),), 3),
    'LEAP SECONDS        ' : fields((('leapseconds', 0, 6, toint),), 3),
    '# OF SATELLITES     ' : fields((('numsatellites', 0, 6, toint),)),
    'PRN / # OF OBS      ' : fields((('obsnumpersatellite', 3, 60, satnumobs()),), 2),
#    'END OF HEADER       ' : fields((), 1)
}

def get_data(fid):
    ''' Reads data out of a RINEX 2.11 Observation Data File'''
    fid.seek(0)
    obsdata = GPSData() 
    sawrec = {}
    recordnum = 0
    procheader(fid, obsdata.rnx, sawrec, recordnum)
    while True:
        try:
            line = fid.next().rstrip('\n')
        except StopIteration:
            break
        if line == '':
            break
        epoch = parsetime(line[0:26], True)
        flag = toint(line[28:29])
# 0: Observations.
#  1: Power failure occured since last record.
# Header information:
#  2: associated with start of antenna movement
#  3: associated with occupation of new site (stop moving)
#  4: nothing special
# 5: External event: special records follow, epoch is significant
# 6: Cycle slip records.  same format with slips instead of observations?
#  What does that mean?
        numrec = toint(line[29:32])
        if 5 <= flag <= 6:
            [fid.next() for ll in range(numrec)]
        elif 2 <= flag <= 4:
            procheader(fid, obsdata.rnx, sawrec, recordnum, numrec)
        elif 0 <= flag <= 1:
            obsdata += [record(epoch, not flag, tofloat(line[68:80]))]
            prnlist = []
            while True:
                for s in range(min(numrec, 12)):
                    prn = btog(line[32 + s * 3]) + '%02d' % toint(line[33 + s * 3 : 35 + s * 3])
                    prnlist += [prn]
                    obsdata[recordnum][prn] = {}
                numrec -= 12
                if numrec > 0:
                    line = fid.next().rstrip('\n')
                else:
                    break
            if 'obscodes' not in obsdata.rnx:
                raise RuntimeError('RINEX file did not define data records')
            elif type(obsdata.rnx['obscodes'][0]) is tuple:
                obscodes = obsdata.rnx['obscodes'][-1][0]
            else:
                obscodes = obsdata.rnx['obscodes']
            for prn in prnlist:
                for (obs, s) in zip(obscodes, range(len(obscodes))):
                    s = s % 5
                    if not s:
                        line = fid.next().rstrip('\n')
                    val = value(tofloat(line[s * 16 : s * 16 + 14]))
                    LLI = toint(line[s * 16 + 14 : s * 16 + 15])
                    val.lostlock = bool(LLI % 2)
                    freq = toint(obs[1])
                    if isinstance(obsdata.rnx['ambiguity'], list):
                        ambig = obsdata.rnx['ambiguity'][-1][0]
                    else:
                        ambig = obsdata.rnx['ambiguity']
                    if (LLI >> 1) % 2 and prn[0] == 'G' and freq <= 2: 
                        # wavelength factor opposite of currently set
                        # by RINEX definition, valid for GPS L1, 2 only
                        val.wavefactor = (ambig[prn][freq-1] % 2) + 1
                    elif prn[0] == 'G' and freq <= 2:
                        val.wavefactor = ambig[prn][freq-1]
                    val.antispoofing = bool((LLI >> 2) % 2)
                    val.STR = toint(line[s * 16 + 15 : s * 16 + 16])
                    # Signal strength.
                    # 1 is minimum; 5 is good; 9 is maximum.  0 is unknown
                    obsdata[recordnum][prn][obs] = val
            recordnum += 1
    fid.close()
    return obsdata

def procheader(fid, rnxdata, sawrec, recordnum, numlines=None):
    linesread = 0
    while True:
        if numlines is not None:
            linesread += 1
            if linesread > numlines:
                return
        try:
            line = '%-80s' % fid.next().rstrip('\n') # pad spaces to 80
        except StopIteration:
            return
        label = line[60:]
        if label in RINEX:
            RL = RINEX[label]
            if label in sawrec:
                if RL.multi_act == 0:   # warn and replace
                    warn('The header ' + label + ' was encountered ' +
                         'multiple times.  Old values clobbered.')
                elif RL.multi_act == 1: # forbidden
                    raise ValueError('Header ' + label + ' occurs too often!')
                elif RL.multi_act == 2: # replace
                    pass
                elif RL.multi_act == 3: # list with recordnums
                    for field in RL:
                        if field.name not in rnxdata:
                            rnxdata[field.name] = []
                        elif type(rnxdata[field.name]) is not list:
                            rnxdata[field.name] = [(rnxdata[field.name], sawrec[label])]
                        rnxdata[field.name] += [(field.read(line), recordnum)]
                    continue
                elif RL.multi_act == 4: # ignore
                    continue
                elif RL.multi_act == 5: # make list entries for new recordnum
                    if sawrec[label] != recordnum:
                        for field in RL:
                            if field.name not in rnxdata:
                                rnxdata[field.name] = []
                            elif type(rnxdata[field.name]) is not list:
                                rnxdata[field.name] = [(rnxdata[field.name], sawrec[label])]
                            rnxdata[field.name] += [(field.read(line), recordnum)]
                        continue
                    # else replace...
                else:
                    raise RuntimeError('Bad multiple-header action; fix RINEX')
            for field in RL:
                rnxdata[field.name] = field.read(line)
            sawrec[label] = recordnum
        elif label == 'END OF HEADER       ':
            break
        else:
            warn('Header line ' + label + ' unrecognized; ignoring')

def read_rinex(URL, verbose=False, gunzip=None, uncompress=None, untar=None):
    (filename, headers) = urllib.urlretrieve(URL) # does nothing if local file
    if verbose:
        if filename != URL:
            print URL, 'downloaded to', filename, '.'
        else:
            print 'Local file', filename, 'used directly.'
    if untar or (untar is None and tarfile.is_tarfile(filename)):
        if gunzip:
            if verbose:
                print 'Unpacking gzipped tarfile.'
            zfile = tarfile.open(filename,'r:gz')
            zfile = zfile.extractfile(zfile.next())
        elif gunzip is None:
            if verbose:
                print 'Unpacking tarfile.'
            zfile = tarfile.open(filename)  # Automatically handles tar.gz,bz2
            zfile = zfile.extractfile(zfile.next())
        else:
            if verbose:
                print 'Unpacking noncompressed tarfile.'
            zfile = tarfile.open(filename,'r:') # Force no gunzip
            zfile = zfile.extractfile(zfile.next())
    elif gunzip or gunzip is None and re.match(filename, '.+\.gz$', re.I):
        if verbose:
            print 'Gunzipping file.'
        zfile = gzip.open(filename) 
    else:
        zfile = open(filename)
    if uncompress or (uncompress is None and re.match(
            '^' + CR_VER + ' +COMPACT RINEX FORMAT +CRINEX VERS +/ +TYPE$', zfile.readline())):
        if verbose:
            print 'Uncompressing HATANAKA RINEX data.'
        zfile.seek(0)
        zfile = crx2rnx(zfile)
    return get_data(zfile)

def main():
    '''
    Read RINEX observation data, downloading, gunzipping, and uncompressing
    as necessary.
    '''
    
    parser = OptionParser(description=main.func_doc,
               usage=sys.argv[0] + ' [-hvVpgutGUT] <filename> [-o [<output file>]]',
               epilog='<output file>, if given, receives a binary pickle of the RINEX data.')
    parser.add_option('-V', '--verbose', action='store_true',
            help='Verbose operation')
    parser.add_option('-p', '--pickle', action='store_true',
            help='Save parsed data as a pickle file (extension becomes .pkl')
    parser.add_option('-g', '--gunzip', action='store_true',
            help='Force treatment as gzipped')
    parser.add_option('-G', '--no-gunzip', action='store_false', dest='gunzip',
            help='Do not gunzip')
    parser.add_option('-u', '--uncompress', action='store_true',
            help='Force treatment as Compact RINEX')
    parser.add_option('-U', '--no-uncompress', action='store_false',
            dest='uncompress', help='Do not treat as Compact RINEX')
    parser.add_option('-t', '--tar', action='store_true',
            help='Force treatment as tar file')
    parser.add_option('-T', '--notar', action='store_false', dest='tar',
            help='Do not untar')
    parser.add_option('-v', '--version', action='store_true',
            help='Show version and quit')
    parser.add_option('-o', '--output', action='store',
            help='File to save pickle data in (overrides -p)')
    (opts, args) = parser.parse_args()
    if opts.version:
        print 'GPSData.rinex version', __ver__, 'supporting RINEX version',\
                RNX_VER, 'and Compact RINEX version', CR_VER, '.'
    elif not args:
        parser.error('Filename or URL required.')
    else:
        parsed_data = [read_rinex(url, opts.verbose, opts.gunzip, 
            opts.uncompress, opts.tar) for url in args]
        if opts.output is not None:
            op = open(opts.output, 'w')
            dump(parsed_data, op, 2)
            op.close()
        elif opts.pickle:
            op = open(args[0] + '.pkl', 'w')
            dump(parsed_data, op, 2)
            op.close()

if __name__ == '__main__':
    main()
