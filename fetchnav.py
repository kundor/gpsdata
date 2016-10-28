from ftplib import FTP
from urllib.request import urlretrieve
import os
from .gpstime import getutctime, gpsweek, gpsdow, dhours
from .utility import decompress

sp3dir = '/scratch/sp3'

sp3sites = [
    ('ftp.igs.org',        'pub/product'),
    ('igscb.jpl.nasa.gov', 'pub/product'),
    ('cddis.gsfc.nasa.gov','pub/gps/products'),
    ('garner.ucsd.edu',    'archive/garner/products'),
    ('igs.ensg.ign.fr',    'pub/igs/products'),
]
# TODO : add   ('ftp.unibe.ch',       'aiub/CODE', aiub, sp3)
# which has a totally different organization
#  latest COD.EPH_U
#  rapid  COD%WEEK%DoW.EPH_R (current two weeks)
#         %YEAR_M/COD%WEEK%DoW.EPH_M.Z (anytime -- available sometime next day)
#  final  %YEAR/COD%WEEK%DoW.EPH.Z (after about two weeks)
## ftp://ftp.unibe.ch/aiub/AIUB_AFTP.TXT


#  TODO: try http access as backup (http may work where ftp does not)
#    (https,'igscb.jpl.nasa.gov', 'igscb/product', igs, sp3),
#    (httpA, 'garner.ucsd.edu',   'pub/products', 'anonymous', 'anon@mail.com', igs, sp3),
# (note, first column is "proto" function; add ftp for the rest)
# for (proto, *info, format) in sites: try: proto(*info)


#rnavsites = [
#    (ftp,  'cddis.gsfc.nasa.gov','gnss/data/hourly', hourly, rnav),
#]
# hourly : %YEAR/%DoY/hour%DoY0.%YYn.Z

while True:
    try:
        os.makedirs(sp3dir, exist_ok=True)
    except OSError as e:
        print("The directory to store sp3 files, " + sp3dir + ", is inaccessible "
              "(occupied by another file, or no permissions).")
        print(e)
        sp3dir = input("Choose another path, or q to quit:")
        if sp3dir == 'q':
            raise
        continue
    break

def sp3path(filename):
    return os.path.join(sp3dir, filename)

def ultra(dt):
    """IGS ultrarapid filename immediately preceding dt."""
    return 'igu{}{}_{:02}.sp3'.format(gpsweek(dt), gpsdow(dt), dt.hour//6*6)

def sp3list(dt):
    """Return list of potential filenames containing ephemerides for the given
    time, in decreasing order of preference."""
    return ['igs{}{}.sp3'.format(gpsweek(dt), gpsdow(dt)),
            'igr{}{}.sp3'.format(gpsweek(dt), gpsdow(dt)),
            ultra(dt + dhours(18)),
            ultra(dt + dhours(12)),
            ultra(dt + dhours(6)),
            ultra(dt),
            ultra(dt - dhours(6)),
            ultra(dt - dhours(12)),
            ultra(dt - dhours(18))]

def latencies(dt):
    """Return list of how many hours after dt we expect the corresponding
    files in sp3list to be available."""
    return [336 - dt.hour,
             41 - dt.hour,
             21 - dt.hour % 6,
             15 - dt.hour % 6,
              9 - dt.hour % 6,
              3 - dt.hour % 6,
             -3 - dt.hour % 6,
             -9 - dt.hour % 6,
            -15 - dt.hour % 6]

def canread(filename):
    return os.access(filename, os.R_OK)

def ftplist(site, fdir, wk1, wk2):
    with FTP(site) as ftp:
        ftp.login()
        ftp.cwd(fdir)
        ftp.cwd(wk1)
        dirfiles = ftp.nlst('ig*.sp3.Z')
        # unfortunately 'ig[rsu]*.sp3.Z' does not work on all servers
        if wk1 != wk2:
            ftp.cwd('../' + wk2)
            dirfiles += ftp.nlst('ig*.sp3.Z')
        return dirfiles

def ftpfetch(site, fdir, file):
    fullpath = 'ftp://' + site + '/' + fdir + '/' + file[3:7] + '/' + file + '.Z'
    (filename, headers) = urlretrieve(fullpath, sp3path(file + '.Z'))
# overwrites any existing file without complaint
    return decompress(filename)

def getsp3file(dt=None):
    """Download the appropriate sp3 file for the given time and return filename.

    Input may be datetime, struct_time, unix second, or Y,M,D,H,M,S tuple,
    and defaults to now.  Input is assumed to be UTC, except for aware
    datetime objects and struct_times.
    """
    dt = getutctime(dt)
    diff = getutctime() - dt
    if diff < dhours(-12):
        raise ValueError("Sorry, future predictions beyond 12 hours not supported.")
    flist = sp3list(dt)
    latlist = [dhours(l) for l in latencies(dt)]
    fsfound = [canread(sp3path(f)) for f in flist]
    fsnum = fsfound.index(True) if True in fsfound else None
    if fsnum == 0:
        return sp3path(flist[0])
    elif fsnum and latlist[fsnum - 1] > diff:
        # not enough time has passed to get a better file than we already have
        return sp3path(flist[fsnum])
    # otherwise, try to fetch best file available
    for (site, fdir) in sp3sites:
        try:
            remotelist = ftplist(site, fdir, flist[2][3:7], flist[-1][3:7])
        except Exception:
            print(site + ' failed; trying another...')
            continue
        ftpfound = [f + '.Z' in remotelist for f in flist]
        if True not in ftpfound:
            print('No files found on ' + site + '; trying another...')
            continue
        ftpnum = ftpfound.index(True)
        if fsnum is not None and fsnum <= ftpnum:
            return sp3path(flist[fsnum])
        return ftpfetch(site, fdir, flist[ftpnum])
    # if we get here, we tried every ftp site without success
    if fsnum is None:
        raise RuntimeError('Could not fetch an sp3 file from any site, '
                           'and no local file was found in ' + sp3dir + '.')
    return sp3path(flist[fsnum])


#igs : %WEEK/igu%WEEK%DoW_%HR.sp3.Z
#  where %HR is 00 (After 3:00 UTC), 06 (after 9:00 UTC),
#               12 (after 15:00 UTC), or 18 (after 21:00 UTC)
#           /igr%WEEK%DoW.sp3.Z  (after 17:00 UTC the next day or so)
#           /igs%WEEK%DoW.sp3.Z  (after about 12 days, but currently 17 days!!)

