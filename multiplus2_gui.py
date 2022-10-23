import logging
import time
import tkinter as tki

from multiplus2 import MultiPlus2

# port = '/dev/ttyUSB0'
port = '/dev/serial/by-id/usb-VictronEnergy_MK3-USB_Interface_HQ2132VK4JK-if00-port0'

class App:
    def __init__(self):
        self.root = tki.Tk()
        self.root.title('MultiPlus-II Test')
        self.mp2 = MultiPlus2(port)
        # UI
        self.ui_width, self.ui_height = 800, 400
        self.root.resizable(False, False)
        self.root.geometry('{}x{}'.format(self.ui_width, self.ui_height))  # Window

        self.ui_btn_on = tki.Button(self.root, text="Wakeup", command=self.mp2.vebus.wakeup)  # ON
        self.ui_btn_off = tki.Button(self.root, text="Sleep", command=self.mp2.vebus.sleep)  # OFF
        self.ui_btn_0w = tki.Button(self.root, text="0 Watt", command=lambda: self.ui_slider_set_power.set(0))  # Stop Button

        self.ui_var_power_enable = tki.IntVar()  # checkbox needs a seperate variable
        self.ui_check_power_enable = tki.Checkbutton(master=self.root, text="Cyclic power update",
                                                     variable=self.ui_var_power_enable)  # Checkbox

        self.ui_slider_set_power = tki.Scale(master=self.root, from_=2000, to=-3000, orient=tki.HORIZONTAL,
                                             resolution=10)
        self.ui_text = tki.Text()  # textbox for output
        self.ui_text.configure(font=("Courier", 12))  # use fixed font for textbox

        # place with absolut positions
        self.ui_btn_on.place(x=20, y=20, width=100)
        self.ui_btn_off.place(x=140, y=20, width=100)
        self.ui_btn_0w.place(x=260, y=20, width=100)
        self.ui_check_power_enable.place(x=360, y=25)
        tki.Label(self.root, text="Charge").place(x=10, y=60)
        tki.Label(self.root, text="Feed/Discharge").place(x=self.ui_width - 130, y=60)
        self.ui_slider_set_power.place(x=10, y=75, width=self.ui_width - 20)
        self.ui_text.place(x=10, y=150, width=self.ui_width - 20, height=235)
        self.set_p = 0

    def getval(self, k):
        try:
            return self.mp2.data[k]
        except:
            return '?'

    def timer(self):
        if self.ui_var_power_enable.get():
            self.set_p = self.ui_slider_set_power.get()
            self.mp2.vebus.set_power(self.set_p)

        self.mp2.update()

        try:
            led = "0x{:04X}".format(self.mp2.data['led'])
        except:
            led = '?'
        s = "\n"
        s += " mk2_version:     {}\n".format(self.getval('mk2_version'))
        s += " state:           {}\n".format(self.getval('state'))
        s += " device_state:    {}\n".format(self.getval('device_state_name'))
        s += " device_state_id: {}\n".format(self.getval('device_state_id'))
        s += " led_info:        {}\n".format(self.getval('led_info'))
        s += " led_light:       {}\n".format(self.getval('led_light'))
        s += " led_blink:       {}\n".format(self.getval('led_blink'))
        s += "\n"
        s += " mains_u:  {:>6} V        bat_u:    {:>6} V        inv_p:    {:>6} W\n".format(self.getval('mains_u'),
                                                                                             self.getval('bat_u'),
                                                                                             self.getval('inv_p'))
        s += " mains_i:  {:>6} A        bat_i:    {:>6} A        out_p:    {:>6} W\n".format(self.getval('mains_i'),
                                                                                             self.getval('bat_i'),
                                                                                             self.getval('out_p'))
        s += " inv_u:    {:>6} V        bat_p:    {:>6} W\n".format(self.getval('inv_u'), self.getval('bat_p'))
        s += " inv_i:    {:>6} A                                  set_p:    {:>6} W\n".format(self.getval('inv_i'),
                                                                                              self.set_p)

        self.ui_text.delete(1.0, "end")
        self.ui_text.insert(tki.END, s)
        self.root.after(1000, self.timer)  # call timer() after 100ms


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d %(name)-10s %(levelname)-6s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

logging.getLogger('mp2').setLevel(logging.DEBUG)  # specific logger configuration

app = App()
app.timer()
app.root.mainloop()
