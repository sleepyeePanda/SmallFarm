# coding=utf-8
import asyncio
import datetime
import glob
import itertools
import json
from functools import partial
import serial
from threading import Thread
import time


from PyQt5 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg
import serial_asyncio
import sys


import db
import client

sys.path.append('../')
from res.ui.Ui_design import Ui_MainWindow
from res.preference import config
# TODO remote 임포트 삭제하기
# import Remote

__status__ = '2019.7.29'


class UartCom:
    def __init__(self):

        ui.connect.clicked.connect(lambda: self.connect_serial(str(ui.coms.currentText())))
        ui.disconnect.clicked.connect(partial(self.disconnect_serial, True))
        ui.refresh.pressed.connect(partial(self.get_com, 0, None))

        # 작동기
        ui.led_switch.pressed.connect(partial(self.control_led_power, init=False))
        ui.fan_switch.pressed.connect(partial(self.control_fan_power, init=False))
        ui.cs_switch.toggled.connect(lambda x: self.control_cs_power(toggled=x))
        ui.cs_switch.toggled.connect(lambda x: config.actuator_status.update({'cs': x}))
        ui.blackout_check_button.pressed.connect(partial(self.check_blackout))

        # fan 자동 제어
        self.fan_freq_timer = QtCore.QTimer()
        self.fan_act_timer = None
        self.fan_freq_timer.timeout.connect(partial(self.control_fan_power, order=True))
        ui.fan_auto.toggled.connect(lambda x: self.control_fan_power(order=True) if x else self.stop_timers('fan'))
        # cs 자동 제어
        self.cs_freq_timer = QtCore.QTimer()
        self.cs_act_timer = None
        self.cs_freq_timer.timeout.connect(partial(self.control_cs_power, order=True))
        ui.cs_auto.toggled.connect(lambda x: self.control_cs_power(order=True) if x else self.stop_timers('cs'))

        self.com = None
        self.uart = None
        self.loop = None
        self.local = None
        # TODO remote COM 삭제하기
        # self.remote = None
        self.thread = None

    def get_com(self, waiting=0, prev_com=None):
        """사용 가능한 시리얼 포트 화면에 추가"""
        time.sleep(waiting)
        connectable_ports = []
        connectable_ports.extend(self.serial_ports())
        print(connectable_ports)
        ui.coms.clear()
        if not prev_com and not connectable_ports:
            manager.alertSignal.emit('Please try again after checking out connection.', False)
            return None
        elif prev_com in connectable_ports:
            ui.coms.addItem(prev_com)
            ui.coms.setCurrentIndex(0)
            return prev_com
        else:
            for comport in connectable_ports:
                ui.coms.addItem(comport)
            return ui.coms.currentText()

    def serial_ports(self):
        """사용 가능한 시리얼 포트 검색"""
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal '/dev/tty'
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')
        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        return result

    def run(self, loop):
        try:
            loop.run_forever()
        except Exception as e:
            print(str(e))
        finally:
            loop.stop()
            loop.close()
        print('Closed Uart Thread!')

    def handle_exception(self, loop, context):
        # TODO Remote COM 삭제하기
        # self.remote.transport.loop.stop()
        # self.remote.transport.close()
        # self.remote.transport = None
        self.disconnect_serial(by_user=False)
        manager.alertSignal.emit(f"Please press 'Retry' after checking out connection if you want to reconnect {uartCom.com}.", True)
        print(str(context))

    def connect_serial(self, connectable_com):
        """시리얼 연결 설정"""
        if connectable_com:
            self.com = connectable_com
            print(self.com)
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.set_exception_handler(self.handle_exception)
            try:
                self.local = serial_asyncio.create_serial_connection(self.loop, lambda: UartProtocol(self), self.com,
                                                                     baudrate=115200)
                # self.local = serial_asyncio.create_serial_connection(self.loop, lambda: UartProtocol(self), "COM3",
                #                                                      baudrate=115200)
                # TODO remote COM 삭제하기
                # self.remote = serial_asyncio.create_serial_connection(self.loop, lambda: Remote.UartProtocol(), 'COM2',
                #                                                     baudrate=115200)
                print(self.com + ' connected')
            except Exception as e:
                print(str(e))

            # TODO remote COM 삭제하기
            # self.loop.run_until_complete(self.remote)
            self.loop.run_until_complete(self.local)

            self.thread = Thread(target=self.run, args=(self.loop,))
            self.thread.setDaemon(True)
            self.thread.start()

            self.initialize_actuator()
            valueUpdater.sensor_timer.start(calculate_millisecond(ui.sensor_freq.value(), ui.sensor_freq_unit.currentText()))

            ui.connect.setText('connected')
            ui.connect.setChecked(True)
            ui.connect.setEnabled(False)
            ui.disconnect.setEnabled(True)
            ui.refresh.setEnabled(False)
            ui.coms.setEnabled(False)
        else:
            ui.connect.setChecked(False)

    def stop_timers(self, actuator):
        if actuator == 'fan':
            if self.fan_act_timer:
                self.fan_act_timer.stop()
            if self.fan_freq_timer:
                self.fan_freq_timer.stop()
        elif actuator == 'cs':
            if self.cs_act_timer:
                self.cs_act_timer.stop()
            if self.cs_freq_timer:
                self.cs_freq_timer.stop()

    def reset(self):
        """작동기 상태 초기화"""
        self.stop_timers('fan')
        self.stop_timers('cs')
        config.actuator_status.update({'led': False, 'fan': False})
        for actuator in [ui.led_switch_image, ui.fan_switch_image, ui.cs_switch]:
            actuator.setChecked(False)
        config.is_sensing = False

    def disconnect_serial(self, by_user=True):
        """시리얼 연결 해제"""
        valueUpdater.sensor_timer.stop()
        self.reset()
        if self.uart is not None:
            self.uart.loop.stop()
            self.uart.close()
            self.uart = None
        # TODO remote COM 삭제하기
        # if self.remote is not None:
        #     self.remote.loop.stop()
        #     self.remote.close()
        #     self.remote = None
        # ui.coms.clear()
        ui.connect.setChecked(False)
        ui.connect.setText('connect')
        ui.connect.setEnabled(True)
        ui.disconnect.setEnabled(False)
        ui.refresh.setEnabled(True)
        ui.coms.setEnabled(True)
        if by_user:
            self.get_com(waiting=0.3)

    def initialize_actuator(self):
        """작동기 최초 상태 읽기"""
        if self.uart is not None:
            self.control_led_power(init=True)
            time.sleep(0.2)
            self.control_fan_power(init=True)
            time.sleep(0.2)
            self.check_blackout()

    def send_msg(self, msg):
        """데이터 송신"""
        if self.uart is not None:
            try:
                self.uart.write(msg.encode())
                print(msg)
                return True
            except Exception as e:
                print(str(e))
                manager.alertSignal.emit('Please try again after checking out connection.', False)
                return False
        else:
            manager.alertSignal.emit('Please try again after checking out connection.', False)
            print('Not Connected')
            return False

    def check_water_status(self):
        """양액 온도, DO, pH, TDS 상태 읽기"""
        self.send_msg('\x02W1WATER?\x03\x0A\x0D')
        time.sleep(0.2)

    def check_air_status(self):
        """실내 온도, Humid, Co2 상태 읽기"""
        self.send_msg('\x02T1TEMP?\x03\x0A\x0D')
        time.sleep(0.2)

    def control_led_power(self, init=False, order=None):
        """led 작동 제어"""
        msgs = {True: '\x02L01W000R555G555B555\x03\x0A\x0D', False: '\x02L0W1111R555G555B555\x03\x0A\x0D'}
        if order:
            self.send_msg(msgs[not order])
        else:
            self.send_msg('\x02L01ST\x03\x0A\x0D' if init else msgs[config.actuator_status['led']])

    def control_fan_power(self, init=False, order=None):
        """fan 작동 제어"""
        msgs = {True: '\x02F1FX\x03\x0A\x0D', False: '\x02F1FO\x03\x0A\x0D'}
        if order == True:
            msg = msgs[False]
            self.fan_act_timer = QtCore.QTimer()
            self.fan_act_timer.setSingleShot(True)
            self.fan_act_timer.timeout.connect(lambda: self.control_fan_power(order=False))
            # hours*60*60*1000msec
            # minutes*60*1000msec
            self.fan_act_timer.start(config.settings['fan']['act_min']*60000)
            self.fan_freq_timer.start(config.settings['fan']['freq_hour']*3600000)
        elif order == False:
            msg = msgs[True]
        else:
            msg = msgs[config.actuator_status['fan']]
        self.send_msg('\x02F1ST\x03\x0A\x0D' if init else msg)

    def control_cs_power(self, order=None, toggled=None):
        """cs 작동 제어"""
        msgs = {True: '\x02NSTOP\x03\x0A\x0D', False: '\x02NSTART\x03\x0A\x0D'}
        if order == True:
            msg = msgs[False]
            ui.cs_switch.setChecked(True)
            self.cs_act_timer = QtCore.QTimer()
            self.cs_act_timer.setSingleShot(True)
            self.cs_act_timer.timeout.connect(lambda: self.control_cs_power(order=False))
            # 1 hours = 60*60*1000 msec
            # 1 minutes = 60*1000 msec
            self.cs_act_timer.start(config.settings['cs']['act_min']*60000)
            self.cs_freq_timer.start(config.settings['cs']['freq_hour']*3600000)
        elif order == False:
            msg = msgs[True]
            ui.cs_switch.setChecked(False)
        else:
            msg = msgs[not toggled]
        self.send_msg(msg)

    def check_blackout(self):
        pass


