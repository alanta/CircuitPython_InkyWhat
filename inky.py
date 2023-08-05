"""Inky e-Ink Display Driver."""
# This is a port of the Pimoroni Inky library to CircuitPython
# The original library is available at https://github.com/pimoroni/inky/tree/master/library/inky

import time
import struct
import displayio
import supervisor # for timing
import board, microcontroller, busio
from digitalio import DigitalInOut, Direction, Pull
from adafruit_bus_device.spi_device import SPIDevice

import inky_eeprom

try:
    import ulab
except ImportError:
    raise ImportError('This library requires the ulab numpy-like module')

# Pimoroni has not specified the driver chip
# Most likely it's an SSD1619A 

# Display colour codes
WHITE = 0
BLACK = 1
RED = YELLOW = 2

# GPIO pins required by BCM number
RESET_PIN = board.IO5 #27
BUSY_PIN = board.IO4
DC_PIN = board.IO6

# In addition the following pins are used for SPI
CS_PIN = board.IO7
MOSI_PIN = board.MOSI
SCLK_PIN = board.SCK

# SPI channel for device 0
# CS0 = 0

_SPI_CHUNK_SIZE = 4096
_SPI_COMMAND = False
_SPI_DATA = True

_RESOLUTION = {
    (800, 480): (800, 480, 0),
    (600, 448): (600, 448, 0),
    (400, 300): (400, 300, 0),
    (212, 104): (104, 212, -90),
    (250, 122): (250, 122, -90),
}


