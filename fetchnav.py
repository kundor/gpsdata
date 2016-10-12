from ftplib import FTP
from urllib.request import urlretrieve
from warnings import warn
import time
from datetime import datetime, timezone, timedelta
from collections.abc import Sequence
from numbers import Number
import os

sp3dir = '/bowie/scratch/sp3'

sp3sites = [
    ('ftp.igs.org',        'pub/product'),
    ('igscb.jpl.nasa.gov', 'pub/product'),
    ('cddis.gsfc.nasa.gov','pub/gps/products'),
    ('garner.ucsd.edu',    'archive/garner/products'),
    ('igs.ensg.ign.fr',    'pub/igs/products'),
]
# TODO : add   ('ftp.unibe.ch',       'aiub/CODE', aiub, sp3)
# has a totally different organization
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

gpsepoch = datetime(1980, 1, 6, 0, 0, 0, 0, timezone.utc)

try:
    os.makedirs(sp3dir, exist_ok = True)
except OSError as e:
    print("The path where we store sp3 files, " + sp3dir + ", is inaccessible "
            "(occupied by another file, or no permissions.")
    print e
    raise SystemExit

def isnaive(dt):
    return isinstance(dt, datetime) and (dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None)

def getutctime(dt = None):
    '''Convert datetime, struct_time, tuple (Y,M,D,H,M,S,μS), or POSIX timestamp
       to UTC-aware datetime object. Assumed to already be UTC unless the timezone
       is included (aware datetime objects and struct_times).'''
    if dt is None:
        return datetime.now(timezone.utc)
    elif isinstance(dt, time.struct_time):
        return datetime.fromtimestamp(time.mktime(dt), timezone.utc)
    elif isinstance(dt, Sequence): # list or tuple: Year, Month, Day, H, M, S, μS
        return datetime(*dt, tzinfo=timezone.utc)
    elif isinstance(dt, Number):
        return datetime.fromtimestamp(dt, timezone.utc)
    elif isnaive(dt):
        return dt.replace(tzinfo=timezone.utc)
    elif isinstance(dt, datetime):
        return dt
    raise ValueError("Don't know how to interpret this as time")

def gpsweek(dt):
    '''Given UTC datetime, return GPS week number. (Does NOT correct for leap seconds,
    so it could be one too low on the last few seconds of Saturday (UTC).)'''
    return int((dt - gpsepoch) / timedelta(weeks = 1))

def gpsdow(dt):
    '''Day of Week.'''
    return dt.isoweekday() % 7

def iguhh(dt):
    '''Appropriate ultra-rapid suffix: 00 after 3:00 UTC, 06 after 9:00,
      12 after 15:00, 18 after 21:00.'''
    sufs = ['00', '06', '12', '18']
    return sufs[(dt.hour - 3)//6]

def sp3path(filename):
    return os.path.join(sp3dir, filename)

def canread(filename):
    return os.access(filename, os.R_OK)

def ftplist(site, dirs):
    with FTP(site) as ftp:
        ftp.login()
        dirfiles = []
        for dir in dirs:
            ftp.cwd(dir)
            dirfiles += ftp.nlst()
        return dirfiles

def ftpfetch(site, dir, file):
    (filename, headers) = urlretrieve('ftp://' + site + '/' + dir + '/' + 

def getsp3file(dt = None):
    '''Download the appropriate sp3 file for the datetime, struct_time, or
       unix second dt (default now). Assumed to be UTC, except for aware
       datetime objects and struct_times.
       Return filename.'''
    dt = getutctime(dt)
    diff = getutctime() - dt
    if diff < timedelta(hours=-12):
        raise ValueError("Sorry, future predictions not supported")
    final = 'igs{}{}.sp3.Z'.format(gpsweek(dt), gpsdow(dt)) # usually after 12 days
    rapid = 'igr{}{}.sp3.Z'.format(gpsweek(dt), gpsdow(dt)) # usually late next day
    ultra = 'igu{}{}_{}.sp3.Z'.format(gpsweek(dt - timedelta(hours = 3)),
                                      gpsdow(dt - timedelta(hours = 3)),
                                      iguhh(dt)) # real-time
    falbk = 'igu{}{}_{}.sp3.Z'.format(gpsweek(dt - timedelta(hours = 9)),
                                      gpsdow(dt - timedelta(hours = 9)),
                                      iguhh(dt - timedelta(hours = 6))) # preceding ultra-rapid
    if canread(sp3path(final)):
        return sp3path(final)
    if diff < timedelta(days = 12) and canread(sp3path(rapid)):
        return sp3path(rapid)
    if diff < timedelta(hours = 17) and canread(sp3path(ultra)):
        return sp3path(ultra)
    for (site, dir) in sp3sites:
        dirs = [dir + '/{}'.format(gpsweek(dt))]
        if gpsdow(dt) == 0 and dt.hour < 9:
            dirs += [dir + '/{}'.format(gpsweek(dt) - 1)]
        try:
            wkfiles = ftplist(site, dirs)
        except Exception:
            warn(site + ' failed; trying another...')
        else: # no exception
            break


#igs : %WEEK/igu%WEEK%DoW_%HR.sp3.Z
#  where %HR is 00 (After 3:00 UTC), 06 (after 9:00 UTC), 12 (after 15:00 UTC), or 18 (after 21:00 UTC)
#           /igr%WEEK%DoW.sp3.Z  (after 17:00 UTC the next day or so)
#           /igs%WEEK%DoW.sp3.Z  (after about 12 days, but currently 17 days!!)