class UartProtocol(asyncio.Protocol):
    def __init__(self, uartCom):
        super().__init__()
        self.uartCom = uartCom
        self.rcvParser = RcvParser()

    def connection_made(self, transport):
        self.uartCom.uart = transport
        print('port opened', transport)
        self.uartCom.uart.serial.rts = False

    def data_received(self, data):
        message = data.decode()
        self.rcvParser.parsing(message)

    def connection_lost(self, exc):
        print('port closed')


class RcvParser(QtCore.QObject):
    updateStateSignal = QtCore.pyqtSignal()
    updateActuatorSignal = QtCore.pyqtSignal()
    updateGraphSignal = QtCore.pyqtSignal(str, str)
    saveDataSignal = QtCore.pyqtSignal(str, list)

    def __init__(self):
        super().__init__()
        self.init_protocol()
        self.updateStateSignal.connect(manager.update_status)
        self.updateActuatorSignal.connect(manager.update_actuator)
        self.updateGraphSignal.connect(manager.update_graph)
        self.saveDataSignal.connect(db.insert_data)

    def parsing(self, pkt):
        """수신 데이터 파싱"""
        info = pkt.strip('\x02\x03\n\r')
        print('local: data parsed', info)
        cmd = info[0]
        try:
            func = self.protocol.get(cmd)
            return func(info)
        except Exception as e:
            print(str(e))

    def rcv_air_status(self, info):
        """실내 온도, Humid, CO2 상태 파싱
           파싱 예외 발생 시 이전 상태 데이터 사용"""
        sensing_datetime = datetime.datetime.now()
        config.last_sensing = sensing_datetime.strftime('%H : %M : %S')
        try:
            indoor_temp = float(info[3:8])
        except Exception as e:
            print(str(e))
            indoor_temp = config.indoor_temp[-1]
        try:
            humid = int(info[9:11])
        except Exception as e:
            print(str(e))
            humid = config.humid[-1]
        try:
            co2 = int(info[12:16])
        except Exception as e:
            print(str(e))
            co2 = config.co2[-1]
        # 실내 온도, Humid, CO2 상태 업데이트
        self.updateStateSignal.emit()
        # 그래프 업데이트
        if ui.page_stackedWidget.currentIndex() == 1 and ui.air_day.isChecked():
            self.updateGraphSignal.emit('air', '')
        # 실내 온도, Humid, CO2 상태 데이터 추가
        for data, status in zip([config.indoor_temp, config.humid, config.co2], [indoor_temp, humid, co2]):
            data.append(status)
            data.pop(0)
        config.is_sensing = True
        # DB에 실내 온도, Humid, CO2 상태 데이터 저장
        self.saveDataSignal.emit('AIR', [sensing_datetime, indoor_temp, humid, co2])

    def rcv_water_status(self, info):
        """양액 온도, DO, pH, TDS 상태 파싱
           파싱 예외 발생 시 이전 상태 데이터 사용"""
        sensing_datetime = datetime.datetime.now()
        config.last_sensing = sensing_datetime.strftime('%H : %M : %S')
        try:
            cs_temp = float(info[3:8])
        except Exception as e:
            print(str(e))
            cs_temp = config.cs_temp[-1]
        try:
            do = float(info[9:13])
        except Exception as e:
            print(str(e))
            do = config.do[-1]
        try:
            ph = float(info[14:18])
        except Exception as e:
            print(str(e))
            ph = config.ph[-1]
        try:
            tds = int(info[19:23])
        except Exception as e:
            print(str(e))
            tds = config.tds[-1]
        # 양액 온도, DO, pH, TDS 상태 업데이트
        self.updateStateSignal.emit()
        # 그래프 업데이트
        if ui.page_stackedWidget.currentIndex() == 1 and ui.water_day.isChecked():
            self.updateGraphSignal.emit('water', '')
        # 양액 온도, DO, pH, TDS 상태 데이터 추가
        for data, status in zip([config.cs_temp, config.do, config.ph, config.tds], [cs_temp, do, ph, tds]):
            data.append(status)
            data.pop(0)
        config.is_sensing = True
        # DB에 양액 온도, DO, pH, TDS 상태 데이터 저장
        self.saveDataSignal.emit('WATER', [sensing_datetime, cs_temp, do, ph, tds])

    def rcv_led(self, info):
        """led 상태 데이터 파싱"""
        try:
            config.actuator_status['led'] = False if info[4] == '0' else True
        except Exception as e:
            print(str(e))
        # 작동기 상태 업데이트
        self.updateActuatorSignal.emit()

    def rcv_fan(self, info):
        """fan 상태 데이터 파싱"""
        try:
            config.actuator_status['fan'] = True if info[3] == 'O' else False
        except Exception as e:
            print(str(e))
        # 작동기 상태 업데이트
        self.updateActuatorSignal.emit()

    def rcv_blackout_check(self, info):
        """정전 여부 데이터 파싱"""
        try:
            if info[4] == 'O':
                manager.alertSignal.emit('Black out occurred!', False)
        except Exception as e:
            print(str(e))

    def init_protocol(self):
        self.protocol = {'T': self.rcv_air_status,
                         'W': self.rcv_water_status,
                         'L': self.rcv_led,
                         'F': self.rcv_fan,
                         # TODO 정전 프로토콜 추가하기
                         '': self.rcv_blackout_check}


