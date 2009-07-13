# Ported from CRX2RNX 4.0.3
# (Yuki HATANAKA, Geographical Survey Institute, Japan, 2007.06.21)
# Created by Nick Matteo <kundor@kundor.org> June 10, 2009

import re
import subprocess
from os import path, access, W_OK, fdopen
from tempfile import mkstemp

CR_VER = '1.0'

def crx2rnx(fid):
    '''
    Convert Compact RINEX Format (version ''' + CR_VER + ''')
    observation file back to standard RINEX, writing file 
    (with extension changed from .##d to .##O)
    to same directory as source file, or (if that file exists or is unwritable)
    to the current directory, or to a temporary file.

    Ported from CRX2RNX (Yuki HATANAKA) .

    '''
    newfile = re.sub('[dD]$', 'O', fid.name)
    dir = path.dirname(path.abspath(newfile))
    if path.lexists(newfile) or not access(dir, W_OK):
        newfile = path.basename(newfile)
    if path.lexists(newfile) or not access(path.curdir, W_OK):
        (ofid, newfile) = mkstemp(suffix=path.splitext(newfile)[1])
    else:
        ofid = open(newfile, 'w')
# TODO: translate to python
    crx = subprocess.Popen('./crx2rnx', stdin=subprocess.PIPE, stdout=ofid)
    crx.communicate(fid.read())
    crx.stdin.close()
    if isinstance(ofid, int):
        ofid = fdopen(ofid)
    elif isinstance(ofid, file):
        ofid.close()
        ofid = open(ofid.name)
    return ofid

