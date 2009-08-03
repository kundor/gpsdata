'''Utilities to produce plots of a given observation from GPSData objects.'''

from os import path

class MarkerNames(object):
    '''Class to hold data from stations.dat mapping marker names in RINEX
    files to full location titles.
    '''

    statfile = path.join(path.dirname(path.abspath(__file__)), 'stations.dat')

    def __init__(self):
        self.stations = []
        for line in open(self.statfile):
            self.stations += [line.split(',')]

    def match(self, station):
        '''Given prefix string `station', find full name and country of 
        observation station.
        '''
        for stat in self.stations:
            if station in stat[:3]:
                return stat[7].upper() + ', ' + stat[8]
        return 'Unknown Station ' + station

markernames = MarkerNames()

def plot(gdo, obs, fname=None):
    '''Given GPSData object `gdo', plot observation `obs' against time of day
    for all satellites.  Save to file `fname', or display if None.
    '''
    import matplotlib
    if fname:
        matplotlib.use('Agg')
    from matplotlib.pyplot import figure, show

    legends = list(gdo.prns)
    legends.sort()
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
    ax = fig.add_subplot(1,1,1)
    ax.set_position([0.125, 0.1, 0.7, 0.8])
    lines = ax.plot(*dubdub, **{'linestyle':'', 'marker':'.', 'ms':1.})
    ax.axis((0, 24, 0, 150))
    ax.set_xlabel('UTC Time (hr)')
    ax.set_ylabel('TEC (Units)')
    ax.set_title(markernames.match(gdo.meta.marker[-1]) +
                                                   ' : Uncalibrated Slant TEC')
    fig.text(.08, .95, gdo.meta.firsttime.strftime('%d/%m/%Y'),
                                                        transform=ax.transAxes)
    fig.legend(lines, legends, numpoints=1, markerscale=5, 
                           prop=matplotlib.text.FontProperties(size='smaller'))
    if fname:
        fig.savefig(fname)
    else:
        show()
