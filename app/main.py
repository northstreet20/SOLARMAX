#!/usr/bin/env python
# coding: utf-8

# project modules
from datalogger import dataLogger
import sys, os, time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import threading
import configparser, argparse
import paho.mqtt.client as paho
import json

# Global variable
signal = None
lock = threading.Lock()


# main threads
def thread_logger(config):
    global signal
    # create instance of datalogger
    logger = dataLogger(config=config)
    while True:
        _signal = logger.logData()
        with lock:
            signal = _signal.value
        time.sleep(logger.waiting_time)


# a watch dog thread to see if still alive
def thread_heartbeat(config):
    heart_beat_seconds = int(config['GENERAL']['HeartBeatSeconds'])
    client = paho.Client("solarmax1")  # create client object
    slog = logging.getLogger("__main__")
    slog.debug('start heartbeat with interval=%d seconds' % heart_beat_seconds)
    start = datetime.now()
    _topic_base = f"{config['MQTT']['TopicPrefix']}-system"
    _msg = {'last_start': datetime.timestamp(start) * 1000, 'period': heart_beat_seconds,}
    i = 0

    while True:
        i = i + 1
        client.connect(host=config['MQTT']['BrokerHostUri'], port=int(conf['MQTT']['Port']))  # establish mqtt connection
        _msg['current_state'] = signal
        _msg['timestamp'] = datetime.timestamp(datetime.now())*1000
        client.publish(f"{_topic_base}/heartbeat", json.dumps(_msg))  # publish mqtt
        time.sleep(heart_beat_seconds)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Personal information')
    parser.add_argument('--config', dest='configfile', type=str, help='path of configfile', default="./solarmax.cfg")
    args = parser.parse_args()
    print(f"default environment is: working-directory={os.getcwd()}, configfile={args.configfile}")

    # check if config file is there, otherwise copy from default
    if not os.path.isfile(args.configfile):
        print("config file not found, copy from ./app/default.cfg ..", end=".")
        cmd = 'cp ./app/default.cfg ' + args.configfile
        os.popen(cmd)
        time.sleep(2)
        print('ok')

    # read config file and store to global conf var
    conf = configparser.ConfigParser()
    conf.sections()
    if conf.read(args.configfile) == []:
        sys.exit('Error: Missing Config File ' + args.configfile)
    else:
        print("configuration loaded successfully")
        print(" * syslogfile -> %s" % conf['GENERAL']['SysLogFile'])

    print("Start logging into syslog file")

    file_handler = logging.handlers.RotatingFileHandler(
        conf['GENERAL']['SysLogFile'],
        maxBytes=int(conf['GENERAL']['MaxSysLogFileSizeMB'])*1024*1024,
        backupCount=5)

    stdout_handler = logging.StreamHandler(sys.stdout)
    handlers = [file_handler, stdout_handler]

    logging.basicConfig(
        level=int(conf['GENERAL']['LogLevel']),
        format='%(asctime)s %(levelname)s %(module)s/%(funcName)s: %(message)s',
        handlers=handlers
        )

    # rollover syslogfile at startup
    if conf['GENERAL']['RollOverSysLogAtEachStartup'] == 'True':
        file_handler.doRollover()

    sl = logging.getLogger(__name__)

    # initialize and start logger thread
    t_log = threading.Thread(target=thread_logger, args=(conf,))
    sl.info(f"start logger thread")
    t_log.start()

    # initialize and start heartbeat thread
    t_hb = threading.Thread(target=thread_heartbeat, args=(conf,))
    sl.info(f"start heartbeat thread")
    t_hb.start()

