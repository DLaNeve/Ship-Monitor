#!/usr/bin/python3
# ShipMonitor_v6.0

import pandas as pd
import threading
import smtplib
import time
import datetime
import serial
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from EmulatorGUI import GPIO                                                #RPI replace with ->  from RPi import GPIO
#from RPi import GPIO
serialPort = 'com3'
#serialPort='/dev/serial0',

#  ---------------------------------READ CONFIG FILE & INITIALIZE VARIABLES AND GPIO------------------------
#datadir = ('/var/www/html')
#conn = sqlite3.connect ("ShipMonitor.db")
datadir = ('/python34/shipmonitor')                                         #RPI replace with -> datadir = ('/var/www/html')
conn = sqlite3.connect (datadir + "/ShipMonitor.db")
cur = conn.cursor()
cfgdata = pd.read_sql_query ("select * from Config;", conn, index_col='param')
cfg = pd.DataFrame (cfgdata)
offduration     = 0
powerofftime    = 0
via_sms         = cfg.value.via_sms
via_email       = cfg.value.via_email
pump            = [0] * int(cfg.value.numofpumps)
signal          = [0] * int(cfg.value.numofpumps)
savsignal       = [0] * int(cfg.value.numofpumps)
on              = [0] * int(cfg.value.numofpumps)
off             = [0] * int(cfg.value.numofpumps)
duration        = [0] * int(cfg.value.numofpumps)
reminder_target = int(cfg.value.reminder_target)* 60

ser = serial.Serial (

        port = serialPort,                                                       #RPI replace with ->  port='/dev/serial0',
        baudrate=9600,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
    )

GPIO_map = {
  0: 25,    #Bilge Pump 1
  1: 5,     #Bilge Pump 2
  2: 6,     #Bilge Pump 3
  3: 26,    #Bilge Pump 4
  4: 13,    #Bilge Pump 5
  5: 16,    #Bilge Pump 6
  9: 21     #Power monitor
}


