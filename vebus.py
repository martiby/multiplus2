import logging
import struct
import time

import serial

"""
Victron Energy MK3 Bus Interface

Functions to control a Multiplus-II in ESS Mode 3 

Based on: Technical-Information-Interfacing-with-VE-Bus-products-MK2-Protocol-3-14.pdf and listening to the
communication between Venus OS and MK3 at the internal FTDI TXD/RXD lines.  

23.10.2022 Martin Steppuhn
27.11.2022 Martin Steppuhn    receive_frame() with quick and dirty start search
"""


class VEBus:
    def __init__(self, port, log='vebus'):
        self.port = port
        self.log = logging.getLogger(log)
        self.serial = None
        self.open_port()

    def open_port(self):
        try:
            self.serial = serial.Serial(self.port, 2400, timeout=0)
        except Exception as e:
            self.serial = None
            self.log.error("open_port: {}".format(e))

    def get_version(self):
        """
        Read versionnumber (MK2). Also used to check connection.

        007.169 TX: 02 FF 56 A9                     V|
        007.211 RX: 07 FF 56 24 DB 11 00 42 52      V| 24 DB 11 00 42         VERSION version=1170212 mode=B

        Firmware laut VE Configure: 2629492

        :return: Versionnumber or None
        """

        if self.serial is None:
            self.open_port()  # open port

        try:
            self.send_frame('V', [])
            rx = self.receive_frame(b'\x07\xFF', timeout=0.5)
            cmd, mk2_version = struct.unpack("<BI", rx[2:7])
            self.log.info("mk2_version={}".format(mk2_version))
            return mk2_version
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            return None

    def init_address(self):
        """
        Init device address. With a single Multiplus on the bus the Address is 0x00

        011.883 TX: 04 FF 41 01 00 BB          A| 01 00          Device address: action=1 device=0
        011.925 RX: 04 FF 41 01 00 BB          A| 01 00          Device address: action=1 device=0

        :return: True/False
        """
        if self.serial is None:
            self.open_port()  # open port

        addr = 0x00  # for addr in range(0, 3):
        try:
            self.send_frame('A', [0x01, addr])
            rx = self.receive_frame(b'\x04\xFF\x41')
            if rx[4] == addr:  # check if correct answer and address
                self.log.info("init_address {} successful".format(addr))
                return True
            else:
                raise Exception("init_address failed")
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            self.log.error("get_version: {}".format(e))
        return False

    def get_led(self):
        """
        Get LED status

        005.163 TX: 02 FF 4C B3                     L |                                                LED request
        005.245 RX: 08 FF 4C 01 0C 00 00 80 00 20   L | 01 0C 00 00 80 00                              LED ON:Mains BLINK:Bulk Float

        :return: {'led_light': 0, 'led_blink': 0} or None
        """
        if self.serial is None:
            self.open_port()  # open port

        try:
            self.send_frame('L', [])
            rx = self.receive_frame(b'\x08\xFF\x4C', timeout=0.5)
            led_light, led_blink = struct.unpack("<BB", rx[3:5])  # high=blink   low = light

            led_info = self.make_led_names(led_light | led_blink)

            self.log.info("led_light=0x{:02X} led_blink=0x{:02X}".format(led_light, led_blink))
            return {'led_light': led_light, 'led_blink': led_blink, 'led_info': led_info}
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            self.log.error("get_led: {}".format(e))
            return None

    def make_led_names(self, bitmask):
        led_names = ["mains", "absorption", "bulk", "float", "inverter", "overload", "low_bat", "temperature"]
        l = []
        for i in range(len(led_names)):  # number of bits
            if bitmask & (1 << i):
                l.append(led_names[i])
        return l

    def get_ac_info(self):
        """
        Get AC Info

        Info: VenusOS combines Snapshot request und get AC Info

        009.261 TX: 06 FF 46 06 0E 10 0F 82 03 FF 46 01 B7              F | 06 0E 10 0F    Info Request=6 RAM snapshot: Inverter Power (14), Output power, Inverter Power (15)
                  : 03 FF 46 01 B7                                      F | 01             Info Request=1 AC L1 info
        009.374 RX: 0F 20 01 01 01 09 08 EC 5A 5F FF EC 5A 08 00 C3 08  !!! AC !!! {'bf_factor': 1, 'inverter_factor': 1, 'state': 'StateCharge', 'phase_info': 8, 'mains_voltage': 23276, 'mains_current': 65375, 'inverter_voltage': 23276, 'inverter_current': 8, 'mains_period': 195}

        return: Dictionary or None
        """
        if self.serial is None:
            self.open_port()  # open port

        try:
            self.send_frame('F', [0x01])
            rx = self.receive_frame(b'\x0F\x20')
            bf_factor, inv_factor, device_state_id, phase_info, mains_u, mains_i, inv_u, inv_i, mains_period = struct.unpack(
                "<BBxBBhhhhB", rx[2:16])

            device_state_name = {0: 'down', 1: 'startup', 2: 'off', 3: 'slave', 4: 'invert_full', 5: 'invert_half',
                                 6: 'invert_aes', 7: 'power_assist', 8: 'bypass', 9: 'charge'}[device_state_id]

            r = {'device_state_id': device_state_id,
                 'device_state_name': device_state_name,
                 'mains_u': round(mains_u / 100, 2),
                 'mains_i': round(mains_i / 100, 2),
                 'inv_u': round(inv_u / 100, 2),
                 'inv_i': round(inv_i / 100, 2)}
            self.log.info(r)
            return r
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            self.log.error("get_ac_info: {}".format(e))
            return None

    def send_snapshot_request(self):
        """
        Trigger a snapshot for values. Could be combined with a other request. NO RESPONSE !

        017.127 TX: 06 FF 46 06 0E 10 0F 82 05 FF 59 30 86 00 ED     F | 06 0E 10 0F        Info Request=6 RAM snapshot: Inverter Power (14), Output power, Inverter Power (15)
                  : 05 FF 59 30 86 00 ED                             Y | 30 86 00           0x30/CommandReadRAMVar: ram_id=[134, 0]/['?', 'UMainsRMS']

        14 Inverter Power (filtered)
        15 Inverter Power (filtered)
        16 Output power (filtered)
         4 UBat
         5 IBat
        """
        if self.serial is None:
            self.open_port()  # open port

        try:
            ids = [15, 16, 4, 5, 13]  # up to 6x
            self.send_frame('F', [0x06] + ids)
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            self.log.error("send_snapshot_request: {}".format(e))
            return None

    def read_snapshot(self):
        """
        007.987 TX: 03 FF 58 38 6E
                          X| 38                         0x38/CommandReadSnapShot

        008.079 RX: 09 FF 58 99 89 FE 05 00 72 01 08
                          X| 99 89 FE 05 00 72 01       0x99/CommandReadSnapShot response: [-375, 5, 370]

        new rx      0B FF 58 99 FF FF FF FF 1C 13 00 00 DA

        # 14 Inverter Power (filtered), +: charge AC>DC -: feed DC>AC
        # 15 Inverter Power(filtered)  falsches Vorzeichen aber genauer am sollwert
        # 16 Output power (filtered)  AC-Output +: out -: in

        ~130ms
        """
        if self.serial is None:
            self.open_port()  # open port

        try:
            self.send_frame('X', [0x38])
            frame = self.receive_frame(b'\x0D\xFF\x58')
            if frame[3] != 0x99:
                raise Exception('invalid response')
            inv_p, out_p, bat_u, bat_i, soc = struct.unpack("<hhhhh", frame[4:4 + 5 * 2])
            r = {'inv_p': -inv_p,
                 'out_p': out_p,
                 'bat_u': round(bat_u / 100, 2),
                 'bat_i': round(bat_i / 10, 1),
                 'bat_p': round(bat_u / 100 * bat_i / 10),
                 'soc': soc}
            self.log.info("read_snapshot: {}".format(r))
            return r
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            self.log.error("read_snapshot: {}".format(e))
            return None

    def set_power(self, power):
        """
        Set ESS Power     positiv = charge   negative = feed/discharge,  ~110ms

        013.883 TX: 07 FF 5A 37 00 83 72 01 73  Z| 37 00 83 72 01  !!! SET=370 !!! 0x37/CommandWriteViaID flags=0x00 id=131 data=370
        013.904 RX: 03 FF 5A 87 1D              Z| 87              0x87/CommandWriteViaID response: Write ramvar OK

        new rx :    03 FF 58 87 1F

        :param power: in watt
        :return: True/False
        """
        if self.serial is None:
            self.open_port()  # open port

        try:
            data = struct.pack("<BBBh", 0x37, 0x00, 131, -power)  # cmd, flags, id, power
            self.send_frame('X', data)
            rx = self.receive_frame([b'\x05\xFF\x58', b'\x03\xFF\x58'])   # two different answers are possible
            if rx[3] == 0x87:
                self.log.info("set_ess_power to {}W done".format(power))
                return True
            else:
                raise Exception("invalid response")
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            self.log.error("set_ess_power: power={} error={}".format(power, e))
            return False

    def format_hex(self, data):
        return " ".join(["{:02X}".format(b) for b in data])

    def send_frame(self, cmd, data):
        frame = self.build_frame(cmd, data)
        self.log.debug("TX: cmd={} frame={}".format(cmd, self.format_hex(frame)))
        self.serial.reset_input_buffer()   # test ob es was hilft ?
        self.serial.write(frame)

    def build_frame(self, cmd, data):
        """
        Build Frame

        :param cmd: byte [2] after 0xFF
        :param data: payload (bytes or list/tuple)
        :return: complete frame in bytes
        """
        frame = bytes((len(data) + 2, 0xFF))  # [length, 0xFF,

        if isinstance(cmd, str):
            frame += bytes((ord(cmd),))
        if isinstance(data, (list, tuple)):
            frame += bytes(data)
        else:
            frame += data
        checksum = 256 - sum(frame) & 0xFF  # calculate checksum
        frame += bytes((checksum,))  # append checksum
        return frame

    def receive_frame(self, head, timeout=0.5):
        """
        Receive frame

        :param head: search pattern (frame start)
        :param timeout:
        :return: frame bytes
        """
        # self.serial.reset_input_buffer()
        rx = bytes()
        tout = time.perf_counter() + timeout
        while time.perf_counter() < tout:
            rx += self.serial.read(500)
            time.sleep(0.010)
            if isinstance(head, (list, tuple)):
                for h in head:
                    p = rx.find(h)
                    if p >= 0:
                        break
            else:
                p = rx.find(head)

            if (p >= 0):
                flen = rx[p] + 2  # expected full package length
                if (len(rx) - p) >= flen:  # rx matches expected full package length
                    return rx[p:p + flen]

        if rx:
            raise Exception("invalid rx frame {}".format(self.format_hex(rx)))
        else:
            raise Exception("receive timeout, no data")

    def wakeup(self):
        try:
            self.serial.write(bytes([0x05, 0x3F, 0x07, 0x00, 0x00, 0x00, 0xC2]))
            self.log.info("WAKEUP !!!")
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            self.log.error("wakeup: {}".format(e))

    def sleep(self):
        """
        Set Multiplus in Sleepmode by command

        Standby consumption: ~1,3 Watt     DC: 27mA AC: 0.0 Watt
        """
        try:
            self.serial.write(bytes([0x05, 0x3F, 0x04, 0x00, 0x00, 0x00, 0xC5]))
            self.log.info("SLEEP !!!")
        except IOError:
            self.serial = None
            self.log.error("serial port failed")
        except Exception as e:
            self.log.error("sleep: {}".format(e))
