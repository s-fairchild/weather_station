import sqlite3
from datetime import date, datetime, time

connect_mes = "Successfully Connected to SQLite database wxdata.db"
close_mes = "The SQLite connection is closed"
insert_mes = "Record inserted successfully into"

def make_table():
    sqlite_insert_query1 = """ CREATE TABLE IF NOT EXISTS weather(
                                ID INTEGER PRIMARY KEY,
                                SampleDateTime TEXT NOT NULL,
                                StationID TEXT,
                                TemperatureF NUMERIC NOT NULL,
                                Pressure NUMERIC NOT NULL,
                                Humidity NUMERIC NOT NULL,
                                PM25 NUMERIC,
                                PM10 NUMERIC,
                                AQI
                            );"""
    sqlite_insert_query2 = """ CREATE TABLE IF NOT EXISTS packets(
                                ID INTEGER PRIMARY KEY,
                                SampleDate TEXT NOT NULL,
                                packet TEXT NOT NULL,
                                Sent INTEGER NOT NULL
                            );"""
    try:
        sqliteConnection = sqlite3.connect('wxdata.db')
        cursor = sqliteConnection.cursor()
        print(connect_mes)
        cursor.execute(sqlite_insert_query1)
        print(f"weather table successfully created")                                                                        
        sqliteConnection.commit()
        cursor.execute(sqlite_insert_query2)
        sqliteConnection.commit()
        print(f"{cursor.rowcount} packets table successfully created")                                                                        
    except sqlite3.Error as error:
            print(f"CRITICAL: Failed to create weather table: {error}")
    finally:
            if (sqliteConnection):
                sqliteConnection.close()
               # print("The SQLite connection is closed")

def read_save_enviro(data):
  try:
        now = datetime.now()
        sqliteConnection = sqlite3.connect('wxdata.db')
        cursor = sqliteConnection.cursor()
        #print(connect_mes)
        weather_insert = """INSERT INTO weather(SampleDateTime, StationID, TemperatureF, Pressure, Humidity, pm25, pm10) 
        VALUES(?, ?, ?, ?, ?, ?, ?);"""
        data_tuple = (now, data['callsign'], data['temperature'], data['pressure'], data['humidity'], data['pm25'], data['pm10'])
        cursor.execute(weather_insert, data_tuple)
        sqliteConnection.commit()
        print(f"{cursor.rowcount} {insert_mes} weather table")
        cursor.close()
  except sqlite3.Error as error:
        print(f"CRITICAL: Failed to insert data into sqlite weather table: {error}")
  finally:
        if (sqliteConnection):
            sqliteConnection.close()
            #print("The SQLite connection is closed")

def read_save_packet(data):
    try:
        now = datetime.now()
        sqliteConnection = sqlite3.connect('wxdata.db')
        cursor = sqliteConnection.cursor()
        #print(connect_mes)
        packet_insert = """INSERT INTO packets(SampleDate, packet, Sent) 
        VALUES(?, ?, ?);"""
        data_tuple = (now.date(), data['packet'], data['sent'])
        cursor.execute(packet_insert, data_tuple)
        sqliteConnection.commit()
        print(f"{cursor.rowcount} {insert_mes} packet table")
        cursor.close()

    except sqlite3.Error as error:
          print(f"CRITICAL: Failed to insert data into sqlite packets table: {error}")
    finally:
        if (sqliteConnection):
          sqliteConnection.close()
          #print(close_mes)
