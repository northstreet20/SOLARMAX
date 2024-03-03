# This module provides low layer functions to access the solarmax MT inverter
import socket
from datetime import datetime
import json
import logging

SOLARMAX_DATE_FORMAT = "%m/%d/%Y, %H:%M:%S"


class sm13MT2:
    # this map contains all command codes (keys), a readable name (name) and a unit field (response_type)
    # unsupported and not wanted commands are recommended to be commented out
    # if the unit field is equal '', nothing will be done at decoding
    QUERY_MAP = {
        'SDAT': {'name': 'actual timestamp', 'response_type': 'datetime'},
        'FDAT': {'name': 'first timestamp', 'response_type': 'datetime'},
        'ADR': {'name': 'Address', 'response_type': ''},
        'TYP': {'name': 'Type', 'response_type': 1},
        'MAC': {'name': 'MAC Address', 'response_type': ''},

        'PIN': {'name': 'Installed Power (W)', 'response_type': 1},
        'SYS': {'name': 'System Status', 'response_type': ''},  # 4E28 = 17128
        'SAL': {'name': 'System Alarms', 'response_type': 1},
        'LAN': {'name': 'Language', 'response_type': 1},
        'SWV': {'name': 'Software Version', 'response_type': 1},
        'BDN': {'name': 'Build number', 'response_type': 1},
        'CAC': {'name': 'Start Ups', 'response_type': 1},

        'KDY': {'name': 'Energy today (kWh)', 'response_type': 0.1},
        # 'KDL': {'name': 'Energy yesterday (kWh)',  'response_type':0.1 },
        'KYR': {'name': 'Energy this year (kWh)', 'response_type': 1},
        'KLY': {'name': 'Energy last year (kWh)', 'response_type': 1},
        'KMT': {'name': 'Energy this month (kWh)', 'response_type': 1},
        'KLM': {'name': 'Energy last month (kWh)', 'response_type': 1},
        'KT0': {'name': 'Total Energy (kWh)', 'response_type': 1},
        'KHR': {'name': 'Operating Hours', 'response_type': 1},

        'PDC': {'name': 'DC Power (W)', 'response_type': 0.5},
        'PAC': {'name': 'AC Power (W)', 'response_type': 0.5},  # Watts * 2
        'PRL': {'name': 'Relative power (%)', 'response_type': 1},

        'TNF': {'name': 'Generated frequency (Hz)', 'response_type': 0.01},  # Hz  * 100
        'TKK': {'name': 'Inverter Temparature (C)', 'response_type': 1},  # inverter operating temp

        # 'UDC': {'name': 'dc_voltage', 'response_type':0.1 },           # DC voltage (V DC)  * 10
        # 'IDC': {'name': 'DC Current (A)',  'response_type':0.01 }, # A *100
        # 'TNP': {'name': 'Grid period duration', 'response_type':1 },
        'UL1': {'name': 'AC Voltage Phase 1 (V)', 'response_type': 0.1},  # Voltage * 10
        'UL2': {'name': 'AC Voltage Phase 2 (V)', 'response_type': 0.1},  # Voltage * 10
        'UL3': {'name': 'AC Voltage Phase 3 (V)', 'response_type': 0.1},  # Voltage * 10
        # 'U_L1L2': {'name': 'Phase1 to Phase2 Voltage (V)', 'response_type':0.1 }, # Voltage * 10
        # 'U_L2L3': {'name': 'Phase2 to Phase3 Voltage (V)', 'response_type':0.1 }, # Voltage * 10
        # 'U_L3L1': {'name': 'Phase3 to Phase1 Voltage (V)', 'response_type':0.1 }, # Voltage * 10
        'IL1': {'name': 'AC Current Phase 1 (A)', 'response_type': 0.01},
        'IL2': {'name': 'AC Current Phase 2 (A)', 'response_type': 0.01},
        'IL3': {'name': 'AC Current Phase 3 (A)', 'response_type': 0.01},
        # 'F_AC':{'name': 'Grid Frequency', 'response_type':1 },
        'UD01': {'name': 'String 1 Voltage (V)', 'response_type': 0.1},
        'UD02': {'name': 'String 2 Voltage (V)', 'response_type': 0.1},
        'UD03': {'name': 'String 3 Voltage (V)', 'response_type': 0.1},
        'ID01': {'name': 'String 1 Current (A)', 'response_type': 0.01},
        'ID02': {'name': 'String 2 Current (A)', 'response_type': 0.01},
        'ID03': {'name': 'String 3 Current (A)', 'response_type': 0.01},
        'DIN': {'name': 'DIN', 'response_type': ''},

        # 'DDY': {'name': 'Date day', 'response_type':''},
        # 'DMT': {'name': 'Date month', 'response_type':''},
        # 'DYR': {'name': 'Date year', 'response_type':''},
        # 'THR': {'name': 'Time hours','response_type':''},
        # 'TMI': {'name': 'Time minutes','response_type':''},
        # 'SE1':  {'name':'SE1', 'response_type':''},

        # 'U_AC': {'name':'U_AC','response_type':''}
    }

    ERROR_CODES = {
        'EC00': {'name': 'Error Code 0', 'response_type': ''},
        'EC01': {'name': 'Error Code 1', 'response_type': ''},
        'EC02': {'name': 'Error Code 2', 'response_type': ''},
        'EC03': {'name': 'Error Code 3', 'response_type': ''},
        'EC04': {'name': 'Error Code 4', 'response_type': ''},
        'EC05': {'name': 'Error Code 5', 'response_type': ''},
        'EC06': {'name': 'Error Code 6', 'response_type': ''},
        'EC07': {'name': 'Error Code 7', 'response_type': ''},
        'EC08': {'name': 'Error Code 8', 'response_type': ''}}

    MOMENTARIES = {
        'PDC', 'PAC', 'PRL', 'TNF', 'TKK', 'UL1', 'UL2', 'UL3', 'IL1', 'IL2', 'IL3', 'UD01', 'UD02', 'UD03',
        'ID01', 'ID02', 'ID03'}

    DAILYS = {
        'KDY'
    }


