import asyncio
import sys
import threading

from PyQt5.QtCore import QTimer
from main import calculate_millisecond

sys.path.append('../')
from res.preference import config


class TCPClient(threading.Thread):

    def __init__(self, ui):
        threading.Thread.__init__(self)
        ui.server_freq_apply.clicked.connect(lambda: self.server_timer.start(calculate_millisecond(
            #ui.server_freq.value(), ui.server_freq_unit.currentText())))
            config.settings['server']['freq'], config.settings['server']['unit'])))
        ui.led_switch_image.toggled.connect(lambda: self.loop.create_task(self.send_msg(self.create_msg(type='actuator'))))
        ui.fan_switch_image.toggled.connect(lambda: self.loop.create_task(self.send_msg(self.create_msg(type='actuator'))))
        ui.cs_switch.toggled.connect(lambda: self.loop.create_task(self.send_msg(self.create_msg(type='actuator'))))

        self.loop = asyncio.get_event_loop()
        self.loop.set_exception_handler(self.handle_exception)
        # self.server_timer = QTimer()
        # self.server_timer.timeout.connect(lambda: self.loop.create_task(self.send_msg(self.create_msg(type='sensor'))))
        # self.server_timer.start(calculate_millisecond(config.settings['server']['freq'], config.settings['server']['unit']))

    def handle_exception(self, context):
        print(str(context))

    def create_msg(self, type):
        if type == 'sensor':
            if config.is_sensing:
                msg = f'\x02O4{config.settings["PID"][:8]}|AT{config.indoor_temp[-1]:0=+5.1f}:ST-----:' \
                  f'AH{config.humid[-1]:0=4.1f}:LX--:CO{config.co2[-1]:04d}:NT{config.cs_temp[-1]:0=+5.1f}:' \
                  f'PH{config.ph[-1]:0=4.1f}:TD{config.tds[-1]:04d}:DO{config.cs_temp[-1]:0=4.1f}\x03'
            else:
                msg = f'\x02O4{config.settings["PID"][:8]}|AT-----:ST-----:' \
                      f'AH----:LX--:CO----:NT-----:PH----:TD----:DO----\x03'
        elif type == 'actuator':
            msg = f'\x02O6{config.settings["PID"][:8]}|L1{["X","O"][int(config.actuator_status["led"])]}L2-:' \
                  f'P1{["X","O"][int(config.actuator_status["cs"])]}P2-:'\
                  f'F1{["X","O"][int(config.actuator_status["fan"])]}F2-:'\
                  f'C1-C2-\x03'
        print(len(msg))
        return msg

    async def send_msg(self, message):
        try:
            reader, writer = await asyncio.open_connection(config.settings['server']['ip'],
                                                           config.settings['server']['port'])
            print('Send: %r' % message)
            writer.write(message.encode())

            data = await reader.read(100)
            print('Received: %r' % data.decode())

            writer.close()
            print('Close the socket')
        except Exception as e:
            print(str(e))
