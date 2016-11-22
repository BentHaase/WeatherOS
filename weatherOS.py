#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import time
import Adafruit_DHT
import Adafruit_BMP.BMP085 as BMP180
import RPi.GPIO as GPIO
import MySQLdb
import requests
import json
import subprocess

# Software revision
os_rev = "0.2.0.2"

# create timestamp
timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

# get system uptime
uptime = subprocess.Popen(["uptime", "--pretty"], stdout=subprocess.PIPE).communicate()[0]
uptime = uptime[3:-1]

# preparing GPIO of Raspberry pi
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

# set pin 11 (GPIO 17) output (status LED)
GPIO.setup(11, GPIO.IN)
if GPIO.input(11) == GPIO.LOW:
    rain = True;
else:
    rain = False;

# activate LED
GPIO.setup(37, GPIO.OUT)
GPIO.output(37, GPIO.HIGH)

# fetch outside temperature
temp1 = open('/sys/bus/w1/devices/28-021503675aff/w1_slave', 'r')
# regex to extract temperature from data (e.g. 1725) -> /1000 -> 1.725
ds18b20_temp = (float(re.search("t=(\d.+|-\d.+)", temp1.read()).group(1))/1000)

# fetch CPU temperature
temp2 = open('/sys/class/thermal/thermal_zone0/temp', 'r')
cpu_temp = (float(temp2.read())/1000)

# fetch barometric data
sensor = BMP180.BMP085()
temperature_bmp180 = sensor.read_temperature()
pressure_bmp180 = (float(sensor.read_pressure())/100)

# close all opened files
temp1.close()
temp2.close()

# placeholder for future expansion
lux = "NULL"

# fetch humidity and temperature (at wall)
am2302_humid, am2302_temp = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, 22)

# connecting to MySQL database and creating cursor
# all queries are executed by the cursor
db = MySQLdb.connect(host="<DB_URL>", user="<DB_USER>", passwd="<DB_PW>", db="<DB_NAME>", connect_timeout=15)
cur = db.cursor()

print('Preparing SQL statement')
sql = (('INSERT INTO `cf56bfb4` (`t_out`, `t_out_wall`, `humidity`, `t_cpu`, `pressure`, `t_case`, `lux`, `rain`) VALUES ({:.2f}, {:.1f}, {:.2f}, {:.2f}, {:.2f}, {:.2f}, {}, {});').format(ds18b20_temp, am2302_temp, am2302_humid, cpu_temp, pressure_bmp180, temperature_bmp180, lux, rain))

print('Executing SQL statement')
cur.execute(sql)
print('Commiting SQL statement')
db.commit()
print('Closing database connection')
cur.close()
db.close()

# prepare request data
ds18b20_data=('tile=big_value&key=t_out_<LOCATION>&data={{"title": "Outside Temperature", "description": "DS18B20 sensor", "big-value": "{0:3.2f} °C"}}').format(ds18b20_temp)
am2303_data=('tile=big_value&key=humidity_<LOCATION>&data={{"title": "Outside Humidity", "description": "AM2303 sensor", "big-value": "{0:3.1f}%"}}').format(am2302_humid)
bmp180_data=('tile=big_value&key=pressure_<LOCATION>&data={{"title": "Barometric Pressure", "description": "BMP180 sensor", "big-value": "{0:4.0f}hPa"}}').format(pressure_bmp180)
rain_data=('tile=big_value&key=rain_<LOCATION>&data={{"title": "Rainfall", "description": "Does it currently rain?", "big-value": "{0}"}}').format("Yes" if rain else "No")
info=('tile=listing&key=info_<LOCATION>&data={{"items": ["Location: Lüneburg", "Latest Data: {0}", "CPU Temperature: {1:.2f} °C", "Case Temperature: {2} °C", "Uptime: {3}", "WeatherOS Version: {4}"]}}').format(timestamp,cpu_temp,temperature_bmp180,uptime,os_rev)
print(am2303_data)

# prepare requests
r1 = requests.post("https://<PANEL_URL>/api/v0.1/a1aba1e3b9884ad38fb46f76114c3b87/push", data=ds18b20_data)
r2 = requests.post('https://<PANEL_URL>/api/v0.1/a1aba1e3b9884ad38fb46f76114c3b87/push', data=am2303_data)
r3 = requests.post("https://<PANEL_URL>/api/v0.1/a1aba1e3b9884ad38fb46f76114c3b87/push", data=bmp180_data)
r4 = requests.post("https://<PANEL_URL>/api/v0.1/a1aba1e3b9884ad38fb46f76114c3b87/push", data=rain_data)
r5 = requests.post("https://<PANEL_URL>/api/v0.1/a1aba1e3b9884ad38fb46f76114c3b87/push", data=info)

# print status of each request to the console
print(r1.text)
print(r1.status_code, r1.reason)

print(r2.text)
print(r2.status_code, r2.reason)

print(r3.text)
print(r3.status_code, r3.reason)

print(r4.text)
print(r4.status_code, r4.reason)

print(r5.text)
print(r5.status_code, r4.reason)

# deactivate LED
GPIO.output(37, GPIO.LOW)

# being verbose for debugging the script when run in shell
print ("{0}{1}").format(timestamp,"<br>")
print ("Outside Temperature (Sensor ds18b20 ): {0:>3.3f} °C<br>").format(ds18b20_temp)
print ("Outside Temperature (Sensor AM2302  ): {0:>3.3f} °C<br>").format(am2302_temp)
print ("Outside Humidity    (Sensor AM2302  ): {0:>3.3f}  %<br>").format(am2302_humid)
print ("CPU Temperature     (Sensor INTERNAL): {0:>3.3f} °C<br>").format(cpu_temp)
print ("Barometric Pressure (Sensor BMP180  ): {0:>4.2f} hPa<br>").format(pressure_bmp180)
print ("Case Temperature    (Sensor BMP180  ): {0:>2.2f} °C<br>").format(temperature_bmp180)
print ("Rain detected       (Generic        ): {0}<br>").format("Yes" if rain else "No")
