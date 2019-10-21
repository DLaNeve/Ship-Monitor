#!/usr/bin/python3
# ShipMonitor_v5.0

import pandas as pd
import threading
import smtplib
import time
import serial
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from EmulatorGUI import GPIO         #Testing only - Replace with: from RPi import GPIO

#  ---------------------------------READ CONFIG FILE & INITIALIZE VARIABLES AND GPIO------------------------

datadir = ('/python34/shipmonitor')  # Testing only - Replace with: datadir = ('/var/www/html')

conn = sqlite3.connect (datadir + "/ShipMonitor.db")
cur = conn.cursor()
cfgdata = pd.read_sql_query ("select * from Config;", conn, index_col='param')
cfg = pd.DataFrame (cfgdata)

offduration     = 0
powerofftime    = 0
reminder_time   = 0

log_data        = ["", "", "", ""]
pump            = [0] * int(cfg.value.numofpumps)
signal          = [0] * int(cfg.value.numofpumps)
savsignal       = [0] * int(cfg.value.numofpumps)
on              = [0] * int(cfg.value.numofpumps)
off             = [0] * int(cfg.value.numofpumps)
duration        = [0] * int(cfg.value.numofpumps)
reminder_target = int(cfg.value.reminder_target)* 60

GPIO.setmode (GPIO.BCM)  # USE THE SILKSCREENED PIN #s
for x in range (0, int(cfg.value.numofpumps)):
    signal[x] = GPIO.setup (x + 20, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    signal[x] = 0
powerstatus = GPIO.setup (5, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

#----------------------------------  FUNCTIONS  ------------------------------------------------------------------

def startup ():
    pf_time = time.strftime ("%H:%M:%S", time.localtime ())
    pf_date = time.strftime ("%m-%d-%Y", time.localtime ())
    log_data = [pf_date, pf_time, "ShipMonitor Initialized", " "]
    logit (log_data)
    print ("Watching " + cfg.value.boatname + " ShorePower AND the following Bilge Compartments:")
    for y in range (0, int (cfg.value.numofpumps)):
        print (eval("    " + "cfg.value." + ("pump" + str (y + 1))))
    if cfg.value.via_email == "True":
        emailThread = threading.Thread (target=send_mail, args=["Monitor Initialized",
                                                                pf_date,
                                                                pf_time,
                                                                "Monitoring Bilge Pumps and Shore Power",
                                                                " "])
        emailThread.start ()
    if cfg.value.via_sms == "True":
        msg = "Monitor Initialized\n" + pf_date + "  " + pf_time + "\nMonitoring Bilge Pumps & ShorePower"
        sms = TextMessage (cfg.value.recipient1, msg)
        sms.connectPhone ()
        sms.sendMessage ()
        sms.disconnectPhone ()
    return

def shorepower_monitor():
    global offduration, powerofftime, reminder_time   ##TODO is this necessary???
    if GPIO.input (5) == True and offduration == 0:
        offduration = 0
        powerofftime = 0
    elif GPIO.input (5) == False and offduration == 0:
        powerofftime = int (time.time ())
        offduration = 1
        reminder_time = int ((time.time () + reminder_target))
        pf_time = time.strftime ("%H:%M:%S", time.localtime ())
        pf_date = time.strftime ("%m-%d-%Y", time.localtime ())
        log_data = [pf_date, pf_time, "Power Failure", ""]
        logit (log_data)
        if cfg.value.via_email == "True":
            emailThread = threading.Thread (target=send_mail,
                                            args=["POWER FAILURE",
                                                  pf_date,
                                                  pf_time,
                                                  "Power Failure",
                                                  " "])
            emailThread.start ()
        if cfg.value.via_sms == "True":
            msg = "Power Failure\n" + pf_date + "  " + pf_time
            sms = TextMessage (cfg.value.sms_recip1, msg)
            sms.connectPhone ()
            sms.sendMessage ()
            sms.disconnectPhone ()
    elif GPIO.input (5) == False and time.time () > reminder_time:
        offduration = int (time.time () - powerofftime) / 60
        pf_time = time.strftime ("%H:%M:%S", time.localtime ())
        pf_date = time.strftime ("%m-%d-%Y", time.localtime ())
        hrs = str(format(offduration/60,'.1f'))
        reminder_time = int ((time.time () + reminder_target))
        if cfg.value.via_email == "True":
            emailThread = threading.Thread (target=send_mail, args=["POWER REMAINS OFF",
                                                                    pf_date,
                                                                    pf_time,
                                                                    "Reminder, power remains OFF!!",
                                                                    "  " + hrs + " hrs"])
            emailThread.start ()
        if cfg.value.via_sms == "True":
            msg = "Power Remains Off\n" + \
                  pf_date + "  " + \
                  pf_time + "\n" + \
                  mins + " Minutes"
            sms = TextMessage (cfg.value.sms_recip1, msg)
            sms.connectPhone ()
            sms.sendMessage ()
            sms.disconnectPhone ()

    elif GPIO.input (5) == True and offduration > 0:
        offduration = int (time.time () - powerofftime) / 60
        mins = str (format (offduration, '.1f'))
        pf_time = time.strftime ("%H:%M:%S", time.localtime ())
        pf_date = time.strftime ("%m-%d-%Y", time.localtime ())
        log_data = [pf_date, pf_time, "Power Restored.  Duration: ", mins]
        logit (log_data)
        if cfg.value.via_email == "True":
            emailThread = threading.Thread (target=send_mail,
                                            args=["POWER RESTORED",
                                                  pf_date,
                                                  pf_time,
                                                  "Power Systems Normal",
                                                  mins + " Minutes"])
            emailThread.start ()
        if cfg.value.via_sms == "True":
            msg = "Power Restored\n" + \
                  pf_date + "  " + \
                  pf_time + "\n" + \
                  mins + " Minutes"
            sms = TextMessage (cfg.value.sms_recip1, msg)
            sms.connectPhone ()
            sms.sendMessage ()
            sms.disconnectPhone ()
        offduration = 0
        powerofftime = 0
        reminder_time = 0
        log_data = ["", "", "", "0"]

    if time.strftime ("%H:%M:%S") == "12:00:00" and powerofftime == 0:
        pf_time = time.strftime ("%H:%M:%S", time.localtime ())
        pf_date = time.strftime ("%m-%d-%Y", time.localtime ())
        time.sleep (1)
        if cfg.value.via_email == "True":
            emailThread = threading.Thread (target=send_mail,
                                            args=[cfg.value.boatname + " Status",
                                                  pf_date,
                                                  pf_time,
                                                  "Systems Normal",
                                                  " "])
            emailThread.start ()
        if cfg.value.via_sms == "True":
            msg = "Systems Normal\n" + pf_date + "  " + pf_time
            sms = TextMessage (cfg.value.sms_recip1, msg)
            sms.connectPhone ()
            sms.sendMessage ()
            sms.disconnectPhone ()
    return

def pump_monitor():
    for y in range (0, int (cfg.value.numofpumps)):
        signal[y] = GPIO.input (20 + y, )
        if signal[y] > savsignal[y]:
            on[y] = time.time ()
            savsignal[y] = signal[y]
        elif signal[y] < savsignal[y]:
            savsignal[y] = signal[y]
            off[y] = time.time ()
            duration[y] = (off[y] - on[y])
            mins = str (format (duration[y], '.1f'))
            start_time = time.strftime ("%H:%M:%S", time.localtime (on[y]))
            start_date = time.strftime ("%m-%d-%Y", time.localtime (on[y]))
            log_data = [start_date,
                        start_time,
                        eval("cfg.value." + ("pump" + str (y + 1))) + " Bilge Pump",
                        mins + " Seconds"]
            logit (log_data)
            if cfg.value.via_email == "True":
                emailThread = threading.Thread (target=send_mail, args=['Bilge Pump Cycled',
                                                                        start_date,
                                                                        start_time,
                                                                        "PUMP:           " + eval("cfg.value." + ("pump" + str (y + 1))),
                                                                        mins + " Seconds"])
                emailThread.start ()
            if cfg.value.via_sms == "True":
                msg = "Bilge Pump Cycled\n" + \
                      start_date + "  " + \
                      start_time + "\n" + \
                      eval ("cfg.value." + ("pump" + str (y + 1))) + "\n" + \
                      mins + " Seconds"
                sms = TextMessage (cfg.value.sms_recip1, msg)
                sms.connectPhone ()
                sms.sendMessage ()
                sms.disconnectPhone ()
    return

def send_mail(subject, start_date, start_time, pump_name, minutes):

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
    body = (pump_name
            + "\n\nDATE:              " + start_date
            + "\nTIME:               " + start_time
            + "\nDURATION:     " + minutes)
    msg.attach (MIMEText (body, 'plain'))
    text = msg.as_string ()

    try:  # INITIALIZE AND LOGON TO SMTP SERVER
        time.sleep (5)
        smtp_server = smtplib.SMTP (cfg.value.smtpserver, cfg.value.smtpport)  # Specify Gmail Mail server
        smtp_server.ehlo ()  # Send mandatory 'hello' message to SMTP server
        smtp_server.starttls ()  # Start TLS Encryption as we're not using SSL.
        smtp_server.login (cfg.value.username, cfg.value.password)  # login
        smtp_server.sendmail (from_addr, group, text)  # SEND THE EMAIL
        smtp_server.quit ()
    except:
        pf_time = time.strftime ("%H:%M:%S", time.localtime ())
        pf_date = time.strftime ("%m-%d-%Y", time.localtime ())
        log_data = [pf_date, pf_time, "Email Failed", " "]
        logit (log_data)
    return

def logit(log_data):
    cur.execute('INSERT INTO msglog VALUES (?,?,?,?)', (log_data[0],log_data[1],log_data[2],log_data[3]) )
    conn.commit()
    print (log_data[0], log_data[1], log_data[2], log_data[3])  # write to console
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
        time.sleep(1)

    def sendMessage(self):
        self.ser.write('ATZ\r'.encode())
        time.sleep(1)
        self.ser.write('AT+CMGF=1\r'.encode())
        time.sleep(1)
        self.ser.write('''AT+CMGS="'''.encode() + self.recipient.encode() + '''"\r'''.encode())
        time.sleep(1)
        self.ser.write(self.content.encode() + "\r".encode())
        time.sleep(1)
        self.ser.write(chr(26).encode())
        time.sleep(1)

    def disconnectPhone(self):
        self.ser.close()

# -------------------------------------------------MAIN  ----------------------------------------------------------

if __name__ == '__main__':

    startup ()
    while True:
        pump_monitor()
        shorepower_monitor()
