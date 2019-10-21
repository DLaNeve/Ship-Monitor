#!/usr/bin/env python3

import time
import serial

ser = serial.Serial (
    port='/dev/ttyS0',          # i think this is the right port!
    baudrate=9600,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=None
)

while 1:
    x = ser.readline ()     # read until EOL is reached  or you can use x = ser.read(z)  z = num of bytes
    print(x)
    time.sleep(2)           # sleep 2 seconds
