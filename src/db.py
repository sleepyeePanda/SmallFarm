import sqlite3
queries = {'INSERT': {'AIR': 'INSERT INTO SENSORED_DATA(datetime, INDOOR_TEMP, HUMID, CO2) VALUES(?, ?, ?, ?)',
                      'WATER': 'INSERT INTO SENSORED_DATA(datetime, CS_TEMP, pH, DO, TDS) VALUES(?, ?, ?, ?, ?)'},
           'FETCH': {'AIR': 'SELECT avg(INDOOR_TEMP), avg(HUMID), avg(CO2) from SENSORED_DATA ',
                     'WATER': 'SELECT avg(CS_TEMP), avg(DO), avg(pH), avg(TDS) from SENSORED_DATA '},
           'by_week': 'GROUP BY strftime("%Y-%W",datetime) ORDER BY DateTime DESC LIMIT 48',
           'by_month': 'GROUP BY strftime("%Y-%m",datetime) ORDER BY DateTime DESC LIMIT 48'}


def insert_data(data_type, data):
    try:
        connection = sqlite3.connect('../res/sensor_data.db')
        connection.cursor().execute(queries['INSERT'][data_type], data)
        connection.commit()
    except Exception as e:
        print(str(e))
    finally:
        connection.close()


def fetch_data(data_type, option):
    try:
        connection = sqlite3.connect('../res/sensor_data.db')
        cursor = connection.cursor()
        cursor.execute(queries['FETCH'][data_type]+queries[option])
        rows = cursor.fetchall()
        if data_type == 'AIR':
            indoor_temp = [row[0] for row in rows]
            humid = [row[1] for row in rows]
            co2 = [row[2] for row in rows]
            return [indoor_temp, humid, co2]
        else:
            cs_temp = [row[0] for row in rows]
            do = [row[1] for row in rows]
            ph = [row[2] for row in rows]
            tds = [row[3] for row in rows]
            return [cs_temp, do, ph, tds]
    except Exception as e:
        print(str(e))
    finally:
        connection.close()
