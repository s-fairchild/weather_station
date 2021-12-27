from statistics import mean
import logging, threading as th
from time import sleep, time
from db import WeatherDatabase
from aprs import SendAprs
from yaml import safe_load

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

def start_bme280(address=0x76):
    from bme280pi import Sensor
    while True:
        try:
            sensor = Sensor(address)
            break
        except Exception as e:
            logging.critical(f"Exception occured, {e}\nMaybe try reloading i2c-dev and i2c_bcm2835 kernel modules?")
            logging.error(f"Waiting 10 seconds before retrying...")
            sleep(10)
            logging.error(f"Trying to start bme280 again.")
            continue
    try:
        chipid, version = sensor._get_info_about_sensor()
        logging.info(f"BME280 Information:\n\tChipID: {chipid}\n\tVersion: {version}")
    except Exception as e:
        logging.error(f"{e}: Unable to get BME280 ChipID and Version")
    return sensor

def wait_delay(start_time, interval):
        end_time = time() # Capture end time
        elapsed_time = end_time - start_time
        wait_time = round(interval - elapsed_time, 2) # Calculate time to wait before restart loop
        if wait_time < 0:
            logging.error(f"WARNING: Minutes past since last report: {round(elapsed_time / 60, 2)}\n\
                This is longer than the interval period of {interval / 60} minutes.")
            wait_time = 0
        logging.info(f"Generating next report in {round((wait_time / 60), 2)} minutes")
        sleep(wait_time) # Flush buffered output and wait for seconds in wxstation.yaml report_interval:

def parse_config(config_file):
    try:
        logging.info(f"Reading {config_file}.")
        with open(config_file, 'r') as file:
            config = safe_load(file)
        if len(config) != 0:
            logging.info(f"Successfully loaded {config_file}.")
            return config
        else:
            logging.error(f"{config_file} file loaded with 0 length, somethings wrong.")
    except Exception as e:
        logging.exception(f"Could not read {config_file}, {e}")

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

def init_objects():
    sensors = {}
    threads = {}
    # Create bme280 object if enabled        
    if config['sensors']['bme280']:
        sensors['bme280'] = start_bme280(config['bme280_addr'])
    # Create bme280 object if enabled
    if config['sensors']['rain1h']:
        from rainfall import RainMonitor
        sensors['rmonitor'] = RainMonitor()
        logging.info("Starting rainfall monitoring thread.")
        threads['rain'] = th.Thread(target=sensors['rmonitor'].monitor, daemon=True)
        threads['rain'].start()
    if config['sensors']['wspeed']:
        from wspeed import WindMonitor
        sensors['wmonitor'] = WindMonitor()
        logging.info("Starting wind speed monitoring thread.")
        stop_event = th.Event()
        threads['wmonitor'] = th.Thread(target=sensors['wmonitor'].monitor_wind, daemon=True)
        threads['wspeed'] = th.Thread(target=sensors['wmonitor'].calculate_speed, args=[stop_event], daemon=True)
        threads['wmonitor'].start()
        threads['wspeed'].start()
    if config['sensors']['wdir']:
        from wdir import WindDirectionMonitor
        sensors['wdir_monitor'] = WindDirectionMonitor()
        logging.info("Starting wind direction monitoring thread.")
        threads['wdir'] = th.Thread(target=sensors['wdir_monitor'].monitor, daemon=True)
        threads['wdir'].start()
    if config['sds011']['enabled']:
        from pysds011 import MonitorAirQuality
        logging.info("Loading AirQuality monitoring modules.")
        if config['sds011']['tty'] in config and config['sds011']['tty'] is not None:
            sensors['air_monitor'] = MonitorAirQuality(tty=config['sds011']['tty'], interval=config['sds011']['interval'])
        else:
            sensors['air_monitor'] = MonitorAirQuality(interval=config['sds011']['interval'])
    return sensors, threads

if __name__=="__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.info("Reading 'wxstation.yaml'")
    config = parse_config('wxstation.yaml')
    # Create database object
    db = WeatherDatabase(password=config['db_pass'],host=config['db_host'])
    # Create aprs object
    aprs = SendAprs(db, config['loglevel'])
    # If dev mode is disabled, enable sensors and import packages as needed
    if config['dev_mode'] is False:
        sensors, threads = init_objects()
    logging.info("Done reading config file.\nStarting main program now.")
    # Create stop event for wind monitor
    stop_event = th.Event()

    while True:
        if config['dev_mode']:
            gen_random_data()

        start_time = time() # Capture loop start time
        if 'air_monitor' in sensors: # If SDS011 is enabled make and start thread
            logging.info('Starting air_monitor thread')
            threads['sds011'] = th.Thread(target=sensors['air_monitor'].monitor)
            threads['sds011'].start()
            logging.debug(f"sds011 thread status: {threads['sds011'].is_Alive}")

        if 'bme280' in sensors:
            logging.info('Reading bme280 temperature, pressure, and humidity now.')
            while True:
                try:
                    data['temperature'] = sensors['bme280'].get_temperature(unit='F')
                    data['pressure'] = sensors['bme280'].get_pressure()
                    data['humidity'] = sensors['bme280'].get_humidity()
                    logging.debug(f"temperature: {data['temperature']}, pressure: {data['pressure']}, humidity: {data['humidity']}")
                    break
                except Exception as e:
                    logging.exception(f"Exception occured while trying to read bme280: {e}")
                    continue

        if 'wmonitor' and 'wspeed' in threads:
            if len(sensors['wmonitor'].wind_list) > 0:
                logging.debug('Setting stop event for wmonitor now')
                stop_event.set()
                logging.debug('Aquiring lock for wind_count_lock now')
                sensors['wmonitor'].wind_count_lock.acquire()
                data['wspeed'], data['wgusts'] = mean(sensors['wmonitor'].wind_list), max(sensors['wmonitor'].wind_list)
                logging.info(f"wind speed: {data['wspeed']} wind gusts: {data['wgusts']}")
                sensors['wmonitor'].wind_list.clear()
                sensors['wmonitor'].wind_count_lock.release()
                stop_event.clear()
            else:
                logging.info(f"wind monitor's wind list was not greater than zero: {len(sensors['wmonitor'].wind_list)}")
                data['wgusts'], data['wspeed'] = 0, 0

        if 'wdir' in threads:            
            data['wdir'] = sensors['wdir_monitor'].average() # Record average wind direction in degrees
            sensors['wdir_monitor'].wind_angles.clear() # Clear readings to average

        if 'rain' in threads:
            data['rainfall'] = sensors['rmonitor'].total_rain()
            sensors['rmonitor'].clear_total_rain()
        
        if 'air_monitor' in sensors:
            # wait for thread to complete before getting average readings
            threads['sds011'].join()
            data['pm25_avg'], data['pm10_avg'] = sensors['air_monitor'].average()
            sensors['air_monitor'].air_values['pm25_total'].clear()
            # Reset readings used for averages
            sensors['air_monitor'].air_values['pm10_total'].clear()

        th_makepacket = th.Thread(target=aprs.send_data(data, config))
        th_sensorsave = th.Thread(target=db.read_save_sensors(data))
            
        th_sensorsave.start()
        th_makepacket.start()
        th_sensorsave.join()
        th_makepacket.join()
        wait_delay(start_time, config['report_interval'])
