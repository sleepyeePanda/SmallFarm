import asyncio
import datetime
import glob
import json
from functools import partial
import serial
from threading import Thread
import time

from PyQt5 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg
import serial_asyncio
import sys
sys.path.append('../')

import Remote
from res.ui.Ui_design import Ui_MainWindow
from res.preference import config


class UartCom:
    def __init__(self):

        self.get_com()

        ui.connect.clicked.connect(self.connect_serial)
        ui.disconnect.clicked.connect(self.disconnect_serial)

        # 작동기
        ui.led_switch.pressed.connect(partial(self.control_led_power, init=False))
        ui.fan_switch.pressed.connect(partial(self.control_fan_power, init=False))
        ui.cs_switch.pressed.connect(partial(self.control_cs_power, init=False))
        ui.blackout_check_button.pressed.connect(partial(self.check_blackout))

        self.uart = None
        self.run_time = None
        self.run_timer = None
        self.humid_act_timer = None
        self.humid_freq_timer = None
        self.progress_timer = None
        self.isLinux = False
        self.remote = None
        self.local = None
        self.thread = None
        # self.connect_serial()

    def get_com(self, waiting=0):
        time.sleep(waiting)
        connect_port = []
        if sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            self.isLinux = True
        else:
            self.isLinux = False
        if self.isLinux:
            ports = self.serial_ports()
            for port in ports:
                if port.find('USB') > -1:
                    connect_port.append(port)
                    self.connect_serial()
        else:
            ports = self.serial_ports()
            for port in ports:
                if port.find('COM') > -1:
                    connect_port.append(port)
        print(connect_port)
        if not connect_port:
            manager.alertSignal.emit('통신 연결을 확인한 후 프로그램을 재실행 해주십시오')
        else:
            for comport in connect_port:
                ui.coms.addItem(comport)

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
        except serial.serialutil.SerialException as se:
            print(str(se))
            print('serial exception occured')
        except Exception as e:
            print(str(e))
        finally:
            loop.stop()
            loop.close()
        print('Closed Uart Thread!')

    def connect_serial(self):
        """시리얼 연결 설정"""
        com_no = str(ui.coms.currentText())
        print(com_no)
        if com_no:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            if self.isLinux:
                self.local = serial_asyncio.create_serial_connection(self.loop, lambda: UartProtocol(self), 'USB1',
                                                                     baudrate=115200)
                self.remote = serial_asyncio.create_serial_connection(self.loop, lambda: Remote.UartProtocol(), 'USB2',
                                                                      baudrate=115200)
                print(com_no+' connected')
            else:
                try:
                    self.local = serial_asyncio.create_serial_connection(self.loop, lambda: UartProtocol(self), 'COM1',
                                                                         baudrate=115200)
                    print('COM1 connected')
                except Exception as e:
                    print(str(e))
                try:
                    self.remote = serial_asyncio.create_serial_connection(self.loop, lambda: Remote.UartProtocol(), 'COM2',
                                                                          baudrate=115200)
                    print('COM2 connected')
                except Exception as e:
                    print(str(e))

            self.loop.run_until_complete(self.remote)
            self.loop.run_until_complete(self.local)

            self.thread = Thread(target=self.run, args=(self.loop,))
            self.thread.setDaemon(True)
            self.thread.start()

            self.initialize_actuator()
            valueUpdater.sensor_timer.start(3000)

            ui.connect.setText('완료')
            ui.connect.setChecked(True)
            ui.connect.setEnabled(False)
            ui.coms.setEnabled(False)
        else:
            ui.connect.setChecked(False)
            ui.connect.setText('연결')
            ui.coms.setEnabled(True)
            ui.connect.setEnabled(True)
            ui.disconnect.setChecked(False)

    def reset(self):
        """작동기 상태 초기화"""
        self.stop()
        config.status = {'heater': False, 'humidifier': False, 'fan': False, 'led': False, 'dryer': False}
        for actuator in [ui.led_switch, ui.fan_switch, ui.cs_switch]:
            actuator.setChecked(False)

    def disconnect_serial(self):
        """시리얼 연결 해제"""
        valueUpdater.sensor_timer.stop()
        self.reset()
        if self.uart is not None:
            self.uart.close()
            self.uart = None
        ui.coms.clear()
        ui.connect.setChecked(False)
        ui.connect.setText('연결')
        ui.connect.setEnabled(True)
        ui.coms.setEnabled(True)
        ui.disconnect.setChecked(False)
        self.get_com(0.3)

    def initialize_actuator(self):
        """작동기 최초 상태 읽기"""
        if self.uart is not None:
            self.control_led_power(init=True)
            time.sleep(0.15)
            self.control_fan_power(init=True)
            time.sleep(0.15)
            self.control_cs_power(init=True)
            time.sleep(0.15)
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
                manager.alertSignal.emit('통신 연결 상태를 확인해 주십시오.')
                return False
        else:
            manager.alertSignal.emit('통신 연결 상태를 확인해 주십시오.')
            print('Not Connected')
            return False

    def check_status(self):
        """모니터링 요소 상태 읽기"""
        self.send_msg('\x02S1TEMP?\x03\x0A\x0D')

    def control_led_power(self, init=False):
        """led 작동 제어"""
        msgs = {True: '\x02MF1FX\x03\x0A\x0D', False: '\x02MF1FO\x03\x0A\x0D'}
        self.send_msg('\x02MF1ST\x03\x0A\x0D' if init else msgs[config.actuator_status['led']])

    def control_fan_power(self, init=False, order=None):
        """fan 작동 제어"""
        msgs = {True: '\x02MH1FX\x03\x0A\x0D', False: '\x02MH1FO\x03\x0A\x0D'}
        if order == False:
            msg = msgs[False]
            self.fan_act_timer = QtCore.QTimer()
            self.fan_act_timer.setSingleShot(True)
            self.fan_act_timer.timeout.connect(lambda: self.control_fan_power(order=True))
            # hours*60*60*1000msec
            # minutes*60*1000msec
            self.humid_act_timer.start(config.settings['fan']['act_min'][0]*60000)
            self.humid_freq_timer.start(config.settings['fan']['freq_hour'][0]*3600000)
        elif order == True:
            msg = msgs[True]
        else:
            msg = msgs[config.actuator_status['fan']]
        self.send_msg('\x02MH1ST\x03\x0A\x0D' if init else msg)

    def control_cs_power(self, init=False, order=None):
        """cs 작동 제어"""
        msgs = {True: '\x02MH1FX\x03\x0A\x0D', False: '\x02MH1FO\x03\x0A\x0D'}
        if order == False:
            msg = msgs[False]
            self.cs_act_timer = QtCore.QTimer()
            self.cs_act_timer.setSingleShot(True)
            self.cs_act_timer.timeout.connect(lambda: self.control_cs_power(order=True))
            # 1 hours = 60*60*1000 msec
            # 1 minutes = 60*1000 msec
            self.cs_act_timer.start(config.actuator_status['cs']['act_min'][0]*60000)
            self.cs_freq_timer.start(config.actuator_status['cs']['freq_hour'][0]*3600000)
        elif order == True:
            msg = msgs[True]
        else:
            msg = msgs[config.actuator_status['cs']]
        self.send_msg('\x02MH1ST\x03\x0A\x0D' if init else msg)

    def check_blackout(self):
        pass


