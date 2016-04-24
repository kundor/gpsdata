- Was losing track of header interval information
  - Also, turn parser-computed intervals into floats (from timedeltas)
    for proper comparison with the interval read from the header
- We can't check for phase shift vs. the previous record if there was no 
  measurement for this satellite in the previous record!
- Accept .z or .Z endings for gzipped files
- Remove numpy dependency (replace `sum(X)` by `reduce(add, X)`)

## Version 0.4.3, August 27 2009 ##
- Use `''.ljust()` to pad to 80 spaces instead of formatting operation
- Disable command-line option "-p" for pickling, since it's broken.
- Added unused "line" argument to `gpsdata.showwarn()` to avoid Python 2.6
  warning
- Added README
- If matplotlib is not available, disable the "-i" plotting option in
  readfile.py command-line usage, rather than crashing (which also 
  prevented in-Python usage of `read_file()`)

## Version 0.4.2, August 5 2009 ##
- Was misreading years with all four digits present
- Wow, backticks are better than `str()`!
- Changes to operate with mod_python (Juan Carlos Espinoza):
  - Added `readfile.index()` function
  - Special behaviour in `plotter.plot` if `fname == 'web'`
- Python 2.4 compatibility:
  - Remove `str.rpartition()` in `readfile`
  - Remove try-except-finally in `gpstime`
  - Remove conditionals (x if foo else y)
  - Replace `datetime.strptime` with `time.strptime` in `gpstime`
  - Remove epilog from readfile OptionParser (wasn't up to date anyway)
  - Add `rinex.header.field.__deepcopy__` (2.4 barfed on function references)
- Remove `plotter.MarkerNames` class, just leave in the module
  (I am too class-crazy)
- Add `plotter.colorplot()` to plot lines with meaningfully colored dots
- Make system-determined leap seconds ints, not timedeltas (so that
  comparison with header-derived leap seconds is not bogus)
- Record filename in metadata, report in header summary

## Version 0.4.1, August 2 2009 ##
- Read marker name -> location title information from stations.dat
  (also contains station coordinates, potentially useful elsewhere)
- Command line: When specifying `--image` without `--output`,
  - We were calling `plot()` with a nonexistent variable
  - We were using `fig.show()` for display, which is not in all `matplotlib` backends
    (replaced by `matplotlib.pyplot.show()`)

## Version 0.4, August 1 2009 ##
- Create plotter.py module with function, `plot()`, to plot a given
  observation for all satellites, outputting to given filename
  (extension determines format) (using matplotlib)
- Split `gpsdata.iter()` to `gpsdata.iterdict()` and `gpsdata.iterlist()`
- Eliminate `gpsdata.iterepochs()` in favor of `gpsdata.iterlist('epoch')`
  or `gpsdata.iterdict('epoch')`
- Create utility.py module for "useful" classes that didn't belong in
  gpsdata or readfile:  value, listvalue, fileread so far
  - This fixes a recursive dependency problem in `import readfile`
- Comply PEP 8
  - Hence renamed package from GPSData to gpsdata
    - So main class is now `gpsdata.gpsdata.GPSData`
- Count number of header sections in RINEX file
- Track "phase connected arcs", ie periods between cycle slips, for
  each satellite.
  - New functions in gpsdata.GPSData: `breakphase`, `checkphase`, `sanearcs`
- RINEX: numrec in event flag 5 observation header indicates header lines
  following; process them.
  - Since "epoch is significant" for flag 5, mark these header values
    with the epoch.
  - While I'm at it, mark all header values with the record number
  and line number.
  - Also mark records between flag 2 (start moving) and flag 3 (stop) as
    "in motion."
- Correctly consume any PRN list continuation lines for event flag 6
  (Cycle Slip Records, which we ignore.)

## Version 0.3.1, July 21 2009 ##
- Fix operation for tarfiles (was using nonexistent `next()`):
  Introduce `readfile.fileread` class to wrap various file-like objects
- `record.ptec(prn)` returns (uncorrected, instantaneous, slant) phase TEC.
  `record.ctec(prn)` returns code TEC
- Include leap seconds, observation interval in header summary

## Version 0.3, July 20 2009 ##
- Don't crash on unknown format input files
- Output comments in header summary
- Fix bug in gpsdatetime vs. datetime equality comparison
- Check or supply leap seconds header info when a leap second occurs during
  the observations
- Nicer warning output
- Fix bug introduced since 0.2 in handling multiple files
- Implement Compact RINEX processing in rinex.py, remove crx2rnx
  (eliminates platform dependency on Linux x86)
- Rename GPSData.rnx to GPSData.meta in lame attempt to appear less
  RINEX-dependent
- Forgive incorrect spacing in RINEX header labels
- Split out readfile.py, added support for multiple formats
  (currently only RINEX available)
- Determine interval of observations (for comparison with header)
- `GPSData.sats()` returns set of satellite PRNs in this data
- `GPSData.iter()` allows iteration over a given satellite, observation code,
  or both; `GPSData.iterepochs()` iterates over record epochs
- Fix gpsdatetime unpickling
- Friendlier error for nonexistent files
- 2-digit years disambiguated correctly in absence of FIRST/LAST OBS
  (80-99 -> 1980-1999, 00-79 -> 2000-79)

## Version 0.2, July 15 2009 ##
- Use standard Python datetime for time data, not a home-grown struct
  - Correctly deal with GPS, GLONASS (UTC), Galileo (TAI) time systems
  - Include gpstime.py with useful time zones, leapseconds data
  - gpstime.gpsdatetime is a datetime class allowing UTC offsets which are
    not whole minutes
  - 2-digit years disambiguated by TIME OF FIRST/LAST OBS
- Command-line call to rinex.py outputs header info
- `rinex.get_data()` tracks some header stats and adds or verifies them

## Version 0.1, July 13 2009 ##
- Initial release
