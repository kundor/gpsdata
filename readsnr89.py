import os
from utility import fileread

sitelocs = { 'vpr3' : (-1283634.1275, -4726427.8944, 4074798.0304) } # actually p041's location
class rec:
    pass

def rngcheck(word, name, mn, mx, length, line):
    val = int(word)
    if val < mn or val > mx or len(word) != length:
        raise ValueError(word + ' is not a valid ' + name + ' (in line "' + line + '")')
    return val

def fltcheck(word, name, mn, mx, line):
    val = float(word)
    if val < mn or val > mx or len(word) != length:
        raise ValueError(word + ' is not a valid ' + name + ' (in line "' + line + '")')
    return val

def getline(line):
    words = line.split()
    if len(words) != 7:
        raise ValueError(line + ' is not a valid snr89 record')
    r = rec()
    r.prn = rngcheck(words[0], 'PRN', 1, 32, 2, line)
    r.el = rngcheck(words[1], 'elevation', 0, 90, 2, line)
    r.az = rngcheck(words[2], 'azimuth', 0, 359, 3, line)
    r.sod = fltcheck(words[3], 'second of day', 0, 86400, line)
    zero = rngcheck(words[4], 'zero', 0, 0, 1, line)
    zero = rngcheck(words[5], 'zero', 0, 0, 1, line)
    r.snr = fltcheck(words[6], 'SNR', 0, 100, line)
    return r

def snr89file(dir, filename):
    doy = int(filename[4:7])
    yr = int(filename[9:11])
    fid = fileread(os.path.join(dir, filename))    
    return [getline(l) for l in fid]
