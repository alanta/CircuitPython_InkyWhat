import inky
from ulab import numpy as np
import adafruit_imageload

bitmap, palette = adafruit_imageload.load("InkywHAT-400x300.bmp")

screen=inky.Inky(colour='yellow')
screen.setup()
screen.set_border(inky.BLACK)
screen.set_image(bitmap)

screen.show()