class UartProtocol(asyncio.Protocol):
    def __init__(self, uartCom):
        super().__init__()
        self.uartCom = uartCom
        self.rcvParser = RcvParser()

    def connection_made(self, transport):
        self.transport = transport
        print('port opened', transport)
        transport.serial.rts = False
        self.uartCom.uart = transport

    def data_received(self, data):
        message = data.decode()
        self.rcvParser.parsing(message)

    def connection_lost(self, exc):
        print('COM1 port closed')
        self.transport.loop.stop()


class RcvParser(QtCore.QObject):
    updateStateSignal = QtCore.pyqtSignal()
    updateActuatorSignal = QtCore.pyqtSignal()
    updateGraphSignal = QtCore.pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.init_protocol()
        self.updateStateSignal.connect(manager.update_status)
        self.updateActuatorSignal.connect(manager.update_actuator)
        self.updateGraphSignal.connect(manager.update_graph)
        ui.temp.pressed.connect(manager.update_graph)
        ui.humid.pressed.connect(manager.update_graph)
        ui.co2.pressed.connect(manager.update_graph)

    def parsing(self, pkt):
        """수신 데이터 파싱"""
        info = pkt.strip('\x02\x03\n\r')
        print('local: data parsed', info)
        cmd = info[0:2]
        try:
            func = self.protocol.get(cmd)
            print('local func: ', cmd, func)
            return func(info)
        except Exception as e:
            print(str(e))

    def rcv_status(self, info):
        """모니터링 요소 상태 파싱
           파싱 예외 발생 시 이전 상태 데이터 사용"""
        config.last_sensing = datetime.datetime.now().strftime('%H : %M : %S')
        try:
            temp = float(info[3:8])
        except Exception as e:
            print(str(e))
            temp = config.temp[-1]
        try:
            humid = float(info[9:11])
        except Exception as e:
            print(str(e))
            humid = config.humid[-1]
        try:
            co2 = float(info[12:16])
        except Exception as e:
            print(str(e))
            co2 = config.co2[-1]
        # 모니터링 요소 상태 업데이트
        self.updateStateSignal.emit()
        # 그래프 업데이트
        if ui.stackedWidget.currentIndex() == 1:
            self.updateGraphSignal.emit(True)
        # 모니터링 요소 상태 데이터 추가
        for data, status in zip([config.temp, config.humid, config.co2], [temp, humid, co2]):
            data.append(status)
            data.pop(0)

    def rcv_led(self, info):
        """led 상태 데이터 파싱"""
        try:
            config.actuator_status['led'] = True if info[4] == 'O' else False
        except Exception as e:
            print(str(e))
        # 작동기 상태 업데이트
        self.updateActuatorSignal.emit()

    def rcv_fan(self, info):
        """fan 상태 데이터 파싱"""
        try:
            config.actuator_status['fan'] = True if info[4] == 'O' else False
        except Exception as e:
            print(str(e))
        # 작동기 상태 업데이트
        self.updateActuatorSignal.emit()

    def rcv_cs(self, info):
        """cs 상태 데이터 파싱"""
        try:
            config.actuator_status['cs'] = True if info[4] == 'O' else False
        except Exception as e:
            print(str(e))
        # 작동기 상태 업데이트
        self.updateActuatorSignal.emit()

    def rcv_blackout_check(self, info):
        """정전 여부 데이터 파싱"""
        try:
            if info[4]=='O':
                manager.alertSignal.emit('정전이 발생하였습니다.')
        except Exception as e:
            print(str(e))

    def init_protocol(self):
        self.protocol = {'S1': self.rcv_status,
                         'MF': self.rcv_led,
                         'MW': self.rcv_fan,
                         'MD': self.rcv_cs,
                         'ML': self.rcv_blackout_check}


