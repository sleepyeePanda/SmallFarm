temp = [0 for i in range(10)]
humid = [0 for i in range(10)]
co2 = [0 for i in range(10)]
ph = [0 for i in range(10)]
do = [0 for i in range(10)]
tds = [0 for i in range(10)]

actuator_status = {'led': False, 'fan': False, 'cs': False}
settings = {}

last_sensing = '00 : 00 : 00'
