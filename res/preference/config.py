indoor_temp = [1 for i in range(10)]
humid = [3+i for i in range(10)]
co2 = [4+i for i in range(10)]
cs_temp = [0 for i in range(10)]
ph = [0 for i in range(10)]
do = [0 for i in range(10)]
tds = [0 for i in range(10)]

# TODO cs와 pump 네이밍 통일하기
actuator_status = {'led': False, 'fan': False, 'cs': False}
settings = {}

last_sensing = '00 : 00 : 00'