class TimeUpdater(QtCore.QThread):
    def __init__(self):
        super().__init__()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.change_time)
        self.timer.start(1000)
        self.start()

    def change_time(self):
        date_time = QtCore.QDateTime.currentDateTime()
        ui.cur_time.setText(date_time.toString('hh  mm  ss'))
        ui.cur_date.setText(date_time.toString('yyyy / MM / dd'))


class ValueUpdater(QtCore.QThread):
    def __init__(self):
        super().__init__()
        ui.sensor_freq_apply.clicked.connect(lambda : self.sensor_timer.start())
        self.sensor_timer = QtCore.QTimer()
        self.sensor_timer.timeout.connect(uartCom.check_status)
        self.start()


class Manager(QtCore.QThread):
    alertSignal = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.alertSignal.connect(self.alert)

        # 페이지 변환
        ui.main_button.clicked.connect(lambda: ui.stackedWidget.setCurrentIndex(0))
        ui.graph_button.clicked.connect(self.update_graph)
        ui.graph_button.clicked.connect(lambda: ui.stackedWidget.setCurrentIndex(1))
        ui.settings_button.clicked.connect(self.update_settings)
        ui.settings_button.clicked.connect(lambda: ui.stackedWidget.setCurrentIndex(2))

        # 그래프 조작
        for button in [ui.temp, ui.humid, ui.co2, ui.day, ui.week, ui.month]:
            button.clicked.connect(self.update_graph)

        # initializing
        self.update_settings()
        self.update_graph()

    def update_settings(self):
        """설정화면의 모든 설정 업데이트"""
        # 센서 설정
        ui.sensor_freq.setValue(config.settings['sensor']['freq'])
        # test
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
        ui.led_on_at.setTime(QtCore.QTime.fromString(config.settings['led']['off'], 'hh:mm'))
        ui.led_off_at.setTime(QtCore.QTime.fromString(config.settings['led']['on'], 'hh:mm'))

    def alert(self, message):
        """ 알림 메시지창 생성 """
        msgbox = QtWidgets.QMessageBox()
        msgbox.setIcon(QtWidgets.QMessageBox.Information)
        msgbox.setText(message)
        msgbox.setStandardButtons(QtWidgets.QMessageBox.Ok)
        subapp = msgbox.exec_()

    def save_data(self):
        pass

    def update_status(self):
        """메인 화면 페이지의 모니터링 요소 상태 업데이트"""
        ui.temp_status.setText(str(config.temp[-1]))
        ui.humid_status.setText(str(config.humid[-1]))
        ui.co2_status.setText(str(config.temp[-1]))
        ui.ph_status.setText(str(config.ph[-1]))
        ui.do_status.setText(str(config.do[-1]))
        ui.tds_status.setText(str(config.tds[-1]))
        ui.last_sensing_time.setText(str(config.last_sensing))

    def update_actuator(self):
        """제어 요소 상태 업데이트"""
        ui.led_switch.setChecked(config.actuator_status['led'])
        ui.fan_switch.setChecked(config.actuator_status['fan'])
        ui.cs_switch.setChecked(config.actuator_status['cs'])

    def update_graph(self):
        """그래프 페이지의 그래프 업데이트"""
        global temp_view, main_view, co2_view
        main_view.clear()
        if ui.humid.isChecked():
            main_view.addItem(pg.PlotCurveItem(config.humid, pen=pg.mkPen(color='#83E609', width=3)))
        temp_view.clear()
        if ui.temp.isChecked():
            temp_view.addItem(pg.PlotCurveItem(config.temp, pen=pg.mkPen(color='#08C8CE', width=3)))
        co2_view.clear()
        if ui.co2.isChecked():
            co2_view.addItem(pg.PlotCurveItem(config.co2, pen=pg.mkPen(color='#F5B700', width=3)))

    def change_settings(self):
        """설정 변경"""
        config.settings['sensor'].update({'freq': ui.sensor_freq.value(), 'unit':ui.sensor_freq_unit.currentText()})
        config.settings['server'].update({'ip': ''.join([ui.ip1, ui.ip2, ui.ip3, ui.ip4]), 'port': ui.port.text(),
                                          'freq': ui.sensor_freq.value(), 'unit': ui.sensor_freq_unit.currentText()})
        config.settings['cs'].update({'freq_hour': ui.cs_freq_hour.value(), 'act_min': ui.cs_act_min.value()})
        config.settings['fan'].update({'freq_hour': ui.fan_freq_hour.value(), 'act_min': ui.fan_act_min.currentText()})
        config.settings['led'].update({'on': ui.led_on_at.time().toString('HH:mm'),
                                       'off': ui.led_off_at.time().toString('HH:mm')})
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


