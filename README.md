# GPSData

GPSData is a Python package with classes and functions to store and manipulate
Global Navigation Satellite System (GNSS) observation data (such as time,
pseudoranges, phase, doppler, and signal-noise-ratio measurements).  It is
believed to work with Python versions 2.4, 2.5, or 2.6.

To date, its abilities are to store data from a RINEX observations file; later
it may grow the ability to read Novatel logs or NMEA.  It also reads Compact
(Hatanaka-compressed) RINEX observation files.

You can call the function `read_file(URL)`, in readfile.py, or from the command
line as `./readfile.py URL`.  It will read a RINEX or compressed RINEX file
from a local file or HTTP/FTP url; gzipped or tarballed files are extracted.

The following examples will reflect the fact that GPSData was developed at and
for usage in the Jicamarca Radio Observatory in Peru.

`read_file()` returns a list-like `GPSData` object, with an entry for each
record in the file (i.e., an entry per time epoch):

    >>> data = read_file('jica0970.09o')

`data[0]`, ..., `data[2851]` are dictionaries by PRN, e.g. `data[0]['G03']` or
`data[0]['G14']`; for GPS satellites, you can leave off the system code 'G',
e.g.  `data[0][3]` or `data[0][14]`.  The contents are dictionaries by
observation type.  `data[0][14]['C1']` is the pseudorange measurement on the
civilian channel of L1 for PRN 14 in record 0.

    >>> data[0][14]
    {'C1': 89633541.835999995,
     'L1': 471027535.35000002,
     'L2': 367034476.91900003,
     'P2': 89633549.144999996,
     'S1': 47.564999999999998,
     'S2': 41.023000000000003}

Rinex observation codes are:  
C1, C2, C5 - unencrypted code (pseudorange) on L1, L2, L5.  
P1, P2 - encrypted code.  
L1, L2, L5 - carrier phase.  
D1, D2, D5 - Doppler.  
S1, S2, S5 - signal strength.  
For Galileo, [CLDS][786] are also possible.

Extra information is available as flags, such as "strength" (a value from 0-10
optionally appended to measurements in RINEX):

    >>> data[0][14]['L1']
    471027535.35000002
    >>> data[0][14]['L1'].strength
    8

Custom iterables can be built with `data.iterlist()` or `data.iterdict()`.
These have the same interface, but different return types.

```python
for b in data.iterlist(sat='G12'):
    # b is a list of the observations for G12 in this record.
    # You should know what the observation types are.
    # If an observation isn't available for this sat/this record,
    # None is substituted.
for b in data.iterdict(obscode='L1'):
    # b is a dict of {'G2': value, 'G13': value}, etc, for all the satellites 
    # with an 'L1' observation.
```

All the header information is in data.meta, as a dictionary:

    >>> data.meta['marker']
    {0: 'jica'}

The "marker" record is a dictionary by record number since it can change over
the course of the file.

The meta dictionary does silly tricks:

    >>> data.meta.marker
    {0: 'jica'}

The marker dictionary also does silly tricks:

    >>> data.meta.marker[35]
    'jica'

(Using a record number as key returns the marker name which was in effect
at that record.  This also works for other changeable header information.)

Functions are included which calculate the (uncalibrated slant) TEC from the GPS
readings, assuming they are from a dual-frequency receiver, by fitting the
(smooth, inaccurate) phase-derived TEC to the (noisy, accurate) code-derived
TEC over each phase-connected arc.  This is included as an additional
observation for the satellites, called 'TEC'.
plotter.py is a module to plot this TEC (or any observation parameter) using
`matplotlib`.
Images can be generated from the command line:

    $ ./readfile.py -i TEC -o tec_090527.png jica_090527.09d.tar.gz

To do the same in Python:

```python
from gpsdata import readfile, plotter
gdo = readfile.read_file('jica_090527.09d.tar.gz')
plotter.plot(gdo, 'TEC', 'tec_090527.png')
```

stations.dat is a Jicamarca-specific data file, simply allowing the plotter to
substitute full place names for the location codes used as "marker" tags.

There is a `gpstime` module which has GPS, TAI and UTC timezones for standard
Python datetimes, and a `gpsdatetime` class which inherits `datetime`, solely to
allow non-whole-minute offsets from UTC (which the standard module forbids for
no good reason).  The GPS and TAI timezones deal with leap seconds.
