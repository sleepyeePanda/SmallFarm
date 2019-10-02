import numpy


# msg = f'\x02O4{config.settings["PID"][:8]}|AT{config.indoor_temp[-1]:0>+5.1f}:ST-----:AH{config.humid[-1]:0>+5.1f}:'\
#               f'LX--:CO{config.indoor_temp[-1]:0>4d}:NT{config.cs_temp[-1]:+.1f}: '


# indoor_temp, cs_temp, ph, do
float_values = numpy.arange(0, 100, 0.1)
# tds, co2
int_values = numpy.arange(0, 10000)

humids = numpy.arange(0, 99, 1)


# for value in float_values:
#     print(f'{value:0=+5.1f}')

# for value in int_values:
#     print(f'{value:04d}')

for humid in humids:
    print(f'{humid:0=+5.1f}')