class TimeUpdater(QtCore.QThread):
    def __init__(self):
        super().__init__()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.change_and_check_led_time)
        self.timer.start(1000)
        self.start()

    def change_and_check_led_time(self):
        """현재 시각 변경 및 led 자동 제어"""
        date_time = QtCore.QDateTime.currentDateTime()
        ui.cur_time.setText(date_time.toString('hh  mm  ss'))
        ui.cur_date.setText(date_time.toString('yyyy / MM / dd'))

        # led 자동 제어 모드인 경우
        if ui.led_auto.isChecked():
            if date_time.toString('hh:mm') == config.settings['led']['on'] \
                    and not config.actuator_status['led']:
                uartCom.control_led_power(order=True)
            elif date_time.toString('hh:mm') == config.settings['led']['off']\
                    and config.actuator_status['led']:
                uartCom.control_led_power(order=False)


class ValueUpdater(QtCore.QThread):
    def __init__(self):
        super().__init__()
        ui.sensor_freq_apply.pressed.connect(self.check_sensor_freq_min_time)
        self.sensor_timer = QtCore.QTimer()
        self.sensor_timer.timeout.connect(uartCom.check_air_status)
        self.sensor_timer.timeout.connect(uartCom.check_water_status)
        self.start()

    def check_sensor_freq_min_time(self):
        freq = calculate_millisecond(ui.sensor_freq.value(), ui.sensor_freq_unit.currentText())
        if freq < 10000:
            ui.sensor_freq.setValue(10)
            ui.sensor_freq_unit.setCurrentIndex(0)
            manager.alertSignal.emit('The minimum sensing freq is 10 second.', False)
        manager.change_settings('sensor')
        self.sensor_timer.start(freq)


