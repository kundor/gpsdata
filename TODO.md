- [ ] Warnings with filename
- [ ] Fix pickling
- [ ] Class-based RINEX system
 - [ ] More thorough header summary
 - [ ] Validator and generator functions, run on demand to check/create metadata
   (instead of calling `gpsdata.check()`)
 - [ ] More generic, e.g. 'format' with rinex prog/vers/etc info, &c
- [ ] Unit tests:
  exam, 0970, dtgz, disp plot, save plot, 2.4
- [ ] Support bz2 files in readfile
- [ ] Add leapseconds source: http://sopac.ucsd.edu/input/processing/gamit/tables/leap.sec
- [ ] Autodetect when records are full and perform phase-arc updates
- [ ] Downnload, apply satellite bias corrections
- [ ] Download satellite ephemerides, calculate elevation
