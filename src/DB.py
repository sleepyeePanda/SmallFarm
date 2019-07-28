import sqlite3

INSERT_DATA = 'INSERT INTO data(time, Temp, Humid, CO2, pH, DO, TDS) VALUES(?, ?, ?, ?, ?, ?, ?)'
FETCH_DATA = 'SELECT '

def connect():
    connection = sqlite3.connect('sensor_data.db')
    return connection

def disconnect(connection):
    if connection and connection.open:
        connection.close()

def insert_data():
    try:
        connection = connect()
        connection.cursor().executemany(INSERT_DATA, )
        connection.commit()
    except Exception as e:
        print(str(e))
    finally:
        disconnect(connection)

def fetch_data():
    try:
        connection = connect()
        connection.cursor().execute()
