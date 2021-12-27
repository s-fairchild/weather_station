from gpiozero import MCP3008
from time import sleep
import math, logging

VIN = 3.3 # Input voltage can be 5.0 or 3.3
ADC_CHANNEL= 0
R1 = 10_000
VANE_RESISTANCES = [ # Resistor values inside wind vain
33_000,
6570,
8200,
891,
1000,
688,
2200,
1410,
3900,
3140,
16_000,
14_120,
120_000,
42_120,
64_900,
21_880]

class WindDirectionMonitor:
    def __init__(self, resistances=VANE_RESISTANCES, vin=VIN, R1=R1, adc_channel=ADC_CHANNEL):
        self.wind_angles = [] # List to store wind direction in degrees every 5 seconds, cleared after every transmission
        self.R1 = R1 # Static resistor value on board
        self.resistances = resistances
        self.failed_count = 0 #TODO log failed count and voltage from failure in database
        self.vin = vin
        self.adc_channel = adc_channel

    def voltage_divider(self, r1, r2, vin):
        vout = (vin * r2) / (r1 + r2)
        return round(vout, 1)

    def populate_V2D(self):
        degrees, volts = 0, {}
        for r2 in self.resistances:
            voltage = self.voltage_divider(self.R1, r2, self.vin)
            volts[voltage] = degrees
            degrees += 22.5 # Degrees between each resistor/reed switch in wind vane
        return volts

    def average(self):
        self.wind_angles
        avg = 0.0
        sin_sum, cos_sum = 0.0, 0.0
        try:
            for angle in self.wind_angles:
                r = math.radians(angle)
                sin_sum += math.sin(r)
                cos_sum += math.cos(r)
            
            flen = float(len(self.wind_angles))
            s, c = sin_sum / flen, cos_sum / flen
            arc = math.degrees(math.atan(s / c))

            if s > 0 and c > 0:
                avg = arc
            elif c < 0:
                avg = arc + 180
            elif s < 0 and c > 0:
                avg = arc + 360
            return 0.0 if avg == 360 else round(avg)
        except ZeroDivisionError as e:
            logging.exception(f"ZeroDivisionError: {e}\nWind direction could not be calculated!")

    def monitor(self):
        adc, volts = MCP3008(channel=self.adc_channel), self.populate_V2D()
        while True:
            vane_voltage = round(adc.value * self.vin, 1)
            if vane_voltage in volts:
                self.wind_angles.append(volts[vane_voltage])
            else:
                self.failed_count += 1
                logging.error(f"Unkown wind direction voltage: {vane_voltage}\n\tReading was not recorded\n\tTotal readings not recorded: {self.failed_count}")
            sleep(5)
