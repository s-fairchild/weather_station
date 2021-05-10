import board, busio, adafruit_si4713, digitalio, os
from playsound import playsound

class FM_Transmitter:
    def __init__(self, frequency=102300, rds=False, led=True, soundfile='/tmp/aprs_report.wav'):
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.si_reset = digitalio.DigitalInOut(board.D5)
            self.transmitter = adafruit_si4713.SI4713(self.i2c, reset=self.si_reset, timeout_s=0.5)
        except Exception as e:
            print(f"Exception occured while initilization of si4713 transmitter:\n\t{e}")

        # Specify the FM frequency to transmit on in kilohertz.
        # Datasheet says you can only specify 50khz steps
        #self.FREQUENCY_KHZ = 102300  # 102.300mhz
        self.FREQUENCY_KHZ = frequency
        self.transmitter.tx_frequency_khz = self.FREQUENCY_KHZ
        self.transmitter.tx_power = 0 # Transmist power output range is 88 - 115 dBuV, 0 is off
        self.led = led # Not implimented yet
        self.soundfile = soundfile # Static sound file name/location. Background script will rotate sound files.
        if rds is True:
            self.transmitter.configure_rds(0xADAF, station=b"WxStation", rds_buffer=b"Some WxStation text")

    def get_freq_noise(self):
        noise = self.transmitter.received_noise_level(self.FREQUENCY_KHZ)
        print(f"Noise at {0:0.3f} mhz: {1} dBuV".format(self.FREQUENCY_KHZ / 1000.0, noise))
    
    def get_audio_level(self):
        print(f'Audio level: {0} dB'.format(self.transmitter.input_level))
        print(f'Audio signal status: 0x{0:02x}'.format(self.transmitter.audio_signal_status))
    
    def scan_freq_noise(self):
        lowest_noise = 100 # Arbitrary number
        for f_khz in range(87500, 108000, 50):
            noise = self.transmitter.received_noise_level(f_khz)
            if noise < lowest_noise:
                lowest_noise = noise
                best_freq = f_khz
            print(f'{0:0.3f} mhz = {1} dBuV'.format(f_khz/1000.0, noise))
        print(f"Scan completed.\nBest FM Channel is {best_freq / 1000} MHz at noise level: {lowest_noise} dBuV")
    
    def manage_soundfile(self, packet, make=True):
        if make:
            cmd = f"echo -n {packet} | gen_packets -o {self.soundfile}"
            os.system(cmd)
        else:
            if os.path.isfile(self.soundfile):
                os.system(f'rm {self.soundfile}')
            else:
                print(f"File not found, cannot delete {self.soundfile}")
        
    def transmit(self, packet):
        if os.path.isfile(self.soundfile):
            self.manage_soundfile(packet)
            self.tx_power = 115 # Turn on transmitter with max power
            print("Transmitting at {0:0.3f} mhz".format(self.transmitter.tx_frequency_khz / 1000.0))
            print("Transmitter power: {0} dBuV".format(self.transmitter.tx_power))
            print("Transmitter antenna capacitance: {0:0.2} pF".format(self.transmitter.tx_antenna_capacitance))
            print("Starting transmission now...") 
            playsound(self.soundfile) # Play soundfile while transmitting
            self.tx_power = 0 # Turn off transmitter
            print("Transmission is over, turning off transmitter.")
            print(f"Deleting file {self.soundfile}")
        else:
            print(f"Sound file {self.soundfile} not found. transmission not sent.")