class Inky:
    """Inky e-Ink Display Driver.
    Generally it is more convenient to use either the :class:`inky.InkyPHAT` or :class:`inky.InkyWHAT` classes.
    """

    WHITE = 0
    BLACK = 1
    RED = 2
    YELLOW = 2

    def __init__(self, resolution=(400, 300), colour='black', cs_pin:microcontroller.Pin=CS_PIN, dc_pin:microcontroller.Pin=DC_PIN, reset_pin:microcontroller.Pin=RESET_PIN, busy_pin:microcontroller.Pin=BUSY_PIN, h_flip=False, v_flip=False,
                 spi_bus:busio.SPI=None):
        """Initialise an Inky Display.
        :param resolution: Display resolution (width, height) in pixels, default: (400, 300).
        :type resolution: tuple(int, int)
        :param str colour: One of 'red', 'black' or 'yellow', default: 'black'.
        :param int cs_channel: Chip-select channel for SPI communication, default: `0`.
        :param int dc_pin: Data/command pin for SPI communication, default: `22`.
        :param int reset_pin: Device reset pin, default: `27`.
        :param int busy_pin: Device busy/wait pin: `17`.
        :param bool h_flip: Enable horizontal display flip, default: `False`.
        :param bool v_flip: Enable vertical display flip, default: `False`.
        :param spi_bus: SPI device. If `None` then a default :class:`spidev.SpiDev` object is used. Default: `None`.
        :type spi_bus: :class:`spidev.SpiDev`
        :param i2c_bus: SMB object. If `None` then :class:`smbus2.SMBus(1)` is used.
        :type i2c_bus: :class:`smbus2.SMBus`
        """
        self._spi_bus = spi_bus
        self._spi_device = None

        if resolution not in _RESOLUTION.keys():
            raise ValueError('Resolution {}x{} not supported!'.format(*resolution))

        self.resolution = resolution
        self.width, self.height = resolution
        self.cols, self.rows, self.rotation = _RESOLUTION[resolution]

        if colour not in ('red', 'black', 'yellow'):
            raise ValueError('Colour {} is not supported!'.format(colour))

        self.colour = colour
        self.eeprom = inky_eeprom.EPDType.from_eeprom()
        self.lut = colour

        if self.eeprom is not None:
            if self.eeprom.width != self.width or self.eeprom.height != self.height:
                raise ValueError('Supplied width/height do not match Inky: {}x{}'.format(self.eeprom.width, self.eeprom.height))
            if self.eeprom.display_variant in (1, 6) and self.eeprom.get_color() == 'red':
                self.lut = 'red_ht'

        self.buf:displayio.Bitmap=displayio.Bitmap(self.width, self.height, 4) # 4 color values is 2 bits per pixel
        self.border_colour = 0

        self.dc_pin =  DigitalInOut(dc_pin)
        self.reset_pin = DigitalInOut(reset_pin)
        self.busy_pin = DigitalInOut(busy_pin)
        self.cs_pin = DigitalInOut(cs_pin)
        self.h_flip = h_flip
        self.v_flip = v_flip

        self._gpio_setup = False

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

    def setup(self):
        """Set up Inky GPIO and reset display."""
        if not self._gpio_setup:
            self.dc_pin.direction = Direction.OUTPUT
            self.dc_pin.value = False
            self.reset_pin.direction = Direction.OUTPUT
            self.reset_pin.value = True
            self.busy_pin.direction = Direction.INPUT

            if self._spi_bus is None:
                self._spi_bus = board.SPI()
           
            self._gpio_setup = True

        self.reset_pin.value = False
        time.sleep(0.1)
        self.reset_pin.value = True
        time.sleep(0.1)

        self._send_command(0x12)  # Soft Reset
        self._busy_wait()

    def _busy_wait(self):
        """Wait for busy/wait pin."""
        start= supervisor.ticks_ms()
        while self.busy_pin.value == True:
            time.sleep(0.01)
        stop = supervisor.ticks_ms()
        print("Waited for busy: ", (stop - start)/1000)

    def _update(self, buf_a, buf_b, busy_wait=True):
        """Update display.
        :param buf_a: Black/White pixels
        :param buf_b: Yellow/Red pixels
        """
        self.setup()

        packed_height = list(struct.pack('<H', self.rows))

        print(f'packed_height: {packed_height}')

        if isinstance(packed_height[0], str):
            packed_height = map(ord, packed_height)

        self._send_command(0x74, 0x54)  # Set Analog Block Control
        self._send_command(0x7e, 0x3b)  # Set Digital Block Control

        self._send_command(0x01, packed_height + [0x00])  # Gate setting

        self._send_command(0x03, 0x17)  # Gate Driving Voltage
        self._send_command(0x04, [0x41, 0xAC, 0x32])  # Source Driving Voltage

        self._send_command(0x3a, 0x07)  # Dummy line period
        self._send_command(0x3b, 0x04)  # Gate line width
        self._send_command(0x11, 0x03)  # Data entry mode setting 0x03 = X/Y increment

        self._send_command(0x2c, 0x3c)  # VCOM Register, 0x3c = -1.5v?
        self._send_command(0x22, 0xC7)  # Display Update Sequence

        self._send_command(0x3c, 0b00000000)
        if self.border_colour == self.BLACK:
            self._send_command(0x3c, 0b00000000)  # GS Transition Define A + VSS + LUT0
        elif self.border_colour == self.RED and self.colour == 'red':
            self._send_command(0x3c, 0b01110011)  # Fix Level Define A + VSH2 + LUT3
        elif self.border_colour == self.YELLOW and self.colour == 'yellow':
            self._send_command(0x3c, 0b00110011)  # GS Transition Define A + VSH2 + LUT3
        elif self.border_colour == self.WHITE:
            self._send_command(0x3c, 0b00110001)  # GS Transition Define A + VSH2 + LUT1

        if self.colour == 'yellow':
            self._send_command(0x04, [0x07, 0xAC, 0x32])  # Set voltage of VSH and VSL
        if self.colour == 'red' and self.resolution == (400, 300):
            self._send_command(0x04, [0x30, 0xAC, 0x22])

        self._send_command(0x32, self._luts[self.lut])  # Set LUTs

        # Start image data send

        self._send_command(0x44, [0x00, (self.cols // 8) - 1])  # Set RAM X Start/End
        self._send_command(0x45, [0x00, 0x00] + packed_height)  # Set RAM Y Start/End

        # 0x24 == RAM B/W, 0x26 == RAM Red/Yellow/etc
        for data in ((0x24, buf_a), (0x26, buf_b)):
            cmd, buf = data
            self._send_command(0x4e, 0x00)  # Set RAM X Pointer Start
            self._send_command(0x4f, [0x00, 0x00])  # Set RAM Y Pointer Start
            self._send_command(cmd, buf)

        self._send_command(0x20)  # Trigger Display Update
        time.sleep(0.05)

        if busy_wait:
            self._busy_wait()
        self._send_command(0x10, 0x01)  # Enter Deep Sleep

    def set_pixel(self, x, y, v):
        """Set a single pixel on the buffer.
        :param int x: x position on display.
        :param int y: y position on display.
        :param int v: Colour to set, valid values are `inky.BLACK`, `inky.WHITE`, `inky.RED` and `inky.YELLOW`.
        """
        if v in (WHITE, BLACK, RED):
            self.buf[y][x] = v

    def show(self, busy_wait=True):
        """Show buffer on display.
        :param bool busy_wait: If True, wait for display update to finish before returning, default: `True`.
        """
        region = self.buf

        # TODO : Handle flip / rotate?

        # Split the image into Black and Color planes

        buf_a = self.packbits(region, lambda x:x!=WHITE).tolist()
        buf_b = self.packbits(region, lambda x:x==RED).tolist()

        self._update(buf_a, buf_b, busy_wait=busy_wait)

    def packbits(self, region:displayio.Bitmap, predicate):
        
        outputLength=(region.width*region.height)>>3
        packedData = ulab.numpy.zeros((outputLength), dtype=ulab.numpy.uint8)
        bitIndex = 0
        currentByte = 0
        
        for y in range(region.height) :
            for x in range(region.width) :
                currentByte = currentByte << 1
                if(predicate(region[x,y])):
                    currentByte = currentByte | 1
                bitIndex+=1
                if(bitIndex>7):
                    bitIndex=0
                    byteIndex = (y*region.width+x)>>3
                    packedData[byteIndex]=currentByte
                    currentByte=0
        
        return packedData


    def set_border(self, colour):
        """Set the border colour.
        :param int colour: The border colour. Valid values are `inky.BLACK`, `inky.WHITE`, `inky.RED` and `inky.YELLOW`.
        """
        if colour in (WHITE, BLACK, RED):
            self.border_colour = colour

    def set_image(self, image):
        """Copy an image to the buffer.
        The dimensions of `image` should match the dimensions of the display being used.
        :param image: Image to copy.
        :type image: :class:`PIL.Image.Image` or :class:`numpy.ndarray` or list
        """
        if isinstance(image, displayio.Bitmap):
            self.buf=image # TODO : copy data? Handle rotation?
            return
        
        raise ValueError("image should be a Bitmap")

    def _spi_write(self, dc : bool, values:bytearray):
        """Write values over SPI.
        :param dc: whether to write as data or command
        :param values: list of values to write
        """
        
        self.dc_pin.value = dc

        transferLength=len(values)
        device = SPIDevice(spi=self._spi_bus, chip_select=self.cs_pin, baudrate=488000)
        for start in range(0, transferLength, _SPI_CHUNK_SIZE):
             with device as spi:
                    # Chuncked transfer
                    spi.write(buffer=values, start=start, end=min(start+_SPI_CHUNK_SIZE, transferLength))
        
    def _send_command(self, command, data:bytearray=None):
        """Send command over SPI.
        :param command: command byte
        :param data: optional list of values
        """
        print('SPI \\x{:02x}'.format(command), end=' ')

        self._spi_write(_SPI_COMMAND, bytearray([command]))
        if data is not None:
        if isinstance(data, list):
            data = bytearray(data)
        if isinstance(data, int):
            data = bytearray([data])
            print('{:02x}'.format(len(data)), end=' ')
            print(''.join('{:02x} '.format(x) for x in data))    
            self._spi_write(_SPI_DATA, data)
        else:
            print('\\x00')
