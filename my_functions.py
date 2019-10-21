import smtplib
import json
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_mail(subject,start_date, start_time, pump_name, minutes):

    datadir = ('/var/www/html')
    
                        #  READ CONFIG FILE, ASSIGN VARIABLES
    with open(datadir + "/config.json","r") as config_file:
        config_data = json.load(config_file)  
    boatname =          config_data['boatname']
    smtp_server =       config_data['smtpserver']
    smtp_port =         config_data['smtpport']
    smtp_login =        config_data['username']
    smtp_password =     config_data['password']
    to_addr =           config_data['recipient1']
    cc_addr =           config_data['recipient2']
    group =             [to_addr, cc_addr]
    from_addr = boatname + ' Status Monitor'
 
                        #  USE THE EMAIL MULTIPART MODULE
    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = to_addr + ',' + cc_addr
    msg['Subject'] = subject
    body = (pump_name
           + "\n\nDATE:              " + start_date        
           + "\nTIME:               " + start_time
           + "\nDURATION:     " + minutes + "  mins")
    msg.attach(MIMEText(body, 'plain'))
    text = msg.as_string()
    try: #  INITIALIZE AND LOGON TO SMTP SERVER
        smtp_server = smtplib.SMTP(smtp_server, smtp_port) # Specify Gmail Mail server
        smtp_server.ehlo()  # Send mandatory 'hello' message to SMTP server
        smtp_server.starttls() # Start TLS Encryption as we're not using SSL.
        smtp_server.login(smtp_login,smtp_password)# login
        smtp_server.sendmail(from_addr, group, text)   # SEND THE EMAIL
        smtp_server.quit()
    except Exception:
        print("Email FAILED")


def logit(log_data):
    print(log_data[0],log_data[1],log_data[2],log_data[3]) # write to console
    loginfo = {
            "Date":     log_data[0],
            "Time":     log_data[1],
            "Event":    log_data[2],
            "Duration": log_data[3]
              }
    if os.path.isfile("log.json"):                # if file exists then proceed

        with open("log.json","r") as f:
            current_data=f.read()
            current_data = re.sub("]",",",current_data)

        with open("log.json","w") as f:
            f.write(current_data + json.dumps(loginfo) + "]" + "\n")

    else:                                         # create new file containing the initial open bracket
        with open("log.json","w+") as f:
            f.write("[\n")
            f.write(json.dumps(loginfo) + "]" + "\n")
 



    

        
