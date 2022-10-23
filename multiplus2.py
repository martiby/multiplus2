import time

from vebus import VEBus

"""
Multiplus-II, ESS Mode 3 

23.10.2022 Martin Steppuhn
"""

class MultiPlus2:
    def __init__(self, port, timeout=10):
        self.vebus = VEBus(port=port, log='vebus')
        self.timeout = timeout
        self.data_timeout = time.perf_counter() + self.timeout
        self.data = None   # Dictionary with all information from Multiplus
        self.online = False   # True if connection is established

    def update(self, pause_time=0.01):
        """
        Read all information from Multiplus-II

        :param pause_time: pause time between commands
        :return: distionary
        """
        if not self.online:
            version = self.vebus.get_version()  # hide errors while scanning
            if version:
                self.data = {'mk2_version': version}  # init dictionary
                time.sleep(pause_time)
                if self.vebus.init_address():
                    self.data['state'] = 'init'
                    self.online = True
                    self.data_timeout = time.perf_counter() + self.timeout  # start timeout

        else:
            self.vebus.send_snapshot_request()  # trigger snapshot
            part1 = self.vebus.get_ac_info()  # read ac infos and append to data dictionary
            if part1 is not None:
                self.data.update(part1)
                time.sleep(pause_time)
                part2 = self.vebus.read_snapshot()  # read snapshot infos and append to data dictionary
                if part2 is not None:
                    self.data.update(part2)
                    time.sleep(pause_time)
                    part3 = self.vebus.get_led()  # read led infos and append to data dictionary
                    if part3 is not None:
                        self.data.update(part3)  # all received !!!!
                        self.data_timeout = time.perf_counter() + self.timeout  # reset data timeout with valid rx

                        led = self.data.get('led_light', 0) + self.data.get('led_blink', 0)
                        state = self.data.get('device_state_id', None)
                        if state == 2:
                            self.data['state'] = 'sleep'
                        elif led & 0x40:
                            self.data['state'] = 'low_bat'
                        elif led & 0x80:
                            self.data['state'] = 'temperature'
                        elif led & 0x20:
                            self.data['state'] = 'overload'
                        elif state == 8 or state == 9:
                            self.data['state'] = 'on'
                        elif state == 4:
                            self.data['state'] = 'wait'
                        else:
                            self.data['state'] = '?{}?0x{:02X}?'.format(state, led)

        if time.perf_counter() > self.data_timeout:
            self.online = False
            self.data = {'error': 'offline', 'state': 'offline'}
