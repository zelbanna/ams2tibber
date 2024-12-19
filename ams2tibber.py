#!/usr/bin/python3
# -*- coding: utf-8 -*-
""" MQTT/HDLC bridge daemon

Uses the MQTT server (e.g. mosquitto) to bridge the Tibber Pulse topic so that the daemon can "work on a stick"
by reading the "right" topic and publish into the refleced topic that will end up att Tibber

- requires the jailbreak from https://github.com/MSkjel/LocalPulse2Tibber to get the certificates and the topics
  which contains the ID of the pulse unit
- the ID for state report is essentially the MAC connecting to the wifi (or the string reported in the jailbreak process 
  above)

"""
__author__ = "Zacharias El Banna"
from modules.hdlc import HDLC
from modules.mqtt import mqtt
from argparse import ArgumentParser
from json import load
from sys import exit, stderr
from signal import signal, SIGTERM, SIGINT

###########################################################################################################

if __name__ == '__main__':
 ''' Main

  - Bootstrap process by loading config from arguments
  - Create HDLC handler
  - Start MQTT function and then loop message handler
 '''
 parser = ArgumentParser(prog='ams2tibber',description='AMSreader MQTT monitor to Kamstrup + Tibber Pulse HDLC Monitor and bridge')
 parser.add_argument('-c','--config', help = 'Config file',default = '/etc/ams2tibber/config.json', required=False)
 parser.add_argument('-d','--debug', help = 'Debug output', required = False, action='store_true')
 input = parser.parse_args()
 stderr.write(f'main: Starting\n')

 if not input.config:
  parser.print_help()
  stderr.write("main: No config file\n")
  exit(1)
 stderr.write(f"main: Opening config file {input.config}\n")

 try:
  with open(input.config,'r') as file:
   config = load(file)
 except:
  stderr.write(f"main: Error opening config file {input.config}\n")
  exit(1)
 ''' Setup HDLC converter, MQTT interface and signal handler '''

 def signal_handler(sig, frame):
  ''' Signal handler instantiate OS signalling mechanisms to override standard behavior '''
  if sig == SIGTERM or sig == SIGINT:
   stderr.write(f"main: Caught signal:{sig}\n")
   client.loop_stop()
   client.disconnect()
   client.close()
   exit(0)
  return True

 stderr.write(f"main: Installing signal handlers for SIGTERM, SIGINT\n")
 for sig in [SIGTERM,SIGINT]:
  signal(sig, signal_handler)
 hdlc = HDLC(**config)
 client = mqtt(hdlc, **config)
 client.loop_forever()
 exit(0)
