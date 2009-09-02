from twisted.protocols.basic import LineReceiver
import re


def parse_tracking_satus(status):
    """
    Parse channel tracking status information as described in Table 62 in 
    the OEM4 Family Firmware Version 2.310 Command and Log Reference provided
    by Novatel.

    """
    
    # the only bits we actually care about are 21 and 22, which will tell us
    # which channel we got this measurement from.
    return {'m_l' : 1 + ((status & 0x00600000) >> 21) }


class NovatelMessage(object):
    FieldNames = {
       'GPSEPHEM': ['eph_prn', 'eph_tow', 'eph_health', 
                'eph_iode1', 'eph_iode2', 'eph_week', 'eph_zweek', 'eph_toe', 
                'eph_semi_major', 'eph_motion_difference', 'eph_mean_anomaly',
                'eph_ecc', 'eph_perigee', 'eph_latitude_correction_cosine', 
                'eph_latitude_correction_sine', 'eph_orbit_radius_cosine',
                'eph_orbit_radius_sine', 'eph_inclination_cosine', 
                'eph_inclination_sine', 'eph_inclination', 
                'eph_inclination_rate', 'eph_right_ascension', 
                'eph_right_ascention_rate', 'eph_issue', 'eph_toc', 
                'eph_group_delay', 'eph_offset', 'eph_drift', 'eph_drift_rate', 
                None, 'eph_motion_difference'],
        'SATXYZ' : [ 'sp_prn_id', 'sp_x', 'sp_y', 'sp_z' ],
        'RANGE' : [ 'm_prn_id', None, 'm_pseudorange', 'm_pseudorange_stddev',
                'm_carrier_phase', 'm_carrier_phase_stddev', 'm_doppler',
                'm_signal_density', 'm_lock_age', parse_tracking_status ],
        'PSRXYZ' : [ None, None, 'pos_x', 'pos_y', 'pos_z', 'pos_x_stddev',
                'pos_y_stddev', 'pos_z_sttdev', None ],
    }

    def __init__(self, msgtype):
        self.msgtype = msgtype
        self.content = []

    def addContent(self, line):
        self.content.append(line)

    def generateDicts(self):
        try:
            names = NovatelMessage.FieldNames[self.msgtype]
        except KeyError:
            raise ValueError, "%s not yet understood." % self.msgtype
        out = []
        for c in content:
            cur = {}
            out.append(cur)
            for k,v in zip(names, c):
                try:
                    cur.update(k(v))
                except TypeError: # because 'k' won't always be callable...
                    if k:
                        cur[k] = v
        return out

class NovatelSerialProtocol(LineReceiver):
    def __init__(self):
        self.msg = None
        self.nlines = -1

    def lineReceived(self, line):
        print("Novatel said: %s" % line)
        line = re.subn(r'\[.*?\]', '', strip(line))
        splitline = re.split(r'\s+', line)
        if line.startswith('<'):
            if self.msg:
                if self.nlines == -1:
                    self.nlines = int(splitline[-1])
                else:
                    self.msg.addContent(splitline)
                    self.nlines -= 1
                    if self.nlines == 0:
                        try:
                            forwardEvent = callable(self.messageReceived)
                        except AttributeError:
                            forwardEvent = False
                        if forwardEvent:
                            self.messageReceived(self.msg)
                        self.msg = None
                        self.nlines = -1
            else:
                self.msg = NovatelMessage(splitline[0][1:])

    def sendCommand(self, command):
        self.transport.write(command + "\r\n")

