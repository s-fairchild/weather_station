from gpiozero import Button
from threading import Lock
from time import sleep

class RainMonitor:
    """ DEFAULT_RAIN_SENSOR = Button(5)
        BUCKET_SIZE = 0.2794 # mm
        BUCKET_SIZE = 0.011 # inches"""
    def __init__(self, BUCKET=0.011, button=Button(5)):
        self.tips = 0
        self.button = button
        self.bucket_size = BUCKET
        self.tips_lock = Lock()

    def bucket_tipped(self):
        while True:
            if not self.tips_lock.locked():
                self.tips_lock.acquire()
                self.tips += 1
                #print(f"Bucket tipped! Total rainfall calculated is {self.tips * self.bucket_size}")
                #TODO set above print statement as debug log level
                self.tips_lock.release()
                break

    def total_rain(self): # Convert tips to rain in hundreths of an inch and reset tips counter
        return self.tips * self.bucket_size

    def clear_total_rain(self):
        while True:
            if not self.tips_lock.locked():
                self.tips_lock.acquire()
                self.tips = 0
                self.tips_lock.release()
                break
            else:
                print("RainMonitor thread locked! Waiting 2 seconds to reset tips...")
                sleep(2)

    def monitor(self):
        self.button.when_pressed = self.bucket_tipped
