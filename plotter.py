'''Utilities to produce plots of a given observation from GPSData objects.'''

from os import environ, path
from itertools import count

import matplotlib
from matplotlib.cm import spectral as cmap
from matplotlib.colors import Normalize

statfile = path.join(path.dirname(path.abspath(__file__)), 'stations.dat')
'''File with data mapping marker names in RINEX files to full locations.'''

stations = []
for line in open(statfile):
    stations += [line.split(',')]

def match(station):
    '''Given prefix string `station', find full name and country of the
    observation station.
    '''
    for stat in stations:
        if station in stat[:3]:
            return stat[7].upper() + ', ' + stat[8]
    return 'Unknown Station ' + station


def colorplot(ax, X, Y, C, label=None, numlabs=4):
    '''Plot data in array X vs. array Y with points colored by C (on axis ax)

    X, Y, and C must be arrays (or lists, tuples) and have the same length;
    C can be matplotlib character colors, names, hex strings, RGB tuples.
    If C is only 1d float values, it will be treated as a z-axis and mapped
    to the default colormap.
    label, if defined, is text to be periodically placed on the line.
    '''
    # That means normalizing to 0-1 and using matplotlib.colors.Colormap
    if isinstance(C[0], (float, int)):
        nm = Normalize(min(C), max(C))
        C = cmap(nm(C))
    # TODO : keep nm for all instances, so all lines are colored equivalently
    for x, y, c, n in zip(X, Y, C, count()):
        ax.plot([x], [y], linestyle='', marker='.', ms=1., mfc=c)
        if label is not None and not n % (len(X)//numlabs):
            ax.annotate(label, [x, y])


def plot(gdo, obs, fname=None):
    '''Given GPSData object `gdo', plot observation `obs' against time of day
    for all satellites.  Save to file `fname', or display if None.
    '''
    if fname == 'web':
        # Set environment variable HOME for use with a web server
        environ['HOME'] = '/var/www/mpl/'
    if fname:
        matplotlib.use('Agg')
    from matplotlib.pyplot import figure, show

    legends = sorted(gdo.prns)
    # TODO : split plots if epochs cover different days, or ignore < 10 data
    # points
    bubs = [[(gdte.hour + gdte.minute/60. + gdte.second/3600., ob) for
             gdte, ob in gdo.iterlist(prn, ['epoch', obs])] for prn in legends]
    dubdub = []
    for bub in bubs:
        dubdub += [[b[0] for b in bub]]
        dubdub += [[b[1] for b in bub]]
        # dubdub += '.'
    fig = figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.set_position([0.125, 0.1, 0.7, 0.8])
    ax.plot(*dubdub, **{'linestyle':'', 'marker':'.', 'ms':1.})
    ax.axis((0, 24, 0, 150))
    ax.set_xlabel('UTC Time (hr)')
    ax.set_ylabel('TEC (Units)')
    ax.set_title(match(gdo.meta.marker[-1]) + ' : Uncalibrated Slant TEC')
    fig.text(.08, .95, gdo.meta.firsttime.strftime('%d/%m/%Y'),
             transform=ax.transAxes)
    fig.legend(ax.lines, legends, numpoints=1, markerscale=5,
               prop=matplotlib.text.FontProperties(size='smaller'))
    if fname and fname != 'web':
        fig.savefig(fname)
    elif fname == 'web':
        return fig
    else:
        show()