def calculate_millisecond(freq, unit):
    units = {'S': 1000, 'M': 60000, 'H': 3600000}
    return freq * units[unit]


class Manager(QtCore.QThread):
    alertSignal = QtCore.pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()
        self.alertSignal.connect(self.alert)

        # 페이지 변환
        ui.main_button.clicked.connect(lambda: ui.page_stackedWidget.setCurrentIndex(0))
        ui.graph_button.clicked.connect(lambda: ui.page_stackedWidget.setCurrentIndex(1))
        ui.water_graph.clicked.connect(lambda: ui.graph_stackedWidget.setCurrentIndex(0))
        ui.air_graph.clicked.connect(lambda: ui.graph_stackedWidget.setCurrentIndex(1))
        ui.settings_button.clicked.connect(self.update_settings)
        ui.settings_button.clicked.connect(lambda: ui.page_stackedWidget.setCurrentIndex(2))

        # 그래프 조작
        graph_freqs = ['', 'by_week', 'by_month']
        self.air_checkBoxes = [ui.indoor_temp, ui.humid, ui.co2]
        self.water_checkBoxes = [ui.cs_temp, ui.Do, ui.ph, ui.tds]
        air_radioButtons = [ui.air_day, ui.air_week, ui.air_month]
        water_radioButtons = [ui.water_day, ui.water_week, ui.water_month]

        for checkBox in self.air_checkBoxes:
            checkBox.clicked.connect(lambda: self.update_graph('air', list(itertools.compress(graph_freqs,
                                                                [rb.isChecked() for rb in air_radioButtons]))[0]))
        for checkBox in self.water_checkBoxes:
            checkBox.clicked.connect(lambda: self.update_graph('water', list(itertools.compress(graph_freqs,
                                                                [rb.isChecked() for rb in water_radioButtons]))[0]))

        for radioButton, graph_freq in zip(air_radioButtons, graph_freqs):
            radioButton.clicked.connect(partial(self.update_graph, 'air', graph_freq))
        for radioButton, graph_freq in zip(water_radioButtons, graph_freqs):
            radioButton.clicked.connect(partial(self.update_graph, 'water', graph_freq))

        ui.id_apply.pressed.connect(lambda: config.settings.update({'PID': ui.id.text()}))
        ui.sensor_freq_apply.pressed.connect(partial(self.change_settings, 'sensor'))
        ui.server_freq_apply.pressed.connect(partial(self.change_settings, 'server'))
        ui.cs_apply.pressed.connect(partial(self.change_settings, 'cs'))
        ui.fan_apply.pressed.connect(partial(self.change_settings, 'fan'))
        ui.led_apply.pressed.connect(partial(self.change_settings, 'led'))

        # initializing
        ui.id.setText(config.settings['PID'])
        self.update_settings()
        self.update_graph('air', '')

    def update_settings(self):
        """설정화면의 모든 설정 업데이트"""
        # 센서 설정
        ui.sensor_freq.setValue(config.settings['sensor']['freq'])
        ui.sensor_freq_unit.setCurrentText(config.settings['sensor']['unit'])

        # 서버 설정
        for line_edit, ip_addr in zip([ui.ip1, ui.ip2, ui.ip3, ui.ip4], config.settings['server']['ip'].split('.')):
            line_edit.setText(ip_addr)
        ui.port.setText(config.settings['server']['port'])
        ui.server_freq.setValue(config.settings['server']['freq'])
        ui.server_freq_unit.setCurrentText(config.settings['server']['unit'])

        # 양액 제어 설정
        ui.cs_freq_hour.setValue(config.settings['cs']['freq_hour'])
        ui.cs_act_min.setValue(config.settings['cs']['act_min'])

        # fan 제어 설정
        ui.fan_freq_hour.setValue(config.settings['fan']['freq_hour'])
        ui.fan_act_min.setValue(config.settings['fan']['act_min'])

        # led 제어 설정
        ui.led_on_at.setTime(QtCore.QTime.fromString(config.settings['led']['on'], 'hh:mm'))
        ui.led_off_at.setTime(QtCore.QTime.fromString(config.settings['led']['off'], 'hh:mm'))

    def alert(self, message, reconnect=False):
        """ 알림 메시지창 생성 """
        msgbox = QtWidgets.QMessageBox()
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setText(message)
        if reconnect:
            msgbox.setStandardButtons(QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Cancel)
        else:
            msgbox.setStandardButtons(QtWidgets.QMessageBox.Ok)
        result = msgbox.exec_()
        if result == QtWidgets.QMessageBox.Retry:
            uartCom.connect_serial(uartCom.get_com(prev_com=uartCom.com))
        elif result == QtWidgets.QMessageBox.Cancel:
            ui.coms.clear()

    def update_status(self):
        """메인 화면 페이지의 모니터링 요소 상태 업데이트"""
        ui.indoor_temp_status.setText(str(config.indoor_temp[-1]))
        ui.cs_temp_status.setText(str(config.cs_temp[-1]))
        ui.humid_status.setText(str(config.humid[-1]))
        ui.co2_status.setText(str(config.co2[-1]))
        ui.ph_status.setText(str(config.ph[-1]))
        ui.do_status.setText(str(config.do[-1]))
        ui.tds_status.setText(str(config.tds[-1]))
        ui.last_sensing_time.setText(str(config.last_sensing))

    def update_actuator(self):
        """제어 요소 상태 업데이트"""
        print(config.actuator_status['led'])
        ui.led_switch_image.setChecked(config.actuator_status['led'])
        ui.fan_switch_image.setChecked(config.actuator_status['fan'])

    def update_graph(self, graph_type, graph_freq=''):
        """그래프 페이지의 그래프 업데이트"""
        if graph_type == 'air':
            global air_graph_views
            views = air_graph_views
            checkBoxes = self.air_checkBoxes
            if graph_freq:
                datas = db.fetch_data('AIR', graph_freq)
            else:
                datas = [config.indoor_temp, config.humid, config.co2]
            colors = ['#08C8CE', '#83E609', '#F5B700']
        elif graph_type == 'water':
            global water_graph_views
            views = water_graph_views
            checkBoxes = self.water_checkBoxes
            if graph_freq:
                datas = db.fetch_data('WATER', graph_freq)
            else:
                datas = [config.cs_temp, config.do, config.ph, config.tds]
            colors = ['#08C8CE', '#83E609', '#F5B700', '#CE363B']
        for view, checkbox, data, c in zip(views, checkBoxes, datas, colors):
            view.clear()
            if checkbox.isChecked():
                view.addItem(pg.PlotCurveItem(data, pen=pg.mkPen(color=c, width=3)))

    def change_settings(self, element=None):
        """설정 변경"""
        if element == 'sensor':
            config.settings['sensor'].update({'freq': ui.sensor_freq.value(), 'unit': ui.sensor_freq_unit.currentText()})
        elif element == 'server':
            config.settings['server'].update({'ip': '.'.join([ui.ip1.text(), ui.ip2.text(), ui.ip3.text(), ui.ip4.text()]),
                                              'port': ui.port.text(),
                                              'freq': ui.server_freq.value(), 'unit': ui.server_freq_unit.currentText()})
        elif element == 'led':
            config.settings['led'].update({'on': ui.led_on_at.time().toString('HH:mm'),
                                           'off': ui.led_off_at.time().toString('HH:mm')})
        elif element == 'fan':
            config.settings['fan'].update({'freq_hour': ui.fan_freq_hour.value(), 'act_min': ui.fan_act_min.value()})
        elif element == 'cs':
            config.settings['cs'].update({'freq_hour': ui.cs_freq_hour.value(), 'act_min': ui.cs_act_min.value()})

        self.update_settings()


