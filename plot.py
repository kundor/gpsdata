from math import floor, ceil, pi
import numpy as np
import matplotlib as mp
from matplotlib import pyplot as plt

def posneg(arr):
    """Check that input consists of some positive entries followed by negative entries,
    with no mixing. Return index of first negative entry, or None."""
    neg = False
    ind = None
    for i, k in enumerate(arr):
        if not neg and k < 0:
            ind = i
            neg = True
        if neg and k > 0:
            print("{} (entry {}) is positive, after negative entry at {}!".format(k, i, ind))
            return ind
    return ind

def dorises(snrdata, prn):
    """Plot snr vs. elevation for all periods of rising elevation.

    Finds all ascensions of satellite prn in snrdata, and plots them
    in subplots of a single figure.
    """
    _, el, az, sod, snr = zip(*(r for r in snrdata if r.prn == prn))
    riz = rises(el, sod)
    for i, (rb, re) in enumerate(riz):
        plt.subplot(len(riz), 1, i+1)
        plt.scatter(el[rb:re+1], snr[rb:re+1], s=1)
        plt.xlim(el[rb], el[re])
        plt.xlabel('Elevation')
        plt.ylabel('SNR')
        plt.title('PRN {}, DoY {}, {:02d}:{:02d}--{:02d}:{:02d}, Az {}--{}'.format(
            prn, snrdata.doy, int(sod[rb]//3600), int(sod[rb] % 3600)//60,
            int(sod[re]//3600), int(sod[re] % 3600)//60,
            min(az[rb:re+1]), max(az[rb:re+1])))
    plt.tight_layout()
    
def dorises2(snrdata, prn, doy0):
    """Plot snr vs. elevation for all periods of rising elevation.
    
    Plot each ascension in a different figure, and save to a file instead of
    displaying. Input is a list of Records (metadata is not expected, unlike dorises).
    The time field (fourth entry of each record) is expected to be seconds of week.
    """
    plt.ioff()
    try:
        _, el, az, sow, snr = zip(*(r for r in snrdata if r.prn == prn))
    except ValueError:
        print('PRN {} not found'.format(prn))
        return
    riz = rises(el, sow, prn)
    for i, (rb, re) in enumerate(riz):
        fig = plt.figure()
        plt.scatter(el[rb:re+1], snr[rb:re+1], s=1)
        plt.xlim(el[rb], el[re])
        plt.xlabel('Elevation')
        plt.ylabel('SNR')
        doy = int(doy0 + sow[rb]//86400)
        minaz = min(az[rb:re+1])
        maxaz = max(az[rb:re+1])
        if maxaz > 350 and minaz < 10:
            minaz = min(a for a in az[rb:re+1] if a > 180)
            maxaz = max(a for a in az[rb:re+1] if a < 180)
        plt.title('PRN {}, DoY {}, {}--{}, Az {:.0f}--{:.0f}'.format(
            prn, doy, sowhrmin(sow[rb]), sowhrmin(sow[re]), minaz, maxaz))
        plt.tight_layout()
        quart = int(5 - az[rb] // 90)  # rising quarter
        if quart == 5:
            quart = 1
        hr = (int(sow[rb]) % 86400) // 3600
        plt.savefig('{:02d}-{}-{:02d}-Q{}.png'.format(prn, doy, hr, quart))
        plt.close(fig)

def sodhrmin(sod):
    return '{:02d}:{:02d}'.format(sod//3600, (sod % 3600)//60)

def sowhrmin(sow):
    return sodhrmin(int(sow) % 86400)

def sowdhrmin(sow):
    return str(int(sow) // 86400) + ';' + sowhrmin(sow)

def rises(el, sod, prn=None):
    difel = np.diff(el)
    starts = [-1] + np.argwhere(np.diff(sod) > 1000).ravel().tolist() + [len(difel)]
    riz = []
    for beg, end in zip(starts, starts[1:]):
        if sod[end] - sod[beg+1] < 600: # less than 10 minute arc
            print('Less than 10 minutes, PRN {}, {} to {} ({}--{})'.format(
                prn, beg+1, end, sowdhrmin(sod[beg+1]), sowhrmin(sod[end])))
            continue
        peak = posneg(difel[beg+1:end])
        if peak == 0: # only falling elevations I guess
            print('Only falling elevations? PRN {}, {} to {} ({}--{})'.format(
                prn, beg+1, end, sowdhrmin(sod[beg+1]), sowhrmin(sod[end])))
            continue        
        if peak is not None:
            peak += beg + 1
        else:
            peak = end
        if el[peak] < 15:
            print('Max elevation {}, PRN {}, {} to {} ({}--{})'.format(
                el[peak], prn, beg+1, end, sowdhrmin(sod[beg+1]), sowhrmin(sod[end])))
            continue
        riz.append([beg+1, peak])
    return riz

def polarazel(azis, eles):
    """Plot azimuth and elevations (in degrees) as a curve on a polar plot.
    
    Input should be numpy arrays."""
    plt.figure()
    plt.polar((90 - azis)/180 * pi, 90 - eles)
    xloc, _ = plt.xticks()
    xlab = [str(int(x * 180 / pi)) + '°' for x in xloc]
    plt.xticks(xloc, xlab)
    yloc = range(20, 90, 20)
    plt.yticks(yloc, (str(90 - y) for y in yloc))

def snrVSel(snrdata, prn, secstart=0, secend=86400, color=None):
    snr = [r.snr for r in snrdata if r.prn == prn and secstart < r.sod < secend]
    el = [r.el for r in snrdata if r.prn == prn and secstart < r.sod < secend]
    plt.scatter(el, snr, s=1, color=color)
#    plt.xlim(min(el), max(el))
#    plt.xlabel('Elevation')
#    plt.ylabel('SNR')
#    plt.title('PRN {}, DoY {}'.format(prn, snrdata.doy))
    plt.tight_layout()

def iterSNRs(SNRs):
    for snr in SNRs:
        for rec in snr:
            yield rec.az, rec.el, rec.snr

def itergdo(gdo):
    for r in gdo.iterlist(obscode=('az', 'el', 'S1'), skip=True):
        for rec in r:
            if rec[0] is not None:
                yield rec

def azelbin(iterfn, dat, scale=2):
    snravg = np.zeros((360*scale, 90*scale))
    snrnum = np.zeros((360*scale, 90*scale))
    snrstd = np.zeros((360*scale, 90*scale))
    for az, el, snr in iterfn(dat):
        azi = floor(az*scale)
        eli = floor(el*scale)
        n = snrnum[azi, eli]
        snravg[azi, eli] = n/(n+1)*snravg[azi, eli] + 1/(n+1)*snr
        snrnum[azi, eli] += 1
    for az, el, snr in iterfn(dat):
        azi = floor(az*scale)
        eli = floor(el*scale)
        snrstd[azi, eli] += (snr - snravg[azi, eli])**2
    snrstd = np.sqrt(snrstd / np.where(snrnum > 0, snrnum, 1))
    snravg = np.ma.masked_where(snrnum == 0, snravg)
    snrstd = np.ma.masked_where(snrnum == 0, snrstd)
    plotazel(snravg, 'Mean SNR', scale)
    plotazel(snrstd, 'SNR standard deviation', scale)
    return snravg, snrnum, snrstd

def plotazel(dat, title, scale=2):
    plt.figure()
    vmin = np.percentile(dat.compressed(), 1)
    vmin = max(floor(vmin), np.min(dat))
    vmax = np.percentile(dat.compressed(), 99)
    vmax = min(ceil(vmax), np.max(dat))
    plt.pcolormesh(dat.T, vmin=vmin, vmax=vmax)
    axx = plt.gca()
    box = axx.get_position()
    xloc, xlab = plt.xticks()
    plt.xticks(xloc, xloc/scale)
    yloc, ylab = plt.yticks()
    plt.yticks(yloc, yloc/scale)
    plt.xlim(0, 360*scale)
    plt.ylim(10*scale, 90*scale)
    plt.title(title)
    plt.xlabel('Azimuth')
    plt.ylabel('Elevation')
    axc = plt.axes([box.x0 + box.width * 1.05, box.y0, 0.01, box.height])
    plt.colorbar(cax=axc)


