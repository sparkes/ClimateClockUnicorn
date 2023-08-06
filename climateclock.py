# Climate Clock (unoffical)
#
# based on clock.py and fire.py examples by pimoroni
#
# Create a secrets.py with your Wifi details to be able to get the time
# when the Galactic Unicorn isn't connected to Thonny.
#
# secrets.py should contain:
# WIFI_SSID = "Your WiFi SSID"
# WIFI_PASSWORD = "Your WiFi password"
#
# Clock synchronizes time on start, and resynchronizes if you press the A button

import time
import math
import machine
import network
import ntptime
import datetime
import random
import sys
import urequests as requests

from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN as DISPLAY

#get wifi creds
try:
    from secrets import WIFI_SSID, WIFI_PASSWORD
    wifi_available = True
except ImportError:
    print("Create secrets.py with your WiFi credentials to get time from NTP")
    wifi_available = False


##########################################
#  set up global objects and variables
##########################################
gu = GalacticUnicorn()
graphics = PicoGraphics(DISPLAY)

fire_colours = [graphics.create_pen(50, 20, 20),
                graphics.create_pen(100, 50, 20),
                graphics.create_pen(180, 30, 0),
                graphics.create_pen(220, 160, 0),
                graphics.create_pen(255, 255, 180)]

rtc = machine.RTC()

widthDiv2 = GalacticUnicorn.WIDTH/2

# set up some pens to use later
WHITE = graphics.create_pen(255, 255, 255)
BLACK = graphics.create_pen(0, 0, 0)

width = GalacticUnicorn.WIDTH + 2
height = GalacticUnicorn.HEIGHT + 4
heat = [[0.0 for y in range(height)] for x in range(width)]
fire_spawns = 16
damping_factor = 0.92
    
# the only font we need a modified version of 3x5 font
# MIT licenced?
graphics.set_font(open("3x5new.bitmapfont", "rb").read())

utc_offset = 0

up_button = machine.Pin(GalacticUnicorn.SWITCH_VOLUME_UP, machine.Pin.IN, machine.Pin.PULL_UP)
down_button = machine.Pin(GalacticUnicorn.SWITCH_VOLUME_DOWN, machine.Pin.IN, machine.Pin.PULL_UP)

year, month, day, wd, hour, minute, second, _ = rtc.datetime()

last_second = second
steps = 0

txt1 = ""
txt2 = ""
x1 = 0
x2 = 0

gu.set_brightness(0.5)

##########################################
#  log to the screen as well as the console during setup
##########################################
def log(a):
    print(a)
    graphics.set_pen(BLACK)
    graphics.clear()
    graphics.set_pen(WHITE)
    graphics.text(a, 0, 1, -1, 1)
    gu.update(graphics)

##########################################
#  a less heavy version of the function in clock.py
##########################################
def outline_text(text, x, y):
    graphics.set_pen(BLACK)
    graphics.text(text, x, y - 1, -1, 1)
    graphics.text(text, x - 1, y, -1, 1)
    graphics.text(text, x + 1, y, -1, 1)
    graphics.text(text, x, y + 1, -1, 1)

    graphics.set_pen(WHITE)
    graphics.text(text, x, y, -1, 1)

##########################################
#  connect to wifi and get NTP time (from clock.py)
##########################################
def sync_time():
    if not wifi_available:
        log("WIFI REQ")
        sys.exit(-1)

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    # Wait for connect success or failure
    max_wait = 100
    lstr = "WIFI"
    while max_wait > 0:
        status = wlan.status()
        
        if status == network.STAT_GOT_IP :
            log("GOT IP")
            break
        elif status == network.STAT_IDLE:
            print ("idle")
        elif status == network.STAT_CONNECTING:
            print ("connecting")
        elif status == network.STAT_WRONG_PASSWORD:
            print ("wrong password")
            sys.exit(-1)
        elif status == network.STAT_NO_AP_FOUND:
            print ("no ap")
            sys.exit(-1)
        elif status == network.STAT_CONNECT_FAIL:
            print ("general fail")
            sys.exit(-1)
            
        max_wait -= 1
        log(lstr)
        lstr = lstr + "."
        time.sleep(0.2)

    if max_wait > 0:
        log("NTP SYNC")
        try:
            ntptime.settime()
            log("GOT TIME")
        except OSError:
            log("FAIL")
            sys.exit(-1)

    return True

def get_cccountdown():
    log("GET COUNT")
    r = requests.get(url="https://sparkes.github.io/ClimateClockMinimal/deadline.txt").text
    print (r)
    log("INIT")
    return r

##########################################
#  used to change timezone offset of realtime clock display (from clock.py example)
##########################################
def adjust_utc_offset(pin):
    global utc_offset
    if pin == up_button:
        utc_offset += 1
    if pin == down_button:
        utc_offset -= 1


up_button.irq(trigger=machine.Pin.IRQ_FALLING, handler=adjust_utc_offset)
down_button.irq(trigger=machine.Pin.IRQ_FALLING, handler=adjust_utc_offset)

