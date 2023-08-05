import board, microcontroller, busio, time, displayio
import ssd1619a
from digitalio import DigitalInOut, Direction

from ulab import numpy as np

displayio.release_displays()

if(False) :
    import inky
    import adafruit_imageload

    bitmap, palette = adafruit_imageload.load("InkywHAT-400x300.bmp")

    screen=inky.Inky(colour='yellow')
    screen.setup()
    screen.set_border(inky.BLACK)
    screen.set_image(bitmap)

    screen.show()
else :
    
    spi=board.SPI()
    epd_cs = board.IO7
    epd_dc = board.IO6
    epd_busy = board.IO4

    epd_reset = DigitalInOut(board.IO5)
    epd_reset.direction = Direction.OUTPUT
    epd_reset.value = True
    epd_reset.value = False
    time.sleep(0.1)
    epd_reset.value = True
    time.sleep(0.1)

    display_bus = displayio.FourWire(
    spi, command=epd_dc, chip_select=epd_cs #, baudrate=1000000
    )
    time.sleep(1)

    display = ssd1619a.SSD1619A(
    display_bus,
    color='yellow',
    busy_pin=epd_busy,
    width=400,
    height=300,
    highlight_color=0xFF0000,

    )

    g = displayio.Group()

    with open("/InkywHAT-400x300.bmp", "rb") as f:
    pic = displayio.OnDiskBitmap(f)

    t = displayio.TileGrid(pic, pixel_shader=pic.pixel_shader)

    g.append(t)

    display.show(g)

    display.refresh()

    print("updating")

    display.busy_wait()
