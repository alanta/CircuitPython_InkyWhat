# SPDX-FileCopyrightText: 2019 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`ssd1619a`
================================================================================

CircuitPython `displayio` drivers for SSD1619A-based ePaper displays


* Author(s): Marnix van Valen

Implementation Notes
--------------------

**Hardware:**

* `Pimoroni InkyWhat" 3-color ePaper Display Hat <https://shop.pimoroni.com/products/inky-what?variant=21441988558931>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware (version 5+) for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

import displayio
import microcontroller
import supervisor, time

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/alanta/CircuitPython_InkyWhat.git"

_START_SEQUENCE = (
    b"\x12\x80\x80"  # Software reset ✅ TODO wait for busy instead of fixed delay
    b"\x74\x01\x54"  # set analog block control ✅
    b"\x7e\x01\x3b"  # set digital block control ✅
    b"\x01\x03\x2b\x01\x00"  # driver output control 
    b"\x03\x01\x17"  # Gate driving voltage ✅
    b"\x04\x03\x41\xac\x32"  # Source Driving voltage ✅
    b"\x3a\x01\x07"  # Dummy line period ✅
    b"\x3b\x01\x04"  # Gate line width ✅
    b"\x11\x01\x03"  # Data entry mode setting 0x03 = X/Y increment ✅
    b"\x2c\x01\x3c"  # VCOM Register, 0x3c = -1.5v? ✅
    b"\x22\x01\xc7"  # Display update sequence ✅
    b"\x3c\x01\x00"  # Border color
    b"\x04\x03\x07\xac\x32" # Set voltage of VSH and VSL (yellow)
    #LUT (yellow)
    b"\x32\x46\xfa\x94\x8c\xc0\xd0\x00\x00\xfa\x94\x2c\x80\xe0\x00\x00\xfa\x00\x00\x00\x00\x00\x00\xfa\x94\xf8\x80\x50\x00\xcc\xbf\x58\xfc\x80\xd0\x00\x11\x40\x10\x40\x10\x08\x08\x10\x04\x04\x10\x08\x08\x03\x08\x20\x08\x04\x00\x00\x10\x10\x08\x08\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    #         self._send_command(0x44, [0x00, (self.cols // 8) - 1])  # Set RAM X Start/End
    b"\x44\x02\x00\x31"  # Set RAM X Start/End
    #         self._send_command(0x45, [0x00, 0x00] + packed_height)  # Set RAM Y Start/End
    b"\x45\x04\x00\x00\x2b\x01"  # Set RAM Y Start/End
)

_STOP_SEQUENCE = b"\x10\x01\x01"  # Enter deep sleep ✅


# pylint: disable=too-few-public-methods
class SSD1619A(displayio.EPaperDisplay):
    """SSD1619A driver"""

    def __init__(self, bus: displayio.FourWire, color:str, **kwargs) -> None:

        if color not in ('red', 'black', 'yellow'):
            raise ValueError('Colour {} is not supported!'.format(color))
        self.color=color

        width = kwargs["width"]
        height = kwargs["height"]
        
        start_sequence = bytearray(_START_SEQUENCE)
        start_sequence[11] = (height-1) & 0xFF
        start_sequence[12] = ((height-1) >> 8) & 0xFF

        #print('packed_height: \\x{:02x}\\x{:02x}'.format(start_sequence[10], start_sequence[11]))


        stop_sequence = _STOP_SEQUENCE
        try:
            bus.reset()
        except RuntimeError:
            stop_sequence = b""

        """Inky Lookup Tables.
        These lookup tables comprise of two sets of values.
        The first set of values, formatted as binary, describe the voltages applied during the six update phases:
          Phase 0     Phase 1     Phase 2     Phase 3     Phase 4     Phase 5     Phase 6
          A B C D
        0b01001000, 0b10100000, 0b00010000, 0b00010000, 0b00010011, 0b00000000, 0b00000000,  LUT0 - Black
        0b01001000, 0b10100000, 0b10000000, 0b00000000, 0b00000011, 0b00000000, 0b00000000,  LUT1 - White
        0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,  NOT USED BY HARDWARE
        0b01001000, 0b10100101, 0b00000000, 0b10111011, 0b00000000, 0b00000000, 0b00000000,  LUT3 - Yellow or Red
        0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,  LUT4 - VCOM
        There are seven possible phases, arranged horizontally, and only the phases with duration/repeat information
        (see below) are used during the update cycle.
        Each phase has four steps: A, B, C and D. Each step is represented by two binary bits and these bits can
        have one of four possible values representing the voltages to be applied. The default values follow:
        0b00: VSS or Ground
        0b01: VSH1 or 15V
        0b10: VSL or -15V
        0b11: VSH2 or 5.4V
        During each phase the Black, White and Yellow (or Red) stages are applied in turn, creating a voltage
        differential across each display pixel. This is what moves the physical ink particles in their suspension.
        The second set of values, formatted as hex, describe the duration of each step in a phase, and the number
        of times that phase should be repeated:
          Duration                Repeat
          A     B     C     D
        0x10, 0x04, 0x04, 0x04, 0x04,  <-- Timings for Phase 0
        0x10, 0x04, 0x04, 0x04, 0x04,  <-- Timings for Phase 1
        0x04, 0x08, 0x08, 0x10, 0x10,      etc
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00,
        The duration and repeat parameters allow you to take a single sequence of A, B, C and D voltage values and
        transform them into a waveform that - effectively - wiggles the ink particles into the desired position.
        In all of our LUT definitions we use the first and second phases to flash/pulse and clear the display to
        mitigate image retention. The flashing effect is actually the ink particles being moved from the bottom to
        the top of the display repeatedly in an attempt to reset them back into a sensible resting position.
        """
        self._luts = {
            'black': [
                0b01001000, 0b10100000, 0b00010000, 0b00010000, 0b00010011, 0b00000000, 0b00000000,
                0b01001000, 0b10100000, 0b10000000, 0b00000000, 0b00000011, 0b00000000, 0b00000000,
                0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,
                0b01001000, 0b10100101, 0b00000000, 0b10111011, 0b00000000, 0b00000000, 0b00000000,
                0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,
                0x10, 0x04, 0x04, 0x04, 0x04,
                0x10, 0x04, 0x04, 0x04, 0x04,
                0x04, 0x08, 0x08, 0x10, 0x10,
                0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00,
            ],
            'red': [
                0b01001000, 0b10100000, 0b00010000, 0b00010000, 0b00010011, 0b00000000, 0b00000000,
                0b01001000, 0b10100000, 0b10000000, 0b00000000, 0b00000011, 0b00000000, 0b00000000,
                0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,
                0b01001000, 0b10100101, 0b00000000, 0b10111011, 0b00000000, 0b00000000, 0b00000000,
                0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,
                0x40, 0x0C, 0x20, 0x0C, 0x06,
                0x10, 0x08, 0x04, 0x04, 0x06,
                0x04, 0x08, 0x08, 0x10, 0x10,
                0x02, 0x02, 0x02, 0x40, 0x20,
                0x02, 0x02, 0x02, 0x02, 0x02,
                0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00
            ],
            'red_ht': [
                0b01001000, 0b10100000, 0b00010000, 0b00010000, 0b00010011, 0b00010000, 0b00010000,
                0b01001000, 0b10100000, 0b10000000, 0b00000000, 0b00000011, 0b10000000, 0b10000000,
                0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,
                0b01001000, 0b10100101, 0b00000000, 0b10111011, 0b00000000, 0b01001000, 0b00000000,
                0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,
                0x43, 0x0A, 0x1F, 0x0A, 0x04,
                0x10, 0x08, 0x04, 0x04, 0x06,
                0x04, 0x08, 0x08, 0x10, 0x0B,
                0x02, 0x04, 0x04, 0x40, 0x10,
                0x06, 0x06, 0x06, 0x02, 0x02,
                0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00
            ],
            'yellow': [
                0b11111010, 0b10010100, 0b10001100, 0b11000000, 0b11010000, 0b00000000, 0b00000000,
                0b11111010, 0b10010100, 0b00101100, 0b10000000, 0b11100000, 0b00000000, 0b00000000,
                0b11111010, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000, 0b00000000,
                0b11111010, 0b10010100, 0b11111000, 0b10000000, 0b01010000, 0b00000000, 0b11001100,
                0b10111111, 0b01011000, 0b11111100, 0b10000000, 0b11010000, 0b00000000, 0b00010001,
                0x40, 0x10, 0x40, 0x10, 0x08,
                0x08, 0x10, 0x04, 0x04, 0x10,
                0x08, 0x08, 0x03, 0x08, 0x20,
                0x08, 0x04, 0x00, 0x00, 0x10,
                0x10, 0x08, 0x08, 0x00, 0x20,
                0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00,
            ]
        }


        super().__init__(
            bus,
            start_sequence,
            stop_sequence,
            **kwargs,
            ram_width=width,
            ram_height=height,
            set_column_window_command=0x44,
            set_row_window_command=0x45,
            set_current_column_command=0x4E,
            set_current_row_command=0x4F,
            write_black_ram_command=0x24,
            write_color_ram_command=0x26,
            refresh_display_command=0x20,

        )
    
    def busy_wait(self):
        """Wait for busy/wait pin."""
        start= supervisor.ticks_ms()
        while self.busy == True:
            time.sleep(0.01)
        stop = supervisor.ticks_ms()
        print("Waited for busy: ", (stop - start)/1000)