class communication:

    def __init__(self, ip, port, adr=1, maxc=20, device_type='sm13MT2', logger='__main__'):
        self.log = logging.getLogger(logger)
        self._ip = ip
        self._port = int(port)
        self._adr = adr
        self._devicetype = device_type
        self.response = ""
        self.decodeddata = {}
        self.decodeddata_last = {}
        self.commandmap = sm13MT2.QUERY_MAP.copy()
        self.maxcommands = maxc
        self._socket = None
        self._connected = False
        self._connect()
        self.log.debug('Communication socket to %s:%s initialized' % (ip, port))

    def __del__(self):
        self._disconnect()

    def getCommandList(self):
        return list(self.commandmap.keys())

    def getDeviceType(self):
        return self._devicetype

    def _chunkCommand(self, l, n):
        return [l[i:i + n] for i in range(0, len(l), n)]

    def _difflist(self, li1, li2):
        li_dif = [i for i in li1 + li2 if i not in li1 or i not in li2]
        return li_dif

    # calculates the checksum: the checksum field is a standard 16-bit checksum over the body:
    #   the first character is the source address, the last character is the ‘|’ before the checksum
    def _calcChecksum(self, s):
        total = 0
        for c in s: total += ord(c)
        h = hex(total)[2:].upper()
        while len(h) < 4: h = '0' + h
        return h

    def _validateChecksum(self, s):
        if len(s) < 5:
            return False  # msg to short, return false
        pl = s[1:-5]
        cs = s[-5:-1]
        newcs = self._calcChecksum(pl)
        if cs == newcs:
            return True
        else:
            return False

    def _decodeDateTime(self, s):
        (date, time) = s.split(',')
        time = int(time, 16)
        year = int(date[:3], 16)
        month = int(date[3:5], 16)
        day = int(date[5:], 16)
        hour = int(time / 3600)
        minute = int((time % 3600) / 60)
        second = int((time % 60))

        return datetime(year, month, day, hour, minute, second)

    def getResponsePayload(self):
        if len(self.response) > 5:
            return self.response[1:-6]
        else:
            return ""

    # generate a message, each message has the following format
    #  ‘{‘ : start of message indicator
    #   2 characters source address in hex
    #   ‘;’
    #   2 characters destination address in hex
    #   ‘;’
    #   2 characters message length in hex
    #   ‘|64:’
    #   data
    #   ‘|’
    #   4 characters checksum in hex
    #   ‘}’ : end of message indicator  
    def _encodeRequest(self, commandlist):

        SOURCE_ADR = u'FB' + ';'
        DEST_ADR = u'01' + ';'

        # calculate msg len
        f = lambda x: str(hex(sum([len(i) for i in x]) + (len(x) - 1) * 1 + 19)[2:]).upper()
        msg_length = f(commandlist)

        msg = u'{' + SOURCE_ADR + DEST_ADR + msg_length + u'|64:'

        # add data
        for i in commandlist:
            msg += i + u';'

        # replace last ';'   by '‘|’'
        msg = msg[0:len(msg) - 1] + u'|'

        # add checksum
        msg = msg + self._calcChecksum(msg[1:len(msg)])

        msg += u'}'

        return msg.encode('UTF8')

    def _connect(self):
        self._disconnect()
        self.log.debug('try to connect %s:%i ...' % (self._ip, self._port))
        try:
            self._socket = socket.create_connection((self._ip, self._port), 5)
            self._connected = True
            self.log.debug('connected to %s:%i ok' % (self._ip, self._port))
        except socket.error as msg:
            self.log.debug("connection failed: " + str(msg))
            self._connected = False

    def _disconnect(self):
        try:
            # DEBUG('Closing open connection to %s:%s...' % (self._ip, self._port))
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            del self.__socket
        except:
            pass
        finally:
            self._connected = False
            self._socket = None

    def _decode(self, data):
        asDict = {}

        try:
            asArray = data[:-6].split(':')[1].split(';')
        except:
            self.log.error('decoding failed, bad data format: %s' % (data))
            return {}

        for i in range(0, len(asArray)):
            try:
                key = asArray[i].split("=")[0]
                val = asArray[i].split("=")[1]
                rt = self.commandmap[key]['response_type']
                name = self.commandmap[key]['name']
                if rt == 'datetime':
                    # asDict[key]={'value' : self._decodeDateTime(val), 'description': name, }
                    asDict[key] = {'value': self._decodeDateTime(val).strftime(SOLARMAX_DATE_FORMAT),
                                   'description': name, }
                    # strftime("%m/%d/%Y, %H:%M:%S")
                elif rt == '':
                    asDict[key] = {'value': val, 'description': name, }
                else:
                    asDict[key] = {'value': round(float(int(val, 16)) * rt, 3), 'description': name, }
            except:
                pass

        return asDict

    def _send(self, s):
        try:
            self._socket.send(s)
        except socket.timeout:
            self.log.warning('sending timeout %s:%i' % (self._ip, self._port))
            self._connected = False
        except socket.error:
            self.log.error('sending socket error %s:%i' % (self._ip, self._port))
            self._connected = False

    def _receive(self):
        resp = b''
        try:
            buf = self._socket.recv(2048)
            if len(buf) > 0:
                resp = resp + buf
                self.response = resp.decode('utf8')
                return self.response
            else:
                return ""
        except:
            self.log.error('receive error')
            return ""

    def _subquery(self, commandlist):

        if not self._connected:
            self.log.debug('query not sent - no connection')
            return False

        # encode command and send query
        self._send(self._encodeRequest(commandlist))

        # receive data
        self.response = self._receive()

        # DEBUG(self.response)

        # validate checksum and append to decoded data
        if self._validateChecksum(self.response):
            status = True
            if self.decodeddata == {}:
                self.log.debug('receive ok (1)')
            else:
                self.log.debug('receive ok (2)')
            self.decodeddata.update(self._decode(self.response))

        else:
            self.log.error('bad receive checksum')
            status = False

        return status

    def query(self, commandlist):

        # clear decoded data buffer (and save last)
        self.decodeddata_last = self.decodeddata.copy()
        self.decodeddata = {}

        # split command into chunks because solarmax respond to max 20 commands at once
        cmdchunks = self._chunkCommand(commandlist, self.maxcommands)

        # now, call for data
        for cmds in cmdchunks:
            status = self._subquery(cmds)
            if not status:
                return False

        delta = self._difflist(commandlist, list(self.decodeddata.keys()))
        if len(delta) > 0:
            self.log.warning('unsupported params', delta)

        return status

    def getDataAsJson(self):
        return json.dumps(self.decodeddata, sort_keys=True)  # convert string to json
