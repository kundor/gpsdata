'''Miscellaneous classes which are of use in gpsdata, particularly in rinex.py.

These are not very specific in usage, however, and could be useful anywhere.

'''
from contextlib import suppress, redirect_stdout, contextmanager
import subprocess
import os

@contextmanager
def stdouttofile(file):
    """A decorator to redirect stdout within a function to the given filename."""
    with open(file, 'a') as f, redirect_stdout(f):
        yield

def decompress(filename, move=False):
    """Decompress a (Lempel-Ziv) compress'd file.

    There seems to be no Python module to do this (the gzip module won't handle it,
    though the gzip program will), so we call an external process.
    These programs will only decompress if the filename ends with .Z;
    they remove the original file and output a file without the .Z.
    """
# However, given the -c flag, these programs will decompress to stdout, even if the filename
#  does not end with .Z.
    if not filename.endswith('.Z'):
        if move:
            defile = filename
            filename = filename + '.Z'
            os.rename(defile, filename)
        else:
            raise ValueError('Given filename ' + filename + ' does not end with .Z.')
    else:
        defile = filename[:-2]
    decompresscmds = [['compress', '-d', filename],
                      ['uncompress', filename],
                      ['gunzip', filename],
                      ['gzip', '-d', filename]]
    for cmd in decompresscmds:
        try:
            subprocess.run(cmd, check=True)
        except (OSError, subprocess.CalledProcessError):
            print("Command '", ' '.join(cmd), "' failed. Trying another...")
            continue
        if os.path.isfile(defile):
            return defile
        else:
            print("Command '", ' '.join(cmd), "' succeeded, but did not produce the output file?!")
    raise RuntimeError('Could not get an external program to decompress the file ' + filename)

typedict = {}
# Declaring classes is really slow, so we reuse them.

def value(thing, **kwargs):
    '''Ensure that arbitrary attributes can be set on `thing'.

    E.g. foo = value(foo); foo.bar = 'qux'
    '''
    if hasattr(thing, '__dict__'):
        pass
    elif type(thing) in typedict:
        thing = typedict[type(thing)](thing)
    else:
        class thething(type(thing)):
            pass
        typedict[type(thing)] = thething
        thing = thething(thing)
    thing.__dict__.update(kwargs)
    return thing


class listvalue(dict):
    '''
    Store values as specified in a RINEX header which have validity
    for a range of records, but may be replaced.
    Allows accessing by record number, eg marker[456] returns
    the marker information which was valid for record 456.
    For convenience, listvalue[0] always returns the first definition
    and listvalue[-1] always returns the last.
    '''
    def __getitem__(self, index):
        if index == 0:
            index = min(self)
        elif index == -1:
            index = max(self)
        else:
            index = max([k for k in self if k <= index])
        return dict.__getitem__(self, index)

    def __contains__(self, index):
        if index in (0, -1):
            return True
        return isinstance(index, (int, float)) and index > 0


class metadict(dict):
    '''A dictionary for RINEX header values.
    Add a `numblocks' property (for the number of discontiguous header blocks)
    and field access for meta['name'] by meta.name.
    '''
    def __init__(self, *args, **kwargs):
        self.numblocks = 0
        dict.__init__(self, *args, **kwargs)

    def __getattr__(self, name):
        if not name in self:
            raise AttributeError()
        return self[name]


class fileread(object):
    '''
    Wrap "sufficiently file-like objects" (ie those with readline())
    in an iterable which counts line numbers, strips newlines, and raises
    StopIteration at EOF.
    '''
    def __new__(cls, file):
        '''Create a fileread object.

        Input can be filename string, file descriptor number, or any object
        with `readline'.
        '''
        if isinstance(file, fileread):
            file.reset()
            return file
        fr = object.__new__(cls)
        if isinstance(file, str):
            fr.fid = open(file)
            fr.name = file
        elif isinstance(file, int):
            fr.fid = os.fdopen(file)
            fr.name = "FD: " + str(file)
        elif hasattr(file, 'readline'):
            fr.fid = file
            if hasattr(file, 'name'):
                fr.name = file.name
            elif hasattr(file, 'url'):
                fr.name = file.url
        else:
            raise ValueError("Input of type " + str(type(file)) +
                             " is not supported.")
        fr.reset()
        return fr

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def next(self):
        '''Return the next line, also incrementing `lineno'.'''
        line = self.fid.readline()
        if not line:
            raise StopIteration()
        self.lineno += 1
        return line.rstrip('\r\n')

    __next__ = next

    def readline(self):
        '''A synonym for next() which doesn't strip newlines or raise StopIteration.'''
        line = self.fid.readline()
        if line:
            self.lineno += 1
        return line

    def __iter__(self):
        return self

    def reset(self):
        '''Go back to the beginning if possible. Set lineno to 0 regardless.'''
        if hasattr(self.fid, 'seek'):
            with suppress(OSError):
                self.fid.seek(0)
        self.lineno = 0

    def close(self):
        '''Close the file.  A closed file cannot be used for further I/O.'''
        if hasattr(self.fid, 'fileno') and self.fid.fileno() < 3:
            # Closing stdin, stdout, stderr can be bad
            return
        if hasattr(self.fid, 'close'):
            with suppress(OSError, EOFError):
                self.fid.close()
        elif hasattr(self.fid, 'quit'):
            with suppress(OSError, EOFError):
                self.fid.quit()


