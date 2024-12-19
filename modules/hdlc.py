#!/usr/bin/python3
# -*- coding: utf-8 -*-
""" HDLC converter class """
__author__ = "Zacharias El Banna"
__version__ = "1.0.0"
__all__ = ['HDLC']
from random import randint
from time import localtime, strftime
from json import loads

################################################## HDLC ################################################
#
# TODO: Await timestamp within packet (!)
#
class HDLC:
 ''' HDLC class with proper methods to convert AMSreader data into Kamstrup OBIS format '''

 # Initialize METER and ADDRESSes
 def __init__(self, **kwargs):
  self._address = ((((kwargs.get('hdlc_target_address',21) << 1) | 1) << 8) | ((kwargs.get('hdlc_source_address',16) << 1) | 1))
  self._meter_list = kwargs['hdlc_meter_list']
  self._meter_id = kwargs['hdlc_meter_id']
  self._meter_type = kwargs['hdlc_meter_type']
  self._pulse_ip = kwargs['pulse_ip']
  self._pulse_id = kwargs['pulse_id']
  self._power = []
  self._energy = []
  self._prev = {'power':None,'energy':None} # store some old timestamps, and make sure we never send the same again (fixing the adjust to x0 issue)

 #
 def __str__(self):
  return f"{self._meter_list}, ID:{self._meter_id}, TYPE:{self._meter_type}, ADDRESS:{hex(self._address)}"

 ###################### Internal Functions ###################
 #
 def _crc16(self,aData: bytes, aPoly=0x8408):
  ''' CRC-16-CCITT Algorithm '''
  data = bytearray(aData)
  crc = 0xFFFF
  for b in data:
   cur_byte = 0xFF & b
   for _ in range(0, 8):
    if (crc & 0x0001) ^ (cur_byte & 0x0001):
     crc = (crc >> 1) ^ aPoly
    else:
     crc >>= 1
    cur_byte >>= 1
  crc = (~crc & 0xFFFF)
  crc = (crc << 8) | ((crc >> 8) & 0xFF)
  return crc & 0xFFFF

 #
 def _parse_entry(self, aDT, aValue):
  ''' Entry parsing, checking datatype and encode the right sized array '''
  tp = int(aDT,16)
  ret = bytearray([tp])
  if tp == 6: # Uint32
   val = aValue.to_bytes(4)
  elif tp == 18: # Uint16
   val = aValue.to_bytes(2)
  elif tp == 10: # Ascii string, encode
   val = aValue.encode()
   ret.append(len(val))
  elif tp == 9: # Octet string, straight copy with size
   val = bytearray.fromhex(aValue)
   ret.append(len(val))
  ret.extend(val)
  return ret

 ##################### Exposed Functions #####################
 #
 def load_sample_file(self, aFile):
  ''' Load sample file to verify result against https://www.gurux.fi/GuruxDLMSTranslator '''
  with open(aFile) as f:
   line = f.read().replace('\n', '')
  return loads(line)

 #
 def create_datetime(self, **kwargs):
  ''' For lack of better way to create a DLMS datetime octet string...

    - Either use a preconfigured string: 'date' or use localtime and possibly
    - Adjust time stamp accordingly

  '''
  date = strftime('%Y-%m-%d-%w-%H-%M-%S', localtime()).split('-') if not kwargs.get('date') else kwargs['date'].split('-')
  if kwargs.get('adjust'):
   if kwargs['adjust'] == 'power':
    date[6] = f"{date[6][0]}0"
   else:
    date[5] = "00"
    date[6] = "55"
  ret = bytearray(int(date[0]).to_bytes(2)) # Year
  for x in range (1,7):  # Month, Day, DoW, Hour, Min, Sec
   ret.append(int(date[x]))
  ret.extend(b'\xff\x80\x00\x00') # Ctrl, UTC?
  return ret

 def check_datetime(self, aTopic: str, aDatetime: bytes):
  ''' Check if this datetime has been sent for topic '''
  if self._prev[aTopic] == aDatetime:
   return False
  else:
   self._prev[aTopic] = aDatetime
   return True

 #
 def load_msg(self, aMessage: dict, aTopic: str, aDateTime: bytes = None):
  ''' Main message creator, parse the AMS reader dictionary and push relevant OBIS entries '''
  if aTopic == 'power':
   self._power = [
    ("0A",self._meter_list),
    ("09","0101000005FF"),("0A",self._meter_id),
    ("09","0101600101FF"),("0A",self._meter_type),
    ("09","0101010700FF"),("06", aMessage['P']),
    ("09","0101020700FF"),("06", aMessage['PO']),
    ("09","0101030700FF"),("06", aMessage['Q']),
    ("09","0101040700FF"),("06", aMessage['QO']),
    ("09","01011F0700FF"),("06", int(aMessage['I1']*100)),
    ("09","0101330700FF"),("06", int(aMessage['I2']*100)),
    ("09","0101470700FF"),("06", int(aMessage['I3']*100)),
    ("09","0101200700FF"),("12", int(aMessage['U1'])),
    ("09","0101340700FF"),("12", int(aMessage['U2'])),
    ("09","0101480700FF"),("12", int(aMessage['U3']))
   ]
   parsed = self._power
  elif aTopic == 'energy':
   self._energy = self._power.copy() # Copy, don't use reference/ptr.
   self._energy.extend([
    ("09","0001010000FF"),("09",aDateTime.hex()),
    ("09","0101010800FF"),("06",int(aMessage['tPI']*1000)),
    ("09","0101020800FF"),("06",int(aMessage['tPO']*1000)),
    ("09","0101030800FF"),("06",int(aMessage['tQI']*1000)),
    ("09","0101040800FF"),("06",int(aMessage['tQO']*1000))
   ])
   parsed = self._energy
  return parsed

 #
 def create_frame(self, aEntries: list, aDate: bytearray):
  ''' Create HDLC frame from OBIS entries and Date  '''
  frame = bytearray([0x7E,0,0]) # HDLC, space for A frame format type and for 12 bit length
  frame.extend(self._address.to_bytes(2)) # Preencoded TA and SA
  frame.append(19) # Ctrl field "13"
  frame.extend([0,0]) # Position for HCS
  frame.extend([0xE6,0xE7,0,0xF])  # E6 E7 00 0F
  frame.extend([0,0,0,0]) # LongInvokeIdAndPriority = 00 00 00 00
  frame.append(12) # 12 bytes datetime octet string following
  frame.extend(aDate)
  # Struct
  frame.extend([2,len(aEntries)]) # Struct / dataType 2, with x entries
  for vals in aEntries:
   frame.extend(self._parse_entry(*vals))
  frame.extend([0,0,0x7E])
  frame[1:3] = (40960 + len(frame)-2).to_bytes(2) # A0 + length minus HDLC enclosure
  frame[6:8] = self._crc16(frame[1:6]).to_bytes(2) # Insert HCS
  frame[-3:-1] = self._crc16(frame[1:-3]).to_bytes(2) # Insert FCS
  return frame

 #
 def create_state(self, aState: dict):
  ''' State creation

    - From AMS reader state, converts usable entries into Tibber Pulse format
    - TODO: Should really use randint here for some values...[Vin, Vcap, Vbck, s/w],

  '''
  #rnd = randint(2,8)
  state = {
   "rssi":aState['rssi'],
   "ch":1,
   "ssid":"IOT",
   "usbV":"0.36","Vin":"23.88","Vcap":"4.27","Vbck":"4.65",
   "Build":"1.2.5",
   "Hw":"F",
   "bssid":"cafedeadbeef",
   "ID":self._pulse_id,
   "IP":self._pulse_ip,
   "Uptime":aState['up'],
   "mqttcon":0,"pubcnt":4,"rxcnt":4,
   "wificon":1,"wififail":0,
   "bits":71,"cSet":34,"Ic":4.12,"crcerr":0,"cAx":1.277701,"cB":14,
   "heap":223244,
   "baud":2400,
   "meter":"Kamstrup",
   "ntc":-3.87,
   "s/w":18.010,
   "ct":706,"dtims":25,"mdb":0,"mdb_cnt":0,"bdtl":0
  }
  return {"status":state}
