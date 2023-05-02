# Connecting InkyWhat to a TinyS2

This repo shows how to control an InkyWhat using ESP32 S2 dev board (the TinyS2 in this case).
The InkyWhat requires 5V to drive the display.

⚠️ The required 5V is obtained from a USB cable. There's no way to obstain 5V from a battery using the TinyS2 board.

## Pinout

You'll need 12 wires to connect the InkyWhat.

| Inky    | Pin | Tiny S2 Pin    |
|---------|-----|----------------|
| 3V3     |  1  | 3V3            |
| SDA     |  3  | SDA / IO8      |
| SCL     |  5  | SCL / IO9      |
| #4      |     |                |
| GND     |  6  | GND            |
| MOSI    | 19  | SPI MO / IO35  |
| MISO    | 21  | SPI MI / IO36  |
| SCK     | 23  | SPI SCK / IO37 |
| CE1     |     |                |
| 5V      |  2  | 5V             |
| CSEL    | 24  | IO7            |
| DTA/CMD | 15  | IO6            |
| RESET   | 13  | IO5            |
| BUSY    | 11  | I04            |

Reference:
* [InkyWhat pinout](https://pinout.xyz/pinout/inky_what#)
* [TinyS2 pinout]()

## Inky driver
This driver is ported from [library/inky/inky.py](https://github.com/pimoroni/inky/blob/master/library/inky/inky.py) in the Pimoroni Inky library. It works with the original Red, Black and Yellow Inky What.

These boards feature an eeprom that allows reading out the board type. See [inky_eeprom.py](inky_eeprom.py) for more details.
The original eeprom code was dropped in favor of the CircuitPython driver for the same chip.