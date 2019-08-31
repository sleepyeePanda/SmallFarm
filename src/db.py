import sqlite3
queries = {'INSERT': {'AIR': 'INSERT INTO sensored_data(datetime, INDOOR_TEMP, HUMID, CO2) VALUES(?, ?, ?, ?)',
                      'WATER': 'INSERT INTO sensored_data(datetime, CS_TEMP, pH, DO, TDS) VALUES(?, ?, ?, ?, ?)'},
           'FETCH': {'AIR': 'SELECT avg(datetime), avg(INDOOR_TEMP), avg(HUMID), avg(CO2) from sensored_data',
                     'WATER': 'SELECT avg(datetime), avg(CS_TEMP), avg(pH), avg(DO), avg(TDS) from sensored_data'},
           'by_week': 'GROUP BY strftime("%Y-%W",DateTime) ORDER BY DateTime DESC LIMIT 48',
           'by_month': 'GROUP BY strftime("%Y-%m",DateTime) ORDER BY DateTime DESC LIMIT 48'}


def insert_data(data_type, data):
    try:
        connection = sqlite3.connect('../res/sensor_data.db')
        connection.cursor().execute(queries['INSERT'][data_type], data)
        connection.commit()
    except Exception as e:
        print(str(e))
    finally:
        connection.close()


def fetch_data(option, data):
    try:
        connection = sqlite3.connect('sensor_data.db')
        connection.cursor().execute(queries['FETCH']['AIR']+queries[option], data)
        connection.fetchall()
        connection.cursor().exceute(queries['FETCH']['WATER']+queries[option], data)
        connection.fetchall()
        return
    except Exception as e:
        print(str(e))
    finally:
        if connection and connection.open:
            connection.close()