GPIO.setmode (GPIO.BCM)
for x in range (0, int(cfg.value.numofpumps)):
    signal[x] = GPIO.setup (GPIO_map[x], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    signal[x] = 0
powerstatus = GPIO.setup (GPIO_map[9], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

#----------------------------------  FUNCTIONS  ------------------------------------------------------------------

def startup ():
    log_data = {'subject':"Ship Monitor Initialized", 'event': " ",'duration': "0"}
    logit (log_data)
    return

def shorepower_monitor():
    global offduration, powerofftime, reminder_time                             ##TODO is this necessary???
    if GPIO.input (GPIO_map[9]) == True and offduration == 0:
        offduration = 0
        powerofftime = 0
    elif GPIO.input (GPIO_map[9]) == False and offduration == 0:
        powerofftime = int (time.time ())
        offduration = 1
        reminder_time = int ((time.time () + reminder_target))
        log_data = {'subject': "Power Failure  ", 'event': " ", 'duration': '0'}
        logit (log_data)
    elif GPIO.input (GPIO_map[9]) == False and time.time () > reminder_time:
        offduration = int (time.time () - powerofftime) / 60
        hrs = str(format(offduration/60,'.1f'))
        reminder_time = int ((time.time () + reminder_target))
    elif GPIO.input (GPIO_map[9]) == True and offduration > 0:
        offduration = int (time.time () - powerofftime) / 60
        mins = str (format (offduration, '.1f'))
        log_data = {'subject':"Power Restored", 'event': " ", 'duration': mins}
        logit (log_data)
        offduration = 0
        powerofftime = 0
        reminder_time = 0
        log_data = ["", "", "", "0"]
    if time.strftime ("%H:%M:%S") == "12:00:00" and powerofftime == 0:
        time.sleep (1)
        log_data = {'subject': cfg.value.boatname + "Status",'event': "Systems Normal" }
        if cfg.value.via_email == "True":
            send_mail(log_data)
    return

def pump_monitor():
    for y in range (0, int (cfg.value.numofpumps)):
        signal[y] = GPIO.input (GPIO_map[y], )
        if signal[y] > savsignal[y]:
            on[y] = time.time ()
            savsignal[y] = signal[y]

        elif signal[y] < savsignal[y]:
            savsignal[y] = signal[y]
            off[y] = time.time ()
            duration[y] = (off[y] - on[y])
            mins = str (format (duration[y], '.1f'))
            subject = "Bilge Pump Cycled  "
            event = eval("cfg.value." + ("pump" + str (y + 1)))
            log_data = {'subject': subject, 'event': event, 'duration': mins}
            logit (log_data)
    return




def temp_monitor():
    data = ser.readline ()
    if len (data) > 2:
        for x in range (0, 29):
            dataStr = str (data[0:29])
        Sensor1, Sensor2, Sensor3, Sensor4, Sensor5 = dataStr.split (',')
        for x in range (0,8):
            Sensor[x] = Sensor1[-3:]


        
        mins = int(faulty_temp)
        subject = "Temperature Variance Detected  "
        event = "Inverter" + " Temp ="
        log_data = {'subject': subject, 'event': event, 'duration': mins}
        logit (log_data)
       
    return




def send_mail(start_date, start_time, subject, event, duration):
    boatname = cfg.value.boatname
    smtp_server = cfg.value.smtpserver
    smtp_port = cfg.value.smtpport
    smtp_login = cfg.value.username
    smtp_password = cfg.value.password
    to_addr = cfg.value.recipient1
    cc_addr = cfg.value.recipient2
    group = [to_addr, cc_addr]
    from_addr = boatname + ' Status Monitor'
                                                                            #  USE THE EMAIL MULTIPART MODULE
    msg = MIMEMultipart ()
    msg['From'] = from_addr
    msg['To'] = to_addr + ',' + cc_addr
    msg['Subject'] = subject
    body = (event
            + "\n\nDATE:              " + start_date
            + "\nTIME:               " + start_time)
    if float(duration) >0:
        event = event + "\nDURATION:     " + duration

    msg.attach (MIMEText (body, 'plain'))
    text = msg.as_string ()

                                                                            #    try:  # INITIALIZE AND LOGON TO SMTP SERVER
    time.sleep (5)
    smtp_server = smtplib.SMTP (cfg.value.smtpserver, cfg.value.smtpport)   # Specify Gmail Mail server
    smtp_server.ehlo ()                                                     # Send mandatory 'hello' message to SMTP server
    smtp_server.starttls ()                                                 # Start TLS Encryption as we're not using SSL.
    smtp_server.login (cfg.value.username, cfg.value.password)              # login
    smtp_server.sendmail (from_addr, group, text)                           # SEND THE EMAIL
    smtp_server.quit ()
#    except:
#        print('could not login to email server')
#    return

def logit(log_data):
    event_date = time.strftime ("%m-%d-%Y", time.localtime ())
    event_time = time.strftime ("%H:%M:%S", time.localtime ())
    subject = log_data['subject']
    event = log_data['event']
    duration = log_data['duration']
    sms_recip1 = cfg.value.sms_recip1
                # add to DB log
    cur.execute('INSERT INTO msglog VALUES (?,?,?,?,?)', (event_date, event_time, subject, event, duration))
    conn.commit()
                                                                            # log it to the console
    if float(duration) > 0:
        print (event_date,event_time, subject, event, duration)
    else:
        print (event_date,event_time, subject, event);
                                                                            # send a text msg
    if via_sms == "True":
        if float(duration) > 0:
            msg = event_date + event_time + subject + event + duration
        else:
            msg = event_date + event_time + subject + event;
        sms = TextMessage (sms_recip1, msg)
        sms.connectPhone ()
        sms.sendMessage ()
        sms.disconnectPhone ();
                                                                            # send an email
    if via_email == "True":
        try:
            emailThread = threading.Thread (target=send_mail, args=[event_date, event_time, subject, event, duration])
            emailThread.start ()
        except:
            print (event_date + "  " + event_time + "  " + 'Email failed');
    return

class TextMessage:
    def __init__(self, recipient="0123456789", message="TextMessage.content not set."):
        self.recipient = recipient
        self.content = message
    def setRecipient(self, number):
        self.recipient = number
    def setContent(self, message):
        self.content = message
    def connectPhone(self):
        #self.ser = serial.Serial('/dev/ttyUSB0', 460800, timeout=5)
        #self.ser = serial.Serial ('COM10', 460800, timeout=5)
        self.ser = serial.Serial (port='COM10', baudrate=460800, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE, timeout=1)
        time.sleep(1)
    def sendMessage(self):
        self.ser.write('ATZ\r'.encode())
        time.sleep(1)
        self.ser.write('AT+CMGF=1\r'.encode())                              # Set modem to text mode
        time.sleep(1)
        self.ser.write('''AT+CMGS="'''.encode() + self.recipient.encode() + '''"\r'''.encode())     # send sms to a number
        time.sleep(1)
        self.ser.write(self.content.encode() + "\r".encode())                                       # add the message
        time.sleep(1)
        self.ser.write(chr(26).encode())                                                            # control z to terminate
        time.sleep(1)
    def disconnectPhone(self):
        self.ser.close()

# -------------------------------------------------MAIN  ----------------------------------------------------------

if __name__ == '__main__':
    startup ()
    while True:
        pump_monitor()
        shorepower_monitor()
        temp_monitor()
