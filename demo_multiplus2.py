import time
import logging
from multiplus2 import MultiPlus2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d %(name)-10s %(levelname)-6s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# port = '/dev/ttyUSB1'
port = '/dev/serial/by-id/usb-VictronEnergy_MK3-USB_Interface_HQ2132VK4JK-if00-port0'

logging.getLogger('vebus').setLevel(logging.DEBUG)

mp2 = MultiPlus2(port)
while True:
    t0 = time.perf_counter()
    mp2.update()    # read all information
    print(time.perf_counter() - t0, mp2.data)
    time.sleep(0.5)
    # mp2.vebus.set_power(-200) # set feed power to 200Watt
    # mp2.vebus.set_power(500) # set charge power to 500Watt
    time.sleep(1)