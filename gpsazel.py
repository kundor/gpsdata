from fetchnav import getsp3file
from satpos import readsp3, satpos, coef_fn, mvec, posrecord
from coords import xyz2enu, enu2azel
from warnings import warn
from math import pi
from contextlib import suppress

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

def satcoeffs(pl):
    """Position coefficient functions for all satellites in pl.
    
    Given a poslist (as from poslist() or readsp3()), compute interpolating
    coefficient functions for the positions of each satellite; return a dictionary
    by PRN.
    Only PRNs present in every record of pl are used.
    """
    cofns = posrecord()
    for prn in pl[0]:
        with suppress(KeyError):
            cofns[prn] = coef_fn(pl, prn)
    return cofns

def azeldeg(rxloc, sxloc):
    """Given two ECEF locations in meters, return azimuth and elevation in degrees."""
    az, el = enu2azel(xyz2enu(rxloc, sxloc))
    return az * 180 / pi, el * 180 / pi

def gpsazel(rxloc, prn, gpsweek, gpssow, cofns=None, pl=None):
    """Given receiver location (ECEF), prn, GPS week and GPS second,
    return azimuth and elevation in degrees.
    """
    totsec = totalsec(gpsweek, gpssow)
    if cofns and prn in cofns:
        sx = mvec(totsec) @ cofns[prn](totsec)
    else:
        if pl is None:
            pl = poslist(gpsweek, gpssow)
        sx = satpos(pl, prn, totsec)
    return azeldeg(rxloc, sx*1000)