##########################################
#  update the firey background (from fire.py example)
##########################################
@micropython.native  # noqa: F821
def updateFire():
    # clear the bottom row and then add a new fire seed to it
    for x in range(width):
        heat[x][height - 1] = 0.0
        heat[x][height - 2] = 0.0

    for c in range(fire_spawns):
        x = random.randint(0, width - 4) + 2
        heat[x + 0][height - 1] = 1.0
        heat[x + 1][height - 1] = 1.0
        heat[x - 1][height - 1] = 1.0
        heat[x + 0][height - 2] = 1.0
        heat[x + 1][height - 2] = 1.0
        heat[x - 1][height - 2] = 1.0

    for y in range(0, height - 2):
        for x in range(1, width - 1):
            # update this pixel by averaging the below pixels
            average = (
                heat[x][y] + heat[x][y + 1] + heat[x][y + 2] + heat[x - 1][y + 1] + heat[x + 1][y + 1]
            ) / 5.0

            # damping factor to ensure flame tapers out towards the top of the displays
            average *= damping_factor

            # update the heat map with our newly averaged value
            heat[x][y] = average

##########################################
#  Draw background (from fire.py example (slightly modified to replace some branches with a mult and cast - not sure if quicker or not))
##########################################
@micropython.native  # noqa: F821
def drawFire():
    for y in range(GalacticUnicorn.HEIGHT):
        for x in range(GalacticUnicorn.WIDTH):  
            value = int((heat[x + 1][y])*10)
            
            if (value > 4):
                graphics.set_pen(fire_colours[4])
            else:
                graphics.set_pen(fire_colours[value])

            graphics.pixel(x, y)


##########################################
#  update and draw the timers (based on clock.py example)
##########################################
def updateAndDrawTimers(countdown):
    global year, month, day, wd, hour, minute, second, last_second, steps, x1, x2, txt1, txt2

    year, month, day, wd, hour, minute, second, _ = rtc.datetime()
    
    if second != last_second:
        hour += utc_offset
        
        dt1 = datetime.datetime(year, month, day, hour, minute, second)
        dt2 = strToDatetime(countdown)

        tdelta = dt2 - dt1 
        txts = deltaToString(tdelta)
        clock = "{:02}:{:02}:{:02}".format(hour, minute, second)
    
        step =  steps%15

        if step < 8:
            w = graphics.measure_text(txts[step], 1)
            x1 = int(widthDiv2 - w / 2 + 1)
            txt1 = txts[step]
        else:
            w = graphics.measure_text(txts[7], 1)
            x1 = int(widthDiv2 - w / 2 + 1)
            txt1 = txts[7]
                   
        w = graphics.measure_text(clock, 1)
        x2 = int(widthDiv2 - w / 2 + 1)
        txt2 = clock
        
        last_second = second
        steps+=1
        
    outline_text(txt1, x1, 0)
    outline_text(txt2, x2, 6)

#no datetime.strptime but we know our format.
def strToDatetime (datestr):
    y = int(datestr[:4])
    M = int(datestr[5:7])
    d = int(datestr[8:10])
    h = int(datestr[11:13])
    m = int(datestr[14:16])
    s = int(datestr[17:19])

    return datetime.datetime(y, M, d, h, m, s)

#format the timedelta into a nice string
def deltaToString(delta):
    #this is a good way of getting yrs, weeks, days and a terrible way of getting the seconds
    s = delta.total_seconds()
    
    if (s > 31536000):
        y, s = divmod(s, 31536000)
        y = "%i YEARS"%(y)
    else:
        y = "0 YEARS"
        
    if (s > 604800):
        w, s = divmod(s, 604800)
        w = "%i WEEKS"%(w)
    else:
        w = "0 WEEKS"
    
    if (s > 86400):
        d, s = divmod(s, 86400)
        d = "%i DAYS"%(d)
    else:
        d = "0 DAYS"
        
    if (s > 3600):
        h, s = divmod(s, 3600)
        h = "%i HOURS"%(h)
    else:
        h = "0 HOURS"
      
    if (s > 60):
        m, s = divmod(int(s), 60)
        m = "%i MINUTES"%(m)
    else:
        m = "0 MINUTES"
    
    s = "%s SECONDS" %(str(delta)[-2:])
    
    return ("COUNTDOWN","TO 1.5 DEGREES", y, w, d , h, m, s)
    


if (sync_time() == True):
    countdown = get_cccountdown()
    while True:
        if gu.is_pressed(GalacticUnicorn.SWITCH_BRIGHTNESS_UP):
            gu.adjust_brightness(+0.01)

        if gu.is_pressed(GalacticUnicorn.SWITCH_BRIGHTNESS_DOWN):
            gu.adjust_brightness(-0.01)

        if gu.is_pressed(GalacticUnicorn.SWITCH_A):
            sync_time()

        updateFire()
        drawFire()
    
        updateAndDrawTimers(countdown)

        gu.update(graphics)

        time.sleep(0.001)
