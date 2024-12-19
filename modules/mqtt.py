#!/usr/bin/python3
# -*- coding: utf-8 -*-
""" MQTT daemon

Uses the MQTT server (e.g. mosquitto) to bridge the Tibber Pulse topic so that the daemon can "work on a stick"
by reading the "right" topic and publish into the refleced topic that will end up att Tibber

- requires the jailbreak from https://github.com/MSkjel/LocalPulse2Tibber to get the certificates and the topics
  which contains the ID of the pulse unit
- the ID for state report is essentially the MAC connecting to the wifi (or the string reported in the jailbreak process
  above)

"""
__author__ = "Zacharias El Banna"
__version__ = "1.0.0"
__all__ = ['mqtt']
from modules.hdlc import HDLC
from paho.mqtt import client as mqtt_client
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
from random import randint
from time import localtime, strftime, sleep
from json import loads, dumps
from sys import exit, stderr

############################################## MQTT ##################################################
#
# TODO: Modify to use TLS/SSL instead of 1883 and non-tunneled and add second client for publish :-)
# 
#

def mqtt(aHdlc: HDLC, **kwargs):
  #aUsername: str, aPassword: str, aBroker: str, aPort: int, aSub: str):
 ''' MQTT:
  - Monitor MQTT and resend data in byte format to tibber using the MQTT bridge
  - Recreate 10second info -> send as binary
  - Recrete hourly update ->  send as binary
  - Recreate device status and send similar to AMS, but maybe should be every other minute device updates

  Start by defining some defaults:
 '''
 FIRST_RECONNECT_DELAY = 1
 RECONNECT_RATE = 2
 MAX_RECONNECT_COUNT = 12
 MAX_RECONNECT_DELAY = 60

 #
 def on_connect(client, userdata, flags, rc, properties):
  ''' On Connect: Debug output for standard connection results '''
  # For paho-mqtt 2.0.0, you need to add the properties parameter.
  # def on_connect(client, userdata, flags, rc, properties):
  if rc == 0:
   stderr.write(f"mqtt_connect: Connected to MQTT Broker ({properties})!\n")
  else:
   stderr.write(f"mqtt_connect: Failed to connect, return code {rc}\n")

 #
 def on_disconnect(client, userdata, rc):
  ''' On Disconnect: defines behavior when disconnecting the MQTT server, i.e. reconnection properties '''
  stderr.write(f"mqtt_disconnect: Disconnected with result code: {rc}\n")
  reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
  while reconnect_count < MAX_RECONNECT_COUNT:
   stderr.write(f"mqtt_disconnect: Reconnecting in {reconnect_delay} seconds...\n")
   sleep(reconnect_delay)
   try:
    client.reconnect()
    stderr.write(f"mqtt_disconnect: Reconnected successfully!\n")
    return
   except Exception as err:
    stderr.write(f"mqtt_disconnect: {str(err)}. Reconnect failed. Retrying...\n")
   reconnect_delay *= RECONNECT_RATE
   reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
   reconnect_count += 1
  stderr.write(f"mqtt_disconnect: Reconnect failed after {reconnect_count} attempts. Exiting...\n")
  exit(1)

 #
 def on_publish(client, userdata, mid):
  ''' On Publish: used for debugging '''
  stderr.write(f"mqtt_publish: {userdata} {mid}\n")

 #
 def on_ams_message(client, userdata, msg, properties = None):
  ''' On Message: subscribe to AMS reader messages and reformat into Tibber Pulse '''
  try:
   # stderr.write(f"Payload: {msg.payload.decode()} from {msg.topic}\n")
   topic = msg.topic.rpartition('/')[2]
   payload = msg.payload.decode()
   if topic == 'power' or topic == 'energy':
    date = aHdlc.create_datetime(adjust = topic)
    if aHdlc.check_datetime(topic,date):
     parsed = aHdlc.load_msg(loads(payload), topic, date)
     output = aHdlc.create_frame(parsed,date)
     #stderr.write(f"{strftime('%Y-%m-%d %H:%M:%S', localtime())}: {topic} : {output.hex().upper()}\n")
     client.publish(topic_publish.format(topic),output,2,properties=properties);
    else:
     pass
     #stderr.write(f"{strftime('%Y-%m-%d %H:%M:%S', localtime())}: {topic} : DUPLICATE TIME\n")
   elif topic == 'state':
    output = dumps(aHdlc.create_state(loads(payload)))
    #stderr.write(f"{strftime('%Y-%m-%d %H:%M:%S', localtime())}: state : {output}\n")
    client.publish(topic_publish.format(topic),output,2,properties=properties);
   elif topic == 'realtime' or topic == 'prices':
    pass
   elif topic == 'status':
    stderr.write(f"{strftime('%Y-%m-%d %H:%M:%S', localtime())}: status : `{payload}`\n")
    pass
   else:
    stderr.write(f"{strftime('%Y-%m-%d %H:%M:%S', localtime())}: `{payload}` from `{msg.topic}` topic\n")
  except Exception as e:
   stderr.write(f"{strftime('%Y-%m-%d %H:%M:%S', localtime())}: ERROR:{str(e)} for `{msg.payload.hex().upper()}` from `{msg.topic}` topic\n")

 ################################# Start Client #################################
 # Set Connecting Client ID
 client = mqtt_client.Client(client_id = f'ams2tibber-{randint(0, 1000)}', protocol=mqtt_client.MQTTv5 )
 # For paho-mqtt 2.0.0, you need to set callback_api_version.
 # client = mqtt_client.Client(client_id=client_id, callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)
 client.username_pw_set(kwargs['mqtt_username'], kwargs['mqtt_password'])
 client.on_connect = on_connect
 client.on_disconnect = on_disconnect
 client.on_message = on_ams_message
 # client.on_publish = on_publish
 client.connect(kwargs['mqtt_broker'], port = kwargs['mqtt_port'], clean_start = mqtt_client.MQTT_CLEAN_START_FIRST_ONLY)
 client.subscribe(f"{kwargs['mqtt_ams_sub']}/#")
 client.subscribe(f"{kwargs['mqtt_tibber_sub']}")
 topic_publish = f"{kwargs['mqtt_tibber_pub']}"
 # topic_publish = "debug/{}"
 properties=Properties(PacketTypes.PUBLISH)
 properties.MessageExpiryInterval=30 # in seconds
 return client
