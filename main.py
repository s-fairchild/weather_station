from bme280pi import Sensor
from sys import stdout
import aprs, threading as th
from time import sleep, time
from db import WeatherDatabase
from aprs import SendAprs
from yaml import safe_load

config_file = 'wxstation.yaml'
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
    'rainfall': 0
}

def start_bme280():
    try:
        sensor = Sensor(0x77)
    except Exception as e:
        print(f"Exception occured while setting bme280 to address 0x77: {e}\nTrying address 0x76")
        sensor = Sensor(0x76)
    try:
        chipid, version = sensor._get_info_about_sensor()
        print(f"BME280 Information:\n\tChipID: {chipid}\n\tVersion: {version}")
    except Exception as e:
        print(f"{e}: Unable to get BME280 ChipID and Version")
    return sensor

def wait_delay(start_time):
        seconds = 300
        end_time = time() # Capture end time
        wait_time = round(seconds - (end_time - start_time)) # Calculate time to wait before restart loop
        if wait_time < 0:
            abs(wait_time)
        elif wait_time == 0:
            wait_time = 300
        print(f"Generating next report in {round((wait_time / 60), 2)} minutes")
        stdout.flush(); sleep(wait_time) # Flush buffered output and wait exactly 5 minutes from start time

if __name__=="__main__":
    print(f"Reading {config_file}")
    config = safe_load(config_file)
    db = WeatherDatabase(password=config['db_pass'],host=config['db_host'])
    aprs = SendAprs(db, config['loglevel'])
    if config['sensors']['bme280']:
        sensor = start_bme280()
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
    if config['sensors']['si4713']:
        from si4713 import FM_Transmitter
        fm_transmitter = FM_Transmitter()
    print("Done reading config file.\nStarting main program now.")

    while True:
        start_time = time() # Capture loop start time
        if 'air_monitor' in locals(): # If SDS011 is enabled make and start thread
            th_sds011 = th.Thread(target=air_monitor.monitor)
            th_sds011.start()

        if 'sensor' in locals():
            data['temperature'] = sensor.get_temperature(unit='F')
            data['pressure'] = sensor.get_pressure()
            data['humidity'] = sensor.get_humidity()

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

        if config['tcpip']:
            th_senddata_tcpip = th.Thread(target=aprs.send_data(data, config))

        if 'fm_transmitter' in locals():            
            th_fm_transmit= th.Thread(target=fm_transmitter.manage_soundfile(aprs.make_packet(data, config)))

        th_sensorsave = th.Thread(target=db.read_save_sensors(data))
        if 'th_senddata_tcpip' in locals():
            th_senddata_tcpip.start()

        if 'fm_transmitter' in locals():
            th_fm_transmit.start()
        th_sensorsave.start()
        if 'th_senddata_tcpip' in locals():
            th_senddata_tcpip.join()
        if 'fm_transmitter' in locals():
            th_fm_transmit.join()
        th_sensorsave.join()
        wait_delay(start_time)
