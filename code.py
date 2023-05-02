import board
import struct
import inky_eeprom
import inky

import ulab

print(inky_eeprom.EPDType.from_eeprom())

screen=inky.Inky(colour='yellow')


#screen.set_image()
screen.setup()
for x in range(50, 250):
  screen.set_pixel(x,150, inky.YELLOW)
for x in range(50, 250):
  screen.set_pixel(x,152, inky.BLACK)

screen.show()