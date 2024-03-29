import mariadb as db
from time import sleep
import logging

class WeatherDatabase:
    def __init__(self, user="wxstation", password="password", host="127.0.0.1", port=3306, database="weather"):
        # Set custom options if given, use defaults if not
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.database = database

    def db_connect(self):
        for i in range(1, 4): # Retry 3 times increasing delay by 10 seconds each time
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
                # Increase delay by 10 seconds
                delay = i * 10
                logging.critical(f"Error connecting to MariaDB Server: {e}\n\t Retry number {i}\n\t Retrying in {delay} seconds...")
                sleep(delay)
                continue

    def read_save_sensors(self, data):
        # Create query to insert data into database
        sensors_insert = """INSERT INTO sensors(stationid, ambient_temperature, wind_direction, wind_speed, wind_gust_speed, humidity, air_pressure, rainfall, pm25, pm10) 
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""
        # Create tuple to combine with insert statement
        data_tuple = (data['callsign'], data['temperature'], data['wdir'], data['wspeed'], data['wgusts'], data['humidity'], round(data['pressure'], 2), data['rainfall'], data['pm25_avg'], data['pm10_avg'])
        # Connect to database
        conn = self.db_connect()
        cur = conn.cursor()
        # Execute insert statement
        cur.execute(sensors_insert, data_tuple)
        conn.commit()
        conn.close()

    def rain_avg(self, hours):
        """valid arguements are 00 for since midnight, 1 for past hour, 24 for past 24 hours"""
        if hours == 00:
            # Queries average rainfall between now and 00:00 of today
            query = """SELECT ROUND(AVG(rainfall), 3) FROM sensors where created between CURRENT_DATE() AND NOW();"""
        elif hours == 1 or 24:
            # Queries average rainfall for the past hour or 24 hours
            query = f"SELECT ROUND(AVG(rainfall), 3) FROM sensors WHERE created <= now() - INTERVAL {hours} HOUR;"
        else:
            raise ValueError("rain average hours must be 00, 1, or 24.")

        conn = self.db_connect()
        cur = conn.cursor()
        cur.execute(query)
        row = cur.fetchone()
        if row[0] is None:
            logging.debug(f"Query returned None: {query}")
            query = """SELECT rainfall FROM sensors ORDER BY id DESC LIMIT 1;"""
            logging.debug(f"Running Query: {query}")
            cur.execute(query)
            latest = cur.fetchone()
            conn.close()
            logging.debug(f"Returned: {latest[0]}")
            return latest[0]
        else:
            conn.close()
            logging.debug(f"Query successful: {query}\nReturned row: {row[0]}")
            return row[0]

    def get_all_rain_avg(self):
        all_rain_avgs = {}
        for hour in [ '00', '1', '24' ]:
            all_rain_avgs[hour] = self.rain_avg(hour)
        logging.debug(f"\n\nRain averages collected:\nRain from now to 00:00: {all_rain_avgs['00']}")
        logging.debug(f"Rain from the past hour: {all_rain_avgs['1']}")
        logging.debug(f"Rain from the past 24 hours: {all_rain_avgs['24']}\n")
        return all_rain_avgs