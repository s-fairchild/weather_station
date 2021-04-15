import mariadb as db
from time import sleep

class WeatherDatabase:
    def __init__(self, user="wxstation", password="password1", host="127.0.0.1", port=3306, database="weather"):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.database = database                

    def db_connect(self):
        for i in range(1, 4): # Retry 3 times increasing delay by 10 seconds each time
            delay = i * 10
            try:
                conn = db.connect(
                    user = self.user,
                    password = self.password,
                    host = self.host,
                    port = self.port,
                    database = self.database
                )
                return conn
            except db.Error as e:
                print(f"Error connecting to MariaDB Server: {e}\n\t Retry number {i}\n\t Retrying in {delay} seconds...")
                sleep(delay)
                continue

    def read_save_sensors(self, data):
        sensors_insert = """INSERT INTO sensors(stationid, ambient_temperature, wind_direction, wind_speed, wind_gust_speed, humidity, air_pressure, rainfall, pm25, pm10) 
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""
        data_tuple = (data['callsign'], data['temperature'], data['wdir'], data['wspeed'], data['wgusts'], data['humidity'], data['pressure'], data['rainfall'], data['pm25'], data['pm10'])
        self.conn = self.db_connect()
        cur = self.conn.cursor()
        cur.execute(sensors_insert, data_tuple)
        self.conn.commit(); self.conn.close()

    def read_save_packet(self, packet, transmitted):
        packet_insert = """INSERT INTO packets(packet, transmitted) 
        VALUES(?, ?);"""
        data_tuple = (packet, transmitted)
        conn = self.db_connect()
        cur = conn.cursor()
        cur.execute(packet_insert, data_tuple)
        conn.commit(); conn.close()

    def rain_avg(self, hours): # valid arguements are 00 for since midnight, 1 for past hour, 24 for past 24 hours
        if hours == 00: # Queries average rainfall between now and 00:00 of today
            query = """SELECT AVG(rainfall) FROM sensors where created between CURRENT_DATE() AND NOW() AND rainfall!=0;"""
        elif hours == 1 or 24: # Queries average ranfall for the past hour or 24 hours
            query = f"SELECT AVG(rainfall) FROM sensors WHERE created >= now() - INTERVAL {hours} HOUR AND rainfall!=0;"

        conn = self.db_connect(); cur = conn.cursor()
        cur.execute(query)
        row = cur.fetchone()
        conn.close()
        return 0.0 if row[0] is None else row[0] # Rainfall readings of 0.000 will return NULL, return 0 if NULL