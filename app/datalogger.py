import json
from datetime import datetime
from solarmax import SOLARMAX_DATE_FORMAT, sm13MT2, communication
import logging
import paho.mqtt.client as paho
from enum import Enum


class loggerState(Enum):
    UNINITIALIZED = 1
    SLEEPING = 2
    LOGGING = 3
    LOGGING_LAST = 4


# this function overwrite the response values for momentary parameter to zero, this could be used for additional
# database entries after inverter goes down
def _forceZero(data: dict, clear_dailys=False, sdat_overwrite=None):
    logging.warning(f"forcing to zero, clear_dailies={clear_dailys}, sdat_overwrite={sdat_overwrite}")
    for key in data:
        if key in sm13MT2.MOMENTARIES:
            data[key]['value'] = float(0)

        if key in sm13MT2.DAILYS and clear_dailys:
            data[key]['value'] = float(0)

    if sdat_overwrite and 'SDAT' in data.keys():
        data['SDAT']['value'] = sdat_overwrite
    return data


class dataLogger:

    def __init__(self, config, log='__main__'):
        self.log = logging.getLogger(log)
        self.conf = config
        self.step_min = int(config['LOGGER']['LogStep'])
        self.step_max = int(config['LOGGER']['LogStepMax'])
        self.waiting_time = int(config['LOGGER']['LogStep'])
        self.data = dict()
        self.last_data = dict()
        self.force_last_to_zero = config['LOGGER']['ForceLastToZero'] == 'True'
        self.test_mode = config['LOGGER']['TestMode'] == 'True'

        self.inverter_ip = config['INVERTER']['IP']
        self.inverter_port = config['INVERTER']['Port']
        self.inverter_adr = config['INVERTER']['Address']

        self.mqtt_topic = config['MQTT']['TopicPrefix']
        self.mqtt_broker = self.conf['MQTT']['BrokerHostUri']
        self.mqtt_port = int(self.conf['MQTT']['Port'])
        self.mqtt_enable = config['MQTT']['Enable'] == 'True'
        self.count = 0
        self.logger_state = loggerState.UNINITIALIZED

        if config['LOGGER']['LogQueryList'] == 'All':
            self.commands = list(sm13MT2.QUERY_MAP.keys())
        else:
            self.commands = config['LOGGER']['LogQueryList'].split(',')

    def _sendToMQTT(self, topic: str, message: dict):
        if not self.mqtt_enable:
            return

        # message = json.loads(json.dumps(message, sort_keys=True))
        self.log.debug(f"send to mqtt broker {self.mqtt_broker}:{self.mqtt_port} "
                       f"topic={self.mqtt_topic} payload={message}")

        def on_publish(client, userdata, result):  # create function for callback
            # print("data published \n")
            pass

        _client = paho.Client("solarsmart")  # create client object
        _client.on_publish = on_publish  # assign function to callback
        _client.connect(self.mqtt_broker, self.mqtt_port)  # establish connection

        # _timestamp = jsn.get('SDAT').get('value')
        # _timestamp = datetime.strptime(_timestamp, "%m/%d/%Y, %H:%M:%S").timestamp()

        for key in message:
            datapoint = message.get(key)
            # datapoint['timestamp'] = _timestamp   # comment out this if extras ts element is desired
            _client.publish(f"{topic}/{key}", json.dumps(datapoint))  # publish
        return

    def _isNewDay(self, data, last_data):
        now = datetime.strptime(data['SDAT']['value'], SOLARMAX_DATE_FORMAT)
        if len(self.last_data) > 0:
            last = datetime.strptime(last_data['SDAT']['value'], SOLARMAX_DATE_FORMAT)
        else:
            self.log.info('last data still empty')
            last = now
        return now == last

    def _increase_waiting_time(self):
        self.waiting_time = self.waiting_time * 2
        if self.waiting_time > self.step_max:
            self.waiting_time = self.step_max  # limit waiting time

    def _reset_waiting_time(self):
        self.waiting_time = self.step_min

    def _test_mode(self, status):
        self.count += 1
        if self.count > 2:
            status = False
            self.log.info(f"TESTMODE, step {self.count} -> force status to {status}")
            if self.count > 5:
                self.count = 0
        else:
            self.log.info(f"TESTMODE, step {self.count} -> keep status ({status})")
        return status

    def _query(self, con):
        status = con.query(self.commands)

        if self.test_mode:
            status = self._test_mode(status)

        if status:
            self._reset_waiting_time()
            if not self.logger_state == loggerState.LOGGING:
                self.log.info(f"start logging (last state was: {self.logger_state})")
            self.logger_state = loggerState.LOGGING

        else:
            self._increase_waiting_time()
            self.log.info(f"no response from {con.getDeviceType()}, try again in {self.waiting_time} "
                             f"seconds (state is: {self.logger_state})")

            if self.logger_state == loggerState.LOGGING:
                self.log.warning(f"resend zero-forced last measurement (last state was: {self.logger_state})")
                self.logger_state = loggerState.LOGGING_LAST

            if self.logger_state == loggerState.UNINITIALIZED or self.logger_state == loggerState.LOGGING_LAST:
                self.log.warning(f"change to sleeping state (last state was: {self.logger_state})")
                self.logger_state = loggerState.SLEEPING

        return

    def logData(self):
        # establish connection
        con = communication(ip=self.inverter_ip, port=self.inverter_port, adr=self.inverter_adr)

        # make query and handle response
        self._query(con)

        # send data
        if self.logger_state == loggerState.LOGGING:
            msg = con.decodeddata
            msg['MOD'] = {'value': 0, 'description': 'non modified'}
            self._sendToMQTT(message=con.decodeddata, topic=f"{self.mqtt_topic}-{con.getDeviceType()}")
            # print(msg)

        elif self.logger_state == loggerState.LOGGING_LAST:
            msg = _forceZero(data=con.decodeddata_last, clear_dailys=False)
            msg['MOD'] = {'value': 1, 'description': 'momentaries forced to zero'}
            self._sendToMQTT(message=msg, topic=f"{self.mqtt_topic}-{con.getDeviceType()}")

        else:
            logging.debug('no response from inverter')

        return self.logger_state