def update_views(temp_view, main_view, co2_view):
    temp_view.setGeometry(main_view.sceneBoundingRect())
    co2_view.setGeometry(main_view.sceneBoundingRect())


if __name__ == '__main__':
    import sys
    pg.setConfigOptions(foreground='w', background=pg.mkColor(40, 40, 40), antialias=True)

    app = QtWidgets.QApplication(sys.argv)
    mainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(mainWindow)

    font11 = QtGui.QFont('나눔스퀘어', 11)

    temp_axis = pg.AxisItem('left')
    temp_axis.tickFont = font11
    temp_view = pg.ViewBox()

    layout = pg.GraphicsLayout()
    ui.plotWidget.setCentralWidget(layout)

    layout.addItem(temp_axis, row=2, col=1, rowspan=1, colspan=1)

    plotItem = pg.PlotItem()
    plotItem.getAxis('left').tickFont = font11
    plotItem.getAxis('left').setWidth(60)
    plotItem.getAxis('bottom').tickFont = QtGui.QFont('나눔스퀘어', 11)
    plotItem.showGrid(True, True, 0.5)
    # main_view is humid_view
    main_view = plotItem.vb
    main_view.setLimits(yMin=0, yMax=100)
    layout.addItem(plotItem, row=2, col=2, rowspan=1, colspan=1)

    layout.scene().addItem(temp_view)
    temp_axis.linkToView(temp_view)
    temp_view.setXLink(main_view)
    temp_axis.setWidth(60)

    co2_view = pg.ViewBox()
    co2_axis = pg.AxisItem('right')
    co2_axis.tickFont = font11
    plotItem.layout.addItem(co2_axis, 2, 3)
    plotItem.scene().addItem(co2_view)
    co2_axis.linkToView(co2_view)
    co2_view.setXLink(plotItem)
    co2_axis.setWidth(80)

    main_view.sigResized.connect(lambda: update_views(temp_view, main_view, co2_view))

    temp_view.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
    co2_view.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

    load_settings()
    manager = Manager()
    uartCom = UartCom()
    timeUpdater = TimeUpdater()
    valueUpdater = ValueUpdater()
    # MainWindow.showFullScreen()
    uartCom.get_com()
    uartCom.connect_serial()
    mainWindow.show()
    app.exec_()
    # if uartCom.t and uartCom.t.isAlive():
    #     uartCom.uart.loop.call_soon_threadsafe(uartCom.uart.loop.stop)
    if uartCom.thread and uartCom.thread.isAlive():
        uartCom.uart.loop.call_soon_threadsafe(uartCom.uart.loop.stop)
    save_settings()
    sys.exit()