# Connecting InkyWhat to a CircuitPython

This repo shows how to control an InkyWhat using ESP32 S2 dev board (the Unexpected Maker TinyS2 in this case).
It should work with any CircuitPython board with I2C, SPI and 4 additional IO pins.

## Pinout

You'll need 10 wires to connect the InkyWhat. The driver currently doesn't read data from the display do SPI data in (MISO) is not required.
If you adjust the code a bit, you could also skip the I2C interface beacuse you already know what board you have, right?

| Inky    | Pin | Tiny S2 Pin    | Description
|---------|-----|----------------|----------------------------------------
| 3V3     |  1  | 3V3            | 
| SDA     |  3  | SDA / IO8      | I2C Data -- only needed for eeprom
| SCL     |  5  | SCL / IO9      | I2C Clock -- only needed for eeprom
| #4      |     |                |
| GND     |  6  | GND            |
| MOSI    | 19  | SPI MO / IO35  | SPI data out (mcu to display)
| MISO    | 21  | SPI MI / IO36  | Optional - SPI data in (display to mcu)
| SCK     | 23  | SPI SCK / IO37 | SPI Clock
| CE1     |     |                |
| 5V      |  2  |                | Not needed
| CSEL    | 24  | IO7            | SPI Enable
| DTA/CMD | 15  | IO6            | Low = SPI send command, High = SPI send data
| RESET   | 13  | IO5            | Display hardware reset, needed to wake from sleep
| BUSY    | 11  | I04            | Used to read display busy status

Reference:
* [InkyWhat pinout](https://pinout.xyz/pinout/inky_what#)
* [TinyS2 pinout](https://unexpectedmaker.com/tinys2)

## Inky driver
This driver is ported from [library/inky/inky.py](https://github.com/pimoroni/inky/blob/master/library/inky/inky.py) in the Pimoroni Inky library. 
It works with the original Red, Black and Yellow Inky What.
Pimoroni has not specified the driver chip but the instructions line up with the SSD1619A.

These boards feature an eeprom that allows reading out the board type. See [inky_eeprom.py](inky_eeprom.py) for more details.
The original eeprom code was dropped in favor of the CircuitPython driver for the same chip.

### Changes from original driver
* Small differences in dealing with arrays/lists etc.
* CircuitPython doesn't have the full numpy lib, especially packbits is missing
* CircuitPython has Bitmap from display IO which makes working with image data much easier
* EEPROM code was replaced with the CircuitPython lib for the same chip