def load_settings():
    """설정 불러오기"""
    with open('../res/preference/saved_settings.json', 'r') as file:
        data = json.load(file)
        config.settings = data['element']


def save_settings():
    """설정 저장"""
    with open('../res/preference/saved_settings.json', 'w') as file:
        json.dump({'element': config.settings}, file, indent=4)
    print('saved settings')


def update_views(main_view, views):
    for view in views:
        view.setGeometry(main_view.sceneBoundingRect())


def init_graph(plotWidget, graph_items, views):
    font11 = QtGui.QFont('나눔바른고딕', 10)
    layout = pg.GraphicsLayout()
    plotWidget.setCentralWidget(layout)

    for i, item in enumerate(graph_items):
        if type(item) == pg.PlotItem:
            item.getAxis('left').tickFont = font11
            item.getAxis('left').setWidth(35)
            item.getAxis('bottom').setHeight(30)
            item.getAxis('bottom').tickFont = font11
            item.showGrid(True, True, 0.4)
        else:
            item.tickFont = font11
            item.setWidth(40)
            item.setHeight(290)
        layout.addItem(item, row=2, col=i + 1)

    for view in views:
        layout.scene().addItem(view)
        view.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)


if __name__ == '__main__':
    import sys
    # 그래프 페이지의 그래프 초기 설정
    pg.setConfigOptions(foreground='w', background=pg.mkColor(40, 40, 40), antialias=True)

    app = QtWidgets.QApplication(sys.argv)
    mainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(mainWindow)

    # air 그래프 초기 설정
    indoor_temp_axis = pg.AxisItem('left')

    indoor_temp_view = pg.ViewBox()
    indoor_temp_view.setLimits(yMin=0, yMax=100)

    air_plotItem = pg.PlotItem()
    # air_main_view는 humid_view와 동일
    air_main_view = air_plotItem.vb
    air_main_view.setLimits(yMin=0, yMax=100)

    co2_axis = pg.AxisItem('right')
    co2_view = pg.ViewBox()
    co2_view.setLimits(yMin=0, yMax=2000)

    indoor_temp_axis.linkToView(indoor_temp_view)
    indoor_temp_view.setXLink(air_main_view)
    co2_axis.linkToView(co2_view)
    #co2_view.setXLink(air_plotItem)
    co2_view.setXLink(air_main_view)

    init_graph(ui.air_plotWidget, [indoor_temp_axis, air_plotItem, co2_axis], [indoor_temp_view, co2_view])
    air_main_view.sigResized.connect(lambda: update_views(air_main_view, [indoor_temp_view, co2_view]))

    # water 그래프 초기 설정
    cs_temp_axis = pg.AxisItem('left')
    cs_temp_view = pg.ViewBox()
    cs_temp_view.setLimits(yMin=0, yMax=100)

    water_plotItem = pg.PlotItem()
    # water_main_view는 do_view와 동일
    water_main_view = water_plotItem.vb
    water_main_view.setLimits(yMin=0, yMax=100)

    ph_axis = pg.AxisItem('right')
    ph_view = pg.ViewBox()
    ph_view.setLimits(yMin=0, yMax=2000)

    tds_axis = pg.AxisItem('right')
    tds_view = pg.ViewBox()
    tds_view.setLimits(yMin=0, yMax=2000)

    cs_temp_axis.linkToView(cs_temp_view)
    cs_temp_view.setXLink(water_main_view)
    ph_axis.linkToView(ph_view)
    ph_view.setXLink(water_main_view)
    tds_axis.linkToView(tds_view)
    tds_view.setXLink(water_main_view)

    init_graph(ui.water_plotWidget, [cs_temp_axis, water_plotItem, ph_axis, tds_axis], [cs_temp_view, ph_view, tds_view])

    water_main_view.sigResized.connect(lambda: update_views(water_main_view, [cs_temp_view, ph_view, tds_view]))

    air_graph_views = [indoor_temp_view, air_main_view, co2_view]
    water_graph_views = [cs_temp_view, water_main_view, ph_view, tds_view]

    load_settings()
    manager = Manager()
    uartCom = UartCom()
    timeUpdater = TimeUpdater()
    valueUpdater = ValueUpdater()
    # MainWindow.showFullScreen()
    uartCom.connect_serial(uartCom.get_com())
    # TCPclient = client.TCPClient(ui)
    # TCPclient.start()
    mainWindow.show()
    app.exec_()
    save_settings()
    sys.exit()
