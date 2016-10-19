from fetchnav import getsp3file
from satpos import satpos, readsp3
from coords import xyz2enu, enu2azel
from warnings import warn
from math import pi

def totalsec(gpsweek, gpssow):
    return gpsweek * 7 * 24 * 60 * 60 + gpssow

def poslist(gpsweek, sow_start, sow_end = None):
    """Return a list of sp3 satellite positions encompassing the given times.
    
    It is okay if sow_start and sow_end are negative or larger than a week's worth.
    """
    if sow_end is None:
        sow_end = sow_start
    pl = readsp3(getsp3file((gpsweek, sow_start)))
    totsec = totalsec(gpsweek, sow_start)
    if totsec - pl[0].epoch < 60 * 60 * 2:
        pl0 = readsp3(getsp3file((gpsweek, sow_start - 60*60*12)))
# note: negative seconds of week will work fine
        diff = pl[0].epoch - pl0[-1].epoch
        if diff != 900:
            warn("Difference " + str(diff) + " between sp3 files is not 900 seconds.")
        pl0.extend(pl)
        pl = pl0
    totsec = totalsec(gpsweek, sow_end)
    while pl[-1].epoch - totsec < 60 * 60 * 2:
        sow_start += 60*60*24
        pl1 = readsp3(getsp3file((gpsweek, sow_start)))
# note: seconds of week above 604800 will work fine too
        diff = pl1[0].epoch - pl[-1].epoch
        if diff != 900:
            warn("Difference " + str(diff) + " between sp3 files is not 900 seconds.")
        pl.extend(pl1)
    return pl

def gpsazel(rxloc, prn, gpsweek, gpssow, pl=None):
    """Given receiver location (ECEF), prn, GPS week and GPS second,
    return azimuth and elevation in degrees.
    """
    if pl is None:
        pl = poslist(gpsweek, gpssow)
    totsec = totalsec(gpsweek, gpssow)
    sx = satpos(pl, prn, totsec)
    az, el = enu2azel(xyz2enu(rxloc, sx * 1000))
    return az * 180 / pi, el * 180 / pi


        
