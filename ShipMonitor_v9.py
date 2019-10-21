#!/usr/bin/python3
# ShipMonitor_v8.0

import serial
import pandas as pd
import threading
import smtplib
import time
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from EmulatorGUI import GPIO                                                #RPI replace with ->  from RPi import GPIO

#from RPi import GPIO

def startup():
    # datadir = ('/var/www/html')
    datadir = ('/python34/shipmonitor')

    global conn, cur, cfgdata, cfg
    conn    = sqlite3.connect("ShipMonitor.db")
    cur     = conn.cursor()
    cfgdata = pd.read_sql_query("select * from Config;", conn, index_col='param')
    cfg     = pd.DataFrame(cfgdata)

    global reminder_target, current_tod, current_tod_str
    reminder_target = 30  # int(cfg.value.reminder_target)* 60
    current_tod = time.time()
    current_tod_str = time.strftime("%H:%M:%S")

    global GPIO_map
    GPIO_map = {
        0: 25,  # Bilge Pump 1
        1: 5,  # Bilge Pump 2
        2: 6,  # Bilge Pump 3
        3: 26,  # Bilge Pump 4
        4: 13,  # Bilge Pump 5
        5: 16,  # Bilge Pump 6
        9: 21  # Power monitor
    }

    global pump_on, pump_on_tod, pump_off_tod, pump_duration
    pump_on         = [0] * int(cfg.value.numofpumps)
    pump_on_tod     = [0] * int(cfg.value.numofpumps)
    pump_off_tod    = [0] * int(cfg.value.numofpumps)
    pump_duration   = [0] * int(cfg.value.numofpumps)

    GPIO.setmode(GPIO.BCM)
    for x in range(0, int(cfg.value.numofpumps)):
        pump_on[x] = GPIO.setup(GPIO_map[x], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        pump_on[x] = 0

    global pwr_off_tod, pwr_off_reminder_time, pwr_off_duration, pwr_pin
    pwr_off_tod = 0
    pwr_off_reminder_time = 0
    pwr_off_duration = 0
    pwr_pin = GPIO_map[9]
    GPIO.setup (pwr_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    global raw_data, temp, temp_min, temp_max, temp_ok,temp_tod_min, temp_tod_max
    raw_data    = ' '
    temp        = [0]    * 5
    temp_min    = [0]    * 5
    temp_max    = [0]    * 5
    temp_ok     = [None] * 5
    temp_tod_min= [0]    * 5
    temp_tod_max= [0]    * 5

    for y in range (0,5):
        temp_min[y] = eval("cfg.paramA." + ("Temp" + str(y+1)))

    for y in range(0, 5):
        temp_max[y] = eval("cfg.paramB." + ("Temp" + str(y + 1)))

    # serialPort = 'com3'
    # serialPort = '/dev/serial0'
    # ser = serial.Serial (
    #         port = serialPort,                             # RPI replace with ->  port='/dev/serial0',
    #         baudrate=9600,
    #         parity=serial.PARITY_NONE,
    #         stopbits=serial.STOPBITS_ONE,
    #         bytesize=serial.EIGHTBITS,
    #         timeout=1
    #     )

# testing data follows
    temp_ok     = [False,False,False,False,False]
    raw_data    = '1-025,2-045,3-065,4-085,5-105'
# end of testing data

    log_data = {'subject' :'Ship Monitor Initialized',
                'event'   : '    ',
                'duration': ''}
    logit(log_data)
    return

def shorepower_monitor():
    global pwr_off_duration, pwr_off_tod, pwr_off_reminder_time, pwr_pin
    pwr_ok = GPIO.input (pwr_pin)

    if (pwr_ok) and (pwr_off_tod > 0):                          # Power Restored
        pwr_off_duration = int(time.time() - pwr_off_tod)/60
        mins = str(format(pwr_off_duration, '.1f'))
        log_data = {'subject': "Power Restored",
                    'event': " ",
                    'duration': mins + " mins"}
        logit(log_data)
        pwr_off_duration = 0                                    # Reset all power failure values
        pwr_off_tod = 0
        pwr_off_reminder_time = 0

    elif not pwr_ok and pwr_off_tod == 0:                       # Power Failure Begins
        pwr_off_tod = int(time.time())
        pwr_off_reminder_time = (pwr_off_tod + reminder_target)
        log_data = {'subject': "Power Failure  ",
                    'event': " ",
                    'duration': ''}
        logit(log_data)
        pwr_off_duration = int (time.time () - pwr_off_tod) / 60

    return

def pump_monitor():
    for pump_num in range(0, int(cfg.value.numofpumps)):
        pump_on[pump_num] = GPIO.input (GPIO_map[pump_num], )                           # read the GPIO pins
        if (pump_on[pump_num] is True) and pump_on_tod[pump_num] == 0:
            pump_on_tod[pump_num] = time.time()

        elif (pump_on[pump_num] is False) and pump_on_tod[pump_num] > 0:
            pump_off_tod[pump_num] = time.time()
            pump_duration[pump_num] = (pump_off_tod[pump_num] - pump_on_tod[pump_num])
            subject = "Bilge Pump Cycled:"
            event = eval("cfg.value." + ("pump" + str (pump_num + 1)))
            duration = str(format(pump_duration[pump_num], '.1f'))
            log_data = {'subject' : subject,
                        'event'   : event,
                        'duration': '~ ' + duration + ' secs'}
            logit (log_data)
            pump_on_tod[pump_num] = 0
    return

def temp_monitor():
    global temp_tod_max, temp_tod_min

# readline from serial port      raw_data = ser.readline ()
# test validity by checking length?

    for sensor_num in range (0,5):
        temp[sensor_num] = int(raw_data[2+(sensor_num*6):5+(sensor_num*6)])            # adjust offsets to match the raw data string

        if temp[sensor_num] >= temp_max[sensor_num] and temp_tod_max[sensor_num] == 0: # reached max
            temp_tod_max[sensor_num] = time.time()

            subject = "Temperature Has Exceeded Max  "
            event = eval("cfg.value." + ("Temp" + str(sensor_num + 1)))
            duration = "0"
            log_data = {'subject': subject,
                        'event': event,
                        'duration': duration}
            logit(log_data)

        elif temp[sensor_num] in range(int(temp_min[sensor_num]), int(temp_max[sensor_num])) and temp_tod_min[sensor_num] == 0:  # Reached min
            print (str(sensor_num) + " Min temp Reached")
            temp_tod_min[sensor_num] = time.time()

            subject = "Temperature Minimum Reached  "
            event = eval("cfg.value." + ("Temp" + str(sensor_num + 1)))
            duration = "0"
            log_data = {'subject': subject,
                         'event': event,
                         'duration': duration}
            logit(log_data)
    return

def check_time():
    global pwr_off_reminder_time, current_tod, current_tod_str, pwr_off_duration
    current_tod = int(time.time())
    current_tod_str = time.strftime ("%H:%M:%S")

    if current_tod_str == "12:00:00" and pwr_off_tod == 0 :
        time.sleep (1)
        subject = cfg.value.boatname + 'Status'
        event = "Systems Normal"
        duration = ''
        log_data = {'subject': subject,
                   'event': event,
                   'duration': duration}
        logit(log_data)

    if current_tod == pwr_off_reminder_time:
        pwr_off_duration = int(current_tod - pwr_off_tod) / 60
      #  hrs = str(format(pwr_off_duration / 60, '.1f'))
        time.sleep(1)
        subject = cfg.value.boatname + ' Status:'
        event = "Power remains OFF: "
        duration = str(pwr_off_duration)
        log_data = {'subject': subject,
                    'event': event,
                    'duration': 'Duration = ' + duration + ' hrs'}
        logit(log_data)
        pwr_off_reminder_time = current_tod + reminder_target



    return

def send_mail(start_date, start_time, subject, event, duration_msg):
    boatname = cfg.value.boatname
    server = cfg.value.smtpserver
    port = cfg.value.smtpport
    username = cfg.value.username
    password = cfg.value.password
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
            + "\nTIME:               " + start_time
            + duration_msg)

    msg.attach (MIMEText (body, 'plain'))
    text = msg.as_string ()                                                 #    try:  # INITIALIZE AND LOGON TO SMTP SERVER
    time.sleep (5)

    smtp_server = smtplib.SMTP (server, port)   # Specify Gmail Mail server
    smtp_server.ehlo ()                                                     # Send mandatory 'hello' message to SMTP server
    smtp_server.starttls ()                                                 # Start TLS Encryption as we're not using SSL.
    smtp_server.login (username, password)              # login
    smtp_server.sendmail (from_addr, group, text)                           # SEND THE EMAIL
    smtp_server.quit ()
    #except:
    #    print('could not login to email server')
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
        self.ser = serial.Serial('/dev/ttyUSB0', 460800, timeout=5)
        #self.ser = serial.Serial ('COM10', 460800, timeout=5)
        #self.ser = serial.Serial (port='COM10', baudrate=460800, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
        #                         stopbits=serial.STOPBITS_ONE, timeout=1)
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

def logit(log_data):
    event_date = time.strftime ("%m-%d-%Y", time.localtime ())
    event_time = time.strftime ("%H:%M:%S", time.localtime ())
    subject = log_data['subject']
    event = log_data['event']
    duration = log_data['duration']
    #if float(pwr_off_duration) > 0:
    #    duration_msg = "  Duration = " + str(pwr_off_duration) + "  Hrs"
    #else:
    #    duration_msg = " "
                                                                            # add to DB log
    cur.execute('INSERT INTO msglog VALUES (?,?,?,?,?)', (event_date, event_time, subject, event, duration))
    conn.commit()

    print (event_date,event_time,subject,event,duration)                # log it to the console

    if cfg.value.via_sms == "True":                                                   # send a text msg
        sms_recip1 = cfg.value.sms_recip1
        msg = event_date + event_time + subject + event + duration
        sms = TextMessage (sms_recip1, msg)
        sms.connectPhone ()
        sms.sendMessage ()
        sms.disconnectPhone ()

    if cfg.value.via_email == "True":                                                 # send an email
            emailThread = threading.Thread (target=send_mail, args=[event_date, event_time, subject, event, duration])
            emailThread.start()
    return


# -------------------------------------------------MAIN  ----------------------------------------------------------

if __name__ == '__main__':
    startup()
    while True:
        check_time()
        pump_monitor()
        shorepower_monitor()
     #   temp_monitor()
