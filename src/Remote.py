import asyncio
from PyQt5 import QtCore
import random

class UartProtocol(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        self.rcvParser = RcvParser()

    def connection_made(self, transport):
        self.transport = transport
        print('port opened', transport)
        transport.serial.rts = False
        self.rcvParser.transport = transport

    def data_received(self, data):
        message = data.decode()
        self.rcvParser.parsing(message)

    def connection_lost(self, exc):
        print('COM2 port closed')
        # self.transport.loop.stop()


class RcvParser(QtCore.QObject):

    def __init__(self):
        super().__init__()
        self.init_protocol()
        self.transport = None

    def parsing(self, pkt):
        self.info = pkt.strip('\x02\x03\n\r')
        # print('remote: data parsed', self.info)
        cmd = self.info[0]
        try:
            func = self.protocol.get(cmd)
            return func(self.info)
        except Exception as e:
            print(str(e))

    def send_msg(self, msg):
        if self.transport is not None:
            try:
                self.transport.write(msg.encode())
                print(msg)
                return True
            except Exception as e:
                print(str(e), 'occurred in remote')
                return False
        else:
            print('Remote Not Connected')

    def send_air_status(self, info):
        air_temp = round(random.uniform(10.0, 99.9), 1)
        humid = random.randrange(10, 99)
        co2 = random.randrange(1000, 2000)
        self.send_msg('\x02T1T+'+str(air_temp)+'H'+str(humid)+'C'+str(co2)+'I000\x03\x0A\x0D')

    def send_water_status(self, info):
        water_temp = round(random.uniform(10.0, 99.9), 1)
        do = round(random.uniform(10.0, 99.0),  1)
        ph = round(random.uniform(10.0, 14.0), 1)
        tds = random.randrange(1000, 2000)
        self.send_msg('\x02W1T+' + str(water_temp) + 'D' + str(do) + 'P' + str(ph) + 'T' + str(tds) + '\x03\x0A\x0D')

    def send_fan(self, info):
        if info[2] == 'S':
            self.send_msg('\x02F1FO\x03\x0A\x0D')
        else:
            self.send_msg(info)

    def send_led(self, info):
        if info[3] == 'S':
            self.send_msg('\x02L011555R555G555B555\x03\x0A\x0D')
        else:
            self.send_msg(info)

    def init_protocol(self):
        self.protocol = {'T': self.send_air_status,
                         'W': self.send_water_status,
                         'L': self.send_led,
                         'F': self.send_fan}

