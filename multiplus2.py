import logging
import time

from vebus import VEBus

"""
Multiplus-II, ESS Mode 3 

23.10.2022 Martin Steppuhn
"""


class MultiPlus2:
    def __init__(self, port, timeout=10):
        self.vebus = VEBus(port=port, log='vebus')
        self.log = logging.getLogger('mp2')
        self.timeout = timeout

        self.data_timeout = time.perf_counter() + self.timeout
        self.data = None  # Dictionary with all information from Multiplus

        self.online = False  # True if connection is established

        self.cmd_lock_time = None  # sleep / wakeup "timer"  (time.perf_counter())
        self.power_delay_time = time.perf_counter()  # set 0 Watt for a time before disable sendening power command

        self._wakeup = False
        self._sleep = False

    def sleep(self):
        self._sleep = True

    def wakeup(self):
        self._wakeup = True


    def connect(self):
        version = self.vebus.get_version()  # hide errors while scanning
        if version:
            self.data = {'mk2_version': version}  # init dictionary
            time.sleep(0.1)
            if self.vebus.init_address():
                self.data['state'] = 'init'
                self.online = True
                self.data_timeout = time.perf_counter() + self.timeout  # start timeout


    def command(self, power):
        if self.online:
            t = time.perf_counter()
            if self._wakeup and not self.cmd_lock_time:
                self.cmd_lock_time = t + 3  # lock command for 3 seconds
                self._wakeup = False
                self.vebus.wakeup()
                self.log.info("wakeup")
            elif self._sleep and not self.cmd_lock_time:
                self.cmd_lock_time = t + 3  # lock command for 3 seconds
                self._sleep = False
                self.vebus.sleep()
                self.log.info("sleep")
            else:
                if abs(power) >= 1:
                    if self.power_delay_time is None:
                        self.log.info("set_power start {}".format(power))
                    self.log.debug("set_power {}".format(power))
                    self.vebus.set_power(power)  # send command to multiplus
                    self.power_delay_time = t + 5  # send zero for 5seconds after last value >= 1
                elif self.power_delay_time:
                    self.vebus.set_power(0)
                    if t > self.power_delay_time:
                        self.power_delay_time = None
                        self.log.debug("set_power zero trailing timer end")

            # reset command lock timer
            if self.cmd_lock_time and t > self.cmd_lock_time:
                self.cmd_lock_time = None

    def update(self, pause_time=0.1):
        """
        Read all information from Multiplus-II

        :param pause_time: pause time between commands
        :return: dictionary
        """
        if not self.online:
            self.connect()

        else:
            self.vebus.send_snapshot_request()  # trigger snapshot
            time.sleep(pause_time)
            part1 = self.vebus.get_ac_info()  # read ac infos and append to data dictionary
            time.sleep(pause_time)
            if part1:
                part2 = self.vebus.read_snapshot()  # read snapshot infos and append to data dictionary
                time.sleep(pause_time)
                if part2:
                    part3 = self.vebus.get_led()  # read led infos and append to data dictionary
                    if part3:
                        data = {}
                        data.update(part1)
                        data.update(part2)
                        data.update(part3)
                        led = data.get('led_light', 0) + data.get('led_blink', 0)
                        state = data.get('device_state_id', None)
                        if state == 2:
                            data['state'] = 'sleep'
                        elif led & 0x40:
                            data['state'] = 'low_bat'
                        elif led & 0x80:
                            data['state'] = 'temperature'
                        elif led & 0x20:
                            data['state'] = 'overload'
                        elif state == 8 or state == 9:
                            data['state'] = 'on'
                        elif state == 4:
                            data['state'] = 'wait'
                        else:
                            data['state'] = '?{}?0x{:02X}?'.format(state, led)

                        self.data = data
                        self.data_timeout = time.perf_counter() + self.timeout  # reset data timeout with valid rx

        if time.perf_counter() > self.data_timeout:
            self.online = False
            self.data = {'error': 'offline', 'state': 'offline'}
