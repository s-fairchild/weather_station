from sys import stdout
import aprs, threading as th
from time import sleep, time
from db import WeatherDatabase
from aprs import SendAprs
from yaml import safe_load
from os import popen

data = {
    'callsign': "",
    'wspeed': 0,
    'wgusts': 0,
    'wdir': 0,
    'rain1h': 0,
    'rain24h': 0,
    'rain00m': 0,
    'pm25_avg': 0,
    'pm10_avg': 0,
    'rainfall': 0,
    'pressure' : 0,
    'temperature' : 0,
    'humidity' : 0
}

def start_bme280(address=0x77):
    while True:
        try:
            sensor = Sensor(address)
            break
        except Exception as e:
            print(f"Exception occured, {e}\nMaybe try reloading i2c-dev and i2c_bcm2835 kernel modules?")
            print(f"Waiting 10 seconds before retrying...")
            sleep(10)
            print(f"Trying to start bme280 again.")
            continue
    try:
        chipid, version = sensor._get_info_about_sensor()
        print(f"BME280 Information:\n\tChipID: {chipid}\n\tVersion: {version}")
    except Exception as e:
        print(f"{e}: Unable to get BME280 ChipID and Version")
    return sensor

def wait_delay(start_time, interval):
        end_time = time() # Capture end time
        elapsed_time = end_time - start_time
        wait_time = round(interval - elapsed_time, 2) # Calculate time to wait before restart loop
        if wait_time < 0:
            print(f"WARNING: Minutes past since last report: {round(elapsed_time / 60, 2)}\n\
                This is longer than the interval period of {interval / 60} minutes.")
            wait_time = 0
        print(f"Generating next report in {round((wait_time / 60), 2)} minutes")
        stdout.flush(); sleep(wait_time) # Flush buffered output and wait exactly 5 minutes from start time

def parse_config(config_file):
    try:
        print(f"Reading {config_file}.")
        with open(config_file, 'r') as file:
            config = safe_load(file)
        if len(config) != 0:
            print(f"Successfully loaded {config_file}.")
            return config
        else:
            print(f"{config_file} file loaded with 0 length, somethings wrong.")
    except Exception as e:
        print(f"Could not read {config_file}, {e}")

def gen_random_data():
    from random import randint, random
    from math import trunc
    r = random()
    data['wdir'] = randint(0, 364)
    data['pressure'] = randint(900, 1000) + randint(100, 200) * r # shift decimal point to the left 1 and round
    data['temperature'] = randint(-32, 120)
    data['wspeed'] = randint(0, 100)
    data['wgusts'] = data['wspeed'] + randint(0, 10)
    data['humidity'] = randint(0, 100)
    data['rainfall'] = randint(0, 5)

if __name__=="__main__":
    print("Reading 'wxstation.yaml'")
    config = parse_config('wxstation.yaml')
    # Create database object
    db = WeatherDatabase(password=config['db_pass'],host=config['db_host'])
    # Create aprs object
    aprs = SendAprs(db, config['loglevel'])

    # If dev mode is disabled, enable sensors and import packages as needed
    if config['dev_mode'] is False:
        # Create bme280 object if enabled        
        if config['sensors']['bme280']:      
            from bme280pi import Sensor
            sensor = start_bme280(config['bme280_addr'])
        # Create bme280 object if enabled
        if config['sensors']['rain1h']:
            from rainfall import RainMonitor
            rmonitor = RainMonitor()
            print("Starting rainfall monitoring thread.")
            th_rain = th.Thread(target=rmonitor.monitor, daemon=True)
            th_rain.start()
        if config['sensors']['wspeed']:
            from wspeed import WindMonitor
            from statistics import mean
            wmonitor = WindMonitor()
            print("Starting wind speed monitoring thread.")
            stop_event = th.Event()
            th_wmonitor = th.Thread(target=wmonitor.monitor_wind, daemon=True)
            th_wspeed = th.Thread(target=wmonitor.calculate_speed, args=[stop_event], daemon=True)
            th_wspeed.start(); th_wmonitor.start()
        if config['sensors']['wdir']:
            from wdir import WindDirectionMonitor
            wdir_monitor = WindDirectionMonitor()
            print("Starting wind direction monitoring thread.")
            th_wdir = th.Thread(target=wdir_monitor.monitor, daemon=True)
            th_wdir.start()
        if config['sds011']['enabled']: # If SDS011 is enabled collect readings
            from pysds011 import MonitorAirQuality
            print("Loading AirQuality monitoring modules.")
            if config['sds011']['tty'] in config and config['sds011']['tty'] is not None:
                air_monitor = MonitorAirQuality(tty=config['sds011']['tty'], interval=config['sds011']['interval'])
            else:
                air_monitor = MonitorAirQuality(interval=config['sds011']['interval'])
    print("Done reading config file.\nStarting main program now.")

    while True:
        if config['dev_mode']:
            gen_random_data()
        start_time = time() # Capture loop start time
        if 'air_monitor' in locals(): # If SDS011 is enabled make and start thread
            th_sds011 = th.Thread(target=air_monitor.monitor)
            th_sds011.start()

        if 'sensor' in locals():
            while True:
                try:
                    data['temperature'] = sensor.get_temperature(unit='F')
                    data['pressure'] = sensor.get_pressure()
                    data['humidity'] = sensor.get_humidity()
                    break
                except Exception as e:
                    sensor = start_bme280(config['bme280_addr'])
                    continue

        if 'th_wmonitor' and 'th_wspeed' in locals():
            if len(wmonitor.wind_list) > 0:
                stop_event.set()
                wmonitor.wind_count_lock.acquire()
                data['wspeed'], data['wgusts'] = mean(wmonitor.wind_list), max(wmonitor.wind_list)
                wmonitor.wind_list.clear()
                wmonitor.wind_count_lock.release()
                stop_event.clear()
            else:
                data['wgusts'], data['wspeed'] = 0, 0

        if 'th_wdir' in locals():            
            data['wdir'] = wdir_monitor.average() # Record average wind direction in degrees
            wdir_monitor.wind_angles.clear() # Clear readings to average

        if 'th_rain' in locals():
            data['rainfall'] = rmonitor.total_rain(); rmonitor.clear_total_rain()
        
        if 'air_monitor' in locals():
            th_sds011.join() # wait for thread to complete before getting average readings
            data['pm25_avg'], data['pm10_avg'] = air_monitor.average()
            air_monitor.air_values['pm25_total'].clear(); air_monitor.air_values['pm10_total'].clear() # Reset readings used for averages

        th_makepacket = th.Thread(target=aprs.send_data(data, config))
        th_sensorsave = th.Thread(target=db.read_save_sensors(data))
            
        th_sensorsave.start(); th_makepacket.start()
        th_sensorsave.join(); th_makepacket.join()
        wait_delay(start_time, config['report_interval'])
