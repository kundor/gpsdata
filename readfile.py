#!/usr/bin/python
# Created by Nick Matteo <kundor@kundor.org> July 15, 2009
'''
Read GPS observations in from a file, creating a GPSData object.

read_file(URL) supports local files, http, ftp, gzipped, tarred, etc.
Currently, only RINEX observation files, or Hatanaka-compressed ones,
are supported.
Command-line operation works also; after parsing, some summary
information is printed, and optionally the GPSData objects can be
saved to a pickle file.
'''
# TODO:  read novatel logs; read NMEA; read RTCM

import re
import sys
import gzip
import urllib
import tarfile
import cPickle as pickle
from optparse import OptionParser
from __init__ import __ver__
import rinex

def read_file(URL, format=None, verbose=False, gunzip=None, untar=None):
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
    elif gunzip or gunzip is None and filename.lower().endswith('.gz'):
        if verbose:
            print 'Gunzipping file.'
        zfile = gzip.open(filename)
        zfile.name = filename.rpartition('.gz')[0] 
    else:
        zfile = open(filename)
    if format in ('RINEX', 'CRINEX') or format is None and re.search('\.[0-9]{2}[OoDd]$', zfile.name):
        if verbose:
            print 'Parsing file in RINEX format.'
        return rinex.get_data(zfile, format == 'CRINEX')
    else:
        print 'Unsupported file format!'

def main():
    '''
    Read GPS observation data, downloading, gunzipping, and uncompressing
    as necessary.
    '''
    
    parser = OptionParser(description=main.func_doc,
            usage=sys.argv[0]+' [-hvVpgtGT] [-f FORMAT] <filename> [-o OUTPUT]',
            epilog='OUTPUT, if given, receives a binary pickle of the RINEX data.')
    parser.add_option('-v', '--version', action='store_true',
            help='Show version and quit')
    parser.add_option('-V', '--verbose', action='store_true',
            help='Verbose operation')
    parser.add_option('-p', '--pickle', action='store_true',
            help='Save parsed data as a pickle file (extension becomes .pkl')
    parser.add_option('-g', '--gunzip', action='store_true',
            help='Force treatment as gzipped')
    parser.add_option('-G', '--no-gunzip', action='store_false', dest='gunzip',
            help='Do not gunzip')
    parser.add_option('-t', '--tar', action='store_true',
            help='Force treatment as tar file')
    parser.add_option('-T', '--notar', action='store_false', dest='tar',
            help='Do not untar')
    parser.add_option('-f', '--format', action='store', choices=['RINEX', 'CRINEX'],
            help='Format of GPS observation file (default: by extension)')
    parser.add_option('-o', '--output', action='store',
            help='File to save pickle data in (overrides -p)')
    (opts, args) = parser.parse_args()
    if opts.version:
        print 'GPSData version', __ver__, 'supporting RINEX version',\
                RNX_VER, 'and Compact RINEX version', CR_VER, '.'
    elif not args:
        parser.error('Filename or URL required.')
    else:
        try:
            parsed_data = [read_file(url, opts.format, opts.verbose, 
                opts.gunzip, opts.tar) for url in args]
        except IOError, ioe:
            print ioe
            sys.exit(ioe.errno)
        if opts.output is not None:
            op = open(opts.output, 'wb')
            pickle.dump(parsed_data, op, pickle.HIGHEST_PROTOCOL)
            op.close()
        elif opts.pickle:
            op = open(args[0] + '.pkl', 'wb')
            pickle.dump(parsed_data, op, pickle.HIGHEST_PROTOCOL)
            op.close()
        for data in parsed_data:
            if data is not None:
                print data.header_info()

if __name__ == '__main__':
    main()

