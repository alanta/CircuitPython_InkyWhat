import board
import struct

import adafruit_24lc32
eeprom = adafruit_24lc32.EEPROM_I2C(board.I2C())

DISPLAY_VARIANT = [
    None,
    'Red pHAT (High-Temp)',
    'Yellow wHAT',
    'Black wHAT',
    'Black pHAT',
    'Yellow pHAT',
    'Red wHAT',
    'Red wHAT (High-Temp)',
    'Red wHAT',
    None,
    'Black pHAT (SSD1608)',
    'Red pHAT (SSD1608)',
    'Yellow pHAT (SSD1608)',
    None,
    '7-Colour (UC8159)',
    '7-Colour 640x400 (UC8159)',
    '7-Colour 640x400 (UC8159)',
    'Black wHAT (SSD1683)',
    'Red wHAT (SSD1683)',
    'Yellow wHAT (SSD1683)',
    '7-Colour 800x480 (AC073TC1A)'
]

class EPDType:
    """Class to represent EPD EEPROM structure."""

    valid_colors = [None, 'black', 'red', 'yellow', None, '7colour']

    def __init__(self, width, height, color, pcb_variant, display_variant, write_time=None):
        """Initialise new EEPROM data structure."""
        self.width = width
        self.height = height
        self.color = color
        if type(color) == str:
            self.set_color(color)
        self.pcb_variant = pcb_variant
        self.display_variant = display_variant
        self.eeprom_write_time = '' if write_time is None else write_time

    def __repr__(self):
        """Return string representation of EEPROM data structure."""
        return """Display: {}x{}
Color: {}
PCB Variant: {}
Display Variant: {}
Time: {}""".format(self.width,
                   self.height,
                   self.get_color(),
                   self.pcb_variant / 10.0,
                   self.get_variant(),
                   self.eeprom_write_time)

    @classmethod
    def from_eeprom(class_object):
        """Load epd type from eeprom"""
        return EPDType.from_bytes(eeprom[0:29])

    @classmethod
    def from_bytes(class_object, data):
        """Initialise new EEPROM data structure from a bytes-like object or list."""
        data = bytearray(data)
        data = struct.unpack('<HHBBB22s', data)
        return class_object(*data)

    def get_color(self):
        """Get the stored colour value."""
        try:
            return self.valid_colors[self.color]
        except IndexError:
            return None

    def get_variant(self):
        """Return text name of the display variant."""
        try:
            return DISPLAY_VARIANT[self.display_variant]
        except IndexError:
            return None
