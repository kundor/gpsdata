'''
GPSData Package: Classes and utilities for GPS Observation data

The main thing provided is the class GPSData.gpsdata.GPSData, which stores
pseudoranges, phase, doppler, and SNR for a variety of satellites and
frequencies, as recorded by some receiver.
It is planned that this class will also contain ancillary data for these
observations, such as electron densities or TECs from other sources
(either vertical or per-satellite), satellite ephemerides to compute satellite
position at each epoch (either almanac, broadcast, or post-processed precise),
GPS Times (datetime objects) for each reading set, and meteorological data.
It will also eventually offer a position-solving method, taking into account
as much of this data as is available.

rinex.read_rinex() constructs a GPSData object from a RINEX observations file.

An IGRF (geomagnetic field model) calculator will be added, as will
read_nmea() and read_novatel().
'''
