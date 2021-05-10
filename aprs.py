from rainfall import RainMonitor
import aprslib, time
from math import trunc
from db import WeatherDatabase
from rainfall import RainMonitor
import logging

class SendAprs:
    def __init__(self, db, loglevel="logging.DUBUG"):
        self.db = db
        self.rmonitor = RainMonitor()
        logging.basicConfig(level=loglevel)
        
    # Convert temperature, wind direction, wind speed, and wind gusts to 3 digits
    def add_zeros(self, num):
        if num is not None:
            if num < 100 and num > 9: # Add 0 in front if temperature is between 0 and 99
                return f"0{num}"
            elif num < 9 and num >= 0: # add 00 in front if between 0 and 9
                return f"00{num}"
            elif num < 0 and num > -9:
                return f"00{num}"
            elif num < -9:
                return f"0{num}"
            else:
                return num
        else:
            return "000"

    def format_rain(self, rain):
        if rain is 0.0:
            return "000"
        else:
            rain1avg = str(round(float(rain), 2))
            rain1avg = rain1avg.replace('.', '')
        if rain1avg == "00" or "0":
            return "000"
        else:
            return rain1avg

    # Humidity must be 2 digits. If humidity is 100% assign value of 00
    def format_humidity(self, num):
        if num == 100:
            return "00"
        elif num <= 9:
            return self.add_zeros(num)
        else:
            return num

    def make_packet(self, data, config):
            tmp = data.copy() # Create copy so that original data dictionary is not modified
            tmp['pressure'] = trunc(round(tmp['pressure'], 2) * 10.) # shift decimal point to the left 1 and round
            tmp['temperature'] = self.add_zeros(round(tmp['temperature']))
            tmp['wspeed'] = self.add_zeros(round(tmp['wspeed']))
            tmp['wgusts'] = self.add_zeros(round(tmp['wgusts']))
            tmp['humidity'] = self.format_humidity(round(tmp['humidity']))
            tmp['ztime'] = time.strftime('%d%H%M', time.gmtime()) # Get zulu/UTC time

            all_rain_avgs = self.db.get_all_rain_avg()
            if self.format_rain(all_rain_avgs['1']) == 0.0 and self.rmonitor.tips == 0:
                tmp['rain1h'] = self.format_rain(all_rain_avgs['1'])
            elif self.rmonitor.tips > 0:
                tmp['rain1h'] = self.format_rain(self.rmonitor.tips)
            else:
                tmp['rain1h'] = self.format_rain(all_rain_avgs['1'])

            if self.format_rain(all_rain_avgs['24']) == 0.0 and self.rmonitor.tips == 0:
                tmp['rain24h'] = self.format_rain(all_rain_avgs['24'])
            elif self.rmonitor.tips > 0:
                tmp['rain24h'] = self.format_rain(self.rmonitor.tips)
            else:
                tmp['rain24h'] = self.format_rain(all_rain_avgs['24'])

            if self.format_rain(all_rain_avgs['00']) == 0.0 and self.rmonitor.tips == 0:
                tmp['rain00m'] = self.format_rain(all_rain_avgs['00'])
            elif self.rmonitor.tips > 0:
                tmp['rain00m'] = self.format_rain(self.rmonitor.tips)
            else:
                tmp['rain00m'] = self.format_rain(all_rain_avgs['00'])
            del(all_rain_avgs)

            tmp['wdir'] = self.add_zeros(tmp['wdir'])

            self.packet = f"{config['aprs']['callsign']}>APRS,TCPIP*:@{tmp['ztime']}z{config['aprs']['longitude']}/{config['aprs']['latitude']}_{tmp['wdir']}/{tmp['wspeed']}g{tmp['wgusts']}t{tmp['temperature']}r{tmp['rain1h']}p{tmp['rain24h']}P{tmp['rain00m']}b{tmp['pressure']}h{tmp['humidity']}{config['aprs']['comment']}"
            del(tmp) # Clean up temporary dictionary
            return self.packet
            
    def send_data(self, data, config):
        packet = self.make_packet(data, config)
        if config.getboolean('aprs', 'sendall'):
            for server in config['servers']:
                AIS = aprslib.IS(config['aprs']['callsign'], config['aprs']['passwd'], config['servers'][server], config['aprs']['port'])
                try:
                    AIS.connect()
                    AIS.sendall(packet)
                    print(f"Packet transmitted to {config['servers'][server]} at {time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC time")
                    break
                except Exception as e:
                    print(f"An exception occured trying to send packet to {server}\nException: {e}")
                finally:
                    AIS.close()
            transmitted = 1
        else:
            transmitted = 0
        self.db.read_save_packet(packet[:-len(config['aprs']['comment'])], transmitted) # Store packet in database without comment field
