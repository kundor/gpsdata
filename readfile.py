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

import os
import re
import io
import sys
import gzip
import time
from urllib.request import urlretrieve
import tarfile
import pickle
from optparse import OptionParser
from utility import decompress

from __init__ import __ver__
import rinex
try:
    import plotter
except ImportError:
    pass

def read_file(URL, format=None, verbose=False, gunzip=None, untar=None):
    '''Process URL into a GPSData object.

    Deals with local files, http, or ftp; gzipped files; and single-file
    tar archives.  Then simplistic extension-based format detection is used,
    unless the argument `format' is supplied.
    '''
    if os.path.isfile(URL):
        filename = URL
        if verbose:
            print('Local file', filename, 'used directly.')
    else:
        try:
            (filename, headers) = urlretrieve(URL)
        except ValueError:
            print(URL + ' does not appear to be a local file, nor a valid URL.')
            return
        if verbose:
            print(URL, 'downloaded to', filename, '.')
    if untar or (untar is None and tarfile.is_tarfile(filename)):
        if gunzip:
            if verbose:
                print('Unpacking gzipped tarfile.')
            zfile = tarfile.open(filename, 'r:gz')
        elif gunzip is None:
            if verbose:
                print('Unpacking tarfile.')
            zfile = tarfile.open(filename)  # Automatically handles tar.gz,bz2
        else:
            if verbose:
                print('Unpacking noncompressed tarfile.')
            zfile = tarfile.open(filename, 'r:')  # Force no gunzip
        zfile = zfile.extractfile(zfile.next())
    elif gunzip == 2 or (gunzip is None and filename.endswith('.Z')):
        if verbose:
            print('Uncompressing file.')
        filename = decompress(filename, True)
        zfile = open(filename)
    elif gunzip == 1 or (gunzip is None and filename.lower().endswith(('.gz', '.z'))):
        if verbose:
            print('Gunzipping file.')
        zfile = gzip.open(filename)
        if filename.lower().endswith('.gz'):
            zfile.name = filename[:-3]
        elif filename.lower().endswith('.z'):
            zfile.name = filename[:-2]
        else:
            zfile.name = filename
    else:
        zfile = open(filename)
    if format is None:
        if re.search(r'\.[0-9]{2}[Oo]$', zfile.name):
            format = 'RINEX'
        elif re.search(r'\.[0-9]{2}[Dd]$', zfile.name):
            format = 'CRINEX'
    if format in ('RINEX', 'CRINEX'):
        if verbose:
            print('Parsing file in RINEX format.')
        return rinex.get_data(zfile, format == 'CRINEX')
    else:
        print(URL + ': Unsupported file format!')


def index(req, n_file, n_type):
    '''Read GPS observation data and show summary or TEC plot.

    This function is called for mod_python in a web server (apache).
    '''
    database = '/web/gps/data/'
    filedate = time.strptime(n_file[5:11], '%y%m%d')
    url = os.path.join(database, n_file[0:4], str(filedate.tm_year), n_file[7:9],
                       'rinex', n_file)
    # Parse RINEX file
    dat = read_file(url)
    if n_type.lower() == 'summary':
        # Return summary info
        req.content_type = "text/plain"
        req.write(dat.header_info())
    elif n_type.lower() == 'tec':
        # Return TEC plot
        fig = plotter.plot(dat, 'TEC', 'web')
        with io.BytesIO() as f:
            fig.savefig(f, format='png')
            req.content_type = "image/png"
            req.write(f.getvalue())

def main():
    '''Read GPS observation data, downloading, gunzipping, and uncompressing
    as necessary.
    '''
    usage = sys.argv[0] + ' [-hvVgtGT] [-f FORMAT]'
    if 'plotter' in dir():
        usage = usage + ' [-i OBSERVATION]'
    usage = usage + ' <filename> [-o OUTPUT]'
    parser = OptionParser(description=main.__doc__, usage=usage)
    parser.add_option('-v', '--version', action='store_true',
                      help='Show version and quit')
    parser.add_option('-V', '--verbose', action='store_true',
                      help='Verbose operation')
#   parser.add_option('-p', '--pickle', action='store_true',
#                     help='Save parsed data as a pickle file (extension becomes .pkl')
    parser.set_defaults(pickle=None) # TODO: fix pickling
    if 'plotter' in dir():
        parser.add_option('-i', '--image', action='store', metavar='OBSERVATION',
                          help='Plot given OBSERVATION for all  satellites; '
                               ' display unless -o given')
    else:
        parser.set_defaults(image=None)
    parser.add_option('-g', '--gunzip', action='store_const', const=1,
                      help='Force treatment as gzipped')
    parser.add_option('-u', '--uncompress', action='store_const', const=2, dest='gunzip',
                      help="Force treatment as compress'd")
    parser.add_option('-G', '--no-gunzip', action='store_const', const=0, dest='gunzip',
                      help='Do not gunzip or uncompress')
    parser.add_option('-t', '--tar', action='store_true',
                      help='Force treatment as tar file')
    parser.add_option('-T', '--notar', action='store_false', dest='tar',
                      help='Do not untar')
    parser.add_option('-f', '--format', action='store',
                      choices=['RINEX', 'CRINEX'],
                      help='Format of GPS observation file (default: by extension)')
    parser.add_option('-o', '--output', action='append',
                      help='File to save data in (must specify -i or -p)')
    (opts, args) = parser.parse_args()
    if opts.version:
        print('GPSData version', __ver__, 'supporting RINEX version',
              rinex.RNX_VER, 'and Compact RINEX version', rinex.CR_VER, '.')
    elif opts.image and opts.pickle:
        parser.error('Cannot output both a pickle and an image - sorry.')
    elif not args:
        parser.error('Filename or URL required.')
    else:
        try:
            parsed_data = [read_file(url, opts.format, opts.verbose,
                                     opts.gunzip, opts.tar) for url in args]
        except IOError as ioe:
            print(ioe)
            sys.exit(ioe.errno)
        if opts.output and opts.pickle:
            op = open(opts.output[0], 'wb')
            pickle.dump(parsed_data, op, pickle.HIGHEST_PROTOCOL)
            op.close()
        elif opts.output and opts.image:
            for data, out in zip(parsed_data, opts.output):
                # If there are more input files than output names, or vice
                # versa, we write out the lesser number (ignoring the rest)
                plotter.plot(data, opts.image, out)
        elif opts.pickle:
            op = open(args[0] + '.pkl', 'wb')
            pickle.dump(parsed_data, op, pickle.HIGHEST_PROTOCOL)
            op.close()
        elif opts.image:
            for data in parsed_data:
                plotter.plot(data, opts.image)
        for data in parsed_data:
            if data is not None:
                print(data.header_info())


if __name__ == '__main__':
    main()
